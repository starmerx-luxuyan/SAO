from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class WorldEventStatus(StrEnum):
    RESOLVED = "resolved"


@dataclass(slots=True)
class WorldEventOccurrence:
    occurrence_id: str
    rule_id: str
    status: WorldEventStatus
    triggered_at_ms: int
    resolved_at_ms: int
    payload: dict[str, Any] = field(default_factory=dict)


class WorldEventLedger:
    """Persistent outcomes for world events; executable rule callbacks stay runtime-only."""

    def __init__(self) -> None:
        self.occurrences: dict[str, WorldEventOccurrence] = {}
        self.history: list[dict[str, Any]] = []

    def record_resolved(
        self,
        *,
        occurrence_id: str,
        rule_id: str,
        triggered_at_ms: int,
        resolved_at_ms: int,
        payload: dict[str, Any],
    ) -> WorldEventOccurrence:
        if not occurrence_id or not rule_id:
            raise ValueError("world-event occurrence and rule ids are required")
        if occurrence_id in self.occurrences:
            raise ValueError(f"world-event occurrence already exists: {occurrence_id}")
        if triggered_at_ms < 0 or resolved_at_ms < triggered_at_ms:
            raise ValueError("world-event resolution time cannot precede its trigger")
        if not isinstance(payload, dict):
            raise TypeError("world-event payload must be a dict")
        occurrence = WorldEventOccurrence(
            occurrence_id=occurrence_id,
            rule_id=rule_id,
            status=WorldEventStatus.RESOLVED,
            triggered_at_ms=triggered_at_ms,
            resolved_at_ms=resolved_at_ms,
            payload=dict(payload),
        )
        self.occurrences[occurrence_id] = occurrence
        self.history.append(asdict(occurrence))
        return occurrence

    def dump_state(self) -> dict[str, Any]:
        return {
            "occurrences": {
                occurrence_id: asdict(occurrence)
                for occurrence_id, occurrence in self.occurrences.items()
            },
            "history": list(self.history),
        }

    def load_state(self, payload: dict[str, Any]) -> None:
        occurrences: dict[str, WorldEventOccurrence] = {}
        for occurrence_id, row in payload.get("occurrences", {}).items():
            occurrence = WorldEventOccurrence(
                occurrence_id=row["occurrence_id"],
                rule_id=row["rule_id"],
                status=WorldEventStatus(row["status"]),
                triggered_at_ms=int(row["triggered_at_ms"]),
                resolved_at_ms=int(row["resolved_at_ms"]),
                payload=dict(row.get("payload", {})),
            )
            if occurrence.occurrence_id != occurrence_id:
                raise ValueError("world-event registry key disagrees with occurrence_id")
            if occurrence.resolved_at_ms < occurrence.triggered_at_ms:
                raise ValueError("world-event save contains reversed trigger/resolution time")
            occurrences[occurrence_id] = occurrence
        history = list(payload.get("history", []))
        self.occurrences = occurrences
        self.history = history
