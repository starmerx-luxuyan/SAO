from __future__ import annotations

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
    WeaponClass,
    WeaponTemplate,
)
from sao_mcp.rules.progression import gain_skill_proficiency
from sao_mcp.rules.progression_effects import normal_attack_modifiers, refresh_weapon_enhancement_caps, weapon_proficiency_key
from sao_mcp.runtime.character_setup import begin_campaign_setup, configure_character, grant_character_item
from sao_mcp.runtime.custom_catalog import (
    register_custom_armor,
    register_custom_consumable,
    register_custom_item,
    register_custom_skill,
    register_custom_weapon,
)
from sao_mcp.runtime.gm_observation import GMObservationGate
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


VARIANT = Provenance(ProvenanceKind.OPTIONAL_VARIANT)


def make_runtime():
    return SocialCommunicationAincradRuntime(seed=0xA1C0)


def install_star_skills(runtime):
    register_custom_skill(runtime, SkillDefinition("star_sword", "星辰剑", SkillKind.UNIQUE, provenance=VARIANT))
    register_custom_skill(runtime, SkillDefinition("star_awakened", "星辰剑·解放", SkillKind.UNIQUE, provenance=VARIANT))


def star_mechanics():
    return [
        {
            "mechanic_id": "star_growth",
            "name": "星辰剑成长",
            "effects": [{"type": "level_attribute_growth", "strength_per_level": 1, "agility_per_level": 1, "from_level": 1}],
        },
        {
            "mechanic_id": "star_proficiency",
            "name": "星辰剑熟练度",
            "effects": [
                {"type": "weapon_proficiency_route", "weapon_class": "one_hand_sword", "skill_id": "star_sword"},
                {"type": "proficiency_gain_modifier", "skill_id": "star_sword", "multiplier": 2.0},
                {"type": "skill_unlock", "watch_skill_id": "star_sword", "min_proficiency": 240, "skill_id": "star_awakened"},
            ],
        },
        {
            "mechanic_id": "star_weapon",
            "name": "星辰剑武器成长",
            "effects": [{
                "type": "weapon_enhancement_cap_curve",
                "weapon_class": "one_hand_sword",
                "skill_id": "star_sword",
                "thresholds": [[50, 1], [150, 2], [550, 6], [950, 10]],
            }],
        },
        {
            "mechanic_id": "star_normal_attack",
            "name": "剑技限制解除",
            "effects": [{
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
            }],
        },
    ]


def test_custom_item_templates_enter_the_normal_runtime_and_roundtrip():
    rt = make_runtime()
    begin_campaign_setup(rt)
    register_custom_weapon(rt, WeaponTemplate(
        template_id="star_blade", name="星锋", kind=ItemKind.WEAPON,
        weapon_class=WeaponClass.ONE_HAND_SWORD, damage_type=DamageType.SLASH,
        attack_min=31, attack_max=37, required_level=1, required_strength=5,
        weight=12, base_durability=333, base_speed_ms=610, reach_m=1.6, provenance=VARIANT,
    ))
    register_custom_armor(rt, ArmorTemplate(
        template_id="star_guard", name="星盾", kind=ItemKind.SHIELD,
        armor=17, slot="offhand", weight=7, base_durability=200, provenance=VARIANT,
    ))
    register_custom_consumable(rt, ConsumableTemplate(
        template_id="star_full_heal", name="星露", kind=ItemKind.CONSUMABLE,
        effect=ConsumableEffect.HEAL_FULL, stack_limit=5, provenance=VARIANT,
    ))
    register_custom_item(rt, ItemTemplate(
        template_id="star_shard", name="星屑", kind=ItemKind.MATERIAL,
        weight=0.1, stack_limit=99, provenance=VARIANT,
    ))

    actor = rt.create_character("Custom", level=5, starter_weapon_id="star_blade")
    shield = grant_character_item(rt, actor.actor_id, "star_guard", equip_now=True, allow_overweight=True)
    heal = grant_character_item(rt, actor.actor_id, "star_full_heal", quantity=2, allow_overweight=True)
    grant_character_item(rt, actor.actor_id, "star_shard", quantity=12, allow_overweight=True)
    assert actor.equipment["weapon"] in actor.inventory
    assert actor.equipment["offhand"] == shield.instance_id
    assert actor.armor >= 17
    actor.hp = 1
    rt.use_inventory_item(actor.actor_id, heal.instance_id)
    assert actor.hp == actor.max_hp

    restored = make_runtime()
    import_runtime(export_runtime(rt), into=restored)
    assert restored.catalog.weapons["star_blade"].attack_max == 37
    assert restored.catalog.armors["star_guard"].slot == "offhand"
    assert restored.catalog.consumables["star_full_heal"].effect is ConsumableEffect.HEAL_FULL
    assert restored.catalog.items["star_shard"].stack_limit == 99


