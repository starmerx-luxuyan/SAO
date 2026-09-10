from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sao_mcp.domain.models import ProvenanceKind


class PopulationBand(StrEnum):
    UNCLASSIFIED = "unclassified"
    FRONTLINE = "frontline"
    PRODUCTION = "production"
    MID_TIER = "mid_tier"
    CASUAL = "casual"
    SHELTERED = "sheltered"


@dataclass(slots=True)
class PopulationCohortState:
    """One aggregate cohort containing only players that are not materialized as actors."""

    cohort_id: str
    band: PopulationBand
    count: int
    location_id: str | None
    average_level: float
    activity: str
    cumulative_deaths: int = 0
    provenance_kind: ProvenanceKind = ProvenanceKind.SIMULATION
    source_ref: str | None = None
    movement_target_location_id: str | None = None
    from_location_id: str | None = None
    next_location_id: str | None = None
    started_at_ms: int | None = None
    due_at_ms: int | None = None
    traversal_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.cohort_id:
            raise ValueError("population cohort_id must be non-empty")
        if self.count < 0:
            raise ValueError("population cohort count cannot be negative")
        if self.average_level < 1:
            raise ValueError("population cohort average_level must be at least 1")
        if not self.activity:
            raise ValueError("population cohort activity must be non-empty")
        if self.cumulative_deaths < 0:
            raise ValueError("population cohort cumulative_deaths cannot be negative")
        if self.provenance_kind is not ProvenanceKind.SIMULATION and not self.source_ref:
            raise ValueError("non-simulation population cohort requires source_ref")

    @property
    def active(self) -> bool:
        return self.next_location_id is not None

    def begin_route(self, target_location_id: str) -> None:
        if self.active or self.movement_target_location_id is not None:
            raise ValueError(f"population cohort {self.cohort_id} already has an active movement order")
        if self.count <= 0:
            raise ValueError("empty population cohort cannot move")
        if self.location_id is None:
            raise RuntimeError("settled population cohort must have a location before movement begins")
        if self.location_id == target_location_id:
            raise ValueError("population cohort is already at the requested destination")
        self.movement_target_location_id = target_location_id

    def begin_leg(
        self,
        *,
        from_location_id: str,
        next_location_id: str,
        started_at_ms: int,
        due_at_ms: int,
        traversal_tags: tuple[str, ...],
    ) -> None:
        if self.active:
            raise ValueError(f"population cohort {self.cohort_id} already has an active movement leg")
        if self.movement_target_location_id is None:
            raise RuntimeError("population movement leg requires an active route order")
        if due_at_ms <= started_at_ms:
            raise ValueError("population movement due time must be after its start time")
        if self.location_id != from_location_id:
            raise RuntimeError("population movement origin disagrees with settled cohort location")
        self.from_location_id = from_location_id
        self.next_location_id = next_location_id
        self.started_at_ms = started_at_ms
        self.due_at_ms = due_at_ms
        self.traversal_tags = traversal_tags
        self.location_id = None

    def finish_leg(self) -> str:
        if not self.active or self.next_location_id is None:
            raise RuntimeError("population cohort has no active movement leg")
        destination_id = self.next_location_id
        self.location_id = destination_id
        self.from_location_id = None
        self.next_location_id = None
        self.started_at_ms = None
        self.due_at_ms = None
        self.traversal_tags = ()
        if destination_id == self.movement_target_location_id:
            self.movement_target_location_id = None
        return destination_id

    def cancel_empty_route(self) -> None:
        if self.count != 0:
            raise ValueError("only an empty population cohort can cancel movement by extinction")
        self.location_id = None
        self.movement_target_location_id = None
        self.from_location_id = None
        self.next_location_id = None
        self.started_at_ms = None
        self.due_at_ms = None
        self.traversal_tags = ()
