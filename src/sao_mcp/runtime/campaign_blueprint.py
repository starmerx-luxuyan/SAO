from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from sao_mcp.domain.models import (
    ArmorTemplate,
    ConsumableEffect,
    ConsumableTemplate,
    DamageType,
    ItemKind,
    ItemTemplate,
    Provenance,
    ProvenanceKind,
    SkillDefinition,
    SkillKind,
    StatusType,
    SwordSkillDefinition,
    WeaponClass,
    WeaponTemplate,
)
from sao_mcp.runtime.character_setup import (
    campaign_setup_state,
    character_setup_state,
    configure_character,
    grant_character_item,
    remove_character_item,
    require_campaign_setup_open,
)
from sao_mcp.runtime.custom_catalog import (
    dump_custom_catalog_state,
    register_custom_armor,
    register_custom_consumable,
    register_custom_item,
    register_custom_skill,
    register_custom_sword_skill,
    register_custom_weapon,
)
from sao_mcp.runtime.persistence import export_runtime, import_runtime


BLUEPRINT_SCHEMA = "sao.aincrad.campaign-blueprint.v1"


def _blueprint_digest(blueprint: dict[str, Any]) -> str:
    canonical = json.dumps(blueprint, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _provenance(raw: dict[str, Any] | None) -> Provenance:
    raw = raw or {}
    return Provenance(
        ProvenanceKind(str(raw.get("kind", "optional_variant"))),
        sources=tuple(str(value) for value in raw.get("sources", ())),
        notes=str(raw.get("notes", "")),
    )


def _rows(section: Any, name: str) -> list[dict[str, Any]]:
    if section is None:
        return []
    if not isinstance(section, list):
        raise ValueError(f"blueprint catalog.{name} must be a list")
    rows: list[dict[str, Any]] = []
    for index, value in enumerate(section):
        if not isinstance(value, dict):
            raise ValueError(f"blueprint catalog.{name}[{index}] must be an object")
        rows.append(dict(value))
    return rows


def _require_text(raw: dict[str, Any], key: str, *, context: str) -> str:
    value = str(raw.get(key, "")).strip()
    if not value:
        raise ValueError(f"{context} requires {key}")
    return value


def _build_skill(raw: dict[str, Any], known_skill_ids: set[str]) -> SkillDefinition:
    skill_id = _require_text(raw, "skill_id", context="custom skill")
    name = _require_text(raw, "name", context=f"custom skill {skill_id}")
    prerequisites = tuple(str(value) for value in raw.get("prerequisites", ()))
    missing = [value for value in prerequisites if value not in known_skill_ids]
    if missing:
        raise ValueError(f"custom skill {skill_id} has unknown prerequisites: {missing}")
    return SkillDefinition(
        skill_id=skill_id,
        name=name,
        kind=SkillKind(str(raw["kind"])),
        description=str(raw.get("description", "")),
        prerequisites=prerequisites,
        provenance=_provenance(raw.get("provenance")),
    )


def _build_sword_skill(raw: dict[str, Any], known_skill_ids: set[str]) -> SwordSkillDefinition:
    skill_id = _require_text(raw, "skill_id", context="custom Sword Skill")
    name = _require_text(raw, "name", context=f"custom Sword Skill {skill_id}")
    hits = tuple(float(value) for value in raw.get("hits", ()))
    if not hits or any(value <= 0.0 for value in hits):
        raise ValueError(f"custom Sword Skill {skill_id} requires positive hit multipliers")
    prerequisite = float(raw.get("prerequisite_proficiency", 0.0))
    if not 0.0 <= prerequisite <= 1000.0:
        raise ValueError(f"custom Sword Skill {skill_id} prerequisite_proficiency must be 0..1000")
    timings = tuple(int(raw.get(key, 0)) for key in ("windup_ms", "active_ms", "post_motion_ms"))
    if any(value < 0 for value in timings):
        raise ValueError(f"custom Sword Skill {skill_id} timing cannot be negative")
    proficiency_skill_id = raw.get("proficiency_skill_id")
    if proficiency_skill_id is not None:
        proficiency_skill_id = str(proficiency_skill_id)
        if proficiency_skill_id not in known_skill_ids:
            raise ValueError(f"custom Sword Skill {skill_id} references unknown proficiency skill: {proficiency_skill_id}")
    lunge_m = float(raw.get("lunge_m", 0.0))
    stagger = float(raw.get("stagger", 0.0))
    if lunge_m < 0.0 or stagger < 0.0:
        raise ValueError(f"custom Sword Skill {skill_id} lunge_m and stagger must be non-negative")
    return SwordSkillDefinition(
        skill_id=skill_id,
        name=name,
        weapon_class=WeaponClass(str(raw["weapon_class"])),
        prerequisite_proficiency=prerequisite,
        hits=hits,
        windup_ms=timings[0],
        active_ms=timings[1],
        post_motion_ms=timings[2],
        accuracy_modifier=float(raw.get("accuracy_modifier", 0.0)),
        lunge_m=lunge_m,
        stagger=stagger,
        provenance=_provenance(raw.get("provenance")),
        proficiency_skill_id=proficiency_skill_id,
    )


def _build_weapon(raw: dict[str, Any]) -> WeaponTemplate:
    template_id = _require_text(raw, "template_id", context="custom weapon")
    name = _require_text(raw, "name", context=f"custom weapon {template_id}")
    attack_min = int(raw.get("attack_min", 1))
    attack_max = int(raw.get("attack_max", attack_min))
    required_level = int(raw.get("required_level", 1))
    required_strength = int(raw.get("required_strength", 1))
    weight = float(raw.get("weight", 0.0))
    durability = int(raw.get("base_durability", 100))
    speed = int(raw.get("base_speed_ms", 700))
    reach = float(raw.get("reach_m", 1.5))
    if attack_min < 0 or attack_max < attack_min:
        raise ValueError(f"custom weapon {template_id} has an invalid attack range")
    if required_level < 1 or required_strength < 0:
        raise ValueError(f"custom weapon {template_id} has invalid requirements")
    if weight < 0.0 or durability < 1 or speed < 1 or reach <= 0.0:
        raise ValueError(f"custom weapon {template_id} has invalid physical parameters")
    return WeaponTemplate(
        template_id=template_id,
        name=name,
        kind=ItemKind.WEAPON,
        weight=weight,
        stack_limit=1,
        base_value_col=raw.get("base_value_col"),
        tags=tuple(str(value) for value in raw.get("tags", ())),
        provenance=_provenance(raw.get("provenance")),
        weapon_class=WeaponClass(str(raw.get("weapon_class", "other"))),
        damage_type=DamageType(str(raw.get("damage_type", "mixed"))),
        attack_min=attack_min,
        attack_max=attack_max,
        required_level=required_level,
        required_strength=required_strength,
        base_durability=durability,
        base_speed_ms=speed,
        reach_m=reach,
        bonus_strength=int(raw.get("bonus_strength", 0)),
        bonus_agility=int(raw.get("bonus_agility", 0)),
    )


def _build_armor(raw: dict[str, Any]) -> ArmorTemplate:
    template_id = _require_text(raw, "template_id", context="custom armor")
    name = _require_text(raw, "name", context=f"custom armor {template_id}")
    kind = ItemKind(str(raw.get("item_kind", "armor")))
    if kind not in {ItemKind.ARMOR, ItemKind.SHIELD}:
        raise ValueError(f"custom armor {template_id} item_kind must be armor or shield")
    armor = int(raw.get("armor", 0))
    weight = float(raw.get("weight", 0.0))
    durability = int(raw.get("base_durability", 100))
    if armor < 0 or weight < 0.0 or durability < 1:
        raise ValueError(f"custom armor {template_id} has invalid physical parameters")
    return ArmorTemplate(
        template_id=template_id,
        name=name,
        kind=kind,
        weight=weight,
        stack_limit=1,
        base_value_col=raw.get("base_value_col"),
        tags=tuple(str(value) for value in raw.get("tags", ())),
        provenance=_provenance(raw.get("provenance")),
        armor=armor,
        base_durability=durability,
        slot=str(raw.get("slot") or ("offhand" if kind is ItemKind.SHIELD else "body")),
    )


def _build_consumable(raw: dict[str, Any]) -> ConsumableTemplate:
    template_id = _require_text(raw, "template_id", context="custom consumable")
    name = _require_text(raw, "name", context=f"custom consumable {template_id}")
    magnitude = int(raw.get("magnitude", 0))
    duration = int(raw.get("duration_ms", 0))
    cooldown = int(raw.get("cooldown_ms", 0))
    weight = float(raw.get("weight", 0.0))
    stack_limit = int(raw.get("stack_limit", 1))
    if min(magnitude, duration, cooldown) < 0 or weight < 0.0 or stack_limit < 1:
        raise ValueError(f"custom consumable {template_id} has invalid parameters")
    return ConsumableTemplate(
        template_id=template_id,
        name=name,
        kind=ItemKind.CONSUMABLE,
        weight=weight,
        stack_limit=stack_limit,
        base_value_col=raw.get("base_value_col"),
        tags=tuple(str(value) for value in raw.get("tags", ())),
        provenance=_provenance(raw.get("provenance")),
        effect=ConsumableEffect(str(raw["effect"])),
        magnitude=magnitude,
        duration_ms=duration,
        cooldown_ms=cooldown,
        requires_voice=bool(raw.get("requires_voice", False)),
        status_tags=tuple(StatusType(str(value)) for value in raw.get("status_tags", ())),
    )


def _build_item(raw: dict[str, Any]) -> ItemTemplate:
    template_id = _require_text(raw, "template_id", context="custom item")
    name = _require_text(raw, "name", context=f"custom item {template_id}")
    kind = ItemKind(str(raw.get("item_kind", "misc")))
    if kind in {ItemKind.WEAPON, ItemKind.ARMOR, ItemKind.SHIELD, ItemKind.CONSUMABLE}:
        raise ValueError(f"custom item {template_id} must use its specialized catalog section")
    weight = float(raw.get("weight", 0.0))
    stack_limit = int(raw.get("stack_limit", 1))
    if weight < 0.0 or stack_limit < 1:
        raise ValueError(f"custom item {template_id} has invalid parameters")
    return ItemTemplate(
        template_id=template_id,
        name=name,
        kind=kind,
        weight=weight,
        stack_limit=stack_limit,
        base_value_col=raw.get("base_value_col"),
        tags=tuple(str(value) for value in raw.get("tags", ())),
        provenance=_provenance(raw.get("provenance")),
    )


def _register_blueprint_catalog(runtime, raw_catalog: dict[str, Any]) -> dict[str, list[str]]:
    if not isinstance(raw_catalog, dict):
        raise ValueError("blueprint catalog must be an object")
    ids: dict[str, list[str]] = {
        "skills": [],
        "sword_skills": [],
        "weapons": [],
        "armors": [],
        "consumables": [],
        "items": [],
    }

    skill_rows = _rows(raw_catalog.get("skills"), "skills")
    declared_skill_ids = [_require_text(row, "skill_id", context="custom skill") for row in skill_rows]
    if len(declared_skill_ids) != len(set(declared_skill_ids)):
        raise ValueError("blueprint declares duplicate custom skill ids")
    known_skill_ids = set(runtime.catalog.skills) | set(declared_skill_ids)
    for row in skill_rows:
        definition = _build_skill(row, known_skill_ids)
        register_custom_skill(runtime, definition, replace=bool(row.get("replace", False)))
        ids["skills"].append(definition.skill_id)

    for row in _rows(raw_catalog.get("sword_skills"), "sword_skills"):
        definition = _build_sword_skill(row, set(runtime.catalog.skills))
        register_custom_sword_skill(runtime, definition, replace=bool(row.get("replace", False)))
        ids["sword_skills"].append(definition.skill_id)

    for row in _rows(raw_catalog.get("weapons"), "weapons"):
        definition = _build_weapon(row)
        register_custom_weapon(runtime, definition, replace=bool(row.get("replace", False)))
        ids["weapons"].append(definition.template_id)

    for row in _rows(raw_catalog.get("armors"), "armors"):
        definition = _build_armor(row)
        register_custom_armor(runtime, definition, replace=bool(row.get("replace", False)))
        ids["armors"].append(definition.template_id)

    for row in _rows(raw_catalog.get("consumables"), "consumables"):
        definition = _build_consumable(row)
        register_custom_consumable(runtime, definition, replace=bool(row.get("replace", False)))
        ids["consumables"].append(definition.template_id)

    for row in _rows(raw_catalog.get("items"), "items"):
        definition = _build_item(row)
        register_custom_item(runtime, definition, replace=bool(row.get("replace", False)))
        ids["items"].append(definition.template_id)

    return ids


def _character_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    characters = blueprint.get("characters")
    if not isinstance(characters, list) or not characters:
        raise ValueError("campaign blueprint requires at least one character")
    rows: list[dict[str, Any]] = []
    keys: list[str] = []
    for index, raw in enumerate(characters):
        if not isinstance(raw, dict):
            raise ValueError(f"blueprint characters[{index}] must be an object")
        row = dict(raw)
        key = _require_text(row, "key", context=f"blueprint characters[{index}]")
        _require_text(row, "name", context=f"blueprint character {key}")
        keys.append(key)
        rows.append(row)
    if len(keys) != len(set(keys)):
        raise ValueError("campaign blueprint character keys must be unique")
    return rows


def _grant_inventory(runtime, actor_id: str, rows: Any) -> None:
    if rows is None:
        return
    if not isinstance(rows, list):
        raise ValueError("character inventory must be a list")
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise ValueError(f"character inventory[{index}] must be an object")
        template_id = _require_text(raw, "template_id", context=f"character inventory[{index}]")
        grant_character_item(
            runtime,
            actor_id,
            template_id,
            quantity=int(raw.get("quantity", 1)),
            durability=raw.get("durability"),
            max_durability=raw.get("max_durability"),
            max_enhancement_attempts=raw.get("max_enhancement_attempts"),
            enhancement_attempts_used=int(raw.get("enhancement_attempts_used", 0)),
            enhancements=raw.get("enhancements"),
            quality=float(raw.get("quality", 1.0)),
            maker_id=raw.get("maker_id"),
            metadata=dict(raw.get("metadata") or {}),
            equip_now=bool(raw.get("equip_now", False)),
            allow_overweight=bool(raw.get("allow_overweight", False)),
        )


def _create_blueprint_character(runtime, row: dict[str, Any]):
    level = int(row.get("level", 1))
    starter_weapon_id = str(row.get("starter_weapon_id", "starter_one_hand_sword"))
    actor = runtime.create_character(
        _require_text(row, "name", context=f"blueprint character {row['key']}"),
        level=level,
        starter_weapon_id=starter_weapon_id,
    )
    if not bool(row.get("keep_starter_loadout", False)):
        for instance_id in tuple(actor.inventory):
            remove_character_item(runtime, actor.actor_id, instance_id)

    configure_character(
        runtime,
        actor.actor_id,
        level=level,
        experience=row.get("experience"),
        location_id=row.get("location_id"),
        strength=row.get("strength"),
        agility=row.get("agility"),
        col=row.get("col"),
        max_hp=row.get("max_hp"),
        heal_to_full=bool(row.get("heal_to_full", True)),
        profile=dict(row.get("profile") or {}),
        replace_profile=True,
        skill_proficiencies=dict(row.get("skill_proficiencies") or {}),
        replace_skill_proficiencies=bool(row.get("replace_skill_proficiencies", False)),
        equipped_skills=row.get("equipped_skills"),
        unlocked_special_skills=row.get("unlocked_special_skills"),
        progression_rule_patch=row.get("progression_rules"),
        replace_progression_rules=True if row.get("progression_rules") is not None else False,
        apply_level_growth_retroactive=bool(row.get("apply_level_growth_retroactive", True)),
        custom_mechanics=row.get("custom_mechanics"),
        apply_custom_mechanics_retroactive=bool(row.get("apply_custom_mechanics_retroactive", True)),
    )
    _grant_inventory(runtime, actor.actor_id, row.get("inventory"))
    return actor


def _preview_character(runtime, key: str, actor_id: str, *, committed: bool) -> dict[str, Any]:
    actor = runtime.actors[actor_id]
    inventory = []
    for item in actor.inventory.values():
        template = runtime.catalog.item(item.template_id)
        inventory.append(
            {
                "instance_id": item.instance_id if committed else None,
                "template_id": item.template_id,
                "name": template.name,
                "quantity": item.quantity,
                "durability": item.durability,
                "max_durability": item.max_durability,
                "max_enhancement_attempts": item.max_enhancement_attempts,
                "enhancement_attempts_used": item.enhancement_attempts_used,
                "enhancements": {track.value: value for track, value in item.enhancements.items()},
                "equipped_slots": [slot for slot, instance_id in actor.equipment.items() if instance_id == item.instance_id],
            }
        )
    setup = character_setup_state(runtime, actor_id)
    return {
        "key": key,
        "actor_id": actor_id if committed else None,
        "name": actor.name,
        "level": actor.level,
        "experience": actor.metadata.get("experience"),
        "strength": actor.strength,
        "agility": actor.agility,
        "max_hp": actor.max_hp,
        "hp": actor.hp,
        "col": actor.col,
        "location_id": actor.location_id,
        "profile": setup["profile"],
        "skill_slots_total": setup["skill_slots_total"],
        "equipped_skills": list(actor.equipped_skills),
        "skill_proficiencies": dict(actor.skill_proficiencies),
        "unlocked_special_skills": setup["unlocked_special_skills"],
        "progression_rules": setup["progression_rules"],
        "custom_mechanics": setup["custom_mechanics"],
        "inventory": inventory,
    }


def _apply_blueprint_in_place(runtime, blueprint: dict[str, Any], *, committed: bool) -> dict[str, Any]:
    if not isinstance(blueprint, dict):
        raise ValueError("campaign blueprint must be an object")
    if blueprint.get("schema") != BLUEPRINT_SCHEMA:
        raise ValueError(f"campaign blueprint schema must be {BLUEPRINT_SCHEMA!r}")
    blueprint_id = _require_text(blueprint, "blueprint_id", context="campaign blueprint")
    character_rows = _character_rows(blueprint)
    catalog_ids = _register_blueprint_catalog(runtime, dict(blueprint.get("catalog") or {}))

    actor_ids: dict[str, str] = {}
    for row in character_rows:
        actor = _create_blueprint_character(runtime, row)
        actor_ids[str(row["key"])] = actor.actor_id

    return {
        "schema": BLUEPRINT_SCHEMA,
        "blueprint_id": blueprint_id,
        "title": str(blueprint.get("title", blueprint_id)),
        "digest_sha256": _blueprint_digest(blueprint),
        "committed": committed,
        "catalog": catalog_ids,
        "characters": [
            _preview_character(runtime, key, actor_id, committed=committed)
            for key, actor_id in actor_ids.items()
        ],
    }


def _clone_runtime(runtime):
    clone = type(runtime)(seed=0)
    import_runtime(export_runtime(runtime), into=clone)
    return clone


def validate_campaign_blueprint(runtime, blueprint: dict[str, Any]) -> dict[str, Any]:
    clone = _clone_runtime(runtime)
    result = _apply_blueprint_in_place(clone, blueprint, committed=False)
    return {
        "valid": True,
        "schema": result["schema"],
        "blueprint_id": result["blueprint_id"],
        "digest_sha256": result["digest_sha256"],
        "setup_status": campaign_setup_state(runtime)["status"],
        "catalog_counts": {key: len(values) for key, values in result["catalog"].items()},
        "character_keys": [value["key"] for value in result["characters"]],
    }


def preview_campaign_blueprint(runtime, blueprint: dict[str, Any]) -> dict[str, Any]:
    clone = _clone_runtime(runtime)
    result = _apply_blueprint_in_place(clone, blueprint, committed=False)
    result["setup_status"] = campaign_setup_state(runtime)["status"]
    result["applicable_now"] = result["setup_status"] == "open"
    result["custom_catalog_after"] = dump_custom_catalog_state(clone)
    return result


def apply_campaign_blueprint(runtime, blueprint: dict[str, Any]) -> dict[str, Any]:
    require_campaign_setup_open(runtime)
    clone = _clone_runtime(runtime)
    result = _apply_blueprint_in_place(clone, blueprint, committed=True)
    import_runtime(export_runtime(clone), into=runtime)
    result["setup_status"] = campaign_setup_state(runtime)["status"]
    return result
