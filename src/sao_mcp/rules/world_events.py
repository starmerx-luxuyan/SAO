from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class WorldEventStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    RESOLVED = "resolved"
    SKIPPED = "skipped"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


TERMINAL_WORLD_EVENT_STATUSES = frozenset(
    {
        WorldEventStatus.RESOLVED,
        WorldEventStatus.SKIPPED,
        WorldEventStatus.FAILED,
        WorldEventStatus.INTERRUPTED,
    }
)


@dataclass(slots=True, frozen=True)
class WorldEventResult:
    status: WorldEventStatus
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorldEventOccurrence:
    occurrence_id: str
    rule_id: str
    status: WorldEventStatus
    created_at_ms: int
    expected_at_ms: int | None = None
    triggered_at_ms: int | None = None
    resolved_at_ms: int | None = None
    started_early: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


class WorldEventLedger:
    """Persistent event lifecycle; executable rule callbacks stay runtime-only."""

    def __init__(self) -> None:
        self.occurrences: dict[str, WorldEventOccurrence] = {}
        self.history: list[dict[str, Any]] = []

    @staticmethod
    def _validate_id(value: str, label: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError(f"world-event {label} is required")
        return clean

    @staticmethod
    def _validate_time(value: int | None, label: str) -> None:
        if value is not None and value < 0:
            raise ValueError(f"world-event {label} cannot be negative")

    def _append_history(self, occurrence: WorldEventOccurrence, transitioned_at_ms: int) -> None:
        row = asdict(occurrence)
        row["transitioned_at_ms"] = transitioned_at_ms
        self.history.append(row)

    def plan(
        self,
        *,
        occurrence_id: str,
        rule_id: str,
        created_at_ms: int,
        expected_at_ms: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorldEventOccurrence:
        occurrence_id = self._validate_id(occurrence_id, "occurrence id")
        rule_id = self._validate_id(rule_id, "rule id")
        self._validate_time(created_at_ms, "creation time")
        self._validate_time(expected_at_ms, "expected time")
        if occurrence_id in self.occurrences:
            raise ValueError(f"world-event occurrence already exists: {occurrence_id}")
        if payload is not None and not isinstance(payload, dict):
            raise TypeError("world-event payload must be a dict")
        occurrence = WorldEventOccurrence(
            occurrence_id=occurrence_id,
            rule_id=rule_id,
            status=WorldEventStatus.PENDING,
            created_at_ms=created_at_ms,
            expected_at_ms=expected_at_ms,
            payload=dict(payload or {}),
        )
        self.occurrences[occurrence_id] = occurrence
        self._append_history(occurrence, created_at_ms)
        return occurrence

    def record_resolved(
        self,
        *,
        occurrence_id: str,
        rule_id: str,
        triggered_at_ms: int,
        resolved_at_ms: int,
        payload: dict[str, Any],
        expected_at_ms: int | None = None,
    ) -> WorldEventOccurrence:
        occurrence_id = self._validate_id(occurrence_id, "occurrence id")
        rule_id = self._validate_id(rule_id, "rule id")
        self._validate_time(triggered_at_ms, "trigger time")
        self._validate_time(resolved_at_ms, "resolution time")
        self._validate_time(expected_at_ms, "expected time")
        if occurrence_id in self.occurrences:
            raise ValueError(f"world-event occurrence already exists: {occurrence_id}")
        if resolved_at_ms < triggered_at_ms:
            raise ValueError("world-event resolution time cannot precede its trigger")
        if not isinstance(payload, dict):
            raise TypeError("world-event payload must be a dict")
        occurrence = WorldEventOccurrence(
            occurrence_id=occurrence_id,
            rule_id=rule_id,
            status=WorldEventStatus.RESOLVED,
            created_at_ms=triggered_at_ms,
            expected_at_ms=expected_at_ms,
            triggered_at_ms=triggered_at_ms,
            resolved_at_ms=resolved_at_ms,
            started_early=expected_at_ms is not None and triggered_at_ms < expected_at_ms,
            payload=dict(payload),
        )
        self.occurrences[occurrence_id] = occurrence
        self._append_history(occurrence, resolved_at_ms)
        return occurrence

    def transition(
        self,
        occurrence_id: str,
        status: WorldEventStatus,
        *,
        at_ms: int,
        triggered_at_ms: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorldEventOccurrence:
        self._validate_time(at_ms, "transition time")
        self._validate_time(triggered_at_ms, "trigger time")
        occurrence = self.occurrences[occurrence_id]
        current = occurrence.status
        allowed = {
            WorldEventStatus.PENDING: {
                WorldEventStatus.ACTIVE,
                WorldEventStatus.RESOLVED,
                WorldEventStatus.SKIPPED,
                WorldEventStatus.FAILED,
            },
            WorldEventStatus.ACTIVE: {
                WorldEventStatus.RESOLVED,
                WorldEventStatus.INTERRUPTED,
                WorldEventStatus.FAILED,
            },
        }
        if status not in allowed.get(current, set()):
            raise ValueError(f"illegal world-event transition: {current.value} -> {status.value}")
        if at_ms < occurrence.created_at_ms:
            raise ValueError("world-event transition cannot precede creation")
        if payload is not None and not isinstance(payload, dict):
            raise TypeError("world-event payload must be a dict")

        if current is WorldEventStatus.PENDING:
            if status is WorldEventStatus.ACTIVE:
                occurrence.triggered_at_ms = triggered_at_ms if triggered_at_ms is not None else at_ms
            elif status in {WorldEventStatus.RESOLVED, WorldEventStatus.FAILED}:
                occurrence.triggered_at_ms = triggered_at_ms if triggered_at_ms is not None else at_ms
                occurrence.resolved_at_ms = at_ms
            elif status is WorldEventStatus.SKIPPED:
                occurrence.resolved_at_ms = at_ms
        else:
            if occurrence.triggered_at_ms is None:
                raise RuntimeError("active world-event occurrence has no trigger time")
            occurrence.resolved_at_ms = at_ms

        if occurrence.triggered_at_ms is not None:
            if occurrence.triggered_at_ms < occurrence.created_at_ms:
                raise ValueError("world-event trigger cannot precede creation")
            if occurrence.resolved_at_ms is not None and occurrence.resolved_at_ms < occurrence.triggered_at_ms:
                raise ValueError("world-event resolution cannot precede trigger")
            occurrence.started_early = (
                occurrence.expected_at_ms is not None
                and occurrence.triggered_at_ms < occurrence.expected_at_ms
            )
        occurrence.status = status
        if payload:
            occurrence.payload.update(payload)
        self._append_history(occurrence, at_ms)
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
            status = WorldEventStatus(row["status"])
            triggered_at_ms = row.get("triggered_at_ms")
            resolved_at_ms = row.get("resolved_at_ms")
            created_at_ms = int(
                row.get(
                    "created_at_ms",
                    triggered_at_ms if triggered_at_ms is not None else resolved_at_ms,
                )
            )
            occurrence = WorldEventOccurrence(
                occurrence_id=row["occurrence_id"],
                rule_id=row["rule_id"],
                status=status,
                created_at_ms=created_at_ms,
                expected_at_ms=(
                    int(row["expected_at_ms"])
                    if row.get("expected_at_ms") is not None
                    else None
                ),
                triggered_at_ms=(int(triggered_at_ms) if triggered_at_ms is not None else None),
                resolved_at_ms=(int(resolved_at_ms) if resolved_at_ms is not None else None),
                started_early=bool(row.get("started_early", False)),
                payload=dict(row.get("payload", {})),
            )
            if occurrence.occurrence_id != occurrence_id:
                raise ValueError("world-event registry key disagrees with occurrence_id")
            if occurrence.created_at_ms < 0:
                raise ValueError("world-event save contains negative creation time")
            if occurrence.triggered_at_ms is not None and occurrence.triggered_at_ms < occurrence.created_at_ms:
                raise ValueError("world-event save trigger precedes creation")
            if occurrence.resolved_at_ms is not None:
                floor = occurrence.triggered_at_ms if occurrence.triggered_at_ms is not None else occurrence.created_at_ms
                if occurrence.resolved_at_ms < floor:
                    raise ValueError("world-event save contains reversed resolution time")
            if status is WorldEventStatus.PENDING and (
                occurrence.triggered_at_ms is not None or occurrence.resolved_at_ms is not None
            ):
                raise ValueError("pending world-event save cannot have trigger/resolution times")
            if status is WorldEventStatus.ACTIVE and (
                occurrence.triggered_at_ms is None or occurrence.resolved_at_ms is not None
            ):
                raise ValueError("active world-event save must have only a trigger time")
            if status in TERMINAL_WORLD_EVENT_STATUSES and occurrence.resolved_at_ms is None:
                raise ValueError("terminal world-event save must have a resolution time")
            occurrence.started_early = (
                occurrence.triggered_at_ms is not None
                and occurrence.expected_at_ms is not None
                and occurrence.triggered_at_ms < occurrence.expected_at_ms
            )
            occurrences[occurrence_id] = occurrence
        self.occurrences = occurrences
        self.history = list(payload.get("history", []))
