from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor6_irrational_cube import install_floor6_irrational_cube_scenario


def test_floor6_number_face_puzzle_unlocks_single_gauge_black_core_battle():
    runtime = HousingAincradRuntime(seed=43)
    cube = install_floor6_irrational_cube_scenario(runtime)
    player = runtime.create_character("CubeSolver", level=42)
    runtime.world.floors[6].unlocked = True

    assert "floor_6_stachion" in runtime.world_map.locations
    assert "floor_6_suribus" in runtime.world_map.locations
    assert "floor_6_castle_galey" in runtime.world_map.locations
    assert "floor_6_main_town" not in runtime.world_map.locations

    player.location_id = "floor_6_boss_room"
    state = cube.start_puzzle([player.actor_id])
    assert state["stage"] == "number_face_puzzle"
    assert state["target_code"] == "834159672"
    assert state["boss_id"] is None

    state = cube.rotate_row(state["instance_id"], 2, "left")
    assert not state["puzzle_solved"]
    state = cube.rotate_column(state["instance_id"], 2, "up")
    assert not state["puzzle_solved"]
    state = cube.rotate_row(state["instance_id"], 0, "right")
    assert state["puzzle_solved"]
    assert state["face"] == [[8, 3, 4], [1, 5, 9], [6, 7, 2]]
    assert state["stage"] == "puzzle_solved"

    state = cube.engage_boss(state["instance_id"])
    assert state["stage"] == "battle"
    assert state["boss"]["definitionId"] == "the_irrational_cube"
    assert state["boss"]["hpBars"] == 1
    assert state["boss"]["phase"] == "exposed_black_core"

    boss = runtime.actors[state["boss_id"]]
    encounter = runtime.encounters[state["encounter_id"]]
    boss.hp = 0
    boss.alive = False
    runtime._resolve_defeat(encounter, boss, player.actor_id)

    state = cube.status(state["instance_id"])
    assert state["stage"] == "cleared"
    assert runtime.world.floors[6].floor_boss_defeated
