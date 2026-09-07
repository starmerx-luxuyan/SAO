import json

from sao_mcp.corpus.world import build_world_map_catalog
from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.runtime.engine import GameRuntime
from sao_mcp.ui.system_views import system_menu_view
from sao_mcp.ui.view_models import dumps_view


def test_verified_midgame_main_settlements_replace_generic_placeholders():
    world_map = build_world_map_catalog()
    expected = {
        "floor_22_coral": 22,
        "floor_48_lindarth": 48,
        "floor_50_algade": 50,
        "floor_55_granzam": 55,
        "floor_61_selmburg": 61,
        "floor_75_collinia": 75,
    }
    for location_id, floor in expected.items():
        assert world_map.locations[location_id].floor_number == floor
        assert world_map.locations[location_id].safe_zone
        assert world_map.locations[location_id].teleport_gate
    assert "floor_48_main_town" not in world_map.locations
    assert "floor_75_main_town" not in world_map.locations


def test_named_player_shops_are_real_connected_world_nodes():
    world_map = build_world_map_catalog()
    assert world_map.locations["floor_48_lisbeth_smith_shop"].floor_number == 48
    assert world_map.locations["floor_50_agil_shop"].floor_number == 50
    assert any(
        edge.to_location_id == "floor_48_lisbeth_smith_shop"
        for edge in world_map.adjacency["floor_48_lindarth"]
    )
    assert any(
        edge.to_location_id == "floor_50_agil_shop"
        for edge in world_map.adjacency["floor_50_algade"]
    )


def test_named_world_actors_are_seeded_at_their_shops():
    runtime = GameRuntime(seed=1)
    assert runtime.npcs.states["pc_lisbeth"].location_id == "floor_48_lisbeth_smith_shop"
    assert runtime.npcs.states["pc_agil"].location_id == "floor_50_agil_shop"


def test_system_menu_view_is_json_serializable_and_includes_local_services():
    runtime = GameRuntime(seed=1)
    runtime.economy = EconomyRuntime()
    actor = runtime.create_character("MenuTest")
    view = system_menu_view(runtime, actor.actor_id)
    payload = json.loads(dumps_view(view))
    assert payload["schema"] == "sao.ui.system.v1"
    assert payload["location"]["name"] == "Town of Beginnings"
    assert payload["vendors"]
    assert payload["forge"]["available"] is True
    assert payload["skillManagement"]["slotsTotal"] == 2
