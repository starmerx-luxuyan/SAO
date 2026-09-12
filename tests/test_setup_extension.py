from __future__ import annotations

import json

from sao_mcp.domain.models import (
    DefenseMode,
    Provenance,
    ProvenanceKind,
    SkillDefinition,
    SkillKind,
    SwordSkillDefinition,
    WeaponClass,
)
from sao_mcp.rules.progression import apply_level
from sao_mcp.rules.progression_effects import normal_attack_modifiers
from sao_mcp.runtime.character_setup import (
    begin_campaign_setup,
    campaign_setup_state,
    configure_character,
    finalize_campaign_setup,
    grant_character_item,
    reopen_campaign_setup,
)
from sao_mcp.runtime.custom_catalog import register_custom_skill, register_custom_sword_skill
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


def make_runtime():
    return SocialCommunicationAincradRuntime(seed=0xA1C0)


def install_star_sword(runtime):
    register_custom_skill(
        runtime,
        SkillDefinition(
            skill_id="star_sword",
            name="星辰剑",
            kind=SkillKind.UNIQUE,
            description="Campaign unique sword style.",
            provenance=Provenance(ProvenanceKind.OPTIONAL_VARIANT, notes="test fixture"),
        ),
    )
    register_custom_sword_skill(
        runtime,
        SwordSkillDefinition(
            skill_id="star_sword_meteor",
            name="一式·流星",
            weapon_class=WeaponClass.ONE_HAND_SWORD,
            prerequisite_proficiency=0.0,
            hits=(0.58, 0.60, 0.64, 0.78),
            windup_ms=280,
            active_ms=650,
            post_motion_ms=420,
            accuracy_modifier=0.20,
            lunge_m=2.2,
            stagger=0.08,
            provenance=Provenance(ProvenanceKind.OPTIONAL_VARIANT),
            proficiency_skill_id="star_sword",
        ),
    )


def star_progression_rules():
    return {
        "level_growth_bonus": {
            "strength_per_level": 1,
            "agility_per_level": 1,
            "from_level": 1,
        },
        "weapon_proficiency_skill_by_class": {"one_hand_sword": "star_sword"},
        "weapon_enhancement_cap_by_class": {
            "one_hand_sword": {
                "skill_id": "star_sword",
                "thresholds": [
                    [50, 1], [150, 2], [250, 3], [350, 4], [450, 5],
                    [550, 6], [650, 7], [750, 8], [850, 9], [950, 10],
                ],
            }
        },
        "normal_attack_by_class": {
            "one_hand_sword": {
                "skill_id": "star_sword",
                "min_proficiency": 501,
                "reference_proficiency": 500,
                "damage_multiplier_start": 1.15,
                "damage_multiplier_per_proficiency": 0.0003,
                "damage_multiplier_max": 1.30,
                "recovery_multiplier_start": 0.90,
                "recovery_multiplier_end": 0.80,
                "recovery_end_proficiency": 1000,
            }
        },
    }


def configure_kageaki(runtime, proficiency=238.0):
    install_star_sword(runtime)
    actor = runtime.create_character("凑斗景明", level=7)
    configure_character(
        runtime,
        actor.actor_id,
        col=3860,
        profile={"age": 19, "sex": "male", "appearance": "somewhat_handsome", "physical_condition": "excellent"},
        skill_proficiencies={"star_sword": proficiency, "searching": 64.0, "parry": 82.0},
        equipped_skills=["star_sword", "searching", "parry"],
        unlocked_special_skills=["star_sword"],
        progression_rule_patch=star_progression_rules(),
    )
    return actor


def test_configured_character_growth_and_equipment_cap():
    runtime = make_runtime()
    actor = configure_kageaki(runtime, 238.0)

    assert actor.level == 7
    # Base Lv7 stats are 22/22, then the Unique Skill's retroactive +1/+1 per level adds 6.
    assert (actor.strength, actor.agility) == (28, 28)
    assert actor.col == 3860
    assert actor.equipped_skills == ["star_sword", "searching", "parry"]
    assert actor.skill_proficiencies["star_sword"] == 238.0

    anneal = grant_character_item(
        runtime,
        actor.actor_id,
        "anneal_blade",
        max_enhancement_attempts=8,
        enhancement_attempts_used=3,
        enhancements={"sharpness": 2, "quickness": 1},
        equip_now=True,
        allow_overweight=True,
    )
    # 238 proficiency crosses the +2 threshold.
    assert anneal.max_enhancement_attempts == 10
    assert actor.equipment["weapon"] == anneal.instance_id

    apply_level(actor, 8)
    assert (actor.strength, actor.agility) == (31, 31)  # normal +2/+2 plus unique +1/+1


