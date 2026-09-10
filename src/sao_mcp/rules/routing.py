from __future__ import annotations

import heapq
from collections.abc import Callable

from sao_mcp.corpus.world import WorldMapCatalog
from sao_mcp.domain.models import WorldState


LocationPredicate = Callable[[str], bool]


def shortest_next_hop(
    world: WorldState,
    world_map: WorldMapCatalog,
    origin: str,
    target: str,
    *,
    can_enter: LocationPredicate | None = None,
) -> str | None:
    """Return the first edge on the minimum-travel-time route through the current world graph."""
    if origin not in world_map.locations:
        raise KeyError(origin)
    if target not in world_map.locations:
        raise KeyError(target)
    if origin == target:
        return None

    queue: list[tuple[int, str, str | None]] = [(0, origin, None)]
    best = {origin: 0}
    while queue:
        elapsed, node_id, first_hop = heapq.heappop(queue)
        if elapsed != best.get(node_id):
            continue
        for edge in world_map.adjacency.get(node_id, ()):
            destination = world_map.locations[edge.to_location_id]
            if edge.requires_floor_unlocked and not world.floors[destination.floor_number].unlocked:
                continue
            if can_enter is not None and not can_enter(edge.to_location_id):
                continue
            total = elapsed + edge.travel_ms
            if total >= best.get(edge.to_location_id, 2**63 - 1):
                continue
            next_first = edge.to_location_id if first_hop is None else first_hop
            if edge.to_location_id == target:
                return next_first
            best[edge.to_location_id] = total
            heapq.heappush(queue, (total, edge.to_location_id, next_first))
    raise ValueError(f"destination is unreachable from {origin}: {target}")
