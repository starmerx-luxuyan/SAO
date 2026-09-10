from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import CursorColor, EntityKind
from sao_mcp.rules.access import require_location_access
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.routing import shortest_next_hop
from sao_mcp.rules.travel import has_surviving_colocated_outsider


@dataclass(slots=True, frozen=True)
class GroupTravelResolution:
    actor_ids: tuple[str, ...]
    from_location_id: str
    to_location_id: str
    elapsed_ms: int
    newly_discovered: bool
    traversal_tags: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class RoutedTravelWindowResolution:
    actor_ids: tuple[str, ...]
    started_at_ms: int
    completed_at_ms: int
    minimum_elapsed_ms: int
    route: tuple[GroupTravelResolution, ...]

    @property
    def window_elapsed_ms(self) -> int:
        return self.completed_at_ms - self.started_at_ms


def group_travel_record(resolution: GroupTravelResolution) -> dict:
    return {
        "actor_ids": list(resolution.actor_ids),
        "from_location_id": resolution.from_location_id,
        "to_location_id": resolution.to_location_id,
        "elapsed_ms": resolution.elapsed_ms,
        "newly_discovered": resolution.newly_discovered,
        "traversal_tags": list(resolution.traversal_tags),
    }


def routed_travel_window_record(resolution: RoutedTravelWindowResolution) -> dict:
    return {
        "actor_ids": list(resolution.actor_ids),
        "started_at_ms": resolution.started_at_ms,
        "completed_at_ms": resolution.completed_at_ms,
        "window_elapsed_ms": resolution.window_elapsed_ms,
        "minimum_elapsed_ms": resolution.minimum_elapsed_ms,
        "route": [group_travel_record(segment) for segment in resolution.route],
    }


def _group_context(runtime, actor_ids: list[str] | tuple[str, ...]):
    members = tuple(actor_ids)
    if not members:
        raise ValueError("group travel requires at least one actor")
    if len(set(members)) != len(members):
        raise ValueError("group travel actor_ids must be unique")

    actors = [runtime.actors[actor_id] for actor_id in members]
    for actor_id in members:
        runtime.require_actor_autonomous_travel(actor_id)
    if any(not actor.alive for actor in actors):
        raise ValueError("all group travellers must be alive")
    if any(actor.location_id is None for actor in actors):
        raise ValueError("all group travellers must have a current world location")

    origins = {actor.location_id for actor in actors}
    if len(origins) != 1:
        raise ValueError("all group travellers must be colocated")
    origin = str(actors[0].location_id)

    if any(actor.metadata.get("active_duel_id") for actor in actors):
        raise ValueError("group travel is unavailable while a traveller has an active duel")

    member_ids = set(members)
    for encounter in runtime.encounters.values():
        if not member_ids.intersection(encounter.participants):
            continue
        if has_surviving_colocated_outsider(encounter, member_ids, origin):
            raise ValueError("group travel is unavailable while a live encounter has surviving colocated outsiders")
    return members, actors, origin


def _can_group_enter(runtime, actors, location_id: str) -> bool:
    destination = runtime.world_map.locations[location_id]
    if not runtime.world.floors[destination.floor_number].unlocked:
        return False
    if destination.safe_zone and any(actor.cursor is CursorColor.ORANGE for actor in actors):
        return False
    try:
        for actor in actors:
            require_location_access(actor, location_id)
    except ValueError:
        return False
    return True


def _require_group_can_enter(runtime, actors, location_id: str) -> None:
    destination = runtime.world_map.locations[location_id]
    if not runtime.world.floors[destination.floor_number].unlocked:
        raise ValueError("destination floor is not unlocked")
    if destination.safe_zone and any(actor.cursor is CursorColor.ORANGE for actor in actors):
        raise ValueError("Anti-Criminal Code settlement access is blocked for Orange Players")
    # Preserve the concrete faction/location access reason for direct movement attempts.
    for actor in actors:
        require_location_access(actor, location_id)


def _next_group_hop(runtime, actors, origin: str, destination_id: str) -> str | None:
    return shortest_next_hop(
        runtime.world,
        runtime.world_map,
        origin,
        destination_id,
        can_enter=lambda location_id: _can_group_enter(runtime, actors, location_id),
    )


def _direct_edge(runtime, origin: str, destination_id: str):
    candidates = [
        edge
        for edge in runtime.world_map.adjacency.get(origin, ())
        if edge.to_location_id == destination_id
    ]
    if not candidates:
        raise ValueError("destination is not directly connected to the group's current location")
    return min(candidates, key=lambda value: value.travel_ms)


