from __future__ import annotations

from typing import Any

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import CombatantState, SwordSkillDefinition, WeaponClass
from sao_mcp.rules.custom_mechanics import (
    normal_attack_modifiers as custom_normal_attack_modifiers,
    weapon_enhancement_cap_bonus as custom_weapon_enhancement_cap_bonus,
    weapon_proficiency_route as custom_weapon_proficiency_route,
)


PROGRESSION_RULES_KEY = "progression_rules"


def progression_rules(actor: CombatantState) -> dict[str, Any]:
    raw = actor.metadata.get(PROGRESSION_RULES_KEY, {})
    return raw if isinstance(raw, dict) else {}


def weapon_proficiency_key(
    actor: CombatantState,
    weapon_class: WeaponClass | str,
    *,
    sword_skill: SwordSkillDefinition | None = None,
) -> str:
    value = weapon_class.value if isinstance(weapon_class, WeaponClass) else str(weapon_class)
    if sword_skill is not None and sword_skill.proficiency_skill_id:
        return sword_skill.proficiency_skill_id

    routed = custom_weapon_proficiency_route(actor, value)
    if routed is not None:
        return routed

    mapping = progression_rules(actor).get("weapon_proficiency_skill_by_class", {})
    if isinstance(mapping, dict):
        mapped = mapping.get(value)
        if isinstance(mapped, str) and mapped:
            return mapped

    explicit = f"weapon:{value}"
    if explicit in actor.skill_proficiencies:
        return explicit
    return value


def weapon_proficiency_value(
    actor: CombatantState,
    weapon_class: WeaponClass | str,
    *,
    sword_skill: SwordSkillDefinition | None = None,
) -> float:
    key = weapon_proficiency_key(actor, weapon_class, sword_skill=sword_skill)
    return float(actor.skill_proficiencies.get(key, 0.0))


def configure_level_growth_bonus(
    actor: CombatantState,
    rule: dict[str, Any] | None,
    *,
    apply_retroactive: bool = True,
) -> None:
    rules = progression_rules(actor)
    old = rules.get("level_growth_bonus", {})
    if isinstance(old, dict):
        actor.strength -= int(old.get("applied_strength", 0) or 0)
        actor.agility -= int(old.get("applied_agility", 0) or 0)

    if not rule:
        rules.pop("level_growth_bonus", None)
        actor.metadata[PROGRESSION_RULES_KEY] = rules
        return

    strength_per_level = int(rule.get("strength_per_level", 0) or 0)
    agility_per_level = int(rule.get("agility_per_level", 0) or 0)
    from_level = int(rule.get("from_level", 1) or 1)
    if strength_per_level < 0 or agility_per_level < 0:
        raise ValueError("per-level growth bonuses must be non-negative")
    if from_level < 1:
        raise ValueError("level growth from_level must be >= 1")

    eligible_levels = max(0, actor.level - from_level) if apply_retroactive else 0
    applied_strength = eligible_levels * strength_per_level
    applied_agility = eligible_levels * agility_per_level
    actor.strength += applied_strength
    actor.agility += applied_agility
    rules["level_growth_bonus"] = {
        "strength_per_level": strength_per_level,
        "agility_per_level": agility_per_level,
        "from_level": from_level,
        "applied_strength": applied_strength,
        "applied_agility": applied_agility,
    }
    actor.metadata[PROGRESSION_RULES_KEY] = rules


def apply_level_growth_bonus(actor: CombatantState, old_level: int, new_level: int) -> None:
    if new_level <= old_level:
        return
    rules = progression_rules(actor)
    rule = rules.get("level_growth_bonus")
    if not isinstance(rule, dict):
        return
    strength_per_level = int(rule.get("strength_per_level", 0) or 0)
    agility_per_level = int(rule.get("agility_per_level", 0) or 0)
    from_level = int(rule.get("from_level", 1) or 1)
    eligible_before = max(0, old_level - from_level)
    eligible_after = max(0, new_level - from_level)
    gained_eligible = max(0, eligible_after - eligible_before)
    add_strength = gained_eligible * strength_per_level
    add_agility = gained_eligible * agility_per_level
    actor.strength += add_strength
    actor.agility += add_agility
    rule["applied_strength"] = int(rule.get("applied_strength", 0) or 0) + add_strength
    rule["applied_agility"] = int(rule.get("applied_agility", 0) or 0) + add_agility