def test_custom_sword_skill_uses_unique_proficiency_and_grows_it():
    runtime = make_runtime()
    actor = configure_kageaki(runtime, 238.0)
    anneal = grant_character_item(
        runtime,
        actor.actor_id,
        "anneal_blade",
        max_enhancement_attempts=8,
        equip_now=True,
        allow_overweight=True,
    )
    monster = runtime.create_training_monster(level=1)
    actor.location_id = "floor_1_west_field"
    encounter = runtime.start_encounter([actor.actor_id, monster.actor_id], zone_id="floor_1_west_field", safe_zone=False)

    before = actor.skill_proficiencies["star_sword"]
    # Find a deterministic hit seed; the important assertion is which proficiency receives growth.
    result = None
    for seed in range(100):
        actor.committed_until_ms = 0
        actor.recovery_until_ms = 0
        monster.hp = monster.max_hp
        monster.alive = True
        result = runtime.attack(
            encounter.encounter_id,
            actor.actor_id,
            monster.actor_id,
            sword_skill_id="star_sword_meteor",
            defense=DefenseMode.NONE,
            distance_m=1.0,
            seed=seed,
        )
        if result.hit:
            break
    assert result is not None and result.legal and result.hit
    assert actor.skill_proficiencies["star_sword"] > before
    # The underlying One-Handed Sword proficiency is not silently used as the style's ledger.
    assert actor.skill_proficiencies.get("one_hand_sword", 0.0) == 0.0
    assert anneal.max_enhancement_attempts == 10


def test_normal_attack_rule_activates_after_500():
    runtime = make_runtime()
    actor = configure_kageaki(runtime, 500.0)
    assert normal_attack_modifiers(actor, WeaponClass.ONE_HAND_SWORD) == (1.0, 1.0)

    actor.skill_proficiencies["star_sword"] = 501.0
    damage_501, recovery_501 = normal_attack_modifiers(actor, WeaponClass.ONE_HAND_SWORD)
    assert damage_501 > 1.15
    assert 0.80 < recovery_501 <= 0.90

    actor.skill_proficiencies["star_sword"] = 1000.0
    damage_1000, recovery_1000 = normal_attack_modifiers(actor, WeaponClass.ONE_HAND_SWORD)
    assert abs(damage_1000 - 1.30) < 1e-9
    assert abs(recovery_1000 - 0.80) < 1e-9


def test_custom_catalog_and_character_rules_survive_save_roundtrip():
    runtime = make_runtime()
    actor = configure_kageaki(runtime, 555.0)
    item = grant_character_item(
        runtime,
        actor.actor_id,
        "anneal_blade",
        max_enhancement_attempts=8,
        enhancement_attempts_used=3,
        enhancements={"sharpness": 2, "quickness": 1},
        equip_now=True,
        allow_overweight=True,
    )
    assert item.max_enhancement_attempts == 14  # +6 at 550

    save = export_runtime(runtime)
    payload = json.loads(save)
    assert payload["schema"] == "sao.aincrad.save.v4"
    assert "star_sword" in payload["custom_catalog_state"]["skills"]
    assert "star_sword_meteor" in payload["custom_catalog_state"]["sword_skills"]

    restored = make_runtime()
    import_runtime(save, into=restored)
    restored_actor = restored.actors[actor.actor_id]
    assert restored.catalog.skills["star_sword"].name == "星辰剑"
    assert restored.catalog.sword_skills["star_sword_meteor"].proficiency_skill_id == "star_sword"
    assert restored_actor.skill_proficiencies["star_sword"] == 555.0
    assert restored_actor.metadata["profile"]["age"] == 19
    assert restored_actor.metadata["progression_rules"]["weapon_proficiency_skill_by_class"]["one_hand_sword"] == "star_sword"
    restored_item = restored_actor.inventory[item.instance_id]
    assert restored_item.max_enhancement_attempts == 14


