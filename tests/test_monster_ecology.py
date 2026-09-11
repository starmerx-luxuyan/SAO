import pytest

from sao_mcp.rules.monster_ecology import ECOLOGY_TICK_MS
from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


WEST = "floor_1_west_field"
TOWN = "floor_1_town_of_beginnings"
SCUTTLE = "floor_4_labyrinth"


def _unlock_through_floor(runtime: MonsterEcologyAincradRuntime, target_floor: int) -> None:
    for floor_number in range(1, target_floor):
        runtime.floor_boss_defeated(floor_number)
        runtime.advance_world(2 * ECOLOGY_TICK_MS)
        assert runtime.world.floors[floor_number + 1].unlocked


def test_player_arrival_materializes_wild_presence_without_manual_spawn():
    runtime = MonsterEcologyAincradRuntime(seed=701)
    player = runtime.create_character("Scout")
    assert runtime.monster_ecology_location_state(WEST)["danger"]["live_units"] > 0
    runtime.travel_actor(player.actor_id, WEST)
    state = runtime.monster_ecology_location_state(WEST)
    materialized = [
        actor_id
        for species in state["species"].values()
        for actor_id in species["materialized_actor_ids"]
    ]
    assert materialized
    assert all(runtime.actors[actor_id].alive for actor_id in materialized)
    assert all(runtime.actors[actor_id].location_id == WEST for actor_id in materialized)


def test_materialization_consumes_ecology_capacity_named_defeat_uses_corpus_loot_and_recovers():
    runtime = MonsterEcologyAincradRuntime(seed=702)
    player = runtime.create_character("Hunter")
    runtime.travel_actor(player.actor_id, WEST)
    state = runtime.monster_ecology["frenzy_boar"]
    total_before = runtime._live_units("frenzy_boar")
    boar = runtime.materialize_ecological_monster("frenzy_boar")
    assert runtime._live_units("frenzy_boar") == total_before
    boar.hp = 1
    boar.max_hp = max(boar.max_hp, 1)
    boar.evasion = 0
    player.skill_proficiencies["one_hand_sword"] = 1000
    before_col = player.col
    encounter = runtime.start_encounter([player.actor_id, boar.actor_id])
    result = runtime.attack(
        encounter.encounter_id,
        player.actor_id,
        boar.actor_id,
        defense="none",
        seed=1,
    )
    assert result.hit
    assert not boar.alive
    assert state.cumulative_named_kills == 1
    assert player.col > before_col
    depleted = runtime._live_units("frenzy_boar")
    assert depleted == total_before - 1
    runtime.advance_world(runtime.next_ecology_tick_at_ms - runtime.world.now_ms)
    assert runtime._live_units("frenzy_boar") == state.carrying_capacity
    assert state.cumulative_recoveries >= 1


def test_background_hunting_creates_real_ecology_drop_supply_for_economy():
    runtime = MonsterEcologyAincradRuntime(seed=703)
    _unlock_through_floor(runtime, 4)
    runtime.add_population_cohort(
        "f4_clearers",
        "frontline",
        120,
        SCUTTLE,
        20.0,
        "labyrinth_farming",
    )
    before = runtime.monster_ecology["scuttle_crab"].available_units
    runtime.advance_world(ECOLOGY_TICK_MS)
    after = runtime.monster_ecology["scuttle_crab"].available_units
    assert after < before
    stock = runtime.economy.background_commodity_stock[SCUTTLE]
    assert stock["great_crab_shell"] > 0
    market = runtime.aincrad_economy_state(SCUTTLE)["location"]["market"]
    assert market["cumulative_ecology_supply_units"] >= stock["great_crab_shell"]
    assert any(
        row["event"] == "background_hunt"
        and row["location_id"] == SCUTTLE
        and row["resource_drops"].get("great_crab_shell", 0) > 0
        for row in runtime.monster_ecology_history
    )


def test_monster_pressure_commits_population_losses_and_retreat_through_population_authority():
    runtime = MonsterEcologyAincradRuntime(seed=704)
    runtime.add_population_cohort(
        "field_casuals",
        "casual",
        1_000,
        WEST,
        1.0,
        "field_exploration",
    )
    runtime.advance_world(ECOLOGY_TICK_MS)
    cohort = runtime.population.cohorts["field_casuals"]
    assert cohort.headcount < 1_000
    movement = runtime.population_movement_state("field_casuals")
    assert movement is not None
    destination = runtime.world_map.locations[movement["target_location_id"]]
    assert destination.safe_zone
    assert any(
        row["event"] == "cohort_losses"
        and row["cohort_id"] == "field_casuals"
        and str(row["cause"]).startswith("monster_ecology:")
        for row in runtime.population_history
    )
    assert any(
        row["event"] == "background_population_retreat"
        and row["cohort_id"] == "field_casuals"
        for row in runtime.monster_ecology_history
    )


def test_background_commodity_supply_is_consumed_by_later_regional_demand_not_teleported():
    runtime = MonsterEcologyAincradRuntime(seed=705)
    _unlock_through_floor(runtime, 4)
    runtime.add_population_cohort(
        "f4_clearers",
        "frontline",
        140,
        SCUTTLE,
        20.0,
        "labyrinth_farming",
    )
    runtime.advance_world(ECOLOGY_TICK_MS)
    first_stock = runtime.economy.background_commodity_stock[SCUTTLE]["great_crab_shell"]
    assert first_stock > 0
    assert "great_crab_shell" not in runtime.economy.background_commodity_stock.get(TOWN, {})
    runtime.advance_world(ECOLOGY_TICK_MS)
    tick = next(
        row
        for row in reversed(runtime.economy.market_history)
        if row["event"] == "economy_tick" and row["location_id"] == SCUTTLE
    )
    assert tick["background_commodity_units"] >= 1
    assert tick["background_commodity_units_by_template"]["great_crab_shell"] >= 1


def test_monster_ecology_and_resource_stock_round_trip_exactly():
    runtime = MonsterEcologyAincradRuntime(seed=706)
    runtime.add_population_cohort("hunters", "frontline", 96, WEST, 5.0, "farming")
    runtime.advance_world(ECOLOGY_TICK_MS)
    before = runtime.monster_ecology_state(WEST)
    economy_before = runtime.aincrad_economy_state(WEST)
    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, MonsterEcologyAincradRuntime)
    assert restored.monster_ecology_state(WEST) == before
    assert restored.aincrad_economy_state(WEST) == economy_before
    assert restored.next_ecology_tick_at_ms == runtime.next_ecology_tick_at_ms


def test_release_ecological_monster_returns_one_live_unit_without_history_guessing():
    runtime = MonsterEcologyAincradRuntime(seed=707)
    before = runtime.monster_ecology["frenzy_boar"].available_units
    actor = runtime.materialize_ecological_monster("frenzy_boar")
    assert runtime.monster_ecology["frenzy_boar"].available_units == before - 1
    runtime.release_ecological_monster(actor.actor_id)
    assert actor.actor_id not in runtime.actors
    assert runtime.monster_ecology["frenzy_boar"].available_units == before
