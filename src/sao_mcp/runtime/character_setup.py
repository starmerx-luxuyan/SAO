from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from sao_mcp.domain.models import (
    ArmorTemplate,
    CombatantState,
    EnhancementTrack,
    EntityKind,
    ItemInstance,
    SkillKind,
    WeaponTemplate,
)
from sao_mcp.rules.custom_mechanics import (
    apply_skill_unlocks,
    clear_custom_mechanics,
    configure_custom_mechanics,
    custom_mechanics as actor_custom_mechanics,
)
from sao_mcp.rules.inventory import add_item, equip, recompute_equipment_stats, unequip
from sao_mcp.rules.progression import MAX_SKILL_PROFICIENCY, apply_level, default_max_hp, experience_to_reach_level, skill_slot_count
from sao_mcp.rules.travel import discover_location
from sao_mcp.rules.progression_effects import (
    PROGRESSION_RULES_KEY,
    configure_level_growth_bonus,
    progression_rules,
    refresh_weapon_enhancement_caps,
    validate_progression_rules,
)


CAMPAIGN_SETUP_STATE_ATTR = "_campaign_setup_state"
SETUP_NOT_STARTED = "not_started"
SETUP_OPEN = "open"
SETUP_FINALIZED = "finalized"


def _new_setup_state() -> dict[str, Any]:
    return {
        "status": SETUP_NOT_STARTED,
        "revision": 0,
        "finalized_at_world_ms": None,
    }


def campaign_setup_state(runtime) -> dict[str, Any]:
    state = getattr(runtime, CAMPAIGN_SETUP_STATE_ATTR, None)
    if state is None:
        state = _new_setup_state()
        setattr(runtime, CAMPAIGN_SETUP_STATE_ATTR, state)
    return state


def begin_campaign_setup(runtime) -> dict[str, Any]:
    state = campaign_setup_state(runtime)
    if state["status"] == SETUP_FINALIZED:
        raise ValueError("campaign setup is finalized; public setup cannot be reopened")
    if state["status"] == SETUP_OPEN:
        raise ValueError("campaign setup is already open")
    state["status"] = SETUP_OPEN
    state["finalized_at_world_ms"] = None
    return dict(state)


def require_campaign_setup_open(runtime) -> None:
    state = campaign_setup_state(runtime)
    if state["status"] != SETUP_OPEN:
        raise ValueError("campaign setup is not open; call begin_campaign_setup before setup mutations")


def finalize_campaign_setup(runtime) -> dict[str, Any]:
    require_campaign_setup_open(runtime)
    if not any(actor.kind is EntityKind.PLAYER for actor in runtime.actors.values()):
        raise ValueError("campaign setup requires at least one player character before finalization")
    state = campaign_setup_state(runtime)
    state["status"] = SETUP_FINALIZED
    state["finalized_at_world_ms"] = int(runtime.world.now_ms)
    return dict(state)


def reopen_campaign_setup(runtime) -> dict[str, Any]:
    state = campaign_setup_state(runtime)
    if state["status"] != SETUP_FINALIZED:
        raise ValueError("only a finalized campaign can be reopened")
    state["status"] = SETUP_OPEN
    state["revision"] = int(state.get("revision", 0)) + 1
    state["finalized_at_world_ms"] = None
    return dict(state)


def dump_campaign_setup_state(runtime) -> dict[str, Any]:
    return dict(campaign_setup_state(runtime))


def load_campaign_setup_state(runtime, payload: dict[str, Any] | None) -> None:
    if payload is None:
        state = {
            "status": SETUP_FINALIZED,
            "revision": 0,
            "finalized_at_world_ms": None,
        }
    else:
        status = str(payload.get("status", SETUP_FINALIZED))
        if status not in {SETUP_NOT_STARTED, SETUP_OPEN, SETUP_FINALIZED}:
            raise ValueError(f"unknown campaign setup status: {status}")
        state = {
            "status": status,
            "revision": int(payload.get("revision", 0)),
            "finalized_at_world_ms": payload.get("finalized_at_world_ms"),
        }
    setattr(runtime, CAMPAIGN_SETUP_STATE_ATTR, state)