def test_v3_save_migrates_exactly_with_empty_custom_catalog():
    runtime = make_runtime()
    actor = runtime.create_character("Legacy", level=3)
    payload = json.loads(export_runtime(runtime))
    payload["schema"] = "sao.aincrad.save.v3"
    payload.pop("custom_catalog_state", None)

    restored = make_runtime()
    import_runtime(json.dumps(payload, ensure_ascii=False), into=restored)
    assert restored.actors[actor.actor_id].level == 3
    assert "star_sword" not in restored.catalog.skills
    assert campaign_setup_state(restored)["status"] == "finalized"


def test_normal_attack_modifier_is_applied_inside_combat_resolution():
    import random
    from sao_mcp.rules.combat import resolve_physical_attack

    runtime = make_runtime()
    actor = configure_kageaki(runtime, 500.0)
    anneal = grant_character_item(
        runtime,
        actor.actor_id,
        "anneal_blade",
        max_enhancement_attempts=8,
        equip_now=True,
        allow_overweight=True,
    )
    monster = runtime.create_training_monster(level=3)
    weapon = runtime.catalog.weapons[anneal.template_id]

    before = after = None
    for seed in range(200):
        actor.skill_proficiencies["star_sword"] = 500.0
        r0 = resolve_physical_attack(
            actor, monster, anneal, weapon,
            now_ms=0, rng=random.Random(seed), sword_skill=None,
            defense=DefenseMode.NONE, distance_m=1.0,
        )
        actor.skill_proficiencies["star_sword"] = 501.0
        r1 = resolve_physical_attack(
            actor, monster, anneal, weapon,
            now_ms=0, rng=random.Random(seed), sword_skill=None,
            defense=DefenseMode.NONE, distance_m=1.0,
        )
        if r0.hit and r1.hit and r0.critical == r1.critical:
            before, after = r0, r1
            break
    assert before is not None and after is not None
    assert before.recovery_end_ms - before.action_end_ms == 180
    assert after.recovery_end_ms - after.action_end_ms < 180
    assert after.damage > before.damage


def test_proficiency_crossing_refreshes_weapon_cap_during_real_attack():
    runtime = make_runtime()
    actor = configure_kageaki(runtime, 149.5)
    anneal = grant_character_item(
        runtime,
        actor.actor_id,
        "anneal_blade",
        max_enhancement_attempts=8,
        equip_now=True,
        allow_overweight=True,
    )
    assert anneal.max_enhancement_attempts == 9
    monster = runtime.create_training_monster(level=1)
    actor.location_id = "floor_1_west_field"
    encounter = runtime.start_encounter([actor.actor_id, monster.actor_id], zone_id="floor_1_west_field", safe_zone=False)

    for seed in range(100):
        actor.committed_until_ms = 0
        actor.recovery_until_ms = 0
        monster.hp = monster.max_hp
        monster.alive = True
        result = runtime.attack(
            encounter.encounter_id,
            actor.actor_id,
            monster.actor_id,
            sword_skill_id="star_sword_meteor",
            defense=DefenseMode.NONE,
            distance_m=1.0,
            seed=seed,
        )
        if result.hit:
            break
    assert result.hit
    assert actor.skill_proficiencies["star_sword"] >= 150.0
    assert anneal.max_enhancement_attempts == 10


