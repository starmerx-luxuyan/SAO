from __future__ import annotations

import pytest

from sao_mcp.rules.group_travel import escorted_travel_together
from sao_mcp.rules.live_state import assert_runtime_live_state
from sao_mcp.rules.transport import authorized_transport
from sao_mcp.runtime.engine import GameRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime


def test_encounter_world_clock_uses_state_anchor_not_event_payload():
    runtime = GameRuntime(seed=701)
    runtime.advance_world(1_234)
    player = runtime.create_character("Clock")
    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id

    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    assert encounter.world_started_at_ms == 1_234
    assert runtime.encounter_world_time_ms(encounter.encounter_id) == 1_234

    encounter.events[0].payload["world_started_at_ms"] = 999_999_999
    assert runtime.encounter_world_time_ms(encounter.encounter_id) == 1_234

    runtime.advance_encounter(encounter.encounter_id, 250)
    assert encounter.time_ms == 250
    assert runtime.encounter_world_time_ms(encounter.encounter_id) == 1_484
    assert runtime.world.now_ms == 1_484


def test_actor_cannot_exist_in_two_active_encounters():
    runtime = GameRuntime(seed=702)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    c = runtime.create_character("C")
    b.location_id = a.location_id
    c.location_id = a.location_id
    first = runtime.start_encounter([a.actor_id, b.actor_id])

    with pytest.raises(ValueError, match="already in active encounter"):
        runtime.start_encounter([a.actor_id, c.actor_id])

    runtime.end_encounter(first.encounter_id, reason="test_complete")
    second = runtime.start_encounter([a.actor_id, c.actor_id])
    assert second.active is True


def test_live_state_gate_rejects_active_participant_location_drift():
    runtime = GameRuntime(seed=703)
    player = runtime.create_character("Drift")
    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])

    player.location_id = "floor_1_town_of_beginnings"
    with pytest.raises(RuntimeError, match="active encounter participant"):
        assert_runtime_live_state(runtime)

    player.location_id = encounter.zone_id
    assert_runtime_live_state(runtime)


def test_custody_blocks_autonomous_travel_but_allows_explicit_escort_and_persists():
    runtime = PopulationAincradRuntime(seed=704)
    detainee = runtime.create_character("Detainee")
    escort = runtime.create_character("Escort")
    case_id = "test_case_704"
    runtime.take_actor_custody(
        detainee.actor_id,
        custody_id="custody_test_704",
        authority_id=escort.actor_id,
        case_id=case_id,
        restriction_code="test_custody",
        reason="authority_test",
    )

    with pytest.raises(ValueError, match="restricted by test_custody"):
        runtime.travel_actor(detainee.actor_id, "floor_1_west_field")

    moved = escorted_travel_together(
        runtime,
        [detainee.actor_id],
        [escort.actor_id],
        "floor_1_west_field",
    )
    assert moved.to_location_id == "floor_1_west_field"
    assert runtime.actors[detainee.actor_id].location_id == "floor_1_west_field"
    assert runtime.actor_custody_state(detainee.actor_id)["case_id"] == case_id

    restored = import_runtime(export_runtime(runtime))
    assert restored.actor_custody_state(detainee.actor_id)["restriction_code"] == "test_custody"
    assert restored.actors[detainee.actor_id].location_id == "floor_1_west_field"

    sentence = restored.issue_sentence_order(
        detainee.actor_id,
        sentence_id="sentence_test_704",
        case_id=case_id,
        authority_id=escort.actor_id,
        kind="imprisonment",
    )
    assert sentence.status.value == "ordered"
    active = restored.begin_imprisonment_sentence(detainee.actor_id, duration_ms=1_000)
    assert active.status.value == "active"
    assert active.release_at_ms == restored.world.now_ms + 1_000

    restored.advance_world(1_000)
    restored.complete_imprisonment_sentence(
        detainee.actor_id, resolution="term_completed"
    )
    assert restored.actor_custody_state(detainee.actor_id) is None
    assert restored.actor_sentence_state(detainee.actor_id) is None

    final = import_runtime(export_runtime(restored))
    assert final.actor_custody_state(detainee.actor_id) is None
    assert final.actor_sentence_state(detainee.actor_id) is None
    assert any(row.get("event") == "imprisonment_completed" for row in final.legal.history)
    assert any(row.get("event") == "custody_released" for row in final.legal.history)


def test_npc_active_route_supersedes_old_settled_location_for_transport_decisions():
    runtime = PopulationAincradRuntime(seed=705)
    npc_id = "npc_tutorial_instructor"
    origin = runtime.npcs.states[npc_id].location_id
    agenda = runtime.schedule_npc_travel(npc_id, "floor_1_west_field")

    assert agenda.active is True
    assert runtime.npc_location_id(npc_id) is None
    assert runtime.npcs.states[npc_id].location_id == origin

    with pytest.raises(ValueError, match="NPCs are not all at the required origin"):
        authorized_transport(
            runtime,
            transport_id="illegal_parallel_transport",
            actor_ids=(),
            npc_ids=(npc_id,),
            carrier_actor_id=None,
            from_location_id=origin,
            to_location_id="floor_1_west_field",
            elapsed_ms=1_000,
        )
