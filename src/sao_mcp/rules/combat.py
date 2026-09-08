from __future__ import annotations

import random
from dataclasses import dataclass

from sao_mcp.domain.models import (
    CombatantState,
    DefenseMode,
    EnhancementTrack,
    ItemInstance,
    StatusType,
    SwordSkillDefinition,
    WeaponTemplate,
)


@dataclass(slots=True, frozen=True)
class CombatTuning:
    base_hit: float = 0.72
    min_hit: float = 0.05
    max_hit: float = 0.98
    agility_hit_scale: float = 0.0030
    proficiency_hit_scale: float = 0.00018
    accuracy_enhancement_hit: float = 0.018
    base_crit: float = 0.025
    proficiency_crit_scale: float = 0.000025
    accuracy_enhancement_crit: float = 0.006
    post_motion_hit_bonus: float = 0.16
    ai_reaction_hit_bonus: float = 0.10
    guard_reduction: float = 0.55
    armor_constant: float = 850.0
    strength_damage_scale: float = 0.0055
    proficiency_damage_scale: float = 0.00045
    sharpness_damage_scale: float = 0.045
    quickness_speed_scale: float = 0.045
    heaviness_stagger_scale: float = 0.07
    base_normal_post_motion_ms: int = 180


DEFAULT_TUNING = CombatTuning()


@dataclass(slots=True, frozen=True)
class AttackResolution:
    legal: bool
    hit: bool = False
    critical: bool = False
    parried: bool = False
    guarded: bool = False
    evaded: bool = False
    damage: int = 0
    hit_chance: float = 0.0
    crit_chance: float = 0.0
    attacker_durability_loss: int = 0
    defender_durability_pressure: int = 0
    stagger_ms: int = 0
    action_end_ms: int = 0
    recovery_end_ms: int = 0
    threat_generated: float = 0.0
    reason: str | None = None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _enhancement(item: ItemInstance, track: EnhancementTrack) -> int:
    return max(0, item.enhancements.get(track, 0))


def _weapon_proficiency(actor: CombatantState, weapon: WeaponTemplate) -> float:
    explicit = actor.skill_proficiencies.get(f"weapon:{weapon.weapon_class.value}")
    if explicit is not None:
        return explicit
    return actor.skill_proficiencies.get(weapon.weapon_class.value, 0.0)


def _guild_party_bonus(actor: CombatantState) -> float:
    """Combine the ordinary guild-party bonus with temporary guild-wide item auras."""
    party_bonus = _clamp(float(actor.metadata.get("guild_party_stat_bonus", 0.0)), 0.0, 0.15)
    flag_bonus = _clamp(float(actor.metadata.get("flag_of_valor_stat_bonus", 0.0)), 0.0, 0.25)
    return _clamp(party_bonus + flag_bonus, 0.0, 0.30)


def _incapacitating_status(actor: CombatantState) -> StatusType | None:
    for status in actor.statuses:
        if status.remaining_ms <= 0:
            continue
        if status.status_type in (StatusType.PARALYSIS, StatusType.STUN):
            return status.status_type
    return None


def effective_attack_speed_ms(
    weapon: WeaponTemplate,
    item: ItemInstance,
    *,
    tuning: CombatTuning = DEFAULT_TUNING,
) -> int:
    quickness = _enhancement(item, EnhancementTrack.QUICKNESS)
    factor = 1.0 / (1.0 + quickness * tuning.quickness_speed_scale)
    return max(180, int(round(weapon.base_speed_ms * factor)))


def _auto_defense(defender: CombatantState) -> DefenseMode:
    parry = max(defender.skill_proficiencies.get("parry", 0.0), defender.skill_proficiencies.get("Parry", 0.0))
    if parry >= 450:
        return DefenseMode.PARRY
    if defender.agility >= defender.strength:
        return DefenseMode.EVADE
    return DefenseMode.GUARD