def _commit_group_destination(runtime, members, actors, destination_id: str) -> bool:
    destination = runtime.world_map.locations[destination_id]
    floor = runtime.world.floors[destination.floor_number]
    newly_discovered = destination_id not in floor.discovered_locations
    floor.discovered_locations.add(destination_id)
    for actor in actors:
        actor.location_id = destination_id
        if actor.kind is EntityKind.PLAYER:
            runtime.quests.record_event(
                actor.actor_id,
                kind=QuestObjectiveKind.DISCOVER,
                target_id=destination_id,
            )
    return newly_discovered


def travel_together(runtime, actor_ids: list[str] | tuple[str, ...], destination_id: str) -> GroupTravelResolution:
    members, actors, origin = _group_context(runtime, actor_ids)

    if destination_id not in runtime.world_map.locations:
        raise KeyError(destination_id)
    _require_group_can_enter(runtime, actors, destination_id)

    edge = _direct_edge(runtime, origin, destination_id)
    runtime.advance_world(edge.travel_ms)
    newly_discovered = _commit_group_destination(runtime, members, actors, destination_id)

    return GroupTravelResolution(
        actor_ids=members,
        from_location_id=origin,
        to_location_id=destination_id,
        elapsed_ms=edge.travel_ms,
        newly_discovered=newly_discovered,
        traversal_tags=edge.traversal_tags,
    )


def escorted_travel_together(
    runtime,
    detainee_ids: list[str] | tuple[str, ...],
    escort_ids: list[str] | tuple[str, ...],
    destination_id: str,
) -> GroupTravelResolution:
    detainees = tuple(detainee_ids)
    escorts = tuple(escort_ids)
    if not detainees or not escorts:
        raise ValueError("escorted travel requires detainees and escorts")
    if len(set(detainees)) != len(detainees) or len(set(escorts)) != len(escorts):
        raise ValueError("escorted travel actor ids must be unique")
    if set(detainees).intersection(escorts):
        raise ValueError("an actor cannot be both detainee and escort")

    members = detainees + escorts
    actors = [runtime.actors[actor_id] for actor_id in members]
    if any(not actor.alive for actor in actors):
        raise ValueError("all escorted travellers must be alive")
    if any(actor.location_id is None for actor in actors):
        raise ValueError("all escorted travellers must have a current world location")
    origins = {actor.location_id for actor in actors}
    if len(origins) != 1:
        raise ValueError("detainees and escorts must be colocated")
    origin = str(actors[0].location_id)

    for actor_id in detainees:
        custody = runtime.legal.custody_for(actor_id)
        if custody is None:
            raise ValueError(f"escorted traveller {actor_id} is not in custody")
    for actor_id in escorts:
        runtime.require_actor_autonomous_travel(actor_id)
    if any(actor.metadata.get("active_duel_id") for actor in actors):
        raise ValueError("escorted travel is unavailable while a traveller has an active duel")

    member_ids = set(members)
    for encounter in runtime.encounters.values():
        if not encounter.active or not member_ids.intersection(encounter.participants):
            continue
        if has_surviving_colocated_outsider(encounter, member_ids, origin):
            raise ValueError("escorted travel is unavailable while a live encounter has surviving colocated outsiders")

    if destination_id not in runtime.world_map.locations:
        raise KeyError(destination_id)
    _require_group_can_enter(runtime, actors, destination_id)
    edge = _direct_edge(runtime, origin, destination_id)
    runtime.advance_world(edge.travel_ms)
    newly_discovered = _commit_group_destination(runtime, members, actors, destination_id)
    return GroupTravelResolution(
        actor_ids=members,
        from_location_id=origin,
        to_location_id=destination_id,
        elapsed_ms=edge.travel_ms,
        newly_discovered=newly_discovered,
        traversal_tags=edge.traversal_tags,
    )