def validate_progression_rules(actor: CombatantState, catalog: Catalog, rules: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rules, dict):
        raise ValueError("progression_rules must be an object")
    clean: dict[str, Any] = {}

    mapping = rules.get("weapon_proficiency_skill_by_class")
    if mapping is not None:
        if not isinstance(mapping, dict):
            raise ValueError("weapon_proficiency_skill_by_class must be an object")
        clean_mapping: dict[str, str] = {}
        for weapon_class, skill_id in mapping.items():
            wc = WeaponClass(str(weapon_class)).value
            skill_id = str(skill_id)
            if skill_id not in catalog.skills:
                raise ValueError(f"unknown mapped skill: {skill_id}")
            clean_mapping[wc] = skill_id
        clean["weapon_proficiency_skill_by_class"] = clean_mapping

    enhancement = rules.get("weapon_enhancement_cap_by_class")
    if enhancement is not None:
        if not isinstance(enhancement, dict):
            raise ValueError("weapon_enhancement_cap_by_class must be an object")
        clean_enhancement: dict[str, Any] = {}
        for weapon_class, raw_rule in enhancement.items():
            wc = WeaponClass(str(weapon_class)).value
            if not isinstance(raw_rule, dict):
                raise ValueError("enhancement cap rule must be an object")
            skill_id = str(raw_rule.get("skill_id", ""))
            if skill_id not in catalog.skills:
                raise ValueError(f"unknown enhancement-cap skill: {skill_id}")
            thresholds = raw_rule.get("thresholds", [])
            if not isinstance(thresholds, list):
                raise ValueError("enhancement cap thresholds must be a list")
            clean_thresholds: list[list[float | int]] = []
            last_prof = -1.0
            last_bonus = -1
            for pair in thresholds:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError("each enhancement threshold must be [proficiency, bonus]")
                prof = float(pair[0])
                bonus = int(pair[1])
                if not (0.0 <= prof <= 1000.0) or bonus < 0:
                    raise ValueError("invalid enhancement cap threshold")
                if prof <= last_prof or bonus < last_bonus:
                    raise ValueError("enhancement thresholds must increase monotonically")
                clean_thresholds.append([prof, bonus])
                last_prof, last_bonus = prof, bonus
            clean_enhancement[wc] = {"skill_id": skill_id, "thresholds": clean_thresholds}
        clean["weapon_enhancement_cap_by_class"] = clean_enhancement

    normal = rules.get("normal_attack_by_class")
    if normal is not None:
        if not isinstance(normal, dict):
            raise ValueError("normal_attack_by_class must be an object")
        clean_normal: dict[str, Any] = {}
        for weapon_class, raw_rule in normal.items():
            wc = WeaponClass(str(weapon_class)).value
            if not isinstance(raw_rule, dict):
                raise ValueError("normal attack rule must be an object")
            skill_id = str(raw_rule.get("skill_id", ""))
            if skill_id not in catalog.skills:
                raise ValueError(f"unknown normal-attack skill: {skill_id}")
            min_prof = float(raw_rule.get("min_proficiency", 0.0))
            reference = float(raw_rule.get("reference_proficiency", min_prof))
            damage_start = float(raw_rule.get("damage_multiplier_start", 1.0))
            damage_per = float(raw_rule.get("damage_multiplier_per_proficiency", 0.0))
            damage_max = float(raw_rule.get("damage_multiplier_max", damage_start))
            recovery_start = float(raw_rule.get("recovery_multiplier_start", 1.0))
            recovery_end = float(raw_rule.get("recovery_multiplier_end", recovery_start))
            recovery_end_prof = float(raw_rule.get("recovery_end_proficiency", 1000.0))
            if not (0.0 <= min_prof <= 1000.0 and 0.0 <= reference <= 1000.0):
                raise ValueError("normal attack proficiency bounds must be 0..1000")
            if damage_start < 0.0 or damage_max < damage_start or damage_per < 0.0:
                raise ValueError("invalid normal attack damage progression")
            if not (0.05 <= recovery_start <= 2.0 and 0.05 <= recovery_end <= 2.0):
                raise ValueError("invalid normal attack recovery multiplier")
            if recovery_end_prof < min_prof or recovery_end_prof > 1000.0:
                raise ValueError("invalid normal attack recovery end proficiency")
            clean_normal[wc] = {
                "skill_id": skill_id,
                "min_proficiency": min_prof,
                "reference_proficiency": reference,
                "damage_multiplier_start": damage_start,
                "damage_multiplier_per_proficiency": damage_per,
                "damage_multiplier_max": damage_max,
                "recovery_multiplier_start": recovery_start,
                "recovery_multiplier_end": recovery_end,
                "recovery_end_proficiency": recovery_end_prof,
            }
        clean["normal_attack_by_class"] = clean_normal

    # Level growth is configured through configure_level_growth_bonus so that
    # retroactive contributions are tracked and can be replaced without drift.
    if "level_growth_bonus" in rules:
        clean["level_growth_bonus"] = dict(rules["level_growth_bonus"] or {})
    return clean


