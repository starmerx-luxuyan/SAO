import pytest

from sao_mcp.corpus.floor6_ambush import GAS_MASK_ID, IRON_KEY_ID
from sao_mcp.corpus.floor6_elfwar import MEDITATION_SKILL_ID, SACRED_KEY_BAG_ID
from sao_mcp.corpus.floor6_finale import COMBINED_IRON_KEY_ID, GOLDEN_CUBE_ID
from sao_mcp.corpus.floor6_stachion import GOLDEN_KEY_ID, POISON_JAR_ID, QUEST_ID, WITNESSES
from sao_mcp.corpus.floor6_trials import THEANO_IRON_KEY_ID
from sao_mcp.domain.models import CursorColor
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor6_elfwar import (
    AGATE_SHRINE,
    CASTLE_GALEY,
    CASTLE_SPRING,
    QUSACK_RESCUE_CAVE,
    STORYTELLER_SUMMIT,
    install_floor6_elfwar_scenario,
)
from sao_mcp.scenarios.floor6_south import (
    BOSS_ROOM,
    GOSKAI,
    GOSKAI_CAVES,
    LABYRINTH,
    LABYRINTH_BREACH,
    LAKE_TALPHA,
    MURUTSUKI,
    install_floor6_south_scenario,
)
from sao_mcp.scenarios.floor6_stachion import (
    CYLON_MANOR,
    CYLON_TRANSPORT,
    PITHAGRUS_HOUSE,
    PUZZLE_QUARTER,
    STACHION,
    SURIBUS,
    install_floor6_stachion_scenario,
)
from sao_mcp.scenarios.floor6_trials import (
    DUNGEON_FINAL_CHAMBER,
    DUNGEON_SECRET_BACK_DOOR,
    install_floor6_trials_scenario,
)


