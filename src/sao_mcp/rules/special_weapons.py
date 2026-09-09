from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import CombatantState, ItemInstance, WeaponTemplate
from sao_mcp.rules.nightfolk import is_night_kind
from sao_mcp.rules.progression import current_experience, experience_to_reach_level


DOLEFUL_EXP_DRAIN_RATIO_PER_ATTACK = 0.02
EQUIPMENT_HP_REGEN_RATIO_PER_SECOND = 0.0025


@dataclass(slots=True, frozen=True)
class SoulCostResolution:
    actor_id: str
    item_instance_id: str
    drained_experience: int
    experience_after: int
    level_floor_experience: int
    exempt_by_night_rank: bool


def apply_weapon_soul_cost(
    actor: CombatantState,
    weapon_item: ItemInstance,
    weapon: WeaponTemplate,
) -> SoulCostResolution | None:
    if "experience_drain_without_civis_nocte" not in weapon.tags:
        return None
    floor_xp = experience_to_reach_level(actor.level)
    total = current_experience(actor)
    if is_night_kind(actor):
        return SoulCostResolution(
            actor.actor_id,
            weapon_item.instance_id,
            0,
            total,
            floor_xp,
            True,
        )

    accumulated = max(0, total - floor_xp)
    if accumulated <= 0:
        return SoulCostResolution(
            actor.actor_id,
            weapon_item.instance_id,
            0,
            total,
            floor_xp,
            False,
        )
    drained = max(1, int(round(accumulated * DOLEFUL_EXP_DRAIN_RATIO_PER_ATTACK)))
    drained = min(accumulated, drained)
    actor.metadata["experience"] = total - drained
    return SoulCostResolution(
        actor.actor_id,
        weapon_item.instance_id,
        drained,
        total - drained,
        floor_xp,
        False,
    )


def apply_equipment_hp_regeneration(actor: CombatantState, elapsed_ms: int) -> int:
    if elapsed_ms <= 0 or not actor.alive or actor.hp >= actor.max_hp:
        return 0
    instance_id = actor.metadata.get("equipment_hp_regeneration_instance_id")
    if instance_id is None:
        return 0
    if instance_id not in actor.inventory:
        raise RuntimeError("equipment regeneration instance is not in the actor inventory")
    item = actor.inventory[instance_id]
    if item.broken:
        raise RuntimeError("broken equipment still advertises active HP regeneration")
    seconds = elapsed_ms / 1000.0
    restored = max(1, int(round(actor.max_hp * EQUIPMENT_HP_REGEN_RATIO_PER_SECOND * seconds)))
    restored = min(actor.max_hp - actor.hp, restored)
    actor.hp += restored
    return restored
