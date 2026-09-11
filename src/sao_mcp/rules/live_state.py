from __future__ import annotations

from dataclasses import asdict

from sao_mcp.rules.legal_state import SentenceKind, SentenceStatus


def active_encounter_ids_for_actor(runtime, actor_id: str) -> tuple[str, ...]:
    if actor_id not in runtime.actors:
        raise KeyError(actor_id)
    return tuple(
        sorted(
            encounter_id
            for encounter_id, encounter in runtime.encounters.items()
            if encounter.active and actor_id in encounter.participants
        )
    )


def actor_route_state(runtime, actor_id: str) -> dict | None:
    """Resolve one actor's current autonomous route from live agenda state, never history."""

    if actor_id not in runtime.actors:
        raise KeyError(actor_id)
    matches: list[dict] = []
    actor = runtime.actors[actor_id]

    npc_id = actor.metadata.get("npc_definition_id")
    npc_agendas = getattr(runtime, "npc_agendas", {})
    if isinstance(npc_id, str):
        agenda = npc_agendas.get(npc_id)
        if agenda is not None and agenda.active and agenda.activity_kind == "travel":
            matches.append(
                {
                    "kind": "npc_travel",
                    "owner_id": npc_id,
                    "actor_ids": [actor_id],
                    "from_location_id": agenda.from_location_id,
                    "to_location_id": agenda.target_location_id,
                    "started_at_ms": agenda.started_at_ms,
                    "due_at_ms": agenda.due_at_ms,
                    "traversal_tags": list(agenda.traversal_tags),
                }
            )

    guild_agendas = getattr(runtime, "guild_agendas", {})
    for guild_id, agenda in guild_agendas.items():
        if agenda.active and actor_id in agenda.assigned_member_ids:
            matches.append(
                {
                    "kind": "guild_travel",
                    "owner_id": guild_id,
                    "actor_ids": list(agenda.assigned_member_ids),
                    "from_location_id": agenda.from_location_id,
                    "to_location_id": agenda.next_location_id,
                    "started_at_ms": agenda.started_at_ms,
                    "due_at_ms": agenda.due_at_ms,
                    "traversal_tags": list(agenda.traversal_tags),
                }
            )

    if len(matches) > 1:
        raise RuntimeError(f"actor {actor_id} has multiple active route authorities")
    return matches[0] if matches else None


def custody_state(runtime, actor_id: str) -> dict | None:
    state = runtime.legal.custody_for(actor_id)
    return asdict(state) if state is not None else None


def sentence_state(runtime, actor_id: str) -> dict | None:
    state = runtime.legal.sentence_for(actor_id)
    return asdict(state) if state is not None else None


def _has_direct_edge(runtime, from_location_id: str, to_location_id: str) -> bool:
    return any(
        edge.to_location_id == to_location_id
        for edge in runtime.world_map.adjacency.get(from_location_id, ())
    )


