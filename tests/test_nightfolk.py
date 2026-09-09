import random
from copy import deepcopy

from sao_mcp.corpus.floor7 import SWORD_OF_VOLUPTA_ID
from sao_mcp.domain.models import DefenseMode, ItemInstance
from sao_mcp.rules.combat import resolve_physical_attack
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.nightfolk import become_civis_nocte
from sao_mcp.rules.progression import experience_to_reach_level
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


def _give_doleful(runtime, actor, instance_id):
    template = runtime.catalog.weapons[SWORD_OF_VOLUPTA_ID]
    item = ItemInstance(
        instance_id=instance_id,
        template_id=SWORD_OF_VOLUPTA_ID,
        owner_id=actor.actor_id,
        durability=template.base_durability,
        max_durability=template.base_durability,
    )
    add_item(actor, item, runtime.catalog, allow_overweight=True)
    runtime.equip_item(actor.actor_id, item.instance_id)
    return item


def test_civis_nocte_combat_bonus_is_part_of_physical_resolution():
    runtime = HousingAincradRuntime(seed=1)
    attacker = runtime.create_character("NightCandidate", level=20)
    defender = runtime.create_character("Target", level=20)
    attacker.skill_proficiencies["one_hand_sword"] = 1000.0
    weapon_item, weapon = runtime._equipped_weapon(attacker)

    normal_actor = deepcopy(attacker)
    normal_item = normal_actor.inventory[normal_actor.equipment["weapon"]]
    civis_actor = deepcopy(attacker)
    civis_item = civis_actor.inventory[civis_actor.equipment["weapon"]]
    become_civis_nocte(civis_actor, master_actor_id="dominus_fixture", now_ms=0)

    normal = resolve_physical_attack(
        normal_actor,
        deepcopy(defender),
        normal_item,
        weapon,
        now_ms=0,
        rng=random.Random(1),
        defense=DefenseMode.NONE,
    )
    civis = resolve_physical_attack(
        civis_actor,
        deepcopy(defender),
        civis_item,
        weapon,
        now_ms=0,
        rng=random.Random(1),
        defense=DefenseMode.NONE,
    )

    assert normal.hit and civis.hit
    assert civis.hit_chance > normal.hit_chance
    assert civis.damage > normal.damage


def test_doleful_drains_only_accumulated_xp_from_non_night_wielder():
    runtime = HousingAincradRuntime(seed=11)
    actor = runtime.create_character("MortalWielder", level=20)
    actor.location_id = "floor_1_west_field"
    floor_xp = experience_to_reach_level(actor.level)
    actor.metadata["experience"] = floor_xp + 1000
    _give_doleful(runtime, actor, "doleful_mortal")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([actor.actor_id, monster.actor_id], zone_id="floor_1_west_field")

    result, _ = runtime.attack_authoritative(
        encounter.encounter_id,
        actor.actor_id,
        monster.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )

    assert result.legal
    assert actor.metadata["experience"] == floor_xp + 980
    soul_events = [event for event in encounter.events if event.event_type == "weapon_soul_cost"]
    assert soul_events[-1].payload["drained_experience"] == 20
    assert soul_events[-1].payload["level_floor_experience"] == floor_xp


def test_civis_nocte_is_exempt_from_doleful_xp_drain_and_regenerates_hp():
    runtime = HousingAincradRuntime(seed=13)
    actor = runtime.create_character("CivisWielder", level=20)
    actor.location_id = "floor_1_west_field"
    floor_xp = experience_to_reach_level(actor.level)
    actor.metadata["experience"] = floor_xp + 1000
    _give_doleful(runtime, actor, "doleful_civis")
    become_civis_nocte(actor, master_actor_id="dominus_fixture", now_ms=runtime.world.now_ms)
    actor.hp -= 500
    hp_before = actor.hp

    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([actor.actor_id, monster.actor_id], zone_id="floor_1_west_field")
    runtime.advance_encounter(encounter.encounter_id, 1000)
    assert actor.hp > hp_before

    xp_before = actor.metadata["experience"]
    result, _ = runtime.attack_authoritative(
        encounter.encounter_id,
        actor.actor_id,
        monster.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )
    assert result.legal
    assert actor.metadata["experience"] == xp_before
    soul_events = [event for event in encounter.events if event.event_type == "weapon_soul_cost"]
    assert soul_events[-1].payload["drained_experience"] == 0
    assert soul_events[-1].payload["exempt_by_night_rank"] is True


def test_civis_feeding_restores_hp_without_transforming_donor():
    runtime = HousingAincradRuntime(seed=17)
    civis = runtime.create_character("Civis", level=20)
    donor = runtime.create_character("Donor", level=20)
    civis.location_id = "floor_1_west_field"
    donor.location_id = "floor_1_west_field"
    become_civis_nocte(civis, master_actor_id="dominus_fixture", now_ms=0)
    civis.hp -= 500
    civis_before = civis.hp
    donor_before = donor.hp

    result = runtime.feed_civis_nocte(civis.actor_id, donor.actor_id, 100)

    assert result["hp_restored"] == 70
    assert civis.hp == civis_before + 70
    assert donor.hp == donor_before - 100
    assert donor.metadata.get("night_rank") is None
