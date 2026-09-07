from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.recipes import WeaponRecipe
from sao_mcp.domain.models import CombatantState, ItemInstance, ItemKind
from sao_mcp.rules.crafting import CraftQuality, roll_craft_quality
from sao_mcp.rules.inventory import add_item


@dataclass(slots=True, frozen=True)
class CraftWeaponResolution:
    recipe_id: str
    product_instance_id: str
    product_template_id: str
    maker_id: str
    quality: CraftQuality
    materials_consumed: tuple[tuple[str, int], ...]
    hammer_hits: int


@dataclass(slots=True, frozen=True)
class ReclaimResolution:
    source_instance_id: str
    source_template_id: str
    ingot_template_id: str
    quantity_created: int
    recovered_quality: float
    result_instance_id: str


def _inventory_count(actor: CombatantState, template_id: str) -> int:
    return sum(item.quantity for item in actor.inventory.values() if item.template_id == template_id)


def _consume(actor: CombatantState, template_id: str, quantity: int) -> None:
    if quantity < 1:
        return
    if _inventory_count(actor, template_id) < quantity:
        raise ValueError(f"insufficient material: {template_id}")
    remaining = quantity
    for instance_id, item in list(actor.inventory.items()):
        if item.template_id != template_id:
            continue
        used = min(item.quantity, remaining)
        item.quantity -= used
        remaining -= used
        if item.quantity <= 0:
            if instance_id in actor.equipment.values():
                raise ValueError("equipped material cannot be consumed")
            actor.inventory.pop(instance_id)
        if remaining <= 0:
            break


def craft_weapon(
    actor: CombatantState,
    recipe: WeaponRecipe,
    catalog: Catalog,
    *,
    smith_proficiency: float,
    material_quality: float,
    rng: random.Random,
) -> CraftWeaponResolution:
    """Craft a weapon from valid materials. Canonically, valid weapon crafting has no total failure."""
    if recipe.product_template_id not in catalog.weapons:
        raise ValueError("recipe product is not a weapon template")
    for requirement in recipe.materials:
        if _inventory_count(actor, requirement.template_id) < requirement.quantity:
            raise ValueError(f"insufficient material: {requirement.template_id}")

    quality = roll_craft_quality(
        smith_proficiency=smith_proficiency,
        material_quality=material_quality,
        item_difficulty=recipe.difficulty,
        rng=rng,
    )
    for requirement in recipe.materials:
        _consume(actor, requirement.template_id, requirement.quantity)

    template = catalog.weapons[recipe.product_template_id]
    instance = ItemInstance(
        instance_id=f"item_{uuid.uuid4().hex[:12]}",
        template_id=template.template_id,
        owner_id=actor.actor_id,
        durability=max(1, int(round(template.base_durability * quality.multiplier))),
        max_durability=max(1, int(round(template.base_durability * quality.multiplier))),
        max_enhancement_attempts=max(1, int(round(5 * quality.multiplier))),
        maker_id=actor.actor_id,
        quality=quality.multiplier,
        metadata={
            "crafted": True,
            "craft_grade": quality.grade,
            "recipe_id": recipe.recipe_id,
            "nominal_hammer_hits": recipe.nominal_hammer_hits,
        },
    )
    add_item(actor, instance, catalog)
    return CraftWeaponResolution(
        recipe.recipe_id,
        instance.instance_id,
        instance.template_id,
        actor.actor_id,
        quality,
        tuple((req.template_id, req.quantity) for req in recipe.materials),
        recipe.nominal_hammer_hits,
    )


def reclaim_weapon_to_ingot(
    actor: CombatantState,
    instance_id: str,
    catalog: Catalog,
    *,
    ingot_template_id: str = "iron_ingot",
) -> ReclaimResolution:
    """Convert a non-equipped weapon back into an ingot-like crafting material."""
    if instance_id not in actor.inventory:
        raise KeyError(instance_id)
    if instance_id in actor.equipment.values():
        raise ValueError("weapon must be unequipped before reclamation")
    source = actor.inventory[instance_id]
    source_template = catalog.item(source.template_id)
    if source_template.kind is not ItemKind.WEAPON:
        raise ValueError("only weapons can be reclaimed by this rule")
    ingot_template = catalog.item(ingot_template_id)
    if ingot_template.kind is not ItemKind.MATERIAL:
        raise ValueError("reclamation output must be a material")

    recovered_quality = max(0.35, min(1.25, source.quality * (0.82 if source.broken else 0.92)))
    quantity = max(1, int(round(max(1.0, source_template.weight) / max(0.1, ingot_template.weight) * 0.55)))
    actor.inventory.pop(instance_id)
    result = ItemInstance(
        instance_id=f"item_{uuid.uuid4().hex[:12]}",
        template_id=ingot_template_id,
        owner_id=actor.actor_id,
        quantity=quantity,
        quality=recovered_quality,
        metadata={"reclaimed_from": source.template_id},
    )
    add_item(actor, result, catalog, allow_overweight=True)
    return ReclaimResolution(
        instance_id,
        source.template_id,
        ingot_template_id,
        quantity,
        recovered_quality,
        result.instance_id,
    )
