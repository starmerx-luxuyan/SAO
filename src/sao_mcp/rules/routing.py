from __future__ import annotations

import heapq
from collections.abc import Callable

from sao_mcp.corpus.world import WorldMapCatalog
from sao_mcp.domain.models import WorldState


LocationPredicate = Callable[[str], bool]


def shortest_route(
    world: WorldState,
    world_map: WorldMapCatalog,
    origin: str,
    target: str,
    *,
    can_enter: LocationPredicate | None = None,
) -> tuple[tuple[str, ...], int]:
    """Return the minimum-travel-time graph route (excluding origin) and its elapsed ms."""
    if origin not in world_map.locations:
        raise KeyError(origin)
    if target not in world_map.locations:
        raise KeyError(target)
    if origin == target:
        return (), 0

    queue: list[tuple[int, str, tuple[str, ...]]] = [(0, origin, ())]
    best = {origin: 0}
    while queue:
        elapsed, node_id, path = heapq.heappop(queue)
        if elapsed != best.get(node_id):
            continue
        if node_id == target:
            return path, elapsed
        for edge in world_map.adjacency.get(node_id, ()):
            destination = world_map.locations[edge.to_location_id]
            if edge.requires_floor_unlocked and not world.floors[destination.floor_number].unlocked:
                continue
            if can_enter is not None and not can_enter(edge.to_location_id):
                continue
            total = elapsed + edge.travel_ms
            if total >= best.get(edge.to_location_id, 2**63 - 1):
                continue
            best[edge.to_location_id] = total
            heapq.heappush(queue, (total, edge.to_location_id, path + (edge.to_location_id,)))
    raise ValueError(f"destination is unreachable from {origin}: {target}")


def shortest_next_hop(
    world: WorldState,
    world_map: WorldMapCatalog,
    origin: str,
    target: str,
    *,
    can_enter: LocationPredicate | None = None,
) -> str | None:
    """Return the first edge on the minimum-travel-time route through the current world graph."""
    route, _ = shortest_route(world, world_map, origin, target, can_enter=can_enter)
    return route[0] if route else None
