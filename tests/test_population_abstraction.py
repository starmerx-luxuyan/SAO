import pytest

from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime


TOWN = "floor_1_town_of_beginnings"
WEST_FIELD = "floor_1_west_field"
TOLBANA = "floor_1_tolbana"
URBUS = "floor_2_urbus"
MINUTE = 60_000


def test_population_cohorts_conserve_reclassification_reinforcement_and_losses():
    runtime = PopulationAincradRuntime(seed=503)
    named_player = runtime.create_character("NamedPlayer", level=7)
    runtime.add_population_cohort("frontline_main", "frontline", 120, WEST_FIELD, 8.0, "frontline_clearing")
    runtime.add_population_cohort("production_main", "production", 300, TOWN, 4.0, "crafting_and_trade")
    runtime.add_population_cohort("mid_tier_main", "mid_tier", 800, TOWN, 5.0, "leveling_and_material_hunting")
    runtime.add_population_cohort("casual_main", "casual", 1_800, TOWN, 2.0, "town_life_and_safe_hunting")

    initial = runtime.player_population_state()
    assert initial["abstract_registered_players"] == 3_020
    assert initial["abstract_living_players"] == 3_020
    assert initial["conservation_balance"] == 0
    assert initial["materialized_alive_players"] == 1
    assert initial["total_living_players_represented"] == 3_021

    runtime.reclassify_population_cohort(
        "mid_tier_main", "frontline", count=50, new_cohort_id="frontline_recruits", activity="frontline_training"
    )
    after_reclassification = runtime.player_population_state()
    assert after_reclassification["abstract_registered_players"] == 3_020
    assert after_reclassification["segment_totals"]["frontline"] == 170
    assert after_reclassification["segment_totals"]["mid_tier"] == 750

    runtime.reinforce_population_cohort("production_main", "casual_main", 20)
    after_reinforcement = runtime.player_population_state()
    assert after_reinforcement["abstract_registered_players"] == 3_020
    assert after_reinforcement["abstract_living_players"] == 3_020
    assert after_reinforcement["segment_totals"]["production"] == 280
    assert after_reinforcement["segment_totals"]["casual"] == 1_820

    runtime.apply_population_losses("frontline_recruits", 3, cause="field_combat")
    after_losses = runtime.player_population_state()
    assert after_losses["abstract_registered_players"] == 3_020
    assert after_losses["abstract_living_players"] == 3_017
    assert after_losses["abstract_cumulative_deaths"] == 3
    assert after_losses["conservation_balance"] == 0
    assert named_player.actor_id in runtime.actors

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, PopulationAincradRuntime)
    assert restored.player_population_state() == after_losses
    assert restored.population_history == runtime.population_history


def test_population_graph_movement_uses_exact_world_time_and_no_settled_location_in_transit():
    runtime = PopulationAincradRuntime(seed=509)
    runtime.add_population_cohort("frontline", "frontline", 40, TOWN, 7.0, "clearing")
    movement = runtime.schedule_population_movement("frontline", TOLBANA, reason="frontline_advance")
    assert movement is not None and movement.active
    assert movement.from_location_id == TOWN
    assert movement.next_location_id == WEST_FIELD
    assert runtime.population.cohorts["frontline"].location_id is None
    assert runtime.player_population_state()["abstract_in_transit_players"] == 40
    assert runtime.population_location_state(TOWN)["headcount"] == 0

    runtime.advance_world(12 * MINUTE)
    movement = runtime.population_movements["frontline"]
    assert movement.active
    assert movement.from_location_id == WEST_FIELD
    assert movement.next_location_id == TOLBANA
    assert movement.started_at_ms == 12 * MINUTE
    assert movement.due_at_ms == 54 * MINUTE
    assert runtime.population.cohorts["frontline"].location_id is None

    runtime.advance_world(42 * MINUTE)
    cohort = runtime.population.cohorts["frontline"]
    assert cohort.location_id == TOLBANA and cohort.floor_number == 1
    assert "frontline" not in runtime.population_movements
    assert runtime.population_location_state(TOLBANA)["headcount"] == 40
    completed = [row for row in runtime.population_history if row["event"] == "movement_leg_completed"]
    assert [(row["from_location_id"], row["to_location_id"], row["completed_at_ms"]) for row in completed] == [
        (TOWN, WEST_FIELD, 12 * MINUTE),
        (WEST_FIELD, TOLBANA, 54 * MINUTE),
    ]