RESTRICTED_SKILL_KINDS = {SkillKind.EXTRA, SkillKind.UNIQUE}


def _item_id() -> str:
    return f"item_{uuid.uuid4().hex[:12]}"


def _player(runtime, actor_id: str) -> CombatantState:
    actor = runtime.actors[actor_id]
    if actor.kind is not EntityKind.PLAYER:
        raise ValueError("character setup tools only operate on player actors")
    return actor


def _validate_equipped_skills(runtime, actor: CombatantState, skill_ids: list[str]) -> list[str]:
    if len(skill_ids) != len(set(skill_ids)):
        raise ValueError("equipped_skills contains duplicates")
    if len(skill_ids) > skill_slot_count(actor.level):
        raise ValueError("equipped skills exceed the character's skill-slot count")
    unlocked = set(actor.metadata.get("unlocked_special_skills", ()))
    for skill_id in skill_ids:
        definition = runtime.catalog.skills.get(skill_id)
        if definition is None:
            raise KeyError(skill_id)
        if definition.kind in RESTRICTED_SKILL_KINDS and skill_id not in unlocked:
            raise ValueError(f"Extra/Unique Skill has not been unlocked: {skill_id}")
        for prerequisite in definition.prerequisites:
            if prerequisite not in actor.skill_proficiencies:
                raise ValueError(f"missing skill prerequisite for {skill_id}: {prerequisite}")
    return list(skill_ids)


def _tracked_level_growth(actor: CombatantState, field: str) -> int:
    rule = progression_rules(actor).get("level_growth_bonus", {})
    if not isinstance(rule, dict):
        return 0
    return int(rule.get(field, 0) or 0)


