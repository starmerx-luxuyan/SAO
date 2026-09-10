import pytest

from sao_mcp.rules.knowledge import EpistemicBasis
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


AGIL = "pc_agil"
AGIL_SHOP = "floor_50_agil_shop"
ALGADE = "floor_50_algade"


def test_beliefs_preserve_rumor_correction_history_and_survive_save_load():
    runtime = HousingAincradRuntime(seed=107)
    scout = runtime.create_character("Scout", level=10)
    listener = runtime.create_character("Listener", level=10)
    scout.location_id = "floor_1_town_of_beginnings"
    listener.location_id = scout.location_id

    fact_id = "floor1_boss_room:door_trapped"
    inferred = runtime.record_inference(scout.actor_id, fact_id, True, source_id="field_rumor")
    assert inferred.basis is EpistemicBasis.INFERRED

    reported = runtime.share_known_fact(scout.actor_id, listener.actor_id, fact_id)
    assert reported.basis is EpistemicBasis.REPORTED
    assert reported.value is True
    assert reported.source_id == scout.actor_id

    runtime.advance_world(1_000)
    corrected = runtime.record_observation(scout.actor_id, fact_id, False, source_id="direct_inspection")
    assert corrected.basis is EpistemicBasis.OBSERVED
    assert runtime.belief(scout.actor_id, fact_id).value is False
    assert runtime.belief(listener.actor_id, fact_id).value is True

    runtime.share_known_fact(scout.actor_id, listener.actor_id, fact_id)
    current = runtime.knowledge_state(listener.actor_id)
    assert current["facts"][fact_id]["value"] is False
    assert current["facts"][fact_id]["basis"] is EpistemicBasis.REPORTED

    listener_history = [
        event for event in runtime.knowledge_events
        if event.knower_id == listener.actor_id and event.fact_id == fact_id
    ]
    assert [event.value for event in listener_history] == [True, False]

    restored = import_runtime(export_runtime(runtime))
    assert restored.belief(listener.actor_id, fact_id).value is False
    restored_history = [
        event for event in restored.knowledge_events
        if event.knower_id == listener.actor_id and event.fact_id == fact_id
    ]
    assert [event.value for event in restored_history] == [True, False]
    assert [event.basis for event in restored_history] == [EpistemicBasis.REPORTED, EpistemicBasis.REPORTED]


def test_named_npc_knowledge_identity_survives_materialization_and_travel_blocks_reporting():
    runtime = HousingAincradRuntime(seed=109)
    runtime.world.floors[50].unlocked = True
    listener = runtime.create_character("Customer", level=10)
    listener.location_id = AGIL_SHOP

    fact_id = "algade_market:ore_shortage"
    runtime.record_inference(AGIL, fact_id, True, source_id="market_talk")
    assert runtime.belief(AGIL, fact_id).knower_id == AGIL

    agil_actor = runtime.create_character("Agil", level=30)
    agil_actor.metadata["npc_definition_id"] = AGIL
    agil_actor.location_id = AGIL_SHOP

    # Materialization changes the mechanical vessel, not the epistemic identity.
    assert runtime.belief(agil_actor.actor_id, fact_id).knower_id == AGIL
    first_report = runtime.share_known_fact(AGIL, listener.actor_id, fact_id)
    assert first_report.source_id == AGIL

    runtime.schedule_npc_travel(AGIL, ALGADE)
    assert runtime.npc_location_id(AGIL) is None
    with pytest.raises(ValueError, match="colocated conversation"):
        runtime.share_known_fact(AGIL, listener.actor_id, fact_id)

    runtime.advance_world(2 * 60_000)
    assert runtime.npc_location_id(AGIL) == ALGADE
    assert agil_actor.location_id == ALGADE
    assert runtime.belief(agil_actor.actor_id, fact_id).value is True

    agil_actor.hp = 0
    agil_actor.alive = False
    with pytest.raises(ValueError, match="cannot acquire new knowledge"):
        runtime.record_observation(AGIL, "algade_market:new_fact", True)
