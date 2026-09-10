from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def test_population_cohorts_conserve_players_through_split_materialization_losses_and_travel():
    runtime = HousingAincradRuntime(seed=409)
    executor = GMTurnExecutor(runtime)
    materialized = runtime.create_character("KnownPlayer", level=9)

    initialized = executor.execute(
        [
            {
                "op": "initialize_population",
                "cohorts": [
                    {
                        "cohort_id": "background",
                        "band": "unclassified",
                        "count": 100,
                        "location_id": "floor_1_town_of_beginnings",
                        "provenance_kind": "simulation",
                    }
                ],
            }
        ]
    )
    assert initialized["population"]["initial_population_total"] == 100
    assert initialized["population"]["abstract_alive"] == 100

    changed = executor.execute(
        [
            {
                "op": "split_population_cohort",
                "cohort_id": "background",
                "new_cohort_id": "frontline",
                "count": 20,
                "band": "frontline",
            },
            {
                "op": "materialize_population_member",
                "cohort_id": "background",
                "actor_id": materialized.actor_id,
            },
            {
                "op": "apply_population_losses",
                "cohort_id": "background",
                "deaths": 3,
                "cause": "simulation early-game attrition",
            },
            {
                "op": "schedule_population_travel",
                "cohort_id": "frontline",
                "destination_id": "floor_1_tolbana",
            },
        ]
    )

    population = changed["population"]
    assert population["abstract_alive"] == 96
    assert population["abstract_deaths"] == 3
    assert population["materialized_from_population"] == 1
    assert population["materialized_from_population_alive"] == 1
    assert materialized.metadata["population_origin_cohort_id"] == "background"
    assert population["cohorts"]["frontline"]["active"] is True
    assert population["cohorts"]["frontline"]["location_id"] is None
    assert population["cohorts"]["frontline"]["next_location_id"] == "floor_1_west_field"

    restored = import_runtime(export_runtime(runtime))
    restored_population = restored.population_state()
    assert restored_population["abstract_alive"] == 96
    assert restored_population["abstract_deaths"] == 3
    assert restored_population["materialized_from_population"] == 1
    assert restored.population_cohort_state("frontline")["next_location_id"] == "floor_1_west_field"

    restored.advance_world(12 * 60_000)
    second_leg = restored.population_cohort_state("frontline")
    assert second_leg["active"] is True
    assert second_leg["from_location_id"] == "floor_1_west_field"
    assert second_leg["next_location_id"] == "floor_1_tolbana"

    restored.advance_world(42 * 60_000)
    reached = restored.population_cohort_state("frontline")
    assert reached["active"] is False
    assert reached["location_id"] == "floor_1_tolbana"
    assert reached["movement_target_location_id"] is None

    completed = [
        row
        for row in restored.population_history
        if row["event"] == "population_travel_leg_completed" and row["cohort_id"] == "frontline"
    ]
    assert [(row["from_location_id"], row["to_location_id"]) for row in completed] == [
        ("floor_1_town_of_beginnings", "floor_1_west_field"),
        ("floor_1_west_field", "floor_1_tolbana"),
    ]

    final = restored.population_state()
    assert final["abstract_alive"] + final["abstract_deaths"] + final["materialized_from_population"] == 100