def assert_runtime_live_state(runtime) -> None:
    """Validate encounter clocks/lifecycle, routes, custody and unresolved sentences."""

    now = runtime.world.now_ms
    if not isinstance(now, int) or isinstance(now, bool) or now < 0:
        raise RuntimeError("world clock must be a non-negative integer")
    scheduler_assert = getattr(runtime, "_assert_npc_scheduler_authority", None)
    if scheduler_assert is not None:
        scheduler_assert()

    active_actor_encounter: dict[str, str] = {}
    for encounter_id, encounter in runtime.encounters.items():
        if encounter.encounter_id != encounter_id:
            raise RuntimeError(f"encounter registry key disagrees with encounter_id: {encounter_id}")
        if encounter.world_started_at_ms < 0 or encounter.time_ms < 0:
            raise RuntimeError(f"encounter {encounter_id} has negative time state")
        absolute_ms = encounter.world_started_at_ms + encounter.time_ms
        if absolute_ms > now:
            raise RuntimeError(f"encounter {encounter_id} clock is ahead of world time")
        if encounter.active:
            if encounter.ended_at_world_ms is not None or encounter.end_reason is not None:
                raise RuntimeError(f"active encounter {encounter_id} contains end-state fields")
        else:
            if encounter.ended_at_world_ms is None or not encounter.end_reason:
                raise RuntimeError(f"ended encounter {encounter_id} lacks end time or reason")
            if encounter.ended_at_world_ms < absolute_ms or encounter.ended_at_world_ms > now:
                raise RuntimeError(f"encounter {encounter_id} has invalid end time")
        for actor_id, participant in encounter.participants.items():
            if runtime.actors.get(actor_id) is not participant:
                raise RuntimeError(f"encounter {encounter_id} participant {actor_id} is not the authoritative actor object")
            if encounter.active:
                previous = active_actor_encounter.setdefault(actor_id, encounter_id)
                if previous != encounter_id:
                    raise RuntimeError(f"actor {actor_id} belongs to multiple active encounters: {previous}, {encounter_id}")
                if participant.location_id is None:
                    raise RuntimeError(f"active encounter participant {actor_id} has no settled location")
                if participant.location_id != encounter.zone_id:
                    raise RuntimeError(
                        f"active encounter participant {actor_id} is at {participant.location_id}, not {encounter.zone_id}"
                    )
        for event in encounter.events:
            if event.time_ms < 0 or event.time_ms > encounter.time_ms:
                raise RuntimeError(f"encounter {encounter_id} contains an event outside its current relative clock")

    route_actor: dict[str, str] = {}
    npc_agendas = getattr(runtime, "npc_agendas", {})
    for npc_id, agenda in npc_agendas.items():
        if not agenda.active:
            continue
        if agenda.activity_kind != "travel":
            if agenda.stationary_location_id not in runtime.world_map.locations:
                raise RuntimeError(f"NPC {npc_id} stationary activity references an unknown location")
            if agenda.started_at_ms is None or agenda.due_at_ms is None or not (agenda.started_at_ms <= now < agenda.due_at_ms):
                raise RuntimeError(f"NPC {npc_id} has invalid stationary-activity timing")
            resolver = getattr(runtime, "_materialized_npc_actor", None)
            materialized = resolver(npc_id) if resolver is not None else None
            if materialized is not None and materialized.location_id != agenda.stationary_location_id:
                raise RuntimeError(f"NPC {npc_id} stationary activity actor is not at its settled location")
            continue
        if agenda.from_location_id not in runtime.world_map.locations or agenda.target_location_id not in runtime.world_map.locations:
            raise RuntimeError(f"NPC {npc_id} active route references an unknown location")
        if not _has_direct_edge(runtime, agenda.from_location_id, agenda.target_location_id):
            raise RuntimeError(f"NPC {npc_id} active route is not a world-graph edge")
        if agenda.started_at_ms is None or agenda.due_at_ms is None or not (agenda.started_at_ms <= now < agenda.due_at_ms):
            raise RuntimeError(f"NPC {npc_id} has invalid active-route timing")
        resolver = getattr(runtime, "_materialized_npc_actor", None)
        materialized = resolver(npc_id) if resolver is not None else None
        if materialized is not None:
            if materialized.location_id is not None:
                raise RuntimeError(f"travelling NPC {npc_id} has a settled location")
            route_actor[materialized.actor_id] = f"npc:{npc_id}"

    guild_agendas = getattr(runtime, "guild_agendas", {})
    for guild_id, agenda in guild_agendas.items():
        if not agenda.active:
            continue
        if agenda.activity_kind != "travel":
            raise RuntimeError(f"guild {guild_id} has unsupported active activity {agenda.activity_kind!r}")
        if agenda.from_location_id not in runtime.world_map.locations or agenda.next_location_id not in runtime.world_map.locations:
            raise RuntimeError(f"guild {guild_id} active route references an unknown location")
        if not _has_direct_edge(runtime, agenda.from_location_id, agenda.next_location_id):
            raise RuntimeError(f"guild {guild_id} active route is not a world-graph edge")
        if agenda.started_at_ms is None or agenda.due_at_ms is None or not (agenda.started_at_ms <= now < agenda.due_at_ms):
            raise RuntimeError(f"guild {guild_id} has invalid active-route timing")
        for actor_id in agenda.assigned_member_ids:
            actor = runtime.actors[actor_id]
            if actor.location_id is not None:
                raise RuntimeError(f"travelling guild member {actor_id} has a settled location")
            previous = route_actor.setdefault(actor_id, f"guild:{guild_id}")
            if previous != f"guild:{guild_id}":
                raise RuntimeError(f"actor {actor_id} has multiple active route authorities")

    for actor_id, route_owner in route_actor.items():
        if actor_id in active_actor_encounter:
            raise RuntimeError(f"actor {actor_id} is both in active encounter and active route")
        if runtime.legal.custody_for(actor_id) is not None:
            raise RuntimeError(f"actor {actor_id} is both in custody and active route")

    for actor_id, custody in runtime.legal.custody_by_actor.items():
        if custody.actor_id != actor_id or actor_id not in runtime.actors:
            raise RuntimeError(f"custody registry is inconsistent for actor {actor_id}")
        if custody.started_at_ms > now:
            raise RuntimeError(f"custody for {actor_id} starts after current world time")
        if runtime.actors[actor_id].location_id is None:
            raise RuntimeError(f"actor {actor_id} is in custody without a settled location")
        if actor_id in route_actor:
            raise RuntimeError(f"actor {actor_id} is both in custody and active route")

    for actor_id, sentence in runtime.legal.sentence_by_actor.items():
        if sentence.actor_id != actor_id or actor_id not in runtime.actors:
            raise RuntimeError(f"sentence registry is inconsistent for actor {actor_id}")
        if sentence.issued_at_ms > now:
            raise RuntimeError(f"sentence for {actor_id} was issued after current world time")
        custody = runtime.legal.custody_for(actor_id)
        if custody is None:
            raise RuntimeError(f"unresolved sentence for {actor_id} has no active custody")
        if sentence.case_id != custody.case_id:
            raise RuntimeError(f"sentence/custody case mismatch for {actor_id}")
        if sentence.kind is SentenceKind.IMPRISONMENT:
            if sentence.status is SentenceStatus.ACTIVE:
                if sentence.started_at_ms is None or sentence.release_at_ms is None:
                    raise RuntimeError(f"active imprisonment for {actor_id} lacks timing")
                if sentence.started_at_ms < sentence.issued_at_ms or sentence.release_at_ms <= sentence.started_at_ms:
                    raise RuntimeError(f"active imprisonment for {actor_id} has invalid timing")
            elif sentence.started_at_ms is not None or sentence.release_at_ms is not None:
                raise RuntimeError(f"ordered imprisonment for {actor_id} already contains enforcement timing")
        elif sentence.status is not SentenceStatus.ORDERED:
            raise RuntimeError(f"execution order for {actor_id} cannot enter imprisonment-active status")

    for row in runtime.legal.history:
        at_ms = row.get("at_ms")
        if not isinstance(at_ms, int) or isinstance(at_ms, bool) or at_ms < 0 or at_ms > now:
            raise RuntimeError("legal history event has invalid world time")
