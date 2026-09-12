from __future__ import annotations

from typing import Any

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import CombatantState, WeaponClass


CUSTOM_MECHANICS_KEY = "custom_mechanics"
CUSTOM_MECHANIC_STATE_KEY = "custom_mechanic_state"


def custom_mechanics(actor: CombatantState) -> list[dict[str, Any]]:
    raw = actor.metadata.get(CUSTOM_MECHANICS_KEY, [])
    return raw if isinstance(raw, list) else []


def _state(actor: CombatantState) -> dict[str, Any]:
    state = actor.metadata.get(CUSTOM_MECHANIC_STATE_KEY)
    if not isinstance(state, dict):
        state = {}
        actor.metadata[CUSTOM_MECHANIC_STATE_KEY] = state
    return state


def _validate_conditions(catalog: Catalog, raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("mechanic conditions must be an object")
    clean: dict[str, Any] = {}
    for key in ("min_level", "max_level"):
        if key in raw:
            value = int(raw[key])
            if value < 1:
                raise ValueError(f"{key} must be >= 1")
            clean[key] = value
    if clean.get("max_level", 10**9) < clean.get("min_level", 1):
        raise ValueError("max_level must be >= min_level")
    for key in ("min_hp_ratio", "max_hp_ratio"):
        if key in raw:
            value = float(raw[key])
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{key} must be between 0 and 1")
            clean[key] = value
    if clean.get("max_hp_ratio", 1.0) < clean.get("min_hp_ratio", 0.0):
        raise ValueError("max_hp_ratio must be >= min_hp_ratio")
    for key in ("requires_equipped_skills", "requires_unlocked_skills"):
        if key in raw:
            values = list(dict.fromkeys(str(value) for value in raw[key]))
            unknown = [value for value in values if value not in catalog.skills]
            if unknown:
                raise ValueError(f"unknown skill in {key}: {unknown}")
            clean[key] = values
    if "min_proficiencies" in raw:
        if not isinstance(raw["min_proficiencies"], dict):
            raise ValueError("min_proficiencies must be an object")
        table: dict[str, float] = {}
        for skill_id, value in raw["min_proficiencies"].items():
            skill_id = str(skill_id)
            if skill_id not in catalog.skills and not skill_id.startswith("weapon:"):
                raise ValueError(f"unknown proficiency skill: {skill_id}")
            threshold = float(value)
            if not 0.0 <= threshold <= 1000.0:
                raise ValueError("proficiency conditions must be 0..1000")
            table[skill_id] = threshold
        clean["min_proficiencies"] = table
    return clean


def _validate_thresholds(raw: Any) -> list[list[float | int]]:
    if not isinstance(raw, list):
        raise ValueError("thresholds must be a list")
    clean: list[list[float | int]] = []
    last_prof = -1.0
    for pair in raw:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("threshold must be [proficiency, value]")
        proficiency = float(pair[0])
        value = int(pair[1])
        if not 0.0 <= proficiency <= 1000.0:
            raise ValueError("threshold proficiency must be 0..1000")
        if proficiency <= last_prof:
            raise ValueError("threshold proficiency values must increase")
        clean.append([proficiency, value])
        last_prof = proficiency
    return clean


def validate_custom_mechanics(catalog: Catalog, mechanics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(mechanics, list):
        raise ValueError("custom_mechanics must be a list")
    seen: set[str] = set()
    route_classes: set[str] = set()
    clean_mechanics: list[dict[str, Any]] = []
    for index, mechanic in enumerate(mechanics):
        if not isinstance(mechanic, dict):
            raise ValueError(f"custom mechanic {index} must be an object")
        mechanic_id = str(mechanic.get("mechanic_id", "")).strip()
        if not mechanic_id:
            raise ValueError("custom mechanic requires mechanic_id")
        if mechanic_id in seen:
            raise ValueError(f"duplicate custom mechanic id: {mechanic_id}")
        seen.add(mechanic_id)
        effects = mechanic.get("effects", [])
        if not isinstance(effects, list) or not effects:
            raise ValueError(f"custom mechanic {mechanic_id} requires effects")
        clean_effects: list[dict[str, Any]] = []
        for effect_index, effect in enumerate(effects):
            if not isinstance(effect, dict):
                raise ValueError(f"custom mechanic effect {mechanic_id}[{effect_index}] must be an object")
            effect_type = str(effect.get("type", "")).strip()
            conditions = _validate_conditions(catalog, effect.get("conditions"))
            clean: dict[str, Any] = {"type": effect_type}
            if conditions:
                clean["conditions"] = conditions

            if effect_type == "level_attribute_growth":
                clean.update(
                    strength_per_level=int(effect.get("strength_per_level", 0)),
                    agility_per_level=int(effect.get("agility_per_level", 0)),
                    from_level=int(effect.get("from_level", 1)),
                )
                if clean["from_level"] < 1:
                    raise ValueError("level_attribute_growth from_level must be >= 1")
            elif effect_type == "weapon_proficiency_route":
                weapon_class = WeaponClass(str(effect["weapon_class"])).value
                skill_id = str(effect["skill_id"])
                if skill_id not in catalog.skills:
                    raise ValueError(f"unknown proficiency route skill: {skill_id}")
                if weapon_class in route_classes:
                    raise ValueError(f"multiple custom proficiency routes for {weapon_class}")
                route_classes.add(weapon_class)
                clean.update(weapon_class=weapon_class, skill_id=skill_id)
            elif effect_type == "weapon_enhancement_cap_curve":
                weapon_class = WeaponClass(str(effect["weapon_class"])).value
                skill_id = str(effect["skill_id"])
                if skill_id not in catalog.skills:
                    raise ValueError(f"unknown enhancement-cap skill: {skill_id}")
                thresholds = _validate_thresholds(effect.get("thresholds", []))
                if any(int(value) < 0 for _, value in thresholds):
                    raise ValueError("weapon enhancement cap bonuses must be non-negative")
                clean.update(weapon_class=weapon_class, skill_id=skill_id, thresholds=thresholds)
            elif effect_type == "normal_attack_curve":
                weapon_class = WeaponClass(str(effect["weapon_class"])).value
                skill_id = str(effect["skill_id"])
                if skill_id not in catalog.skills:
                    raise ValueError(f"unknown normal-attack skill: {skill_id}")
                minimum = float(effect.get("min_proficiency", 0.0))
                reference = float(effect.get("reference_proficiency", minimum))
                damage_start = float(effect.get("damage_multiplier_start", 1.0))
                damage_per = float(effect.get("damage_multiplier_per_proficiency", 0.0))
                damage_max = float(effect.get("damage_multiplier_max", damage_start))
                recovery_start = float(effect.get("recovery_multiplier_start", 1.0))
                recovery_end = float(effect.get("recovery_multiplier_end", recovery_start))
                recovery_end_prof = float(effect.get("recovery_end_proficiency", 1000.0))
                if not (0.0 <= minimum <= 1000.0 and 0.0 <= reference <= 1000.0):
                    raise ValueError("normal attack proficiency bounds must be 0..1000")
                if damage_start < 0.0 or damage_per < 0.0 or damage_max < damage_start:
                    raise ValueError("invalid normal attack damage curve")
                if recovery_start <= 0.0 or recovery_end <= 0.0:
                    raise ValueError("normal attack recovery multipliers must be positive")
                if not minimum <= recovery_end_prof <= 1000.0:
                    raise ValueError("invalid recovery_end_proficiency")
                clean.update(
                    weapon_class=weapon_class,
                    skill_id=skill_id,
                    min_proficiency=minimum,
                    reference_proficiency=reference,
                    damage_multiplier_start=damage_start,
                    damage_multiplier_per_proficiency=damage_per,
                    damage_multiplier_max=damage_max,
                    recovery_multiplier_start=recovery_start,
                    recovery_multiplier_end=recovery_end,
                    recovery_end_proficiency=recovery_end_prof,
                )
            elif effect_type == "skill_unlock":
                skill_id = str(effect["skill_id"])
                watch_skill_id = str(effect["watch_skill_id"])
                if skill_id not in catalog.skills or watch_skill_id not in catalog.skills:
                    raise ValueError("skill_unlock references unknown skill")
                minimum = float(effect.get("min_proficiency", 0.0))
                if not 0.0 <= minimum <= 1000.0:
                    raise ValueError("skill unlock threshold must be 0..1000")
                clean.update(skill_id=skill_id, watch_skill_id=watch_skill_id, min_proficiency=minimum)
            elif effect_type == "proficiency_gain_modifier":
                skill_id = str(effect.get("skill_id", "*"))
                if skill_id != "*" and skill_id not in catalog.skills:
                    raise ValueError(f"unknown proficiency gain skill: {skill_id}")
                multiplier = float(effect.get("multiplier", 1.0))
                flat_bonus = float(effect.get("flat_bonus", 0.0))
                if multiplier < 0.0:
                    raise ValueError("proficiency gain multiplier must be non-negative")
                clean.update(skill_id=skill_id, multiplier=multiplier, flat_bonus=flat_bonus)
            else:
                raise ValueError(f"unsupported custom mechanic effect type: {effect_type!r}")
            clean_effects.append(clean)
        clean_mechanics.append(
            {
                "mechanic_id": mechanic_id,
                "name": str(mechanic.get("name", mechanic_id)),
                "description": str(mechanic.get("description", "")),
                "effects": clean_effects,
            }
        )
    return clean_mechanics


def _conditions_met(actor: CombatantState, conditions: dict[str, Any] | None) -> bool:
    if not conditions:
        return True
    if actor.level < int(conditions.get("min_level", 1)):
        return False
    if actor.level > int(conditions.get("max_level", 10**9)):
        return False
    hp_ratio = actor.hp / actor.max_hp if actor.max_hp > 0 else 0.0
    if hp_ratio < float(conditions.get("min_hp_ratio", 0.0)):
        return False
    if hp_ratio > float(conditions.get("max_hp_ratio", 1.0)):
        return False
    equipped = set(actor.equipped_skills)
    if not set(conditions.get("requires_equipped_skills", ())).issubset(equipped):
        return False
    unlocked = set(actor.metadata.get("unlocked_special_skills", ()))
    if not set(conditions.get("requires_unlocked_skills", ())).issubset(unlocked):
        return False
    for skill_id, threshold in conditions.get("min_proficiencies", {}).items():
        if float(actor.skill_proficiencies.get(skill_id, 0.0)) < float(threshold):
            return False
    return True


def iter_effects(actor: CombatantState, effect_type: str):
    for mechanic in custom_mechanics(actor):
        for index, effect in enumerate(mechanic.get("effects", ())):
            if effect.get("type") == effect_type and _conditions_met(actor, effect.get("conditions")):
                yield mechanic["mechanic_id"], index, effect


def clear_custom_mechanics(actor: CombatantState) -> None:
    state = _state(actor)
    growth = state.get("level_growth", {})
    if isinstance(growth, dict):
        actor.strength -= sum(int(row.get("strength", 0)) for row in growth.values() if isinstance(row, dict))
        actor.agility -= sum(int(row.get("agility", 0)) for row in growth.values() if isinstance(row, dict))
    actor.metadata[CUSTOM_MECHANICS_KEY] = []
    actor.metadata[CUSTOM_MECHANIC_STATE_KEY] = {}


def configure_custom_mechanics(
    actor: CombatantState,
    catalog: Catalog,
    mechanics: list[dict[str, Any]],
    *,
    apply_retroactive: bool = True,
) -> list[dict[str, Any]]:
    clean = validate_custom_mechanics(catalog, mechanics)
    clear_custom_mechanics(actor)
    actor.metadata[CUSTOM_MECHANICS_KEY] = clean
    state = _state(actor)
    growth_state: dict[str, dict[str, int]] = {}
    if apply_retroactive:
        for mechanic_id, index, effect in iter_effects(actor, "level_attribute_growth"):
            from_level = int(effect.get("from_level", 1))
            eligible = max(0, actor.level - from_level)
            strength = eligible * int(effect.get("strength_per_level", 0))
            agility = eligible * int(effect.get("agility_per_level", 0))
            actor.strength += strength
            actor.agility += agility
            growth_state[f"{mechanic_id}:{index}"] = {"strength": strength, "agility": agility}
    state["level_growth"] = growth_state
    apply_skill_unlocks(actor, catalog)
    return clean


def apply_level_growth(actor: CombatantState, old_level: int, new_level: int) -> None:
    if new_level <= old_level:
        return
    growth_state = _state(actor).setdefault("level_growth", {})
    for mechanic_id, index, effect in iter_effects(actor, "level_attribute_growth"):
        from_level = int(effect.get("from_level", 1))
        before = max(0, old_level - from_level)
        after = max(0, new_level - from_level)
        gained = max(0, after - before)
        strength = gained * int(effect.get("strength_per_level", 0))
        agility = gained * int(effect.get("agility_per_level", 0))
        actor.strength += strength
        actor.agility += agility
        key = f"{mechanic_id}:{index}"
        row = growth_state.setdefault(key, {"strength": 0, "agility": 0})
        row["strength"] = int(row.get("strength", 0)) + strength
        row["agility"] = int(row.get("agility", 0)) + agility


def weapon_proficiency_route(actor: CombatantState, weapon_class: WeaponClass | str) -> str | None:
    value = weapon_class.value if isinstance(weapon_class, WeaponClass) else str(weapon_class)
    for _, _, effect in iter_effects(actor, "weapon_proficiency_route"):
        if effect.get("weapon_class") == value:
            return str(effect["skill_id"])
    return None


def weapon_enhancement_cap_bonus(actor: CombatantState, weapon_class: WeaponClass | str) -> int:
    value = weapon_class.value if isinstance(weapon_class, WeaponClass) else str(weapon_class)
    bonus = 0
    for _, _, effect in iter_effects(actor, "weapon_enhancement_cap_curve"):
        if effect.get("weapon_class") != value:
            continue
        proficiency = float(actor.skill_proficiencies.get(str(effect["skill_id"]), 0.0))
        candidate = 0
        for threshold, amount in effect.get("thresholds", ()):
            if proficiency >= float(threshold):
                candidate = max(candidate, int(amount))
        bonus += candidate
    return bonus


def normal_attack_modifiers(actor: CombatantState, weapon_class: WeaponClass | str) -> tuple[float, float]:
    value = weapon_class.value if isinstance(weapon_class, WeaponClass) else str(weapon_class)
    damage_total = 1.0
    recovery_total = 1.0
    for _, _, effect in iter_effects(actor, "normal_attack_curve"):
        if effect.get("weapon_class") != value:
            continue
        proficiency = float(actor.skill_proficiencies.get(str(effect["skill_id"]), 0.0))
        minimum = float(effect.get("min_proficiency", 0.0))
        if proficiency < minimum:
            continue
        reference = float(effect.get("reference_proficiency", minimum))
        damage = float(effect.get("damage_multiplier_start", 1.0))
        damage += max(0.0, proficiency - reference) * float(effect.get("damage_multiplier_per_proficiency", 0.0))
        damage = min(float(effect.get("damage_multiplier_max", damage)), damage)
        recovery_start = float(effect.get("recovery_multiplier_start", 1.0))
        recovery_end = float(effect.get("recovery_multiplier_end", recovery_start))
        recovery_end_prof = float(effect.get("recovery_end_proficiency", 1000.0))
        if recovery_end_prof <= minimum:
            recovery = recovery_end
        else:
            t = max(0.0, min(1.0, (proficiency - minimum) / (recovery_end_prof - minimum)))
            recovery = recovery_start + (recovery_end - recovery_start) * t
        damage_total *= max(0.0, damage)
        recovery_total *= max(0.05, recovery)
    return damage_total, recovery_total


def proficiency_gain(actor: CombatantState, skill_id: str, base_gain: float) -> float:
    amount = float(base_gain)
    for _, _, effect in iter_effects(actor, "proficiency_gain_modifier"):
        if effect.get("skill_id") not in {"*", skill_id}:
            continue
        amount = amount * float(effect.get("multiplier", 1.0)) + float(effect.get("flat_bonus", 0.0))
    return max(0.0, amount)


def apply_skill_unlocks(actor: CombatantState, catalog: Catalog) -> list[str]:
    unlocked = list(actor.metadata.get("unlocked_special_skills", ()))
    seen = set(unlocked)
    added: list[str] = []
    for _, _, effect in iter_effects(actor, "skill_unlock"):
        watch = str(effect["watch_skill_id"])
        if float(actor.skill_proficiencies.get(watch, 0.0)) < float(effect.get("min_proficiency", 0.0)):
            continue
        skill_id = str(effect["skill_id"])
        if skill_id not in catalog.skills:
            continue
        if skill_id not in seen:
            unlocked.append(skill_id)
            seen.add(skill_id)
            added.append(skill_id)
    actor.metadata["unlocked_special_skills"] = unlocked
    return added