def configure_character(
    runtime,
    actor_id: str,
    *,
    level: int | None = None,
    experience: int | None = None,
    location_id: str | None = None,
    strength: int | None = None,
    agility: int | None = None,
    col: int | None = None,
    max_hp: int | None = None,
    heal_to_full: bool = True,
    profile: dict[str, Any] | None = None,
    replace_profile: bool = False,
    skill_proficiencies: dict[str, float] | None = None,
    replace_skill_proficiencies: bool = False,
    equipped_skills: list[str] | None = None,
    unlocked_special_skills: list[str] | None = None,
    progression_rule_patch: dict[str, Any] | None = None,
    replace_progression_rules: bool = False,
    apply_level_growth_retroactive: bool = True,
    custom_mechanics: list[dict[str, Any]] | None = None,
    apply_custom_mechanics_retroactive: bool = True,
) -> CombatantState:
    actor = _player(runtime, actor_id)
    if custom_mechanics is not None:
        clear_custom_mechanics(actor)

    if level is not None:
        level = int(level)
        if level < actor.level:
            raise ValueError("setup level cannot decrease; recreate the character for a lower level")
        if level > actor.level:
            apply_level(actor, level)

    if experience is not None:
        experience = int(experience)
        minimum = experience_to_reach_level(actor.level)
        if experience < minimum:
            raise ValueError(f"experience cannot be below the current level floor ({minimum})")
        implied_level = actor.level
        while implied_level < 200 and experience >= experience_to_reach_level(implied_level + 1):
            implied_level += 1
        if implied_level > actor.level:
            apply_level(actor, implied_level)
        actor.metadata["experience"] = experience

    if location_id is not None:
        if location_id not in runtime.world_map.locations:
            raise KeyError(location_id)
        location = runtime.world_map.locations[location_id]
        floor = runtime.world.floors[location.floor_number]
        if not floor.unlocked:
            raise ValueError("setup location floor is not unlocked")
        if any(encounter.active and actor.actor_id in encounter.participants for encounter in runtime.encounters.values()):
            raise ValueError("cannot relocate a character in an active encounter")
        discover_location(runtime.world, actor, location)

    if unlocked_special_skills is not None:
        unknown = [skill_id for skill_id in unlocked_special_skills if skill_id not in runtime.catalog.skills]
        if unknown:
            raise KeyError(f"unknown special skills: {unknown}")
        restricted = [
            skill_id
            for skill_id in unlocked_special_skills
            if runtime.catalog.skills[skill_id].kind not in RESTRICTED_SKILL_KINDS
        ]
        if restricted:
            raise ValueError(f"only Extra/Unique Skills belong in unlocked_special_skills: {restricted}")
        actor.metadata["unlocked_special_skills"] = list(dict.fromkeys(unlocked_special_skills))

    if skill_proficiencies is not None:
        normalized: dict[str, float] = {}
        for skill_id, value in skill_proficiencies.items():
            if skill_id not in runtime.catalog.skills and not str(skill_id).startswith("weapon:"):
                raise KeyError(skill_id)
            proficiency = float(value)
            if not 0.0 <= proficiency <= MAX_SKILL_PROFICIENCY:
                raise ValueError(f"skill proficiency must be 0..1000: {skill_id}")
            normalized[str(skill_id)] = proficiency
        if replace_skill_proficiencies:
            actor.skill_proficiencies = normalized
        else:
            actor.skill_proficiencies.update(normalized)

    if strength is not None:
        if int(strength) < 1:
            raise ValueError("strength must be >= 1")
        actor.strength = int(strength) + _tracked_level_growth(actor, "applied_strength")
    if agility is not None:
        if int(agility) < 1:
            raise ValueError("agility must be >= 1")
        actor.agility = int(agility) + _tracked_level_growth(actor, "applied_agility")

    if progression_rule_patch is not None:
        clean = validate_progression_rules(actor, runtime.catalog, progression_rule_patch)
        has_level_rule = "level_growth_bonus" in progression_rule_patch
        if replace_progression_rules and not has_level_rule:
            configure_level_growth_bonus(actor, None)
        current = {} if replace_progression_rules else dict(progression_rules(actor))
        if "level_growth_bonus" in clean:
            configure_level_growth_bonus(
                actor,
                clean["level_growth_bonus"],
                apply_retroactive=apply_level_growth_retroactive,
            )
            # configure_level_growth_bonus writes its tracked contribution into metadata.
            current = dict(progression_rules(actor))
            clean.pop("level_growth_bonus", None)
        if replace_progression_rules:
            level_rule = progression_rules(actor).get("level_growth_bonus")
            current = {"level_growth_bonus": level_rule} if level_rule is not None else {}
        current.update(clean)
        actor.metadata[PROGRESSION_RULES_KEY] = current

    if custom_mechanics is not None:
        configure_custom_mechanics(
            actor,
            runtime.catalog,
            custom_mechanics,
            apply_retroactive=apply_custom_mechanics_retroactive,
        )

    if col is not None:
        if int(col) < 0:
            raise ValueError("col must be >= 0")
        actor.col = int(col)

    if profile is not None:
        if not isinstance(profile, dict):
            raise ValueError("profile must be an object")
        if replace_profile or not isinstance(actor.metadata.get("profile"), dict):
            actor.metadata["profile"] = dict(profile)
        else:
            actor.metadata["profile"].update(profile)

    if equipped_skills is not None:
        actor.equipped_skills = _validate_equipped_skills(runtime, actor, list(equipped_skills))
        for skill_id in actor.equipped_skills:
            actor.skill_proficiencies.setdefault(skill_id, 0.0)

    calculated_hp = default_max_hp(actor.level, actor.strength, actor.agility)
    if max_hp is not None:
        if int(max_hp) < 1:
            raise ValueError("max_hp must be >= 1")
        actor.max_hp = int(max_hp)
    else:
        actor.max_hp = calculated_hp
    if heal_to_full:
        actor.hp = actor.max_hp
        actor.alive = True
    else:
        actor.clamp_hp()

    actor.metadata["experience"] = max(
        int(actor.metadata.get("experience", 0) or 0),
        experience_to_reach_level(actor.level),
    )
    apply_skill_unlocks(actor, runtime.catalog)
    refresh_weapon_enhancement_caps(actor, runtime.catalog)
    recompute_equipment_stats(actor, runtime.catalog)
    return actor