def test_floor6_release_route_merges_stachion_elfwar_and_golden_cube_trail():
    runtime = HousingAincradRuntime(seed=47)
    stachion = install_floor6_stachion_scenario(runtime)
    trials = install_floor6_trials_scenario(runtime)
    elfwar = install_floor6_elfwar_scenario(runtime)
    south = install_floor6_south_scenario(runtime)
    player = runtime.create_character("StachionSolver", level=40)
    runtime.world.floors[6].unlocked = True
    player.location_id = CYLON_MANOR

    state = stachion.start_quest(player.actor_id)
    assert state["stage"] == "interview_old_associates"
    assert not state["ready_to_claim"]

    runtime.travel_actor(player.actor_id, PUZZLE_QUARTER)
    witness_ids = list(WITNESSES)
    for witness_id in witness_ids:
        state = stachion.interview_witness(player.actor_id, witness_id)
    assert state["witness_count"] == 7
    assert state["stage"] == "travel_to_suribus_second_home"
    assert state["quest_progress"]["gather_old_household_testimony"] == 7
    assert state["quest_progress"]["discover_suribus_second_home"] == 1
    state = stachion.interview_witness(player.actor_id, witness_ids[0])
    assert state["witness_count"] == 7

    runtime.travel_actor(player.actor_id, STACHION)
    runtime.travel_actor(player.actor_id, "floor_6_field")
    runtime.travel_actor(player.actor_id, SURIBUS)
    runtime.travel_actor(player.actor_id, PITHAGRUS_HOUSE)
    state = stachion.search_pithagrus_house(player.actor_id)
    golden_key = next(item for item in player.inventory.values() if item.template_id == GOLDEN_KEY_ID)
    original_golden_key_id = golden_key.instance_id
    assert state["stage"] == "golden_key_obtained_capture_pending"
    assert state["ready_to_claim"] is False

    state = stachion.trigger_cylon_capture(player.actor_id)
    cylon = runtime.actors[state["cylon_actor_id"]]
    encounter = runtime.encounters[state["transport_encounter_id"]]
    assert player.location_id == CYLON_TRANSPORT
    assert state["paralysed"]
    assert original_golden_key_id not in player.inventory
    assert cylon.inventory[original_golden_key_id].owner_id == cylon.actor_id

    attack = runtime.attack(encounter.encounter_id, player.actor_id, cylon.actor_id, seed=1)
    assert not attack.legal
    assert attack.reason == "attacker is paralysis"
    with pytest.raises(ValueError, match="ordinary travel is unavailable during a live encounter"):
        runtime.travel_actor(player.actor_id, SURIBUS)

    state = stachion.advance_transport_to_ambush_site(player.actor_id)
    assert state["stage"] == "ambush_cylon_dead"
    assert runtime.world_event_state(
        f"floor6.morte_joe_ambush:{player.actor_id}"
    )["status"] == "resolved"
    morte = runtime.actors[state["morte_actor_id"]]
    joe = runtime.actors[state["joe_actor_id"]]
    assert not cylon.alive
    ground_templates = {row["template_id"] for row in state["ground_items"]}
    assert {GOLDEN_KEY_ID, IRON_KEY_ID, POISON_JAR_ID, GAS_MASK_ID}.issubset(ground_templates)

    state = stachion.topple_poison_jar(player.actor_id)
    assert state["poison_cloud_active"] and state["paralysed"]
    state = stachion.wait_for_paralysis_release(player.actor_id)
    assert state["stage"] == "morte_joe_pvp_active"
    assert runtime.world_event_state(
        f"floor6.paralysis_release:{player.actor_id}"
    )["status"] == "resolved"
    assert not state["paralysed"]

    hostile_strike = runtime.attack(encounter.encounter_id, morte.actor_id, player.actor_id, seed=3)
    assert hostile_strike.legal
    assert morte.cursor is CursorColor.ORANGE
    counter = runtime.attack(encounter.encounter_id, player.actor_id, morte.actor_id, seed=4)
    assert counter.legal
    assert player.cursor is CursorColor.GREEN

    morte.hp = max(1, int(morte.max_hp * 0.20))
    morte.alive = True
    runtime.evaluate_world_events()
    state = stachion.status(player.actor_id)
    assert state["ambushers_neutralized"]
    assert runtime.world_event_state(
        f"floor6.ambusher_retreat:{player.actor_id}"
    )["status"] == "resolved"
    assert morte.metadata["retreated"] is True and joe.metadata["retreated"] is True

    recovery = stachion.recover_cylon_ground_loot(player.actor_id)
    assert original_golden_key_id in recovery["recovered_instance_ids"]
    recovered_templates = {player.inventory[item_id].template_id for item_id in recovery["recovered_instance_ids"]}
    assert {GOLDEN_KEY_ID, IRON_KEY_ID, POISON_JAR_ID, GAS_MASK_ID}.issubset(recovered_templates)
    cylon_iron_key = next(item for item in player.inventory.values() if item.template_id == IRON_KEY_ID)
    original_cylon_iron_key_id = cylon_iron_key.instance_id

    runtime.travel_actor(player.actor_id, SURIBUS)
    runtime.travel_actor(player.actor_id, "floor_6_field")
    runtime.travel_actor(player.actor_id, STACHION)
    trial_state = trials.meet_myia(player.actor_id)
    myia = runtime.actors[trial_state["myia_actor_id"]]
    theano_iron_key = next(item for item in myia.inventory.values() if item.template_id == THEANO_IRON_KEY_ID)
    original_theano_iron_key_id = theano_iron_key.instance_id

    signal = trials.paired_iron_key_signal(player.actor_id)
    assert signal["route_hops"] == 0 and signal["resonance"] == "strong"
    trials.hear_theano_note(player.actor_id)
    runtime.travel_actor(player.actor_id, PUZZLE_QUARTER)
    trial_state = trials.consult_barro(player.actor_id)
    assert trial_state["stage"] == "seek_terro_at_manor"
    runtime.travel_actor(player.actor_id, STACHION)
    runtime.travel_actor(player.actor_id, CYLON_MANOR)
    trial_state = trials.consult_terro(player.actor_id)
    assert trial_state["secret_back_door_revealed"] is True

    assert "opened_dungeon_of_trials_main_entrance" not in player.inventory[original_golden_key_id].metadata
    runtime.travel_actor(player.actor_id, DUNGEON_SECRET_BACK_DOOR)
    runtime.travel_actor(player.actor_id, DUNGEON_FINAL_CHAMBER)
    trial_state = trials.inspect_release_final_chamber(player.actor_id)
    assert trial_state["stage"] == "theano_golden_cube_missing"
    assert trial_state["theano_missing_with_golden_cube"] is True

    # The Elf War route now interlocks with the Stachion route before the southern pursuit.
    runtime.travel_actor(player.actor_id, DUNGEON_SECRET_BACK_DOOR)
    runtime.travel_actor(player.actor_id, CYLON_MANOR)
    runtime.travel_actor(player.actor_id, STACHION)
    runtime.travel_actor(player.actor_id, "floor_6_field")
    runtime.travel_actor(player.actor_id, CASTLE_GALEY)
    elf_state = elfwar.start_castle_galey_route(player.actor_id)
    assert elf_state["stage"] == "retrieve_agate_key"

    runtime.travel_actor(player.actor_id, LAKE_TALPHA)
    runtime.travel_actor(player.actor_id, AGATE_SHRINE)
    elf_state = elfwar.retrieve_agate_key(player.actor_id)
    assert elf_state["stage"] == "return_agate_key_to_castle"
    runtime.travel_actor(player.actor_id, LAKE_TALPHA)
    runtime.travel_actor(player.actor_id, CASTLE_GALEY)
    elf_state = elfwar.return_agate_key(player.actor_id)
    assert elf_state["agate_key_returned"] is True

    runtime.travel_actor(player.actor_id, STORYTELLER_SUMMIT)
    elf_state = elfwar.complete_bouhroum_trial(player.actor_id)
    assert elf_state["meditation_proficiency"] == 500.0
    assert elf_state["awakening_unlocked"] is True
    assert player.skill_proficiencies[MEDITATION_SKILL_ID] == 500.0
    runtime.travel_actor(player.actor_id, CASTLE_GALEY)

    elf_state = elfwar.trigger_castle_galey_attack(player.actor_id)
    assert elf_state["spirit_tree_poisoned"] is True
    assert elf_state["castle_weakness_active"] is True
    runtime.travel_actor(player.actor_id, CASTLE_SPRING)
    elf_state = elfwar.purify_spirit_tree_spring(player.actor_id)
    assert elf_state["spirit_tree_poisoned"] is False
    assert elf_state["castle_weakness_active"] is False
    runtime.travel_actor(player.actor_id, CASTLE_GALEY)

    elf_state = elfwar.borrow_sacred_key_bag(player.actor_id)
    sacred_bag_id = elf_state["sacred_key_bag_instance_id"]
    assert player.inventory[sacred_bag_id].template_id == SACRED_KEY_BAG_ID
    assert player.inventory[sacred_bag_id].metadata["sacred_key_count"] == 4
    runtime.travel_actor(player.actor_id, QUSACK_RESCUE_CAVE)
    elfwar.start_qusack_rescue(player.actor_id)
    elf_state = elfwar.trigger_kysarah_key_theft(player.actor_id)

    assert elf_state["stage"] == "kysarah_stole_and_combined_keys"
    assert original_cylon_iron_key_id not in player.inventory
    assert original_theano_iron_key_id not in myia.inventory
    combined_id = elf_state["combined_iron_key_instance_id"]
    kysarah = runtime.actors[elf_state["combined_iron_key_holder_id"]]
    combined = kysarah.inventory[combined_id]
    assert combined.template_id == COMBINED_IRON_KEY_ID
    assert set(combined.metadata["component_instance_ids"]) == {
        original_cylon_iron_key_id,
        original_theano_iron_key_id,
    }
    assert combined.metadata["repelling_charm_broken_by"] == "npc_floor6_kysarah"
    assert sacred_bag_id in kysarah.inventory
    assert kysarah.inventory[sacred_bag_id].template_id == SACRED_KEY_BAG_ID

    # Argo's southern sighting now begins after both Floor 6 quest lines have converged.
    south_state = south.receive_south_sighting(player.actor_id)
    theano = runtime.actors[south_state["theano_actor_id"]]
    golden_cube_id = south_state["golden_cube_instance_id"]
    assert theano.inventory[golden_cube_id].template_id == GOLDEN_CUBE_ID

    runtime.travel_actor(player.actor_id, CASTLE_GALEY)
    runtime.travel_actor(player.actor_id, LAKE_TALPHA)
    runtime.travel_actor(player.actor_id, GOSKAI)
    runtime.travel_actor(player.actor_id, GOSKAI_CAVES)
    south_state = south.start_basalt_morpha_event(player.actor_id)
    basalt = runtime.actors[south_state["basalt_actor_id"]]
    basalt_encounter = runtime.encounters[south_state["basalt_encounter_id"]]
    intact_armor = basalt.armor
    south_state = south.theano_break_basalt_armor(player.actor_id)
    assert basalt.armor < intact_armor
    assert theano.inventory[golden_cube_id].metadata["break_used_on_basalt_morpha"] is True

    basalt.hp = 1
    basalt.alive = True
    basalt_kill = runtime.attack(basalt_encounter.encounter_id, player.actor_id, basalt.actor_id, seed=1)
    assert basalt_kill.legal and basalt_kill.hit
    assert not basalt.alive
    south_state = south.continue_trail_to_murutsuki(player.actor_id)
    assert theano.location_id == MURUTSUKI
    assert south_state["golden_cube_instance_id"] == golden_cube_id

    runtime.travel_actor(player.actor_id, GOSKAI)
    runtime.travel_actor(player.actor_id, MURUTSUKI)
    runtime.travel_actor(player.actor_id, LABYRINTH)
    south_state = south.breach_labyrinth_with_golden_cube(player.actor_id)
    assert south_state["stage"] == "theano_reached_floor6_boss_room"
    assert theano.location_id == BOSS_ROOM
    assert theano.inventory[golden_cube_id].metadata["break_used_on_labyrinth_walls"] is True

    runtime.travel_actor(player.actor_id, LABYRINTH_BREACH)
    runtime.travel_actor(player.actor_id, BOSS_ROOM)
    assert player.location_id == BOSS_ROOM
    assert south.status(player.actor_id)["golden_cube_instance_id"] == golden_cube_id
    assert QUEST_ID not in runtime.quests.completed_by_actor[player.actor_id]
