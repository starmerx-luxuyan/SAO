import pytest

from sao_mcp.corpus.floor6_ambush import GAS_MASK_ID, IRON_KEY_ID
from sao_mcp.corpus.floor6_finale import GOLDEN_CUBE_ID
from sao_mcp.corpus.floor6_stachion import GOLDEN_KEY_ID, POISON_JAR_ID, QUEST_ID, WITNESSES
from sao_mcp.corpus.floor6_trials import THEANO_IRON_KEY_ID
from sao_mcp.domain.models import CursorColor
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
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


def test_curse_of_stachion_release_route_reaches_floor6_boss_room_with_same_golden_cube():
    runtime = HousingAincradRuntime(seed=47)
    stachion = install_floor6_stachion_scenario(runtime)
    trials = install_floor6_trials_scenario(runtime)
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
    assert state["quest_progress"]["gather_old_household_testimony"] == 7

    runtime.travel_actor(player.actor_id, STACHION)
    runtime.travel_actor(player.actor_id, "floor_6_field")
    runtime.travel_actor(player.actor_id, SURIBUS)
    runtime.travel_actor(player.actor_id, PITHAGRUS_HOUSE)
    state = stachion.search_pithagrus_house(player.actor_id)
    key = next(item for item in player.inventory.values() if item.template_id == GOLDEN_KEY_ID)
    original_key_id = key.instance_id
    assert state["stage"] == "golden_key_obtained_capture_pending"
    assert state["has_golden_key"]
    assert state["ready_to_claim"] is False
    assert QUEST_ID not in runtime.quests.completed_by_actor[player.actor_id]

    state = stachion.trigger_cylon_capture(player.actor_id)
    cylon = runtime.actors[state["cylon_actor_id"]]
    encounter = runtime.encounters[state["transport_encounter_id"]]
    assert state["stage"] == "captured_transport_to_stachion"
    assert player.location_id == CYLON_TRANSPORT
    assert state["paralysed"]
    assert original_key_id not in player.inventory
    assert cylon.inventory[original_key_id].template_id == GOLDEN_KEY_ID
    assert cylon.inventory[original_key_id].owner_id == cylon.actor_id
    assert state["golden_key_owner_id"] == cylon.actor_id

    attack = runtime.attack(encounter.encounter_id, player.actor_id, cylon.actor_id, seed=1)
    assert not attack.legal
    assert attack.reason == "attacker is paralysis"
    with pytest.raises(ValueError, match="ordinary travel is unavailable during a live encounter"):
        runtime.travel_actor(player.actor_id, SURIBUS)

    state = stachion.advance_transport_to_ambush_site(player.actor_id)
    assert state["stage"] == "morte_joe_ambush_pending"
    state = stachion.trigger_morte_joe_ambush(player.actor_id)
    morte = runtime.actors[state["morte_actor_id"]]
    joe = runtime.actors[state["joe_actor_id"]]
    assert not cylon.alive
    assert state["stage"] == "ambush_cylon_dead"
    assert morte.actor_id in encounter.participants
    assert joe.actor_id in encounter.participants
    assert morte.actor_id in encounter.positions
    assert joe.actor_id in encounter.positions

    ground_templates = {row["template_id"] for row in state["ground_items"]}
    assert {GOLDEN_KEY_ID, IRON_KEY_ID, POISON_JAR_ID, GAS_MASK_ID}.issubset(ground_templates)
    ground_key = next(row for row in state["ground_items"] if row["instance_id"] == original_key_id)
    assert ground_key["owner_id"] is None

    state = stachion.topple_poison_jar(player.actor_id)
    assert state["stage"] == "poison_cloud_deployed"
    assert state["poison_cloud_active"]
    assert state["paralysed"]
    assert morte.metadata["avoiding_paralysis_cloud"] is True
    assert joe.metadata["avoiding_paralysis_cloud"] is True

    state = stachion.advance_to_paralysis_release(player.actor_id)
    assert state["stage"] == "morte_joe_pvp_active"
    assert not state["paralysed"]

    hostile_strike = runtime.attack(encounter.encounter_id, morte.actor_id, player.actor_id, seed=3)
    assert hostile_strike.legal
    assert morte.cursor is CursorColor.ORANGE
    counter = runtime.attack(encounter.encounter_id, player.actor_id, morte.actor_id, seed=4)
    assert counter.legal
    assert player.cursor is CursorColor.GREEN

    morte.hp = max(1, int(morte.max_hp * 0.20))
    morte.alive = True
    state = stachion.resolve_ambusher_retreat(player.actor_id)
    assert state["stage"] == "ambushers_neutralized_ground_loot"
    assert state["ambushers_neutralized"]
    assert morte.alive and joe.alive
    assert morte.metadata["retreated"] is True
    assert joe.metadata["retreated"] is True
    assert morte.actor_id not in encounter.participants
    assert joe.actor_id not in encounter.participants

    recovery = stachion.recover_cylon_ground_loot(player.actor_id)
    state = recovery["state"]
    assert state["stage"] == "post_ambush_loot_recovered"
    assert state["ground_items"] == []
    assert original_key_id in recovery["recovered_instance_ids"]
    assert player.inventory[original_key_id].template_id == GOLDEN_KEY_ID
    assert player.inventory[original_key_id].owner_id == player.actor_id
    recovered_templates = {player.inventory[item_id].template_id for item_id in recovery["recovered_instance_ids"]}
    assert {GOLDEN_KEY_ID, IRON_KEY_ID, POISON_JAR_ID, GAS_MASK_ID}.issubset(recovered_templates)

    runtime.travel_actor(player.actor_id, SURIBUS)
    runtime.travel_actor(player.actor_id, "floor_6_field")
    runtime.travel_actor(player.actor_id, STACHION)
    assert player.location_id == STACHION

    trial_state = trials.meet_myia(player.actor_id)
    myia = runtime.actors[trial_state["myia_actor_id"]]
    assert trial_state["stage"] == "myia_met_paired_keys"
    assert trial_state["myia_asks_player_to_keep_cylon_key"] is True
    assert any(item.template_id == THEANO_IRON_KEY_ID for item in myia.inventory.values())

    signal = trials.paired_iron_key_signal(player.actor_id)
    assert signal["route_hops"] == 0
    assert signal["resonance"] == "strong"
    assert signal["canon_mechanic"]["vibration_indicates_direction"] is True
    assert signal["canon_mechanic"]["sound_resonance_indicates_distance"] is True

    trial_state = trials.hear_theano_note(player.actor_id)
    assert trial_state["stage"] == "seek_barro_after_theano_note"
    runtime.travel_actor(player.actor_id, PUZZLE_QUARTER)
    signal = trials.paired_iron_key_signal(player.actor_id)
    assert signal["direction_next_location_id"] == STACHION
    assert signal["route_hops"] == 1

    trial_state = trials.consult_barro(player.actor_id)
    assert trial_state["stage"] == "seek_terro_at_manor"
    runtime.travel_actor(player.actor_id, STACHION)
    runtime.travel_actor(player.actor_id, CYLON_MANOR)
    trial_state = trials.consult_terro(player.actor_id)
    assert trial_state["stage"] == "secret_back_door_revealed"
    assert trial_state["secret_back_door_revealed"] is True

    assert "opened_dungeon_of_trials_main_entrance" not in player.inventory[original_key_id].metadata
    runtime.travel_actor(player.actor_id, DUNGEON_SECRET_BACK_DOOR)
    runtime.travel_actor(player.actor_id, DUNGEON_FINAL_CHAMBER)
    trial_state = trials.inspect_release_final_chamber(player.actor_id)
    assert trial_state["stage"] == "theano_golden_cube_missing"
    assert trial_state["final_chamber_checked"] is True
    assert trial_state["theano_missing_with_golden_cube"] is True
    assert trial_state["ready_to_claim"] is False
    assert trial_state["next_stage"] == "track Theano and the Golden Cube south"

    south_state = south.receive_south_sighting(player.actor_id)
    theano = runtime.actors[south_state["theano_actor_id"]]
    golden_cube_id = south_state["golden_cube_instance_id"]
    assert south_state["stage"] == "theano_sighted_goskai_caves"
    assert theano.inventory[golden_cube_id].template_id == GOLDEN_CUBE_ID

    runtime.travel_actor(player.actor_id, DUNGEON_SECRET_BACK_DOOR)
    runtime.travel_actor(player.actor_id, CYLON_MANOR)
    runtime.travel_actor(player.actor_id, STACHION)
    runtime.travel_actor(player.actor_id, "floor_6_field")
    runtime.travel_actor(player.actor_id, LAKE_TALPHA)
    runtime.travel_actor(player.actor_id, GOSKAI)
    runtime.travel_actor(player.actor_id, GOSKAI_CAVES)

    south_state = south.start_basalt_morpha_event(player.actor_id)
    basalt = runtime.actors[south_state["basalt_actor_id"]]
    basalt_encounter = runtime.encounters[south_state["basalt_encounter_id"]]
    assert south_state["stage"] == "basalt_morpha_battle"
    assert south_state["basalt_rock_armor_intact"] is True
    intact_armor = basalt.armor

    south_state = south.theano_break_basalt_armor(player.actor_id)
    assert south_state["stage"] == "basalt_morpha_armor_broken"
    assert south_state["basalt_rock_armor_intact"] is False
    assert basalt.armor < intact_armor
    assert theano.inventory[golden_cube_id].metadata["break_used_on_basalt_morpha"] is True

    # The Golden Cube changes defense state only. An ordinary combat attack performs the actual kill.
    basalt.hp = 1
    basalt.alive = True
    basalt_kill = runtime.attack(basalt_encounter.encounter_id, player.actor_id, basalt.actor_id, seed=1)
    assert basalt_kill.legal and basalt_kill.hit
    assert not basalt.alive

    south_state = south.continue_trail_to_murutsuki(player.actor_id)
    assert south_state["stage"] == "theano_passed_murutsuki"
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
