from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import CombatantState


MAX_SKILL_PROFICIENCY = 1000.0


def skill_slot_count(level: int) -> int:
    """Canonical Aincrad skill-slot progression."""
    if level < 1:
        raise ValueError("level must be >= 1")
    if level < 6:
        return 2
    if level < 12:
        return 3
    if level < 20:
        return 4
    return 5 + max(0, (level - 20) // 10)


def can_equip_skill(actor: CombatantState, skill_id: str) -> bool:
    return skill_id in actor.equipped_skills or len(actor.equipped_skills) < skill_slot_count(actor.level)


def equip_skill(actor: CombatantState, skill_id: str) -> None:
    if skill_id in actor.equipped_skills:
        return
    if not can_equip_skill(actor, skill_id):
        raise ValueError("no free skill slot")
    actor.equipped_skills.append(skill_id)
    actor.skill_proficiencies.setdefault(skill_id, 0.0)


def remove_skill(actor: CombatantState, skill_id: str, *, preserve_proficiency: bool = False) -> None:
    if skill_id not in actor.equipped_skills:
        raise ValueError("skill is not equipped")
    actor.equipped_skills.remove(skill_id)
    if not preserve_proficiency:
        actor.skill_proficiencies.pop(skill_id, None)


def gain_skill_proficiency(actor: CombatantState, skill_id: str, base_gain: float) -> float:
    """Simulation gain curve layered on the canonical 0..1000 scale."""
    if skill_id not in actor.equipped_skills:
        return 0.0
    current = actor.skill_proficiencies.get(skill_id, 0.0)
    if current >= MAX_SKILL_PROFICIENCY:
        return 0.0
    diminishing = max(0.15, 1.0 - current / 1100.0)
    gain = max(0.0, base_gain) * diminishing
    updated = min(MAX_SKILL_PROFICIENCY, current + gain)
    actor.skill_proficiencies[skill_id] = updated
    return updated - current


def default_max_hp(level: int, strength: int, agility: int) -> int:
    """Simulation HP curve; not an official SAO formula."""
    if level < 1:
        raise ValueError("level must be >= 1")
    return int(350 + level * 105 + strength * 13 + agility * 4)


def default_carry_capacity(strength: int, extended_weight_proficiency: float = 0.0) -> float:
    """Simulation carry-capacity curve in abstract weight units."""
    extension = 1.0 + max(0.0, min(1000.0, extended_weight_proficiency)) / 2500.0
    return max(10.0, 18.0 + strength * 1.65) * extension


@dataclass(slots=True, frozen=True)
class LevelGain:
    old_level: int
    new_level: int
    old_skill_slots: int
    new_skill_slots: int


def apply_level(actor: CombatantState, new_level: int) -> LevelGain:
    if new_level < actor.level:
        raise ValueError("new_level must not decrease")
    old = actor.level
    old_slots = skill_slot_count(old)
    actor.level = new_level
    actor.max_hp = max(actor.max_hp, default_max_hp(new_level, actor.strength, actor.agility))
    actor.hp = min(actor.hp, actor.max_hp)
    return LevelGain(old, new_level, old_slots, skill_slot_count(new_level))
