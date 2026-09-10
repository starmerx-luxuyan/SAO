import pytest

from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime


TOWN = "floor_1_town_of_beginnings"
WEST_FIELD = "floor_1_west_field"


def test_population_cohorts_conserve_reclassification_and_persist_losses():
    runtime = PopulationAincradRuntime(seed=503)
    named_player = runtime.create_character("NamedPlayer", level=7)

    runtime.add_population_cohort(
        "frontline_main",
        "frontline",
        120,
        WEST_FIELD,
        8.0,
        "frontline_clearing",
    )
    runtime.add_population_cohort(
        "production_main",
        "production",
        300,
        TOWN,
        4.0,
        "crafting_and_trade",
    )
    runtime.add_population_cohort(
        "mid_tier_main",
        "mid_tier",
        800,
        TOWN,
        5.0,
        "leveling_and_material_hunting",
    )
    runtime.add_population_cohort(
        "casual_main",
        "casual",
        1_800,
        TOWN,
        2.0,
        "town_life_and_safe_hunting",
    )

    initial = runtime.player_population_state()
    assert initial["abstract_living_players"] == 3_020
    assert initial["materialized_alive_players"] == 1
    assert initial["total_living_players_represented"] == 3_021
    assert initial["segment_totals"] == {
        "frontline": 120,
        "production": 300,
        "mid_tier": 800,
        "casual": 1_800,
    }

    runtime.reclassify_population_cohort(
        "mid_tier_main",
        "frontline",
        count=50,
        new_cohort_id="frontline_recruits",
        activity="frontline_training",
    )
    after_reclassification = runtime.player_population_state()
    assert after_reclassification["abstract_living_players"] == 3_020
    assert after_reclassification["segment_totals"]["frontline"] == 170
    assert after_reclassification["segment_totals"]["mid_tier"] == 750
    assert after_reclassification["cohorts"]["frontline_recruits"]["headcount"] == 50

    runtime.apply_population_losses(
        "frontline_recruits",
        3,
        cause="field_combat",
    )
    after_losses = runtime.player_population_state()
    assert after_losses["abstract_living_players"] == 3_017
    assert after_losses["abstract_cumulative_deaths"] == 3
    assert after_losses["cohorts"]["frontline_recruits"]["headcount"] == 47
    assert after_losses["materialized_alive_players"] == 1
    assert named_player.actor_id in runtime.actors

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, PopulationAincradRuntime)
    restored_state = restored.player_population_state()
    assert restored_state == after_losses
    assert restored.population_history == runtime.population_history


def test_population_cohorts_require_authoritative_world_locations_and_safe_splits():
    runtime = PopulationAincradRuntime(seed=509)

    with pytest.raises(KeyError):
        runtime.add_population_cohort(
            "nowhere",
            "casual",
            10,
            "not_a_world_location",
            2.0,
            "idle",
        )

    runtime.add_population_cohort(
        "mid_tier_pool",
        "mid_tier",
        20,
        TOWN,
        4.0,
        "leveling",
    )
    with pytest.raises(ValueError, match="new_cohort_id"):
        runtime.reclassify_population_cohort(
            "mid_tier_pool",
            "frontline",
            count=5,
        )

    assert runtime.player_population_state()["abstract_living_players"] == 20
