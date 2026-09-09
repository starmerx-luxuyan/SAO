from sao_mcp.corpus.floor6_world import (
    GOLDEN_CUBE_LABYRINTH_BREACH_CONNECTION_ID,
    STACHION_POST_AMBUSH_CONNECTION_ID,
    TRIALS_MAIN_ENTRANCE_CONNECTION_ID,
    TRIALS_SECRET_BACK_DOOR_CONNECTION_ID,
)
from sao_mcp.rules.world import DYNAMIC_CONNECTION_IDS_FLAG, unlock_dynamic_world_connection
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


DYNAMIC_IDS = (
    STACHION_POST_AMBUSH_CONNECTION_ID,
    TRIALS_SECRET_BACK_DOOR_CONNECTION_ID,
    TRIALS_MAIN_ENTRANCE_CONNECTION_ID,
    GOLDEN_CUBE_LABYRINTH_BREACH_CONNECTION_ID,
)

STATIC_FLOOR6_LOCATIONS = {
    "floor_6_cylon_lord_manor",
    "floor_6_traveller_grave",
    "floor_6_cylon_transport_carriage",
    "floor_6_myia_house",
    "floor_6_dungeon_of_trials_entrance",
    "floor_6_dungeon_of_trials",
    "floor_6_dungeon_of_trials_secret_back_door",
    "floor_6_dungeon_of_trials_final_chamber",
    "floor_6_agate_key_shrine",
    "floor_6_castle_galey_storyteller_summit",
    "floor_6_castle_galey_spirit_tree_spring",
    "floor_6_qusack_rescue_cave",
    "floor_6_goskai",
    "floor_6_goskai_caves",
    "floor_6_murutsuki",
    "floor_6_labyrinth_golden_cube_breach",
}

DYNAMIC_ENDPOINTS = {
    ("floor_6_cylon_transport_carriage", "floor_6_suribus"),
    ("floor_6_cylon_transport_carriage", "floor_6_stachion"),
    ("floor_6_cylon_lord_manor", "floor_6_dungeon_of_trials_secret_back_door"),
    ("floor_6_dungeon_of_trials_secret_back_door", "floor_6_dungeon_of_trials_final_chamber"),
    ("floor_6_dungeon_of_trials_entrance", "floor_6_dungeon_of_trials"),
    ("floor_6_labyrinth", "floor_6_labyrinth_golden_cube_breach"),
    ("floor_6_labyrinth_golden_cube_breach", "floor_6_boss_room"),
}


def _edge_pairs(runtime) -> set[tuple[str, str]]:
    return {(edge.from_location_id, edge.to_location_id) for edge in runtime.world_map.connections}


def test_floor6_static_geometry_is_base_world_and_dynamic_routes_persist():
    runtime = HousingAincradRuntime(seed=73)

    assert STATIC_FLOOR6_LOCATIONS.issubset(runtime.world_map.locations)
    assert not DYNAMIC_ENDPOINTS.intersection(_edge_pairs(runtime))

    for connection_id in DYNAMIC_IDS:
        unlock_dynamic_world_connection(runtime.world, runtime.world_map, connection_id)

    assert runtime.world.global_flags[DYNAMIC_CONNECTION_IDS_FLAG] == list(DYNAMIC_IDS)
    assert DYNAMIC_ENDPOINTS.issubset(_edge_pairs(runtime))

    restored = import_runtime(export_runtime(runtime))

    assert STATIC_FLOOR6_LOCATIONS.issubset(restored.world_map.locations)
    assert restored.world.global_flags[DYNAMIC_CONNECTION_IDS_FLAG] == list(DYNAMIC_IDS)
    assert DYNAMIC_ENDPOINTS.issubset(_edge_pairs(restored))
