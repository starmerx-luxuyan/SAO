from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.rules.inventory import carry_capacity, inventory_weight


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def _item_row(runtime, actor, instance_id: str) -> dict:
    item = actor.inventory[instance_id]
    template = runtime.catalog.item(item.template_id)
    return {
        "instance": asdict(item),
        "template": asdict(template),
        "equippedSlots": [slot for slot, equipped_id in actor.equipment.items() if equipped_id == instance_id],
    }


def register_inventory_tools(mcp, runtime) -> None:
    @mcp.tool()
    def get_inventory(actor_id: str) -> str:
        """Return authoritative inventory, equipment, weight and carry capacity."""
        actor = runtime.actors[actor_id]
        return _json(
            {
                "actorId": actor_id,
                "col": actor.col,
                "weight": inventory_weight(actor, runtime.catalog),
                "capacity": carry_capacity(actor),
                "equipment": dict(actor.equipment),
                "items": [_item_row(runtime, actor, instance_id) for instance_id in actor.inventory],
            }
        )

    @mcp.tool()
    def equip_inventory_item(actor_id: str, instance_id: str) -> str:
        """Equip a legal weapon/armour item and recompute authoritative equipment stats."""
        return _json(asdict(runtime.equip_item(actor_id, instance_id)))

    @mcp.tool()
    def unequip_inventory_slot(actor_id: str, slot: str) -> str:
        """Unequip one equipment slot and recompute authoritative equipment stats."""
        return _json(asdict(runtime.unequip_item(actor_id, slot)))

    @mcp.tool()
    def transfer_inventory_item(
        source_id: str,
        destination_id: str,
        instance_id: str,
        quantity: int | None = None,
    ) -> str:
        """Transfer a whole item or part of a stack between players, enforcing inventory constraints."""
        moved = runtime.transfer_inventory_item(
            source_id,
            destination_id,
            instance_id,
            quantity=quantity,
        )
        return _json(asdict(moved))

    @mcp.tool()
    def repair_inventory_item(
        actor_id: str,
        instance_id: str,
        smith_proficiency: float,
        pay_from_actor: bool = True,
    ) -> str:
        """Repair a durable item using the simulation-calibrated repair-cost model."""
        return _json(
            asdict(
                runtime.repair_inventory_item(
                    actor_id,
                    instance_id,
                    smith_proficiency=smith_proficiency,
                    pay_from_actor=pay_from_actor,
                )
            )
        )

    @mcp.tool()
    def inspect_item_instance(actor_id: str, instance_id: str) -> str:
        """Inspect an owned item instance together with its catalog template and provenance."""
        return _json(_item_row(runtime, runtime.actors[actor_id], instance_id))

    @mcp.tool()
    def list_item_catalog(category: str) -> str:
        """List weapons, armours, consumables, materials/misc items, skills or Sword Skills."""
        mappings = {
            "weapons": runtime.catalog.weapons,
            "armors": runtime.catalog.armors,
            "consumables": runtime.catalog.consumables,
            "items": runtime.catalog.items,
            "skills": runtime.catalog.skills,
            "sword_skills": runtime.catalog.sword_skills,
        }
        mapping = mappings.get(category)
        if mapping is None:
            raise ValueError("unknown catalog category")
        return _json(
            {
                "category": category,
                "entries": [
                    {
                        "id": key,
                        "name": value.name,
                        "provenance": asdict(value.provenance),
                    }
                    for key, value in mapping.items()
                ],
            }
        )
