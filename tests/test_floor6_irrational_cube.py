from sao_mcp.corpus.floor6_finale import COMBINED_IRON_KEY_ID, GOLDEN_CUBE_ID
from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor6_irrational_cube import install_floor6_irrational_cube_scenario


def test_floor6_golden_cube_activation_puzzle_hp_floor_and_key_finish_are_one_chain():
    runtime = HousingAincradRuntime(seed=43)
    cube = install_floor6_irrational_cube_scenario(runtime)
    player = runtime.create_character("CubeSolver", level=42)
    runtime.world.floors[6].unlocked = True

    assert "floor_6_stachion" in runtime.world_map.locations
    assert "floor_6_suribus" in runtime.world_map.locations
    assert "floor_6_castle_galey" in runtime.world_map.locations
    assert "floor_6_main_town" not in runtime.world_map.locations

    player.location_id = "floor_6_boss_room"
    golden_cube = ItemInstance("test_golden_cube", GOLDEN_CUBE_ID, player.actor_id)
    combined_key = ItemInstance("test_combined_iron_key", COMBINED_IRON_KEY_ID, player.actor_id)
    add_item(player, golden_cube, runtime.catalog, allow_overweight=True)
    add_item(player, combined_key, runtime.catalog, allow_overweight=True)

    state = cube.activate_guardian(
        [player.actor_id],
        player.actor_id,
        golden_cube.instance_id,
    )
    boss = runtime.actors[state["boss_id"]]
    encounter = runtime.encounters[state["encounter_id"]]
    assert state["stage"] == "number_face_puzzle"
    assert state["target_code"] == "834159672"
    assert state["numbered_armor_active"] is True
    assert state["hp_floor"] == boss.max_hp
    assert golden_cube.instance_id not in player.inventory
    assert boss.inventory[golden_cube.instance_id].template_id == GOLDEN_CUBE_ID

    state = cube.rotate_row(state["instance_id"], 2, "left")
    assert not state["puzzle_solved"]
    state = cube.rotate_column(state["instance_id"], 2, "up")
    assert not state["puzzle_solved"]
    state = cube.rotate_row(state["instance_id"], 0, "right")
    assert state["puzzle_solved"]
    assert state["face"] == [[8, 3, 4], [1, 5, 9], [6, 7, 2]]
    assert state["stage"] == "black_core_battle"
    assert state["numbered_armor_active"] is False
    assert state["black_core_exposed"] is True
    assert state["boss"]["hpBars"] == 1
    assert state["boss"]["phase"] == "exposed_black_core"
    assert state["hp_floor"] == 1

    # Generic combat can reduce the black core to its final pixel but not kill through the mechanic.
    boss.hp = 2
    boss.alive = True
    strike = runtime.attack(encounter.encounter_id, player.actor_id, boss.actor_id, seed=7)
    assert strike.legal and strike.hit
    assert strike.damage == 1
    assert boss.hp == 1
    assert boss.alive

    state = cube.eject_golden_cube(
        state["instance_id"],
        player.actor_id,
        combined_key.instance_id,
    )
    assert state["stage"] == "golden_cube_ejected"
    assert golden_cube.instance_id in player.inventory
    assert player.inventory[golden_cube.instance_id].owner_id == player.actor_id
    assert player.inventory[combined_key.instance_id].metadata["survives_floor6_boss"] is True

    state = cube.reinsert_cube_and_destroy_core(state["instance_id"], player.actor_id)
    assert state["stage"] == "cleared"
    assert state["golden_cube_destroyed"] is True
    assert golden_cube.instance_id not in player.inventory
    assert combined_key.instance_id in player.inventory
    assert not boss.alive and boss.hp == 0
    assert runtime.world.floors[6].floor_boss_defeated