def test_setup_tool_registration_and_one_shot_character_creation():
    from sao_mcp.server_setup import register_setup_tools

    class DummyMCP:
        def __init__(self):
            self.tools = {}

        def tool(self):
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

    runtime = make_runtime()
    dummy = DummyMCP()
    register_setup_tools(dummy, runtime)
    assert {
        "get_campaign_setup_status",
        "begin_campaign_setup",
        "finalize_campaign_setup",
        "create_configured_character",
        "configure_character_setup",
        "get_character_setup_state",
        "grant_character_item",
        "remove_character_item_setup",
        "register_custom_skill_definition",
        "register_custom_sword_skill_definition",
    } <= set(dummy.tools)
    assert "reopen_campaign_setup" not in dummy.tools
    assert json.loads(dummy.tools["get_campaign_setup_status"]())["status"] == "not_started"
    assert json.loads(dummy.tools["begin_campaign_setup"]())["status"] == "open"

    skill = json.loads(dummy.tools["register_custom_skill_definition"](
        "star_sword", "星辰剑", "unique", notes="campaign unique"
    ))
    assert skill["record"]["skill_id"] == "star_sword"

    sword_skill = json.loads(dummy.tools["register_custom_sword_skill_definition"](
        "star_sword_meteor", "一式·流星", "one_hand_sword", 0.0,
        [0.58, 0.60, 0.64, 0.78], 280, 650, 420,
        proficiency_skill_id="star_sword",
    ))
    assert sword_skill["record"]["proficiency_skill_id"] == "star_sword"

    created = json.loads(dummy.tools["create_configured_character"](
        "凑斗景明",
        level=7,
        col=3860,
        profile={"age": 19, "sex": "male"},
        skill_proficiencies={"star_sword": 238, "searching": 64, "parry": 82},
        equipped_skills=["star_sword", "searching", "parry"],
        unlocked_special_skills=["star_sword"],
        progression_rules=star_progression_rules(),
    ))
    actor_id = created["actor"]["actor_id"]
    assert created["actor"]["strength"] == 28
    assert created["actor"]["agility"] == 28
    assert created["actor"]["col"] == 3860

    granted = json.loads(dummy.tools["grant_character_item"](
        actor_id, "anneal_blade",
        max_enhancement_attempts=8,
        enhancement_attempts_used=3,
        enhancements={"sharpness": 2, "quickness": 1},
        equip_now=True,
        allow_overweight=True,
    ))
    assert granted["item"]["max_enhancement_attempts"] == 10
    assert granted["character"]["actor"]["equipment"]["weapon"] == granted["item"]["instance_id"]
    assert json.loads(dummy.tools["finalize_campaign_setup"]())["status"] == "finalized"

    import pytest
    with pytest.raises(ValueError, match="campaign setup is not open"):
        dummy.tools["configure_character_setup"](actor_id, col=999999)


def test_campaign_setup_lifecycle_persists_and_internal_reopen_is_explicit():
    runtime = make_runtime()
    assert campaign_setup_state(runtime)["status"] == "not_started"
    begin_campaign_setup(runtime)
    actor = runtime.create_character("Lifecycle", level=2)
    finalized = finalize_campaign_setup(runtime)
    assert finalized["status"] == "finalized"

    save = export_runtime(runtime)
    restored = make_runtime()
    import_runtime(save, into=restored)
    assert campaign_setup_state(restored)["status"] == "finalized"
    assert restored.actors[actor.actor_id].name == "Lifecycle"

    reopened = reopen_campaign_setup(restored)
    assert reopened["status"] == "open"
    assert reopened["revision"] == 1


def test_explicit_base_attributes_receive_retroactive_growth_without_drift():
    runtime = make_runtime()
    install_star_sword(runtime)
    actor = runtime.create_character("BaseStats", level=7)
    configure_character(
        runtime,
        actor.actor_id,
        strength=30,
        agility=31,
        progression_rule_patch={
            "level_growth_bonus": {
                "strength_per_level": 1,
                "agility_per_level": 1,
                "from_level": 1,
            }
        },
    )
    assert (actor.strength, actor.agility) == (36, 37)

    configure_character(
        runtime,
        actor.actor_id,
        progression_rule_patch={
            "level_growth_bonus": {
                "strength_per_level": 2,
                "agility_per_level": 2,
                "from_level": 1,
            }
        },
    )
    assert (actor.strength, actor.agility) == (42, 43)


def test_public_gm_gate_can_ground_and_start_a_living_ecology_encounter():
    from sao_mcp.runtime.gm_decision import GMDecisionRuntime
    from sao_mcp.runtime.gm_turn import GMTurnExecutor

    runtime = make_runtime()
    actor = runtime.create_character("FieldTester", level=3)
    # Use the same travel path as the ordinary player action; ecology auto-materializes local wildlife.
    runtime.travel_actor(actor.actor_id, "floor_1_west_field")

    executor = GMTurnExecutor(runtime)
    decision_runtime = GMDecisionRuntime(executor.supported_actions())
    observation = executor.observe([actor.actor_id])
    options = observation["viewpoints"][actor.actor_id]["capabilities"]["encounter_options"]
    assert any(row["monster_id"] == "frenzy_boar" for row in options)

    plan = decision_runtime.decide(
        observation,
        [{"op": "engage_monster", "actor_id": actor.actor_id, "monster_id": "frenzy_boar"}],
    )
    result = executor.execute(
        list(plan.actions),
        observer_actor_ids=[actor.actor_id],
        world_tick_ms=0,
    )
    final_view = result["observation"]["viewpoints"][actor.actor_id]
    assert len(final_view["encounters"]) == 1
    encounter = next(iter(final_view["encounters"].values()))
    assert encounter["active"] is True
    assert any(row["kind"] == "monster" for row in encounter["participants"].values())