def grant_character_item(
    runtime,
    actor_id: str,
    template_id: str,
    *,
    quantity: int = 1,
    durability: int | None = None,
    max_durability: int | None = None,
    max_enhancement_attempts: int | None = None,
    enhancement_attempts_used: int = 0,
    enhancements: dict[str, int] | None = None,
    quality: float = 1.0,
    maker_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    equip_now: bool = False,
    allow_overweight: bool = False,
) -> ItemInstance:
    actor = _player(runtime, actor_id)
    template = runtime.catalog.item(template_id)
    quantity = int(quantity)
    if quantity < 1 or quantity > template.stack_limit:
        raise ValueError(f"quantity must be 1..{template.stack_limit}")
    if quality <= 0.0:
        raise ValueError("quality must be > 0")

    template_durability: int | None = None
    if isinstance(template, (WeaponTemplate, ArmorTemplate)):
        template_durability = int(template.base_durability)
    resolved_max = template_durability if max_durability is None else int(max_durability)
    if resolved_max is not None and resolved_max < 1:
        raise ValueError("max_durability must be >= 1")
    resolved_durability = resolved_max if durability is None else int(durability)
    if resolved_durability is not None and resolved_max is not None:
        if not 0 <= resolved_durability <= resolved_max:
            raise ValueError("durability must be between 0 and max_durability")

    resolved_max_attempts = 0 if max_enhancement_attempts is None else int(max_enhancement_attempts)
    attempts_used = int(enhancement_attempts_used)
    if resolved_max_attempts < 0 or attempts_used < 0 or attempts_used > resolved_max_attempts:
        raise ValueError("invalid enhancement attempt counts")
    parsed_enhancements: dict[EnhancementTrack, int] = {}
    for track, value in (enhancements or {}).items():
        key = EnhancementTrack(str(track))
        amount = int(value)
        if amount < 0:
            raise ValueError("enhancement levels must be non-negative")
        if amount:
            parsed_enhancements[key] = amount

    item = ItemInstance(
        instance_id=_item_id(),
        template_id=template_id,
        owner_id=actor.actor_id,
        quantity=quantity,
        durability=resolved_durability,
        max_durability=resolved_max,
        enhancement_attempts_used=attempts_used,
        max_enhancement_attempts=resolved_max_attempts,
        enhancements=parsed_enhancements,
        maker_id=maker_id,
        quality=float(quality),
        metadata=dict(metadata or {}),
    )
    add_item(actor, item, runtime.catalog, allow_overweight=allow_overweight)
    refresh_weapon_enhancement_caps(actor, runtime.catalog)
    if equip_now:
        equip(actor, item.instance_id, runtime.catalog)
    return item


def remove_character_item(runtime, actor_id: str, instance_id: str) -> ItemInstance:
    actor = _player(runtime, actor_id)
    if instance_id not in actor.inventory:
        raise KeyError(instance_id)
    for slot, equipped_id in list(actor.equipment.items()):
        if equipped_id == instance_id:
            unequip(actor, slot, runtime.catalog)
    item = actor.inventory.pop(instance_id)
    recompute_equipment_stats(actor, runtime.catalog)
    return item


def character_setup_state(runtime, actor_id: str) -> dict[str, Any]:
    actor = _player(runtime, actor_id)
    return {
        "actor": asdict(actor),
        "skill_slots_total": skill_slot_count(actor.level),
        "profile": actor.metadata.get("profile", {}),
        "progression_rules": progression_rules(actor),
        "custom_mechanics": actor_custom_mechanics(actor),
        "unlocked_special_skills": list(actor.metadata.get("unlocked_special_skills", ())),
    }
