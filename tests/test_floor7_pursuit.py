from sao_mcp.corpus.floor6_elfwar import KIZMEL_ID
from sao_mcp.corpus.floor7_pursuit import GREENLEAF_CAPE_ID, MAP_OF_SCYIA_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor7_aghyellr import KORLOY_STABLES, install_floor7_aghyellr_scenario
from sao_mcp.scenarios.floor7_pursuit import (
    ANT_VALLEY,
    CASINO,
    LABYRINTH_PURSUIT_TO_0400_MS,
    MAP_ACCEPT_DELAY_MS,
    MAP_CONFIRM_WAIT_MS,
    MAP_RESPONSE_MS,
    PLATEAU,
    REST_AND_APPROACH_MS,
    SAFEROOM,
    VALLEY_TO_LABYRINTH_MS,
    WAIT_FOR_FALLEN_DEPARTURE_MS,
    DRAGON_BONE_TO_VALLEY_MS,
    install_floor7_pursuit_scenario,
)


def test_scyia_blood_map_pursuit_reaches_saferoom_with_zero_keys_and_live_nirrnir_deadline():
    runtime = HousingAincradRuntime(seed=61)
    aghyellr = install_floor7_aghyellr_scenario(runtime)
    pursuit = install_floor7_pursuit_scenario(runtime)
    runtime.world.floors[7].unlocked = True

    lead = runtime.create_character("ScyiaLead", level=28)
    partner = runtime.create_character("ScyiaPartner", level=27)

    kizmel = CombatantState(
        actor_id="floor7_pursuit_kizmel",
        name="Kizmel",
        kind=EntityKind.NPC,
        level=43,
        max_hp=9000,
        hp=9000,
        strength=72,
        agility=70,
        armor=285,
        evasion=15,
        cursor=CursorColor.YELLOW,
        location_id=CASINO,
        metadata={
            "npc_definition_id": KIZMEL_ID,
            "harin_status": "fugitive_clearing_own_name",
            "must_recover_sacred_keys_to_clear_name": True,
        },
    )
    runtime.actors[kizmel.actor_id] = kizmel
    runtime.npcs.states[KIZMEL_ID].location_id = CASINO

    # Nirrnir is poisoned nine hours before the Scyia negotiation. The pursuit then consumes
    # another twenty-seven hours, leaving exactly twelve hours of the existing 48-hour deadline.
    lead.location_id = KORLOY_STABLES
    poison = aghyellr.trigger_nirrnir_poisoning(lead.actor_id)
    assert poison["remaining_ms"] == 48 * 60 * 60 * 1000
    runtime.advance_world(9 * 60 * 60 * 1000)

    lead.location_id = CASINO
    partner.location_id = CASINO
    negotiation_start = runtime.world.now_ms
    state = pursuit.negotiate_scyia_counteroffer(lead.actor_id, partner.actor_id)
    assert state["stage"] == "counteroffer_accepted_rest_and_depart"
    assert state["meeting_location_id"] == "floor_7_dragon_bone"
    assert state["meeting_time_clock"] == "07:00"

    map_item = next(item for item in lead.inventory.values() if item.template_id == MAP_OF_SCYIA_ID)
    assert map_item.metadata["proposed_time"] == "03:00"
    assert map_item.metadata["fallen_counteroffer_location_id"] == "floor_7_dragon_bone"
    assert map_item.metadata["fallen_counteroffer_time"] == "07:00"
    assert map_item.metadata["response_mark"] == "Y"
    assert map_item.metadata["counteroffer_accepted"] is True

    duel = runtime.duels.duels[state["duel_id"]]
    duel_encounter = runtime.encounters[state["duel_encounter_id"]]
    assert duel.status.value == "completed"
    assert duel.winner_id is None and duel.loser_id is None
    assert duel.completion_reason == "draw"
    assert duel_encounter.participants == {}
    assert not runtime._in_live_encounter(lead.actor_id)
    assert "authorized_duel_opponents" not in lead.metadata
    assert "authorized_duel_opponents" not in partner.metadata

    state = pursuit.rest_and_reach_dragon_bone_watch(state["instance_id"])
    cape = next(item for item in kizmel.inventory.values() if item.template_id == GREENLEAF_CAPE_ID)
    assert kizmel.metadata["arid_weakness_suppressed_by"] == cape.instance_id
    assert state["stage"] == "watching_dragon_bone_rendezvous"
    assert state["watch_hill_distance_yards"] == 300
    assert len(state["fallen_scout_ids"]) == 2
    assert all(runtime.actors[scout_id].location_id == "floor_7_dragon_bone" for scout_id in state["fallen_scout_ids"])

    state = pursuit.observe_fallen_departure(state["instance_id"])
    assert state["fallen_departure_clock"] == "07:05"
    state = pursuit.pursue_to_ant_tunnel_valley(state["instance_id"])
    assert lead.location_id == ANT_VALLEY
    assert state["tracks_visible_in_soft_ground"] is True
    assert state["hideout_found_in_valley"] is False

    state = pursuit.follow_through_valley_into_labyrinth(state["instance_id"])
    assert state["fallen_passed_valley_without_hideout"] is True
    assert state["fallen_passed_plateau"] is True
    assert runtime.world_map.locations[PLATEAU].floor_number == 7

    state = pursuit.pursue_until_saferoom(state["instance_id"])
    assert state["stage"] == "labyrinth_saferoom_no_keys"
    assert lead.location_id == SAFEROOM
    assert partner.location_id == SAFEROOM
    assert kizmel.location_id == SAFEROOM
    assert state["sacred_keys_recovered"] == 0
    assert state["fallen_hideout_found"] is False
    assert state["fallen_lost_in_labyrinth"] is True
    assert state["suspected_fallen_base_in_labyrinth"] is True
    assert all(runtime.actors[scout_id].metadata["lost_from_pursuers_after_monster_battles"] for scout_id in state["fallen_scout_ids"])

    expected_pursuit_elapsed = (
        MAP_RESPONSE_MS
        + MAP_ACCEPT_DELAY_MS
        + MAP_CONFIRM_WAIT_MS
        + REST_AND_APPROACH_MS
        + WAIT_FOR_FALLEN_DEPARTURE_MS
        + DRAGON_BONE_TO_VALLEY_MS
        + VALLEY_TO_LABYRINTH_MS
        + LABYRINTH_PURSUIT_TO_0400_MS
    )
    assert expected_pursuit_elapsed == 27 * 60 * 60 * 1000
    assert runtime.world.now_ms - negotiation_start == expected_pursuit_elapsed

    nirrnir = aghyellr.nirrnir_status()
    assert nirrnir["stage"] == "stabilised_silver_poison"
    assert nirrnir["remaining_ms"] == 12 * 60 * 60 * 1000
    assert state["nirrnir_remaining_ms"] == 12 * 60 * 60 * 1000