def refresh_weapon_enhancement_caps(actor: CombatantState, catalog: Catalog) -> None:
    rules = progression_rules(actor)
    by_class = rules.get("weapon_enhancement_cap_by_class", {})
    if not isinstance(by_class, dict):
        return
    for item in actor.inventory.values():
        weapon = catalog.weapons.get(item.template_id)
        if weapon is None:
            continue
        rule = by_class.get(weapon.weapon_class.value)
        base_key = "progression_base_max_enhancement_attempts"
        if base_key not in item.metadata:
            item.metadata[base_key] = int(item.max_enhancement_attempts)
        base = int(item.metadata[base_key])
        bonus = custom_weapon_enhancement_cap_bonus(actor, weapon.weapon_class)
        if isinstance(rule, dict):
            skill_id = str(rule.get("skill_id", ""))
            proficiency = float(actor.skill_proficiencies.get(skill_id, 0.0))
            legacy_bonus = 0
            for threshold, candidate in rule.get("thresholds", []):
                if proficiency >= float(threshold):
                    legacy_bonus = max(legacy_bonus, int(candidate))
            bonus += legacy_bonus
        item.max_enhancement_attempts = max(item.enhancement_attempts_used, base + bonus)


def normal_attack_modifiers(
    actor: CombatantState,
    weapon_class: WeaponClass | str,
) -> tuple[float, float]:
    value = weapon_class.value if isinstance(weapon_class, WeaponClass) else str(weapon_class)
    raw = progression_rules(actor).get("normal_attack_by_class", {})
    custom_damage, custom_recovery = custom_normal_attack_modifiers(actor, value)
    if not isinstance(raw, dict):
        return custom_damage, custom_recovery
    rule = raw.get(value)
    if not isinstance(rule, dict):
        return custom_damage, custom_recovery
    skill_id = str(rule.get("skill_id", ""))
    proficiency = float(actor.skill_proficiencies.get(skill_id, 0.0))
    minimum = float(rule.get("min_proficiency", 0.0))
    if proficiency < minimum:
        return custom_damage, custom_recovery

    reference = float(rule.get("reference_proficiency", minimum))
    damage = float(rule.get("damage_multiplier_start", 1.0))
    damage += max(0.0, proficiency - reference) * float(rule.get("damage_multiplier_per_proficiency", 0.0))
    damage = min(float(rule.get("damage_multiplier_max", damage)), damage)

    recovery_start = float(rule.get("recovery_multiplier_start", 1.0))
    recovery_end = float(rule.get("recovery_multiplier_end", recovery_start))
    recovery_end_prof = float(rule.get("recovery_end_proficiency", 1000.0))
    if recovery_end_prof <= minimum:
        recovery = recovery_end
    else:
        t = max(0.0, min(1.0, (proficiency - minimum) / (recovery_end_prof - minimum)))
        recovery = recovery_start + (recovery_end - recovery_start) * t
    return max(0.0, damage) * custom_damage, max(0.05, recovery) * custom_recovery
