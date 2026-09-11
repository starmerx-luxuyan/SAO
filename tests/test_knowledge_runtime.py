import pytest

from sao_mcp.rules.knowledge import EpistemicBasis
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


AGIL = "pc_agil"
AGIL_SHOP = "floor_50_agil_shop"
ALGADE = "floor_50_algade"
TOWN = "floor_1_town_of_beginnings"


def test_beliefs_preserve_rumor_correction_chain_and_survive_save_load():
    runtime = HousingAincradRuntime(seed=107)
    scout = runtime.create_character("Scout", level=10)
    listener = runtime.create_character("Listener", level=10)
    scout.location_id = TOWN
    listener.location_id = TOWN

    fact_id = "floor1_boss_room:door_trapped"
    rumor_fact = "rumor:floor1_boss_room_door_trapped"
    rumor = runtime.record_observation(
        scout.actor_id,
        rumor_fact,
        True,
        observation_location_id=TOWN,
        source_id="field_rumor",
        confidence=0.60,
    )
    inferred = runtime.record_inference(
        scout.actor_id,
        fact_id,
        True,
        evidence_fact_ids=[rumor_fact],
        source_id="scout_reasoning",
    )
    assert inferred.basis is EpistemicBasis.INFERRED
    assert inferred.evidence_event_ids == (rumor.event_id,)
    assert inferred.confidence == pytest.approx(0.48)

    reported = runtime.share_known_fact(scout.actor_id, listener.actor_id, fact_id)
    assert reported.basis is EpistemicBasis.REPORTED
    assert reported.value is True
    assert reported.source_id == scout.actor_id
    assert reported.evidence_event_ids == (inferred.event_id,)
    assert reported.transmission_depth == 1
    assert reported.confidence == pytest.approx(inferred.confidence * 0.85)

    runtime.advance_world(1_000)
    corrected = runtime.record_observation(
        scout.actor_id,
        fact_id,
        False,
        observation_location_id=TOWN,
        source_id="direct_inspection",
    )
    assert corrected.supersedes_event_id == inferred.event_id
    assert runtime.belief(scout.actor_id, fact_id).value is False
    assert runtime.belief(listener.actor_id, fact_id).value is True

    second_report = runtime.share_known_fact(scout.actor_id, listener.actor_id, fact_id)
    assert second_report.supersedes_event_id == reported.event_id
    current = runtime.knowledge_state(listener.actor_id)
    assert current["facts"][fact_id]["value"] is False
    assert current["facts"][fact_id]["basis"] is EpistemicBasis.REPORTED
    chain = runtime.knowledge_event_chain(second_report.event_id)
    assert [row["event_id"] for row in chain] == [corrected.event_id, second_report.event_id]

    restored = import_runtime(export_runtime(runtime))
    restored_belief = restored.belief(listener.actor_id, fact_id)
    assert restored_belief is not None
    assert restored_belief.value is False
    assert restored_belief.event_id == second_report.event_id
    restored_history = restored.knowledge_history(listener.actor_id, fact_id)
    assert [row["value"] for row in restored_history] == [True, False]
    assert restored_history[-1]["supersedes_event_id"] == reported.event_id


def test_direct_observation_requires_actual_location_and_inference_requires_known_evidence():
    runtime = HousingAincradRuntime(seed=108)
    runtime.world.floors[50].unlocked = True

    with pytest.raises(ValueError, match="observation_location_id"):
        runtime.record_observation(
            AGIL,
            "algade_market:ore_shortage",
            True,
            observation_location_id=ALGADE,
        )

    clue = runtime.record_observation(
        AGIL,
        "market_talk:ore_shortage_claim",
        True,
        observation_location_id=AGIL_SHOP,
        confidence=0.7,
    )
    with pytest.raises(ValueError, match="at least one evidence"):
        runtime.record_inference(AGIL, "algade_market:ore_shortage", True, evidence_fact_ids=[])
    with pytest.raises(ValueError, match="unknown or stale"):
        runtime.record_inference(
            AGIL,
            "algade_market:ore_shortage",
            True,
            evidence_fact_ids=["missing:evidence"],
        )
    inferred = runtime.record_inference(
        AGIL,
        "algade_market:ore_shortage",
        True,
        evidence_fact_ids=[clue.fact_id],
    )
    assert inferred.confidence == pytest.approx(0.56)


def test_stale_belief_disappears_from_current_state_and_stops_driving_npc_goal():
    runtime = HousingAincradRuntime(seed=109)
    npc_id = "npc_tutorial_instructor"
    fact_id = "field_orientation:route_open"
    runtime.set_npc_goal(
        npc_id,
        "use_verified_route",
        TOWN,
        required_fact_id=fact_id,
        required_fact_value=True,
    )
    assert runtime.npc_actor_core_state(npc_id)["current_goal_id"] is None

    observed = runtime.record_observation(
        npc_id,
        fact_id,
        True,
        observation_location_id=TOWN,
        expires_after_ms=100,
    )
    selected = runtime.npc_actor_core_state(npc_id)
    assert selected["current_goal_id"] == "use_verified_route"
    assert selected["decision_basis_event_ids"] == [observed.event_id]
    assert selected["decision_evidence"][observed.event_id]["stale"] is False

    runtime.advance_world(100)
    assert runtime.belief(npc_id, fact_id) is None
    state = runtime.knowledge_state(npc_id)
    assert fact_id not in state["facts"]
    assert state["stale_facts"][fact_id]["event_id"] == observed.event_id
    assert runtime.npc_actor_core_state(npc_id)["current_goal_id"] is None


def test_named_npc_epistemic_identity_survives_materialization_and_travel_blocks_reporting():
    runtime = HousingAincradRuntime(seed=110)
    runtime.world.floors[50].unlocked = True
    listener = runtime.create_character("Customer", level=10)
    listener.location_id = AGIL_SHOP

    clue = runtime.record_observation(
        AGIL,
        "market_talk:ore_shortage_claim",
        True,
        observation_location_id=AGIL_SHOP,
        source_id="market_talk",
        confidence=0.7,
    )
    fact_id = "algade_market:ore_shortage"
    runtime.record_inference(
        AGIL,
        fact_id,
        True,
        evidence_fact_ids=[clue.fact_id],
        source_id="merchant_judgment",
    )
    assert runtime.belief(AGIL, fact_id).knower_id == AGIL

    agil_actor = runtime.create_character("Agil", level=30)
    agil_actor.metadata["npc_definition_id"] = AGIL
    agil_actor.location_id = AGIL_SHOP

    assert runtime.belief(agil_actor.actor_id, fact_id).knower_id == AGIL
    first_report = runtime.share_known_fact(AGIL, listener.actor_id, fact_id)
    assert first_report.source_id == AGIL

    runtime.set_npc_goal(AGIL, "visit_algade_market", ALGADE)
    assert runtime.npc_location_id(AGIL) is None
    with pytest.raises(ValueError, match="colocated conversation"):
        runtime.share_known_fact(AGIL, listener.actor_id, fact_id)

    runtime.advance_world(2 * 60_000)
    assert runtime.npc_location_id(AGIL) == ALGADE
    assert agil_actor.location_id == ALGADE
    assert runtime.npc_agenda_state(AGIL)["goal_reached"] is True
    assert runtime.belief(agil_actor.actor_id, fact_id).value is True

    agil_actor.hp = 0
    agil_actor.alive = False
    with pytest.raises(ValueError, match="cannot acquire new knowledge"):
        runtime.record_observation(
            AGIL,
            "algade_market:new_fact",
            True,
            observation_location_id=ALGADE,
        )
