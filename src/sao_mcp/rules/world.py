from __future__ import annotations

from sao_mcp.corpus.dynamic_world import DYNAMIC_TRAVEL_CONNECTIONS
from sao_mcp.corpus.world import TravelConnection, WorldMapCatalog
from sao_mcp.domain.models import FloorState, WorldState


NEXT_FLOOR_AUTO_GATE_DELAY_MS = 2 * 60 * 60 * 1000
DYNAMIC_CONNECTION_IDS_FLAG = "dynamic_world_connection_ids"


def make_aincrad_world() -> WorldState:
    floors = {
        n: FloorState(number=n, unlocked=(n == 1), main_town_gate_active=(n == 1))
        for n in range(1, 101)
    }
    return WorldState(now_ms=0, floors=floors)


def _rebuild_world_map_adjacency(world_map: WorldMapCatalog) -> None:
    adjacency: dict[str, list[TravelConnection]] = {}
    for connection in world_map.connections:
        adjacency.setdefault(connection.from_location_id, []).append(connection)
        if connection.bidirectional:
            adjacency.setdefault(connection.to_location_id, []).append(
                TravelConnection(
                    connection.to_location_id,
                    connection.from_location_id,
                    connection.travel_ms,
                    True,
                    connection.requires_floor_unlocked,
                    connection.provenance,
                    connection.traversal_tags,
                )
            )
    world_map.adjacency = adjacency


def _dynamic_connection_ids(world: WorldState) -> list[str]:
    value = world.global_flags.get(DYNAMIC_CONNECTION_IDS_FLAG)
    if value is None:
        value = []
        world.global_flags[DYNAMIC_CONNECTION_IDS_FLAG] = value
    if not isinstance(value, list) or any(not isinstance(connection_id, str) for connection_id in value):
        raise RuntimeError("dynamic_world_connection_ids must be a list of connection IDs")
    unknown = [connection_id for connection_id in value if connection_id not in DYNAMIC_TRAVEL_CONNECTIONS]
    if unknown:
        raise RuntimeError(f"unknown dynamic world connection IDs: {unknown}")
    return value


def _install_dynamic_connection(world_map: WorldMapCatalog, connection_id: str) -> None:
    connections = DYNAMIC_TRAVEL_CONNECTIONS[connection_id]
    existing = list(world_map.connections)
    changed = False
    for connection in connections:
        endpoint_conflicts = [
            edge
            for edge in existing
            if edge.from_location_id == connection.from_location_id
            and edge.to_location_id == connection.to_location_id
            and edge != connection
        ]
        if endpoint_conflicts:
            raise RuntimeError(
                f"dynamic connection {connection_id} conflicts with an existing world edge "
                f"{connection.from_location_id}->{connection.to_location_id}"
            )
        if connection not in existing:
            existing.append(connection)
            changed = True
    if changed:
        world_map.connections = tuple(existing)
        _rebuild_world_map_adjacency(world_map)


def unlock_dynamic_world_connection(
    world: WorldState,
    world_map: WorldMapCatalog,
    connection_id: str,
) -> tuple[TravelConnection, ...]:
    if connection_id not in DYNAMIC_TRAVEL_CONNECTIONS:
        raise KeyError(connection_id)
    ids = _dynamic_connection_ids(world)
    if connection_id not in ids:
        ids.append(connection_id)
    _install_dynamic_connection(world_map, connection_id)
    return DYNAMIC_TRAVEL_CONNECTIONS[connection_id]


def restore_dynamic_world_connections(world: WorldState, world_map: WorldMapCatalog) -> None:
    dynamic_endpoint_pairs = {
        (connection.from_location_id, connection.to_location_id)
        for connections in DYNAMIC_TRAVEL_CONNECTIONS.values()
        for connection in connections
    }
    world_map.connections = tuple(
        connection
        for connection in world_map.connections
        if (connection.from_location_id, connection.to_location_id) not in dynamic_endpoint_pairs
    )
    _rebuild_world_map_adjacency(world_map)
    for connection_id in _dynamic_connection_ids(world):
        _install_dynamic_connection(world_map, connection_id)


def defeat_floor_boss(world: WorldState, floor_number: int) -> FloorState:
    if floor_number < 1 or floor_number > 100:
        raise ValueError("floor_number must be in 1..100")
    floor = world.floors[floor_number]
    if floor.floor_boss_defeated:
        return floor
    floor.floor_boss_defeated = True
    floor.floor_boss_defeated_at_ms = world.now_ms
    if floor_number < 100:
        floor.scheduled_gate_activation_at_ms = world.now_ms + NEXT_FLOOR_AUTO_GATE_DELAY_MS
    return floor


def activate_next_floor_early(world: WorldState, defeated_floor_number: int) -> FloorState:
    if defeated_floor_number >= 100:
        raise ValueError("there is no next floor")
    floor = world.floors[defeated_floor_number]
    if not floor.floor_boss_defeated:
        raise ValueError("floor boss has not been defeated")
    next_floor = world.floors[defeated_floor_number + 1]
    next_floor.unlocked = True
    next_floor.main_town_gate_active = True
    floor.scheduled_gate_activation_at_ms = None
    return next_floor


def advance_world_time(world: WorldState, elapsed_ms: int) -> list[int]:
    if elapsed_ms < 0:
        raise ValueError("elapsed_ms must be >= 0")
    world.now_ms += elapsed_ms
    activated: list[int] = []
    for number in range(1, 100):
        floor = world.floors[number]
        when = floor.scheduled_gate_activation_at_ms
        if when is not None and when <= world.now_ms:
            next_floor = world.floors[number + 1]
            next_floor.unlocked = True
            next_floor.main_town_gate_active = True
            floor.scheduled_gate_activation_at_ms = None
            activated.append(number + 1)
    return activated