def test_custom_teleport_consumable_is_observable_and_usable():
    rt = make_runtime()
    begin_campaign_setup(rt)
    register_custom_consumable(rt, ConsumableTemplate(
        template_id="star_gate_crystal", name="星门水晶", kind=ItemKind.CONSUMABLE,
        effect=ConsumableEffect.TELEPORT, stack_limit=3, provenance=VARIANT,
    ))
    actor = rt.create_character("Traveler", level=3)
    crystal = grant_character_item(rt, actor.actor_id, "star_gate_crystal", quantity=1, allow_overweight=True)
    rt.travel_actor(actor.actor_id, "floor_1_west_field")
    caps = GMObservationGate(rt).observe([actor.actor_id])["viewpoints"][actor.actor_id]["capabilities"]
    assert crystal.instance_id in caps["teleport_crystal_instance_ids"]
    rt.teleport_actor(actor.actor_id, crystal.instance_id, "floor_1_town_of_beginnings")
    assert actor.location_id == "floor_1_town_of_beginnings"


def test_declarative_mechanics_drive_growth_routing_caps_attack_and_unlocks():
    rt = make_runtime()
    begin_campaign_setup(rt)
    install_star_skills(rt)
    actor = rt.create_character("景明", level=7)
    configure_character(
        rt, actor.actor_id,
        skill_proficiencies={"star_sword": 238.0},
        equipped_skills=["star_sword", "searching"],
        unlocked_special_skills=["star_sword"],
        custom_mechanics=star_mechanics(),
    )
    assert (actor.strength, actor.agility) == (28, 28)
    assert weapon_proficiency_key(actor, WeaponClass.ONE_HAND_SWORD) == "star_sword"

    sword = grant_character_item(rt, actor.actor_id, "anneal_blade", max_enhancement_attempts=8, allow_overweight=True)
    assert sword.max_enhancement_attempts == 10
    actor.skill_proficiencies["star_sword"] = 501.0
    refresh_weapon_enhancement_caps(actor, rt.catalog)
    damage, recovery = normal_attack_modifiers(actor, WeaponClass.ONE_HAND_SWORD)
    assert damage > 1.15
    assert 0.80 < recovery <= 0.90

    actor.skill_proficiencies["star_sword"] = 239.5
    gained = gain_skill_proficiency(actor, "star_sword", 1.0, catalog=rt.catalog)
    assert gained > 1.0
    assert actor.skill_proficiencies["star_sword"] >= 240.0
    assert "star_awakened" in actor.metadata["unlocked_special_skills"]


def test_custom_mechanics_can_be_replaced_without_level_growth_drift_and_persist():
    rt = make_runtime()
    begin_campaign_setup(rt)
    install_star_skills(rt)
    actor = rt.create_character("Growth", level=7)
    configure_character(rt, actor.actor_id, custom_mechanics=star_mechanics())
    assert (actor.strength, actor.agility) == (28, 28)
    stronger = star_mechanics()
    stronger[0]["effects"][0]["strength_per_level"] = 2
    configure_character(rt, actor.actor_id, custom_mechanics=stronger)
    assert (actor.strength, actor.agility) == (34, 28)

    restored = make_runtime()
    import_runtime(export_runtime(rt), into=restored)
    restored_actor = restored.actors[actor.actor_id]
    assert restored_actor.metadata["custom_mechanics"][0]["mechanic_id"] == "star_growth"
    assert (restored_actor.strength, restored_actor.agility) == (34, 28)
