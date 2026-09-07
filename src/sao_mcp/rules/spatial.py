from __future__ import annotations

import math
from dataclasses import dataclass

from sao_mcp.domain.models import CombatantState, EncounterState, StatusType


IMMOBILIZING_STATUSES = {StatusType.PARALYSIS, StatusType.STUN}


@dataclass(slots=True, frozen=True)
class MovementResolution:
    actor_id: str
    from_position: tuple[float, float]
    to_position: tuple[float, float]
    distance_m: float
    speed_mps: float
    elapsed_ms: int
    completed: bool
    reason: str | None = None


def distance_between_points(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def actor_distance(encounter: EncounterState, actor_id: str, target_id: str) -> float:
    try:
        a = encounter.positions[actor_id]
        b = encounter.positions[target_id]
    except KeyError as exc:
        raise ValueError("encounter spatial position is missing") from exc
    return distance_between_points(a, b)


def movement_speed_mps(actor: CombatantState) -> float:
    """Simulation movement curve for Aincrad encounter positioning."""
    base = 3.4 + max(0, actor.agility) * 0.035
    slow_multiplier = 1.0
    for status in actor.statuses:
        if status.remaining_ms <= 0:
            continue
        if status.status_type is StatusType.SLOW:
            slow_multiplier *= max(0.35, min(0.95, 1.0 - max(0.0, status.magnitude)))
    return max(1.5, min(9.0, base * slow_multiplier))


def validate_movement_ready(actor: CombatantState, *, now_ms: int) -> None:
    if not actor.alive:
        raise ValueError("defeated actors cannot move")
    if now_ms < actor.committed_until_ms:
        raise ValueError("actor is committed to another action")
    if now_ms < actor.recovery_until_ms:
        raise ValueError("actor is still recovering")
    for status in actor.statuses:
        if status.remaining_ms > 0 and status.status_type in IMMOBILIZING_STATUSES:
            raise ValueError(f"movement is blocked by {status.status_type.value}")


def movement_duration_ms(actor: CombatantState, distance_m: float) -> int:
    if distance_m < 0:
        raise ValueError("distance_m must be >= 0")
    if distance_m == 0:
        return 0
    return max(1, math.ceil(distance_m / movement_speed_mps(actor) * 1000.0))


def validate_destination(encounter: EncounterState, destination: tuple[float, float]) -> None:
    if not all(math.isfinite(value) for value in destination):
        raise ValueError("destination coordinates must be finite")
    if math.hypot(destination[0], destination[1]) > encounter.arena_radius_m:
        raise ValueError("destination is outside the encounter arena")


def default_formation(encounter: EncounterState) -> None:
    """Assign deterministic positions for encounters that did not provide a scenario-specific formation."""
    if encounter.positions:
        return
    players = [
        actor for actor in encounter.participants.values() if actor.kind.value == "player"
    ]
    hostiles = [
        actor for actor in encounter.participants.values() if actor.kind.value != "player"
    ]
    for index, actor in enumerate(players):
        offset = (index - (len(players) - 1) / 2.0) * 1.1
        encounter.positions[actor.actor_id] = (-1.2, offset)
    for index, actor in enumerate(hostiles):
        offset = (index - (len(hostiles) - 1) / 2.0) * 1.2
        encounter.positions[actor.actor_id] = (1.2, offset)


def earliest_pending_execution_ms(encounter: EncounterState) -> int | None:
    deadlines: list[int] = []
    for actor in encounter.participants.values():
        pending = actor.metadata.get("pending_boss_action")
        if pending and "execute_at_ms" in pending:
            deadlines.append(int(pending["execute_at_ms"]))
    return min(deadlines) if deadlines else None