def exit_encounter_via_travel(
    runtime,
    encounter_id: str,
    actor_ids: list[str] | tuple[str, ...],
    destination_id: str,
) -> GroupTravelResolution:
    """Leave a live encounter through one real adjacent world-graph edge."""

    encounter = runtime.require_active_encounter(encounter_id)
    members = tuple(actor_ids)
    if not members or len(set(members)) != len(members):
        raise ValueError("encounter-exit travel requires unique actor ids")
    actors = []
    for actor_id in members:
        actor = encounter.participants.get(actor_id)
        if actor is None or runtime.actors.get(actor_id) is not actor:
            raise ValueError("encounter-exit traveller must be an authoritative encounter participant")
        if not actor.alive or actor.location_id is None:
            raise ValueError("encounter-exit traveller must be alive at a settled world location")
        actors.append(actor)
    origins = {actor.location_id for actor in actors}
    if len(origins) != 1:
        raise ValueError("encounter-exit travellers must share one world location")
    origin = str(actors[0].location_id)
    if destination_id not in runtime.world_map.locations:
        raise KeyError(destination_id)
    _require_group_can_enter(runtime, actors, destination_id)
    edge = _direct_edge(runtime, origin, destination_id)

    runtime.advance_encounter(encounter_id, edge.travel_ms)
    newly_discovered = _commit_group_destination(runtime, members, actors, destination_id)
    runtime.remove_encounter_participants(
        encounter_id, members, reason="world_graph_exit"
    )

    return GroupTravelResolution(
        actor_ids=members,
        from_location_id=origin,
        to_location_id=destination_id,
        elapsed_ms=edge.travel_ms,
        newly_discovered=newly_discovered,
        traversal_tags=edge.traversal_tags,
    )


def travel_route_together(
    runtime,
    actor_ids: list[str] | tuple[str, ...],
    destination_id: str,
) -> tuple[GroupTravelResolution, ...]:
    members, actors, origin = _group_context(runtime, actor_ids)
    if destination_id not in runtime.world_map.locations:
        raise KeyError(destination_id)
    route: list[GroupTravelResolution] = []
    current = origin
    while current != destination_id:
        next_hop = _next_group_hop(runtime, actors, current, destination_id)
        if next_hop is None:
            break
        resolution = travel_together(runtime, members, next_hop)
        route.append(resolution)
        current = resolution.to_location_id
    if current != destination_id:
        raise RuntimeError(f"routed group travel stopped before destination: {current} -> {destination_id}")
    return tuple(route)


def complete_routed_travel_within_window(
    runtime,
    actor_ids: list[str] | tuple[str, ...],
    destination_id: str,
    *,
    started_at_ms: int,
    completed_at_ms: int | None = None,
) -> RoutedTravelWindowResolution:
    """Commit off-screen travel that occurred concurrently during an already elapsed world-time window.

    The move still has to fit the current world graph and access rules. This function never creates
    extra time: callers must identify the historical start of the concurrent movement, and the graph's
    minimum route duration must fit between that timestamp and the committed completion timestamp.
    """

    members, actors, origin = _group_context(runtime, actor_ids)
    if destination_id not in runtime.world_map.locations:
        raise KeyError(destination_id)
    end_ms = runtime.world.now_ms if completed_at_ms is None else completed_at_ms
    if started_at_ms < 0 or end_ms < started_at_ms:
        raise ValueError("concurrent travel window is invalid")
    if end_ms > runtime.world.now_ms:
        raise ValueError("concurrent travel cannot complete after current world time")

    planned: list[tuple[str, str, object]] = []
    current = origin
    minimum_elapsed_ms = 0
    while current != destination_id:
        next_hop = _next_group_hop(runtime, actors, current, destination_id)
        if next_hop is None:
            break
        edge = _direct_edge(runtime, current, next_hop)
        planned.append((current, next_hop, edge))
        minimum_elapsed_ms += edge.travel_ms
        current = next_hop
    if current != destination_id:
        raise RuntimeError(f"concurrent route stopped before destination: {current} -> {destination_id}")
    if minimum_elapsed_ms > end_ms - started_at_ms:
        raise ValueError(
            f"concurrent route needs {minimum_elapsed_ms} ms but only {end_ms - started_at_ms} ms elapsed"
        )

    route: list[GroupTravelResolution] = []
    for from_location_id, to_location_id, edge in planned:
        newly_discovered = _commit_group_destination(runtime, members, actors, to_location_id)
        route.append(
            GroupTravelResolution(
                actor_ids=members,
                from_location_id=from_location_id,
                to_location_id=to_location_id,
                elapsed_ms=edge.travel_ms,
                newly_discovered=newly_discovered,
                traversal_tags=edge.traversal_tags,
            )
        )

    return RoutedTravelWindowResolution(
        actor_ids=members,
        started_at_ms=started_at_ms,
        completed_at_ms=end_ms,
        minimum_elapsed_ms=minimum_elapsed_ms,
        route=tuple(route),
    )
