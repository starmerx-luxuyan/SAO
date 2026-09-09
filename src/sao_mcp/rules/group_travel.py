from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import CursorColor, EntityKind
from sao_mcp.rules.access import require_location_access
from sao_mcp.rules.quests import QuestObjectiveKind


@dataclass(slots=True, frozen=True)
class GroupTravelResolution:
    actor_ids: tuple[str, ...]
    from_location_id: str
    to_location_id: str
    elapsed_ms: int
    newly_discovered: bool
    traversal_tags: tuple[str, ...] = ()


def group_travel_record(resolution: GroupTravelResolution) -> dict:
    return {
        "actor_ids": list(resolution.actor_ids),
        "from_location_id": resolution.from_location_id,
        "to_location_id": resolution.to_location_id,
        "elapsed_ms": resolution.elapsed_ms,
        "newly_discovered": resolution.newly_discovered,
        "traversal_tags": list(resolution.traversal_tags),
    }


def travel_together(runtime, actor_ids: list[str] | tuple[str, ...], destination_id: str) -> GroupTravelResolution:
    members = tuple(actor_ids)
    if not members:
        raise ValueError("group travel requires at least one actor")
    if len(set(members)) != len(members):
        raise ValueError("group travel actor_ids must be unique")

    actors = [runtime.actors[actor_id] for actor_id in members]
    if any(not actor.alive for actor in actors):
        raise ValueError("all group travellers must be alive")
    if any(actor.location_id is None for actor in actors):
        raise ValueError("all group travellers must have a current world location")

    origins = {actor.location_id for actor in actors}
    if len(origins) != 1:
        raise ValueError("all group travellers must be colocated")
    origin = actors[0].location_id

    if any(actor.metadata.get("active_duel_id") for actor in actors):
        raise ValueError("group travel is unavailable while a traveller has an active duel")

    member_ids = set(members)
    for encounter in runtime.encounters.values():
        if not member_ids.intersection(encounter.participants):
            continue
        living_outsiders = [
            actor_id
            for actor_id, participant in encounter.participants.items()
            if actor_id not in member_ids
            and participant.alive
            and participant.location_id == origin
        ]
        if living_outsiders:
            raise ValueError("group travel is unavailable while a live encounter has surviving colocated outsiders")

    if destination_id not in runtime.world_map.locations:
        raise KeyError(destination_id)
    destination = runtime.world_map.locations[destination_id]
    floor = runtime.world.floors[destination.floor_number]
    if not floor.unlocked:
        raise ValueError("destination floor is not unlocked")
    if destination.safe_zone and any(actor.cursor is CursorColor.ORANGE for actor in actors):
        raise ValueError("Anti-Criminal Code settlement access is blocked for Orange Players")
    for actor in actors:
        require_location_access(actor, destination_id)

    candidates = [
        edge
        for edge in runtime.world_map.adjacency.get(origin, ())
        if edge.to_location_id == destination_id
    ]
    if not candidates:
        raise ValueError("destination is not directly connected to the group's current location")
    edge = min(candidates, key=lambda value: value.travel_ms)

    newly_discovered = destination_id not in floor.discovered_locations
    runtime.advance_world(edge.travel_ms)
    floor.discovered_locations.add(destination_id)
    for actor in actors:
        actor.location_id = destination_id
        if actor.kind is EntityKind.PLAYER:
            runtime.quests.record_event(
                actor.actor_id,
                kind=QuestObjectiveKind.DISCOVER,
                target_id=destination_id,
            )

    return GroupTravelResolution(
        actor_ids=members,
        from_location_id=origin,
        to_location_id=destination_id,
        elapsed_ms=edge.travel_ms,
        newly_discovered=newly_discovered,
        traversal_tags=edge.traversal_tags,
    )
