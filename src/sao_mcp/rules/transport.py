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
    started_at_ms: int | None = None
    completed_at_ms: int | None = None


def _materialized_npc(runtime, npc_id: str):
    resolver = getattr(runtime, "_materialized_npc_actor", None)
    return resolver(npc_id) if resolver is not None else None


def _npc_location(runtime, npc_id: str) -> str | None:
    materialized = _materialized_npc(runtime, npc_id)
    if materialized is not None:
        return materialized.location_id
    return runtime.npcs.states[npc_id].location_id


def _set_npc_location(runtime, npc_id: str, location_id: str) -> None:
    materialized = _materialized_npc(runtime, npc_id)
    if materialized is not None:
        materialized.location_id = location_id
    else:
        runtime.npcs.states[npc_id].location_id = location_id


def _prepare_transport(
    runtime,
    *,
    transport_id: str,
    actor_ids: list[str] | tuple[str, ...],
    npc_ids: list[str] | tuple[str, ...],
    carrier_actor_id: str | None,
    from_location_id: str,
    to_location_id: str,
    elapsed_ms: int,
    carrier_to_location_id: str | None,
):
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
        if _npc_location(runtime, npc_id) != from_location_id:
            raise ValueError("authorized transport NPCs are not all at the required origin")

    carrier = None
    if carrier_actor_id is not None:
        carrier = runtime.actors[carrier_actor_id]
        if not carrier.alive:
            raise ValueError("authorized transport carrier must be alive")
        if carrier.location_id != from_location_id:
            raise ValueError("authorized transport carrier is not at the required origin")

    return (
        clean_transport_id,
        actors,
        npcs,
        moving_actors,
        carrier,
        carrier_destination_id,
        destination,
    )


def _commit_transport(
    runtime,
    *,
    clean_transport_id: str,
    actors: tuple[str, ...],
    npcs: tuple[str, ...],
    moving_actors,
    carrier,
    carrier_actor_id: str | None,
    carrier_destination_id: str,
    from_location_id: str,
    destination,
    elapsed_ms: int,
    transport_tags: tuple[str, ...],
    started_at_ms: int | None,
    completed_at_ms: int | None,
) -> AuthorizedTransportResolution:
    floor = runtime.world.floors[destination.floor_number]
    newly_discovered = destination.location_id not in floor.discovered_locations
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
        _set_npc_location(runtime, npc_id, destination.location_id)
    if carrier is not None:
        carrier.location_id = carrier_destination_id

    return AuthorizedTransportResolution(
        transport_id=clean_transport_id,
        actor_ids=actors,
        npc_ids=npcs,
        carrier_actor_id=carrier_actor_id,
        from_location_id=from_location_id,
        to_location_id=destination.location_id,
        carrier_to_location_id=carrier_destination_id if carrier_actor_id is not None else None,
        elapsed_ms=elapsed_ms,
        newly_discovered=newly_discovered,
        transport_tags=tuple(transport_tags),
        started_at_ms=started_at_ms,
        completed_at_ms=completed_at_ms,
    )


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
    prepared = _prepare_transport(
        runtime,
        transport_id=transport_id,
        actor_ids=actor_ids,
        npc_ids=npc_ids,
        carrier_actor_id=carrier_actor_id,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        elapsed_ms=elapsed_ms,
        carrier_to_location_id=carrier_to_location_id,
    )
    started_at_ms = runtime.world.now_ms
    runtime.advance_world(elapsed_ms)
    return _commit_transport(
        runtime,
        clean_transport_id=prepared[0],
        actors=prepared[1],
        npcs=prepared[2],
        moving_actors=prepared[3],
        carrier=prepared[4],
        carrier_actor_id=carrier_actor_id,
        carrier_destination_id=prepared[5],
        from_location_id=from_location_id,
        destination=prepared[6],
        elapsed_ms=elapsed_ms,
        transport_tags=transport_tags,
        started_at_ms=started_at_ms,
        completed_at_ms=runtime.world.now_ms,
    )


def authorized_transport_within_window(
    runtime,
    *,
    transport_id: str,
    actor_ids: list[str] | tuple[str, ...],
    npc_ids: list[str] | tuple[str, ...] = (),
    carrier_actor_id: str | None,
    from_location_id: str,
    to_location_id: str,
    elapsed_ms: int,
    started_at_ms: int,
    completed_at_ms: int | None = None,
    carrier_to_location_id: str | None = None,
    transport_tags: tuple[str, ...] = (),
) -> AuthorizedTransportResolution:
    """Commit a special transport that ran concurrently during an already elapsed world-time window."""

    end_ms = runtime.world.now_ms if completed_at_ms is None else completed_at_ms
    if started_at_ms < 0 or end_ms < started_at_ms:
        raise ValueError("authorized transport window is invalid")
    if end_ms > runtime.world.now_ms:
        raise ValueError("authorized transport cannot complete after current world time")
    if elapsed_ms > end_ms - started_at_ms:
        raise ValueError(
            f"authorized transport needs {elapsed_ms} ms but only {end_ms - started_at_ms} ms elapsed"
        )
    prepared = _prepare_transport(
        runtime,
        transport_id=transport_id,
        actor_ids=actor_ids,
        npc_ids=npc_ids,
        carrier_actor_id=carrier_actor_id,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        elapsed_ms=elapsed_ms,
        carrier_to_location_id=carrier_to_location_id,
    )
    return _commit_transport(
        runtime,
        clean_transport_id=prepared[0],
        actors=prepared[1],
        npcs=prepared[2],
        moving_actors=prepared[3],
        carrier=prepared[4],
        carrier_actor_id=carrier_actor_id,
        carrier_destination_id=prepared[5],
        from_location_id=from_location_id,
        destination=prepared[6],
        elapsed_ms=elapsed_ms,
        transport_tags=transport_tags,
        started_at_ms=started_at_ms,
        completed_at_ms=end_ms,
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
        "started_at_ms": resolution.started_at_ms,
        "completed_at_ms": resolution.completed_at_ms,
    }
