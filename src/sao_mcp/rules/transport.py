from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import CursorColor, EntityKind
from sao_mcp.rules.access import require_location_access
from sao_mcp.rules.quests import QuestObjectiveKind


@dataclass(slots=True, frozen=True)
class AuthorizedTransportResolution:
    transport_id: str
    actor_ids: tuple[str, ...]
    npc_ids: tuple[str, ...]
    carrier_actor_id: str | None
    from_location_id: str
    to_location_id: str
    carrier_to_location_id: str | None
    elapsed_ms: int
    newly_discovered: bool
    transport_tags: tuple[str, ...] = ()


def authorized_transport(
    runtime,
    *,
    transport_id: str,
    actor_ids: list[str] | tuple[str, ...],
    npc_ids: list[str] | tuple[str, ...] = (),
    carrier_actor_id: str | None,
    from_location_id: str,
    to_location_id: str,
    elapsed_ms: int,
    carrier_to_location_id: str | None = None,
    transport_tags: tuple[str, ...] = (),
) -> AuthorizedTransportResolution:
    clean_transport_id = transport_id.strip()
    if not clean_transport_id:
        raise ValueError("authorized transport requires a transport_id")
    actors = tuple(actor_ids)
    npcs = tuple(npc_ids)
    if len(set(actors)) != len(actors):
        raise ValueError("authorized transport actor_ids must be unique")
    if len(set(npcs)) != len(npcs):
        raise ValueError("authorized transport npc_ids must be unique")
    if carrier_actor_id is not None and carrier_actor_id in actors:
        raise ValueError("authorized transport carrier must not be duplicated in actor_ids")
    if not actors and not npcs and carrier_actor_id is None:
        raise ValueError("authorized transport requires at least one mover")
    if elapsed_ms < 1:
        raise ValueError("authorized transport elapsed_ms must be positive")
    if from_location_id not in runtime.world_map.locations:
        raise KeyError(from_location_id)
    if to_location_id not in runtime.world_map.locations:
        raise KeyError(to_location_id)
    carrier_destination_id = carrier_to_location_id or to_location_id
    if carrier_actor_id is not None and carrier_destination_id not in runtime.world_map.locations:
        raise KeyError(carrier_destination_id)

    destination = runtime.world_map.locations[to_location_id]
    if not runtime.world.floors[destination.floor_number].unlocked:
        raise ValueError("authorized transport destination floor is not unlocked")

    moving_actors = [runtime.actors[actor_id] for actor_id in actors]
    if any(not actor.alive for actor in moving_actors):
        raise ValueError("authorized transport actors must be alive")
    if any(actor.location_id != from_location_id for actor in moving_actors):
        raise ValueError("authorized transport actors are not all at the required origin")
    if destination.safe_zone and any(actor.cursor is CursorColor.ORANGE for actor in moving_actors):
        raise ValueError("Anti-Criminal Code settlement access is blocked for Orange Players")
    for actor in moving_actors:
        require_location_access(actor, to_location_id)

    for npc_id in npcs:
        if npc_id not in runtime.npcs.states:
            raise KeyError(npc_id)
        if runtime.npcs.states[npc_id].location_id != from_location_id:
            raise ValueError("authorized transport NPCs are not all at the required origin")

    carrier = None
    if carrier_actor_id is not None:
        carrier = runtime.actors[carrier_actor_id]
        if not carrier.alive:
            raise ValueError("authorized transport carrier must be alive")
        if carrier.location_id != from_location_id:
            raise ValueError("authorized transport carrier is not at the required origin")

    floor = runtime.world.floors[destination.floor_number]
    newly_discovered = destination.location_id not in floor.discovered_locations
    runtime.advance_world(elapsed_ms)
    floor.discovered_locations.add(destination.location_id)
    for actor in moving_actors:
        actor.location_id = destination.location_id
        if actor.kind is EntityKind.PLAYER:
            runtime.quests.record_event(
                actor.actor_id,
                kind=QuestObjectiveKind.DISCOVER,
                target_id=destination.location_id,
            )
    for npc_id in npcs:
        runtime.npcs.states[npc_id].location_id = destination.location_id
    if carrier is not None:
        carrier.location_id = carrier_destination_id

    return AuthorizedTransportResolution(
        transport_id=clean_transport_id,
        actor_ids=actors,
        npc_ids=npcs,
        carrier_actor_id=carrier_actor_id,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        carrier_to_location_id=carrier_destination_id if carrier_actor_id is not None else None,
        elapsed_ms=elapsed_ms,
        newly_discovered=newly_discovered,
        transport_tags=tuple(transport_tags),
    )


def authorized_transport_record(resolution: AuthorizedTransportResolution) -> dict:
    return {
        "transport_id": resolution.transport_id,
        "actor_ids": list(resolution.actor_ids),
        "npc_ids": list(resolution.npc_ids),
        "carrier_actor_id": resolution.carrier_actor_id,
        "from_location_id": resolution.from_location_id,
        "to_location_id": resolution.to_location_id,
        "carrier_to_location_id": resolution.carrier_to_location_id,
        "elapsed_ms": resolution.elapsed_ms,
        "newly_discovered": resolution.newly_discovered,
        "transport_tags": list(resolution.transport_tags),
    }
