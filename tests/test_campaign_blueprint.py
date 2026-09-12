from __future__ import annotations

import json

import pytest

from sao_mcp.rules.progression_effects import normal_attack_modifiers, weapon_proficiency_key
from sao_mcp.domain.models import WeaponClass
from sao_mcp.runtime.campaign_blueprint import (
    BLUEPRINT_SCHEMA,
    apply_campaign_blueprint,
    preview_campaign_blueprint,
    validate_campaign_blueprint,
)
from sao_mcp.runtime.character_setup import begin_campaign_setup, finalize_campaign_setup
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


def make_runtime():
    return SocialCommunicationAincradRuntime(seed=0xA1C0)


def star_sword_blueprint():
    sword_skills = []
    for index in range(1, 13):
        sword_skills.append(
            {
                "skill_id": f"star_sword_art_{index:02d}",
                "name": f"星辰剑·第{index}式",
                "weapon_class": "one_hand_sword",
                "proficiency_skill_id": "star_sword",
                "prerequisite_proficiency": float((index - 1) * 40),
                "hits": [0.55 + index * 0.01, 0.65 + index * 0.01],
                "windup_ms": max(100, 300 - index * 8),
                "active_ms": 480 + index * 15,
                "post_motion_ms": max(160, 430 - index * 12),
                "accuracy_modifier": 0.05 + index * 0.005,
                "lunge_m": 1.5 + index * 0.08,
                "stagger": 0.03 + index * 0.005,
                "provenance": {"kind": "optional_variant", "notes": "campaign blueprint fixture"},
            }
        )
    return {
        "schema": BLUEPRINT_SCHEMA,
        "blueprint_id": "kageaki_star_sword_start",
        "title": "凑斗景明·星辰剑开局",
        "catalog": {
            "skills": [
                {
                    "skill_id": "star_sword",
                    "name": "星辰剑",
                    "kind": "unique",
                    "description": "Campaign-specific sword system replacement.",
                    "provenance": {"kind": "optional_variant"},
                },
                {
                    "skill_id": "star_sword_overlimit",
                    "name": "星辰剑·超限",
                    "kind": "unique",
                    "description": "Unlocked after the style passes its system-limit threshold.",
                    "prerequisites": ["star_sword"],
                    "provenance": {"kind": "optional_variant"},
                },
            ],
            "sword_skills": sword_skills,
            "weapons": [
                {
                    "template_id": "star_sword_blade",
                    "name": "星辰剑·试作一型",
                    "weapon_class": "one_hand_sword",
                    "damage_type": "slash",
                    "attack_min": 23,
                    "attack_max": 31,
                    "required_level": 7,
                    "required_strength": 20,
                    "weight": 4.2,
                    "base_durability": 420,
                    "base_speed_ms": 575,
                    "reach_m": 1.75,
                    "tags": ["campaign_unique"],
                    "provenance": {"kind": "optional_variant"},
                }
            ],
            "consumables": [
                {
                    "template_id": "full_restore_crystal",
                    "name": "完全回复结晶",
                    "effect": "heal_full",
                    "magnitude": 0,
                    "duration_ms": 0,
                    "cooldown_ms": 60000,
                    "weight": 0.2,
                    "stack_limit": 10,
                    "provenance": {"kind": "optional_variant"},
                },
                {
                    "template_id": "setup_teleport_crystal",
                    "name": "转移结晶",
                    "effect": "teleport",
                    "magnitude": 0,
                    "duration_ms": 0,
                    "cooldown_ms": 0,
                    "requires_voice": True,
                    "weight": 0.2,
                    "stack_limit": 10,
                    "provenance": {"kind": "optional_variant"},
                },
            ],
        },
        "characters": [
            {
                "key": "player",
                "name": "凑斗景明",
                "level": 7,
                "keep_starter_loadout": False,
                "col": 3860,
                "profile": {
                    "age": 19,
                    "sex": "male",
                    "appearance": "somewhat_handsome",
                    "physical_condition": "excellent",
                },
                "skill_proficiencies": {
                    "star_sword": 520.0,
                    "searching": 64.0,
                    "parry": 82.0,
                },
                "replace_skill_proficiencies": True,
                "equipped_skills": ["star_sword", "searching", "parry"],
                "unlocked_special_skills": ["star_sword"],
                "custom_mechanics": [
                    {
                        "mechanic_id": "star_sword_growth",
                        "name": "星辰剑成长",
                        "effects": [
                            {
                                "type": "level_attribute_growth",
                                "strength_per_level": 1,
                                "agility_per_level": 1,
                                "from_level": 1,
                            },
                            {
                                "type": "weapon_proficiency_route",
                                "weapon_class": "one_hand_sword",
                                "skill_id": "star_sword",
                            },
                            {
                                "type": "weapon_enhancement_cap_curve",
                                "weapon_class": "one_hand_sword",
                                "skill_id": "star_sword",
                                "thresholds": [[50, 1], [150, 2], [250, 3], [350, 4], [450, 5], [550, 6]],
                            },
                            {
                                "type": "normal_attack_curve",
                                "weapon_class": "one_hand_sword",
                                "skill_id": "star_sword",
                                "min_proficiency": 501,
                                "reference_proficiency": 500,
                                "damage_multiplier_start": 1.15,
                                "damage_multiplier_per_proficiency": 0.0003,
                                "damage_multiplier_max": 1.30,
                                "recovery_multiplier_start": 0.90,
                                "recovery_multiplier_end": 0.80,
                                "recovery_end_proficiency": 1000,
                            },
                            {
                                "type": "proficiency_gain_modifier",
                                "skill_id": "star_sword",
                                "multiplier": 1.25,
                                "flat_bonus": 0.1,
                            },
                            {
                                "type": "skill_unlock",
                                "skill_id": "star_sword_overlimit",
                                "watch_skill_id": "star_sword",
                                "min_proficiency": 500,
                            },
                        ],
                    }
                ],
                "inventory": [
                    {
                        "template_id": "star_sword_blade",
                        "max_enhancement_attempts": 8,
                        "enhancement_attempts_used": 2,
                        "enhancements": {"sharpness": 2, "quickness": 1},
                        "equip_now": True,
                    },
                    {"template_id": "full_restore_crystal", "quantity": 2},
                    {"template_id": "setup_teleport_crystal", "quantity": 3},
                ],
            }
        ],
    }