def test_partial_population_migration_splits_without_creating_or_losing_players():
    runtime = PopulationAincradRuntime(seed=510)
    runtime.add_population_cohort("mid_pool", "mid_tier", 100, TOWN, 5.0, "leveling")
    runtime.schedule_population_movement(
        "mid_pool",
        WEST_FIELD,
        reason="field_training",
        count=30,
        new_cohort_id="field_detachment",
    )
    state = runtime.player_population_state()
    assert state["abstract_registered_players"] == 100
    assert state["abstract_living_players"] == 100
    assert runtime.population.cohorts["mid_pool"].headcount == 70
    assert runtime.population.cohorts["field_detachment"].headcount == 30
    assert runtime.population.cohorts["mid_pool"].location_id == TOWN
    assert runtime.population.cohorts["field_detachment"].location_id is None

    runtime.advance_world(12 * MINUTE)
    assert runtime.population.cohorts["field_detachment"].location_id == WEST_FIELD
    assert runtime.player_population_state()["conservation_balance"] == 0


def test_cross_floor_population_waits_for_real_gate_activation_then_transfers():
    runtime = PopulationAincradRuntime(seed=511)
    runtime.add_population_cohort("frontier", "frontline", 25, TOWN, 10.0, "next_floor_push")
    movement = runtime.schedule_population_movement("frontier", URBUS, reason="floor2_frontier")
    assert movement is not None and not movement.active
    assert movement.wait_reason == "target_floor_gate_inactive"
    assert runtime.population.cohorts["frontier"].location_id == TOWN
    waiting_state = runtime.player_population_state()
    assert waiting_state["abstract_waiting_movement_players"] == 25
    assert waiting_state["abstract_in_transit_players"] == 0
    assert runtime.population_location_state(TOWN)["headcount"] == 25
    assert runtime.population_floor_state(1)["headcount"] == 25

    runtime.floor_boss_defeated(1)
    runtime.advance_world(2 * 60 * MINUTE)
    cohort = runtime.population.cohorts["frontier"]
    assert runtime.world.floors[2].unlocked is True
    assert cohort.location_id == URBUS and cohort.floor_number == 2
    assert "frontier" not in runtime.population_movements
    gate_rows = [row for row in runtime.population_history if row["event"] == "movement_gate_transfer"]
    assert len(gate_rows) == 1
    assert gate_rows[0]["from_location_id"] == TOWN
    assert gate_rows[0]["to_location_id"] == URBUS
    assert gate_rows[0]["at_ms"] == 2 * 60 * MINUTE


def test_active_population_movement_round_trips_and_preserves_due_boundary():
    runtime = PopulationAincradRuntime(seed=512)
    runtime.add_population_cohort("travellers", "casual", 12, TOWN, 2.0, "relocation")
    runtime.schedule_population_movement("travellers", TOLBANA, reason="relocation")
    restored = import_runtime(export_runtime(runtime))
    movement = restored.population_movements["travellers"]
    assert movement.active and movement.due_at_ms == 12 * MINUTE
    assert restored.population.cohorts["travellers"].location_id is None
    restored.advance_world(12 * MINUTE)
    assert restored.population_movements["travellers"].from_location_id == WEST_FIELD
    assert restored.population.registered_total == 12


def test_population_location_and_floor_interfaces_are_background_only():
    runtime = PopulationAincradRuntime(seed=513)
    named = runtime.create_character("NamedGuildCandidate", level=5)
    runtime.add_population_cohort("producers", "production", 60, TOWN, 4.0, "market_supply")
    runtime.add_population_cohort("casuals", "casual", 140, TOWN, 2.0, "consumer_life")
    location = runtime.population_location_state(TOWN)
    assert location["headcount"] == 200
    assert location["segment_totals"]["production"] == 60
    assert location["segment_totals"]["casual"] == 140
    floor = runtime.population_floor_state(1)
    assert floor["headcount"] == 200
    assert named.actor_id not in location["cohort_ids"]
    assert runtime.player_population_state()["materialized_alive_players"] == 1


def test_population_cohorts_require_authoritative_world_locations_and_safe_splits():
    runtime = PopulationAincradRuntime(seed=514)
    with pytest.raises(KeyError):
        runtime.add_population_cohort("nowhere", "casual", 10, "not_a_world_location", 2.0, "idle")
    runtime.add_population_cohort("mid_tier_pool", "mid_tier", 20, TOWN, 4.0, "leveling")
    with pytest.raises(ValueError, match="new_cohort_id"):
        runtime.reclassify_population_cohort("mid_tier_pool", "frontline", count=5)
    assert runtime.player_population_state()["abstract_living_players"] == 20
