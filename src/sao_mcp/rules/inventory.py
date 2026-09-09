from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import ArmorTemplate, CombatantState, ItemInstance, ItemKind, StatusType, WeaponTemplate
from sao_mcp.rules.progression import default_carry_capacity


@dataclass(slots=True, frozen=True)
class EquipmentChange:
    slot: str
    equipped_instance_id: str | None
    previous_instance_id: str | None
    armor_after: int
    weight_after: float


def inventory_weight(actor: CombatantState, catalog: Catalog) -> float:
    total = 0.0
    for item in actor.inventory.values():
        template = catalog.item(item.template_id)
        total += template.weight * max(1, item.quantity)
    return round(total, 4)


def personal_carry_capacity(actor: CombatantState) -> float:
    return default_carry_capacity(
        actor.strength,
        actor.skill_proficiencies.get("extended_weight_limit", 0.0),
    )


def carry_capacity(actor: CombatantState) -> float:
    shared = actor.metadata.get("shared_carry_capacity_override")
    if shared is not None:
        return max(personal_carry_capacity(actor), float(shared))
    return personal_carry_capacity(actor)


def can_receive(actor: CombatantState, item: ItemInstance, catalog: Catalog) -> bool:
    template = catalog.item(item.template_id)
    projected = inventory_weight(actor, catalog) + template.weight * max(1, item.quantity)
    return projected <= carry_capacity(actor)


def add_item(actor: CombatantState, item: ItemInstance, catalog: Catalog, *, allow_overweight: bool = False) -> None:
    if item.instance_id in actor.inventory:
        raise ValueError("item instance already exists in inventory")
    if not allow_overweight and not can_receive(actor, item, catalog):
        raise ValueError("carrying the item would exceed the actor's weight limit")
    item.owner_id = actor.actor_id
    actor.inventory[item.instance_id] = item


def locate_item_container(
    actors: dict[str, CombatantState],
    instance_id: str,
) -> tuple[CombatantState, ItemInstance] | None:
    matches = [
        (actor, actor.inventory[instance_id])
        for actor in actors.values()
        if instance_id in actor.inventory
    ]
    if len(matches) > 1:
        actor_ids = sorted(actor.actor_id for actor, _ in matches)
        raise RuntimeError(f"item instance {instance_id} exists in multiple inventories: {actor_ids}")
    return matches[0] if matches else None


def _sync_equipment_passives(actor: CombatantState, catalog: Catalog) -> None:
    actor.metadata.pop("equipment_hp_regeneration_instance_id", None)
    actor.metadata.pop("equipment_poison_nullification_instance_id", None)
    weapon_id = actor.equipment.get("weapon")
    if not weapon_id or weapon_id not in actor.inventory:
        return
    weapon_item = actor.inventory[weapon_id]
    if weapon_item.broken:
        return
    template = catalog.item(weapon_item.template_id)
    tags = set(template.tags)
    if "hp_regeneration" in tags:
        actor.metadata["equipment_hp_regeneration_instance_id"] = weapon_id
    if "poison_nullification" in tags:
        actor.metadata["equipment_poison_nullification_instance_id"] = weapon_id
        actor.statuses = [status for status in actor.statuses if status.status_type is not StatusType.POISON]


def recompute_equipment_stats(actor: CombatantState, catalog: Catalog) -> None:
    armor = 0
    for slot, instance_id in list(actor.equipment.items()):
        if instance_id not in actor.inventory:
            actor.equipment.pop(slot, None)
            continue
        instance = actor.inventory[instance_id]
        if instance.broken:
            continue
        template = catalog.item(instance.template_id)
        if isinstance(template, ArmorTemplate):
            armor += template.armor
    actor.armor = armor
    _sync_equipment_passives(actor, catalog)


