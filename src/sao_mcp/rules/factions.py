from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import WorldState


FACTION_STANDING_KEY = "faction_standing"
MIN_STANDING = -100
MAX_STANDING = 100


@dataclass(slots=True, frozen=True)
class FactionStandingChange:
    subject_id: str
    faction_id: str
    previous: int
    delta: int
    current: int
    reason: str


def faction_standing(world: WorldState, subject_id: str, faction_id: str) -> int:
    table = world.global_flags.setdefault(FACTION_STANDING_KEY, {})
    faction = table.setdefault(faction_id, {})
    if subject_id not in faction:
        faction[subject_id] = 0
    value = faction[subject_id]
    if not isinstance(value, int):
        raise RuntimeError(
            f"faction standing for {subject_id!r} toward {faction_id!r} is not an integer"
        )
    if value < MIN_STANDING or value > MAX_STANDING:
        raise RuntimeError(
            f"faction standing for {subject_id!r} toward {faction_id!r} is outside the valid range"
        )
    return value


def adjust_faction_standing(
    world: WorldState,
    subject_id: str,
    faction_id: str,
    delta: int,
    *,
    reason: str,
) -> FactionStandingChange:
    if not isinstance(delta, int) or delta == 0:
        raise ValueError("faction-standing delta must be a non-zero integer")
    clean_reason = reason.strip()
    if not clean_reason:
        raise ValueError("faction-standing changes require an explicit reason")
    previous = faction_standing(world, subject_id, faction_id)
    current = max(MIN_STANDING, min(MAX_STANDING, previous + delta))
    world.global_flags[FACTION_STANDING_KEY][faction_id][subject_id] = current
    return FactionStandingChange(subject_id, faction_id, previous, delta, current, clean_reason)
