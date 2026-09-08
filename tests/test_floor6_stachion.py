import pytest

from sao_mcp.corpus.floor6_stachion import GOLDEN_KEY_ID, QUEST_ID, WITNESSES
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor6_stachion import (
    CYLON_MANOR,
    CYLON_TRANSPORT,
    PITHAGRUS_HOUSE,
    PUZZLE_QUARTER,
    STACHION,
    SURIBUS,
    install_floor6_stachion_scenario,
)


def test_curse_of_stachion_reaches_scripted_capture_with_real_key_ownership_and_paralysis():
    runtime = HousingAincradRuntime(seed=47)
    stachion = install_floor6_stachion_scenario(runtime)
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

    # Re-interviewing the same witness must not double-count the seven-person investigation.
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
    assert state["paralysed"]
    assert state["next_canon_stage"] == "Morte and Joe ambush Cylon's carriage"
    assert state["ready_to_claim"] is False
