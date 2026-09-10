import pytest

from sao_mcp.corpus.world import LocationDefinition
from sao_mcp.domain.models import ZoneKind
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime


TOWN = "floor_1_town_of_beginnings"
WEST_FIELD = "floor_1_west_field"
TOLBANA = "floor_1_tolbana"


def _initialize(runtime: PopulationAincradRuntime) -> None:
    runtime.initialize_player_population(
        [
            {
                "cohort_id": "background",
                "band": "unclassified",
                "count": 100,
                "location_id": TOWN,
                "average_level": 3.0,
                "activity": "early_game_adaptation",
                "provenance_kind": "simulation",
            }
        ]
    )


def test_population_conserves_people_through_materialization_losses_and_inflight_persistence():
    runtime = PopulationAincradRuntime(seed=503)
    _initialize(runtime)
    named_player = runtime.create_character("NamedPlayer", level=7)

    before_claim = runtime.population_state()
    assert before_claim["initial_population_total"] == 100
    assert before_claim["abstract_alive"] == 100
    assert before_claim["untracked_materialized_player_actor_ids"] == [named_player.actor_id]

    runtime.split_population_cohort(
        "background",
        "frontline",
        20,
        band="frontline",
        activity="frontline_clearing",
        average_level=7.0,
    )
    runtime.materialize_population_member("background", named_player.actor_id)
    runtime.apply_population_losses(
        "background",
        3,
        cause="simulation early-game attrition",
    )
    runtime.schedule_population_travel("frontline", TOLBANA)

    active = runtime.population_state()
    assert active["abstract_alive"] == 96
    assert active["abstract_deaths"] == 3
    assert active["materialized_from_population"] == 1
    assert active["represented_living"] == 97
    assert active["represented_deaths"] == 3
    assert active["untracked_materialized_player_actor_ids"] == []
    assert active["band_totals"]["frontline"] == 20
    assert active["cohorts"]["frontline"]["location_id"] is None
    assert active["cohorts"]["frontline"]["from_location_id"] == TOWN
    assert active["cohorts"]["frontline"]["next_location_id"] == WEST_FIELD

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, PopulationAincradRuntime)
    restored_state = restored.population_state()
    assert restored_state["abstract_alive"] == 96
    assert restored_state["abstract_deaths"] == 3
    assert restored_state["materialized_from_population"] == 1
    assert restored.population_cohort_state("frontline")["next_location_id"] == WEST_FIELD

    restored.advance_world(12 * 60_000)
    second_leg = restored.population_cohort_state("frontline")
    assert second_leg["active"] is True
    assert second_leg["from_location_id"] == WEST_FIELD
    assert second_leg["next_location_id"] == TOLBANA

    restored.advance_world(42 * 60_000)
    reached = restored.population_cohort_state("frontline")
    assert reached["active"] is False
    assert reached["location_id"] == TOLBANA
    assert reached["floor_number"] == 1

    legs = [
        row
        for row in restored.population_history
        if row["event"] == "population_travel_leg_completed"
        and row["cohort_id"] == "frontline"
    ]
    assert [(row["from_location_id"], row["to_location_id"]) for row in legs] == [
        (TOWN, WEST_FIELD),
        (WEST_FIELD, TOLBANA),
    ]

    restored.actors[named_player.actor_id].alive = False
    restored.actors[named_player.actor_id].hp = 0
    final = restored.population_state()
    assert final["represented_living"] == 96
    assert final["represented_deaths"] == 4
    assert (
        final["abstract_alive"]
        + final["abstract_deaths"]
        + final["materialized_from_population"]
        == 100
    )


def test_population_rejects_arbitrary_addition_and_preflights_unreachable_routes():
    runtime = PopulationAincradRuntime(seed=509)
    _initialize(runtime)

    assert not hasattr(runtime, "add_population_cohort")
    with pytest.raises(ValueError, match="already been initialized"):
        _initialize(runtime)

    isolated = "floor_1_population_isolated_test_node"
    runtime.world_map.locations[isolated] = LocationDefinition(
        isolated,
        1,
        "Population Isolated Test Node",
        ZoneKind.FIELD,
    )
    history_before = list(runtime.population_history)
    cohort_before = runtime.population_cohort_state("background")

    with pytest.raises(ValueError, match="unreachable"):
        runtime.schedule_population_travel("background", isolated)

    assert runtime.population_cohort_state("background") == cohort_before
    assert runtime.population_history == history_before


def test_population_split_and_role_change_preserve_total():
    runtime = PopulationAincradRuntime(seed=511)
    _initialize(runtime)

    production = runtime.split_population_cohort(
        "background",
        "production",
        30,
        band="production",
        activity="crafting_and_trade",
        average_level=4.5,
    )
    assert production.count == 30
    assert production.average_level == 4.5
    assert runtime.population_state()["abstract_alive"] == 100

    runtime.set_population_cohort_role(
        "production",
        "mid_tier",
        activity="material_hunting",
        average_level=5.0,
    )
    state = runtime.population_state()
    assert state["cohorts"]["production"]["band"] == "mid_tier"
    assert state["cohorts"]["production"]["activity"] == "material_hunting"
    assert state["abstract_alive"] == 100
    assert state["abstract_deaths"] == 0
