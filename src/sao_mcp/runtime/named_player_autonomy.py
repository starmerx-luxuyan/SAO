from __future__ import annotations

from typing import Any

from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.travel import (
    AUTONOMOUS_TRAVEL_RESTRICTION_KEY,
    begin_autonomous_world_transit,
    discover_location,
)


NAMED_PLAYER_AUTONOMY_KEY = "named_player_autonomy"
NAMED_PLAYER_AUTONOMY_SCHEMA = "named-player-autonomy.v1"


def configure_named_player_autonomy(runtime, actor_id: str, raw: dict[str, Any] | None) -> dict[str, Any] | None:
    actor = runtime.actors[actor_id]
    if actor.kind is not EntityKind.PLAYER:
        raise ValueError("named-player autonomy applies only to player actors")
    if raw is None:
        actor.metadata.pop(NAMED_PLAYER_AUTONOMY_KEY, None)
        return None
    if not isinstance(raw, dict):
        raise ValueError("named-player autonomy must be an object")
    allowed = {
        "enabled",
        "route_location_ids",
        "activities",
        "interval_ms",
        "initial_delay_ms",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"named-player autonomy has unknown fields: {sorted(unknown)}")
    route = [str(value) for value in raw.get("route_location_ids", ())]
    if not route:
        raise ValueError("named-player autonomy requires route_location_ids")
    if len(route) != len(set(route)) and len(route) > 2:
        raise ValueError("named-player autonomy route should not repeat locations")
    for location_id in route:
        if location_id not in runtime.world_map.locations:
            raise KeyError(location_id)
        floor = runtime.world_map.locations[location_id].floor_number
        if not runtime.world.floors[floor].unlocked:
            raise ValueError("named-player autonomy route cannot start on a locked floor")
    if actor.location_id not in route:
        raise ValueError("named-player autonomy route must include the actor's current location")
    for current, following in zip(route, route[1:] + route[:1]):
        if current == following:
            continue
        if not any(edge.to_location_id == following for edge in runtime.world_map.adjacency.get(current, ())):
            raise ValueError(f"named-player autonomy route has a non-adjacent leg: {current} -> {following}")
    activities = [str(value).strip() for value in raw.get("activities", ())]
    if not activities or any(not value for value in activities):
        raise ValueError("named-player autonomy requires non-empty activity labels")
    interval_ms = int(raw.get("interval_ms", 90 * 60_000))
    initial_delay_ms = int(raw.get("initial_delay_ms", interval_ms))
    if interval_ms < 60_000 or initial_delay_ms < 0:
        raise ValueError("named-player autonomy interval must be >= 60s and initial delay non-negative")
    route_index = route.index(actor.location_id)
    state = {
        "schema": NAMED_PLAYER_AUTONOMY_SCHEMA,
        "enabled": bool(raw.get("enabled", True)),
        "route_location_ids": route,
        "route_index": route_index,
        "activities": activities,
        "activity_index": 0,
        "current_activity": activities[0],
        "interval_ms": interval_ms,
        "next_action_at_ms": int(runtime.world.now_ms) + initial_delay_ms,
        "transit": None,
        "cycles": 0,
        "history": [],
    }
    actor.metadata[NAMED_PLAYER_AUTONOMY_KEY] = state
    return state


def named_player_autonomy_state(actor) -> dict[str, Any] | None:
    value = actor.metadata.get(NAMED_PLAYER_AUTONOMY_KEY)
    return value if isinstance(value, dict) else None