def equip(actor: CombatantState, instance_id: str, catalog: Catalog) -> EquipmentChange:
    if instance_id not in actor.inventory:
        raise KeyError(instance_id)
    item = actor.inventory[instance_id]
    if item.broken:
        raise ValueError("broken equipment cannot be equipped")
    template = catalog.item(item.template_id)

    if isinstance(template, WeaponTemplate):
        if actor.level < template.required_level:
            raise ValueError("character level is below the weapon requirement")
        if actor.strength < template.required_strength:
            raise ValueError("strength is below the weapon requirement")
        slot = "weapon"
    elif isinstance(template, ArmorTemplate):
        slot = template.slot
    elif template.kind is ItemKind.SHIELD:
        slot = "offhand"
    else:
        raise ValueError("item is not equippable")

    previous = actor.equipment.get(slot)
    actor.equipment[slot] = instance_id
    recompute_equipment_stats(actor, catalog)
    return EquipmentChange(slot, instance_id, previous, actor.armor, inventory_weight(actor, catalog))


def unequip(actor: CombatantState, slot: str, catalog: Catalog) -> EquipmentChange:
    previous = actor.equipment.pop(slot, None)
    recompute_equipment_stats(actor, catalog)
    return EquipmentChange(slot, None, previous, actor.armor, inventory_weight(actor, catalog))


def transfer_item(
    source: CombatantState,
    destination: CombatantState,
    instance_id: str,
    catalog: Catalog,
    *,
    quantity: int | None = None,
    allow_destination_overweight: bool = False,
) -> ItemInstance:
    if source.actor_id == destination.actor_id:
        raise ValueError("source and destination are the same actor")
    if source.inventory is destination.inventory:
        raise ValueError("source and destination already share the same inventory")
    if instance_id not in source.inventory:
        raise KeyError(instance_id)
    if instance_id in source.equipment.values():
        raise ValueError("equipped items must be unequipped before transfer")

    source_item = source.inventory[instance_id]
    move_qty = source_item.quantity if quantity is None else quantity
    if move_qty < 1 or move_qty > source_item.quantity:
        raise ValueError("invalid transfer quantity")

    moving = source_item
    if move_qty < source_item.quantity:
        moving = deepcopy(source_item)
        moving.instance_id = f"item_{uuid.uuid4().hex[:12]}"
        moving.quantity = move_qty
        source_item.quantity -= move_qty
    else:
        source.inventory.pop(instance_id)

    if not allow_destination_overweight and not can_receive(destination, moving, catalog):
        if moving is source_item:
            source.inventory[instance_id] = source_item
        else:
            source_item.quantity += move_qty
        raise ValueError("destination would exceed carrying capacity")

    moving.owner_id = destination.actor_id
    destination.inventory[moving.instance_id] = moving
    return moving


@dataclass(slots=True, frozen=True)
class RepairResolution:
    repaired: int
    durability_after: int | None
    max_durability_after: int | None
    cost_col: int


def repair_item(
    actor: CombatantState,
    instance_id: str,
    catalog: Catalog,
    *,
    smith_proficiency: float,
    pay_from_actor: bool = True,
) -> RepairResolution:
    item = actor.inventory[instance_id]
    if item.durability is None or item.max_durability is None:
        raise ValueError("item has no durability")
    if item.durability >= item.max_durability:
        return RepairResolution(0, item.durability, item.max_durability, 0)

    missing = item.max_durability - item.durability
    skill = max(0.0, min(1000.0, smith_proficiency)) / 1000.0
    restored = max(1, min(missing, int(round(missing * (0.55 + 0.45 * skill)))))
    template = catalog.item(item.template_id)
    base_value = template.base_value_col or 25
    cost = max(1, int(round(restored / max(1, item.max_durability) * base_value * 0.35)))
    if pay_from_actor:
        if actor.col < cost:
            raise ValueError("insufficient Col for repair")
        actor.col -= cost
    item.durability = min(item.max_durability, item.durability + restored)
    return RepairResolution(restored, item.durability, item.max_durability, cost)