def resolve_physical_attack(
    attacker: CombatantState,
    defender: CombatantState,
    weapon_item: ItemInstance,
    weapon: WeaponTemplate,
    *,
    now_ms: int,
    rng: random.Random,
    sword_skill: SwordSkillDefinition | None = None,
    defense: DefenseMode = DefenseMode.AUTO,
    distance_m: float = 1.0,
    tuning: CombatTuning = DEFAULT_TUNING,
) -> AttackResolution:
    """Resolve one attack without mutating actors. All numeric coefficients are simulation tuning."""
    if not attacker.alive:
        return AttackResolution(False, reason="attacker is defeated")
    if not defender.alive:
        return AttackResolution(False, reason="target is defeated")
    incapacitated = _incapacitating_status(attacker)
    if incapacitated is not None:
        return AttackResolution(False, reason=f"attacker is {incapacitated.value}")
    if attacker.actor_id == defender.actor_id:
        return AttackResolution(False, reason="self-targeted physical attack is unsupported")
    if weapon_item.broken:
        return AttackResolution(False, reason="equipped weapon is broken")
    if attacker.level < weapon.required_level or attacker.strength < weapon.required_strength:
        return AttackResolution(False, reason="weapon requirements are not met")
    if distance_m > weapon.reach_m + (sword_skill.lunge_m if sword_skill else 0.0):
        return AttackResolution(False, reason="target is outside attack reach")
    if now_ms < attacker.committed_until_ms or now_ms < attacker.recovery_until_ms:
        return AttackResolution(False, reason="attacker is still committed or recovering")

    proficiency = _weapon_proficiency(attacker, weapon)
    if sword_skill is not None:
        if sword_skill.weapon_class is not weapon.weapon_class:
            return AttackResolution(False, reason="Sword Skill is incompatible with the equipped weapon")
        if proficiency < sword_skill.prerequisite_proficiency:
            return AttackResolution(False, reason="Sword Skill proficiency prerequisite is not met")

    accuracy_plus = _enhancement(weapon_item, EnhancementTrack.ACCURACY)
    hit_chance = tuning.base_hit
    hit_chance += (attacker.agility - defender.agility) * tuning.agility_hit_scale
    hit_chance += proficiency * tuning.proficiency_hit_scale
    hit_chance += accuracy_plus * tuning.accuracy_enhancement_hit
    if sword_skill:
        hit_chance += sword_skill.accuracy_modifier
    if now_ms < defender.recovery_until_ms:
        hit_chance += tuning.post_motion_hit_bonus
    if now_ms < defender.ai_reaction_until_ms:
        hit_chance += tuning.ai_reaction_hit_bonus

    can_react = now_ms >= defender.committed_until_ms and now_ms >= defender.recovery_until_ms
    chosen_defense = _auto_defense(defender) if defense is DefenseMode.AUTO else defense
    parried = guarded = evaded = False

    if can_react and chosen_defense is DefenseMode.EVADE:
        evasion_bonus = 0.12 + max(-0.06, min(0.18, (defender.agility - attacker.agility) * 0.002))
        hit_chance -= evasion_bonus
    hit_chance = _clamp(hit_chance, tuning.min_hit, tuning.max_hit)

    if can_react and chosen_defense is DefenseMode.PARRY:
        parry_prof = max(defender.skill_proficiencies.get("parry", 0.0), defender.skill_proficiencies.get("Parry", 0.0))
        parry_chance = _clamp(0.12 + parry_prof * 0.00055 + (defender.agility - attacker.agility) * 0.002, 0.05, 0.78)
        if rng.random() < parry_chance:
            parried = True

    base_speed = effective_attack_speed_ms(weapon, weapon_item, tuning=tuning)
    if sword_skill:
        action_duration = sword_skill.windup_ms + sword_skill.active_ms
        post_motion = sword_skill.post_motion_ms
    else:
        action_duration = base_speed
        post_motion = tuning.base_normal_post_motion_ms
    action_end = now_ms + max(1, action_duration)
    recovery_end = action_end + max(0, post_motion)

    if parried:
        return AttackResolution(
            legal=True,
            hit=False,
            parried=True,
            hit_chance=hit_chance,
            attacker_durability_loss=2,
            defender_durability_pressure=1,
            stagger_ms=220,
            action_end_ms=action_end,
            recovery_end_ms=recovery_end + 120,
        )

    if rng.random() >= hit_chance:
        evaded = can_react and chosen_defense is DefenseMode.EVADE
        return AttackResolution(
            legal=True,
            hit=False,
            evaded=evaded,
            hit_chance=hit_chance,
            attacker_durability_loss=1,
            action_end_ms=action_end,
            recovery_end_ms=recovery_end,
        )

    rolled = rng.randint(weapon.attack_min, weapon.attack_max)
    strength_over_req = max(0, attacker.strength + weapon.bonus_strength - weapon.required_strength)
    power = 1.0 + strength_over_req * tuning.strength_damage_scale
    power += proficiency * tuning.proficiency_damage_scale
    power += _enhancement(weapon_item, EnhancementTrack.SHARPNESS) * tuning.sharpness_damage_scale
    power *= 1.0 + _guild_party_bonus(attacker)
    skill_multiplier = sword_skill.total_multiplier if sword_skill else 1.0
    raw = rolled * power * skill_multiplier * weapon_item.quality

    crit_chance = tuning.base_crit + proficiency * tuning.proficiency_crit_scale
    crit_chance += accuracy_plus * tuning.accuracy_enhancement_crit
    crit_chance = _clamp(crit_chance, 0.0, 0.25)
    critical = rng.random() < crit_chance
    if critical:
        raw *= 1.55

    effective_armor = defender.armor * (1.0 + _guild_party_bonus(defender))
    armor_mitigation = effective_armor / (effective_armor + tuning.armor_constant) if effective_armor > 0 else 0.0
    damage = raw * (1.0 - armor_mitigation)

    if can_react and chosen_defense is DefenseMode.GUARD:
        guarded = True
        damage *= 1.0 - tuning.guard_reduction

    damage_i = max(1, int(round(damage)))
    heaviness = _enhancement(weapon_item, EnhancementTrack.HEAVINESS)
    defender_pressure = 1 + heaviness // 2 + (2 if guarded else 0)
    stagger_ms = int(heaviness * tuning.heaviness_stagger_scale * 1000)
    if guarded:
        stagger_ms += 80

    return AttackResolution(
        legal=True,
        hit=True,
        critical=critical,
        guarded=guarded,
        damage=damage_i,
        hit_chance=hit_chance,
        crit_chance=crit_chance,
        attacker_durability_loss=1,
        defender_durability_pressure=defender_pressure,
        stagger_ms=stagger_ms,
        action_end_ms=action_end,
        recovery_end_ms=recovery_end,
        threat_generated=float(damage_i) + (8.0 if sword_skill else 3.0),
    )
