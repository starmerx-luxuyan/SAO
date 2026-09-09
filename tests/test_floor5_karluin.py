from sao_mcp.corpus.floor5 import RING_OF_LUMINESCENCE
from sao_mcp.corpus.floor5_shortcut import KARLUIN_SHORTCUT_CONNECTION_ID
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor5_karluin import (
    BLINK_AND_BRINK,
    CATACOMBS_L1,
    CATACOMBS_LOWER,
    KARLUIN,
    RELIC_BONUS_MS,
    RUINED_TEMPLE,
    install_floor5_karluin_scenario,
)
from sao_mcp.scenarios.floor5_shortcut import (
    AREA_BOSS_ROOM,
    MANANARENA,
    PUZZLE_PROGRESS_REQUIRED_HOURS,
    SHORTCUT_TUNNEL,
    install_floor5_shortcut_scenario,
)


def _has_connection(runtime, origin, destination):
    return any(
        edge.from_location_id == origin and edge.to_location_id == destination
        for edge in runtime.world_map.connections
    )


def test_karluin_relic_catacomb_and_shortcut_progression_use_base_world_state():
    runtime = HousingAincradRuntime(seed=37)
    locations_before = dict(runtime.world_map.locations)
    connections_before = tuple(runtime.world_map.connections)
    karluin = install_floor5_karluin_scenario(runtime)
    assert runtime.world_map.locations == locations_before
    assert runtime.world_map.connections == connections_before

    shortcut = install_floor5_shortcut_scenario(runtime)
    player = runtime.create_character("RelicHunter", level=24)
    runtime.world.floors[5].unlocked = True
    player.location_id = KARLUIN

    assert not _has_connection(runtime, AREA_BOSS_ROOM, SHORTCUT_TUNNEL)
    assert not _has_connection(runtime, SHORTCUT_TUNNEL, MANANARENA)

    runtime.travel_actor(player.actor_id, BLINK_AND_BRINK)
    buff = karluin.order_blue_blueberry_tart(player.actor_id)
    assert buff["active"]
    assert buff["remaining_ms"] == RELIC_BONUS_MS

    runtime.travel_actor(player.actor_id, KARLUIN)
    runtime.travel_actor(player.actor_id, RUINED_TEMPLE)
    ring = karluin.search_relic(player.actor_id)
    assert ring.template_id == RING_OF_LUMINESCENCE
    glow = karluin.breathe_on_luminescence_ring(player.actor_id, ring.instance_id)
    assert glow["luminescent"] is True
    assert player.inventory[ring.instance_id].metadata["luminescent"] is True

    runtime.travel_actor(player.actor_id, KARLUIN)
    runtime.travel_actor(player.actor_id, CATACOMBS_L1)
    runtime.travel_actor(player.actor_id, CATACOMBS_LOWER)

    potion = next(item for item in player.inventory.values() if item.template_id == "healing_potion_basic")
    original_id = potion.instance_id
    original_quantity = potion.quantity
    encounter, thief, stolen = karluin.trigger_shrewman_robbery(player.actor_id, original_id)
    assert original_id not in player.inventory
    assert stolen.instance_id == original_id
    assert stolen.owner_id == thief.actor_id
    assert thief.inventory[original_id].quantity == original_quantity

    thief.hp = 0
    thief.alive = False
    runtime._resolve_defeat(encounter, thief, player.actor_id)
    recovered = karluin.recover_shrewman_stolen_items(player.actor_id, thief.actor_id)
    assert recovered == [original_id]
    assert player.inventory[original_id].owner_id == player.actor_id
    assert player.inventory[original_id].quantity == original_quantity

    wraith_encounter, wraith = karluin.create_mournful_wraith_encounter(player.actor_id)
    assert wraith.metadata["monster_id"] == "mournful_wraith"
    assert wraith.actor_id in wraith_encounter.participants
    wraith.hp = 0
    wraith.alive = False
    runtime._resolve_defeat(wraith_encounter, wraith, player.actor_id)

    restored = import_runtime(export_runtime(runtime))
    assert KARLUIN in restored.world_map.locations
    assert BLINK_AND_BRINK in restored.world_map.locations
    assert CATACOMBS_L1 in restored.world_map.locations
    assert CATACOMBS_LOWER in restored.world_map.locations
    restored_locations_before = dict(restored.world_map.locations)
    restored_connections_before = tuple(restored.world_map.connections)
    install_floor5_karluin_scenario(restored)
    assert restored.world_map.locations == restored_locations_before
    assert restored.world_map.connections == restored_connections_before

    runtime.travel_actor(player.actor_id, AREA_BOSS_ROOM)
    before_puzzle = runtime.world.now_ms
    puzzle = shortcut.investigate_puzzle(player.actor_id, hours=23)
    assert not puzzle["solved"]
    puzzle = shortcut.investigate_puzzle(player.actor_id, hours=1)
    assert puzzle["solved"]
    assert puzzle["progress_hours"] == PUZZLE_PROGRESS_REQUIRED_HOURS
    assert runtime.world.now_ms == before_puzzle + 24 * 60 * 60 * 1000

    state = shortcut.start_area_boss_raid([player.actor_id])
    boss = runtime.actors[state["boss_id"]]
    assert state["puzzle_weakened"] is True
    assert boss.metadata["puzzle_weakened"] is True
    assert state["shortcut_unlocked"] is False

    boss.hp = 0
    boss.alive = False
    boss_encounter = runtime.encounters[state["encounter_id"]]
    runtime._resolve_defeat(boss_encounter, boss, player.actor_id)
    cleared = shortcut.status(state["instance_id"])
    assert cleared["stage"] == "cleared"
    assert cleared["shortcut_unlocked"] is True
    assert cleared["shortcut_connection_id"] == KARLUIN_SHORTCUT_CONNECTION_ID
    assert runtime.world.global_flags["dynamic_world_connection_ids"] == [KARLUIN_SHORTCUT_CONNECTION_ID]
    assert _has_connection(runtime, AREA_BOSS_ROOM, SHORTCUT_TUNNEL)
    assert _has_connection(runtime, SHORTCUT_TUNNEL, MANANARENA)

    first_leg = shortcut.traverse_shortcut(player.actor_id, SHORTCUT_TUNNEL)
    assert first_leg["to_location_id"] == SHORTCUT_TUNNEL
    assert first_leg["travel_ms"] == 4 * 60_000
    assert "unlocked_area_boss_passage" in first_leg["traversal_tags"]
    second_leg = shortcut.traverse_shortcut(player.actor_id, MANANARENA)
    assert second_leg["to_location_id"] == MANANARENA
    assert second_leg["travel_ms"] == 8 * 60_000
    assert player.location_id == MANANARENA

    restored_unlocked = import_runtime(export_runtime(runtime))
    restored_player = restored_unlocked.actors[player.actor_id]
    assert restored_unlocked.world.global_flags["dynamic_world_connection_ids"] == [KARLUIN_SHORTCUT_CONNECTION_ID]
    assert _has_connection(restored_unlocked, AREA_BOSS_ROOM, SHORTCUT_TUNNEL)
    assert _has_connection(restored_unlocked, SHORTCUT_TUNNEL, MANANARENA)
    restored_unlocked.travel_actor(restored_player.actor_id, SHORTCUT_TUNNEL)
    restored_unlocked.travel_actor(restored_player.actor_id, AREA_BOSS_ROOM)
    assert restored_player.location_id == AREA_BOSS_ROOM
