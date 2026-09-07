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


def experience_to_reach_level(level: int) -> int:
    """Simulation cumulative XP curve. SAO canon does not publish a full XP table."""
    if level < 1:
        raise ValueError("level must be >= 1")
    n = level - 1
    return int(90 * n + 42 * n * n + 3.5 * n * n * n)


def current_experience(actor: CombatantState) -> int:
    stored = actor.metadata.get("experience")
    if stored is None:
        stored = experience_to_reach_level(actor.level)
        actor.metadata["experience"] = stored
    return int(stored)


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
    gained = new_level - old
    if gained:
        actor.strength += gained * 2
        actor.agility += gained * 2
    actor.level = new_level
    actor.max_hp = max(actor.max_hp, default_max_hp(new_level, actor.strength, actor.agility))
    actor.hp = min(actor.hp, actor.max_hp)
    actor.metadata["experience"] = max(current_experience(actor), experience_to_reach_level(new_level))
    return LevelGain(old, new_level, old_slots, skill_slot_count(new_level))


@dataclass(slots=True, frozen=True)
class ExperienceGain:
    amount: int
    total: int
    old_level: int
    new_level: int
    levels_gained: int
    skill_slots_before: int
    skill_slots_after: int


def grant_experience(actor: CombatantState, amount: int, *, max_level: int = 200) -> ExperienceGain:
    if amount < 0:
        raise ValueError("experience amount must be >= 0")
    old_level = actor.level
    slots_before = skill_slot_count(old_level)
    total = current_experience(actor) + amount
    actor.metadata["experience"] = total
    new_level = old_level
    while new_level < max_level and total >= experience_to_reach_level(new_level + 1):
        new_level += 1
    if new_level > old_level:
        apply_level(actor, new_level)
        actor.metadata["experience"] = total
    return ExperienceGain(
        amount=amount,
        total=total,
        old_level=old_level,
        new_level=new_level,
        levels_gained=new_level - old_level,
        skill_slots_before=slots_before,
        skill_slots_after=skill_slot_count(new_level),
    )