class NamedPlayerAutonomyController:
    """World-time scheduler for autonomous routines of materialized named players.

    The controller owns no duplicate actor or population state. Routine state stays on the real
    player actor metadata so ordinary SAVE persistence remains authoritative. Movement commits are
    delegated to the existing travel authority instead of creating a second movement subsystem.
    """

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        runtime.register_world_advance_hook(self.resolve_due)

    def _autonomous_rows(self):
        for actor in self.runtime.actors.values():
            state = named_player_autonomy_state(actor)
            if state is not None and state.get("enabled", True):
                yield actor, state

    def _record_activity(self, actor, state: dict[str, Any], event: str, **fields: Any) -> None:
        history = state.setdefault("history", [])
        history.append({"event": event, **fields, "at_ms": int(self.runtime.world.now_ms)})
        if len(history) > 32:
            del history[:-32]

    def _actor_busy(self, actor) -> bool:
        if not actor.alive or actor.metadata.get("permanent_death"):
            return True
        if actor.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:
            return True
        if actor.metadata.get("active_duel_id"):
            return True
        return any(
            encounter.active and actor.actor_id in encounter.participants
            for encounter in self.runtime.encounters.values()
        )

    def _begin_leg(self, actor, state: dict[str, Any], due_at_ms: int) -> None:
        if actor.location_id is None:
            raise RuntimeError("settled named-player routine has no current location")
        route = list(state["route_location_ids"])
        current_index = route.index(actor.location_id)
        next_index = (current_index + 1) % len(route)
        destination_id = route[next_index]
        if destination_id == actor.location_id:
            state["route_index"] = next_index
            state["next_action_at_ms"] = due_at_ms + int(state["interval_ms"])
            return
        edges = [
            edge
            for edge in self.runtime.world_map.adjacency.get(actor.location_id, ())
            if edge.to_location_id == destination_id
        ]
        if not edges:
            raise RuntimeError("named-player routine route stopped being adjacent")
        edge = min(edges, key=lambda row: row.travel_ms)
        origin = begin_autonomous_world_transit(actor)
        state["transit"] = {
            "from_location_id": origin,
            "to_location_id": destination_id,
            "started_at_ms": due_at_ms,
            "due_at_ms": due_at_ms + int(edge.travel_ms),
            "route_index_after": next_index,
        }
        state["next_action_at_ms"] = None
        self._record_activity(
            actor,
            state,
            "travel_started",
            from_location_id=origin,
            to_location_id=destination_id,
            due_at_ms=state["transit"]["due_at_ms"],
        )

    def _finish_leg(self, actor, state: dict[str, Any]) -> None:
        transit = state.get("transit")
        if not isinstance(transit, dict):
            raise RuntimeError("named-player routine has no transit state to finish")
        destination_id = str(transit["to_location_id"])
        discover_location(self.runtime.world, actor, self.runtime.world_map.locations[destination_id])
        state["route_index"] = int(transit["route_index_after"])
        state["transit"] = None
        activities = list(state["activities"])
        activity_index = (int(state.get("activity_index", 0)) + 1) % len(activities)
        state["activity_index"] = activity_index
        state["current_activity"] = activities[activity_index]
        state["cycles"] = int(state.get("cycles", 0)) + 1
        state["next_action_at_ms"] = int(self.runtime.world.now_ms) + int(state["interval_ms"])
        self._record_activity(
            actor,
            state,
            "travel_completed",
            location_id=destination_id,
            activity=state["current_activity"],
            cycles=state["cycles"],
        )

    def _resolve_action(self, actor, state: dict[str, Any]) -> None:
        if self._actor_busy(actor):
            state["current_activity"] = "occupied"
            state["next_action_at_ms"] = int(self.runtime.world.now_ms) + int(state["interval_ms"])
            self._record_activity(actor, state, "routine_deferred")
            return
        self._begin_leg(actor, state, int(self.runtime.world.now_ms))

    def resolve_due(self, before_ms: int, after_ms: int) -> None:
        for actor, state in list(self._autonomous_rows()):
            transit = state.get("transit")
            if isinstance(transit, dict) and int(transit["due_at_ms"]) <= after_ms:
                if int(transit["due_at_ms"]) != after_ms:
                    raise RuntimeError("named-player autonomy transit boundary was skipped")
                self._finish_leg(actor, state)
                continue
            due = state.get("next_action_at_ms")
            if due is not None and int(due) <= after_ms:
                if int(due) != after_ms:
                    raise RuntimeError("named-player autonomy action boundary was skipped")
                self._resolve_action(actor, state)

    def next_scheduler_boundary(self, target_ms: int, current_boundary: int) -> int:
        now = int(self.runtime.world.now_ms)
        candidates: list[int] = []
        for _, state in self._autonomous_rows():
            transit = state.get("transit")
            if isinstance(transit, dict):
                due = int(transit["due_at_ms"])
            else:
                next_action = state.get("next_action_at_ms")
                if next_action is None:
                    continue
                due = int(next_action)
            if now < due <= target_ms:
                candidates.append(due)
        return min([current_boundary, *candidates]) if candidates else current_boundary


def install_named_player_autonomy(runtime) -> NamedPlayerAutonomyController:
    existing = getattr(runtime, "named_player_autonomy", None)
    if isinstance(existing, NamedPlayerAutonomyController):
        return existing
    return NamedPlayerAutonomyController(runtime)