def test_star_sword_blueprint_preview_is_pure_and_apply_commits_complete_start():
    runtime = make_runtime()
    begin_campaign_setup(runtime)
    blueprint = star_sword_blueprint()
    before = export_runtime(runtime)

    validation = validate_campaign_blueprint(runtime, blueprint)
    assert validation["valid"] is True
    assert validation["character_keys"] == ["player"]
    assert validation["catalog_counts"]["sword_skills"] == 12
    assert export_runtime(runtime) == before

    preview = preview_campaign_blueprint(runtime, blueprint)
    assert preview["committed"] is False
    assert preview["applicable_now"] is True
    assert preview["characters"][0]["actor_id"] is None
    assert {item["template_id"] for item in preview["characters"][0]["inventory"]} == {
        "star_sword_blade", "full_restore_crystal", "setup_teleport_crystal"
    }
    assert export_runtime(runtime) == before

    result = apply_campaign_blueprint(runtime, blueprint)
    actor_id = result["characters"][0]["actor_id"]
    actor = runtime.actors[actor_id]

    assert result["committed"] is True
    assert len([skill_id for skill_id in runtime.catalog.sword_skills if skill_id.startswith("star_sword_art_")]) == 12
    assert actor.level == 7
    assert (actor.strength, actor.agility) == (28, 28)
    assert actor.col == 3860
    assert actor.skill_proficiencies == {"star_sword": 520.0, "searching": 64.0, "parry": 82.0}
    assert actor.equipped_skills == ["star_sword", "searching", "parry"]
    assert "star_sword_overlimit" in actor.metadata["unlocked_special_skills"]
    assert weapon_proficiency_key(actor, WeaponClass.ONE_HAND_SWORD) == "star_sword"
    damage, recovery = normal_attack_modifiers(actor, WeaponClass.ONE_HAND_SWORD)
    assert damage > 1.15
    assert recovery < 0.90

    inventory_templates = {item.template_id for item in actor.inventory.values()}
    assert inventory_templates == {"star_sword_blade", "full_restore_crystal", "setup_teleport_crystal"}
    weapon = next(item for item in actor.inventory.values() if item.template_id == "star_sword_blade")
    assert actor.equipment["weapon"] == weapon.instance_id
    assert weapon.max_enhancement_attempts == 13  # baseline 8 + proficiency-450 bonus 5


def test_invalid_blueprint_apply_leaves_authoritative_runtime_unchanged():
    runtime = make_runtime()
    begin_campaign_setup(runtime)
    blueprint = star_sword_blueprint()
    blueprint["characters"][0]["inventory"].append({"template_id": "does_not_exist", "quantity": 1})
    before = export_runtime(runtime)

    with pytest.raises(KeyError):
        apply_campaign_blueprint(runtime, blueprint)

    assert export_runtime(runtime) == before
    assert "star_sword" not in runtime.catalog.skills
    assert not runtime.actors


def test_applied_blueprint_survives_finalize_and_save_roundtrip():
    runtime = make_runtime()
    begin_campaign_setup(runtime)
    result = apply_campaign_blueprint(runtime, star_sword_blueprint())
    actor_id = result["characters"][0]["actor_id"]
    finalized = finalize_campaign_setup(runtime)
    assert finalized["status"] == "finalized"

    payload = json.loads(export_runtime(runtime))
    assert payload["schema"] == "sao.aincrad.save.v4"
    assert "star_sword" in payload["custom_catalog_state"]["skills"]
    assert len(payload["custom_catalog_state"]["sword_skills"]) >= 12

    restored = make_runtime()
    import_runtime(json.dumps(payload, ensure_ascii=False), into=restored)
    actor = restored.actors[actor_id]
    assert restored.catalog.skills["star_sword"].name == "星辰剑"
    assert actor.metadata["custom_mechanics"][0]["mechanic_id"] == "star_sword_growth"
    assert {item.template_id for item in actor.inventory.values()} == {
        "star_sword_blade", "full_restore_crystal", "setup_teleport_crystal"
    }
