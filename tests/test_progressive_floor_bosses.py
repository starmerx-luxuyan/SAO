from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


def test_progressive_floor_bosses_three_through_five_start_in_existing_runtime():
    cases = (
        (3, "nerius_the_evil_treant", 4),
        (4, "wythege_the_hippocampus", 6),
        (5, "fuscus_the_vacant_colossus", 6),
    )
    for floor, definition_id, hp_bars in cases:
        runtime = HousingAincradRuntime(seed=floor)
        player = runtime.create_character(f"Floor{floor}", level=20 + floor * 3)
        runtime.world.floors[floor].unlocked = True
        player.location_id = f"floor_{floor}_boss_room"
        encounter, boss = runtime.start_floor_boss_encounter(
            [player.actor_id],
            boss_definition_id=definition_id,
        )
        assert boss.actor_id in encounter.participants
        assert runtime.boss_bar_state(boss)["hpBars"] == hp_bars
