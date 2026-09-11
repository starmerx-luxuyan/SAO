from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


PLAYER_POPULATION_SCHEMA = "player-population.v2"


class PlayerPopulationSegment(StrEnum):
    FRONTLINE = "frontline"
    PRODUCTION = "production"
    MID_TIER = "mid_tier"
    CASUAL = "casual"


class PopulationMovementStatus(StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"


@dataclass(slots=True)
class PopulationCohortState:
    cohort_id: str
    segment: PlayerPopulationSegment
    headcount: int
    floor_number: int | None
    location_id: str | None
    average_level: float
    activity: str
    provenance: str = "simulation"

    def __post_init__(self) -> None:
        self.segment = PlayerPopulationSegment(self.segment)
        if not self.cohort_id:
            raise ValueError("population cohort_id must be non-empty")
        if self.headcount < 0:
            raise ValueError("population cohort headcount cannot be negative")
        if (self.floor_number is None) != (self.location_id is None):
            raise ValueError("population cohort floor/location must both be settled or both be in transit")
        if self.floor_number is not None and not 1 <= self.floor_number <= 100:
            raise ValueError("population cohort floor_number must be between 1 and 100")
        if self.location_id is not None and not self.location_id:
            raise ValueError("population cohort location_id must be non-empty when settled")
        if self.average_level < 1:
            raise ValueError("population cohort average_level must be at least 1")
        if not self.activity:
            raise ValueError("population cohort activity must be non-empty")
        if self.provenance not in {"canon", "canon_inferred", "simulation"}:
            raise ValueError("population cohort provenance must be canon, canon_inferred, or simulation")

    @property
    def settled(self) -> bool:
        return self.location_id is not None

    def settle(self, *, floor_number: int, location_id: str) -> None:
        if not 1 <= floor_number <= 100 or not location_id:
            raise ValueError("population settlement requires a valid floor and location")
        self.floor_number = floor_number
        self.location_id = location_id

    def depart(self) -> None:
        if not self.settled:
            raise ValueError("population cohort is already in transit")
        self.floor_number = None
        self.location_id = None


@dataclass(slots=True)
class PopulationMovementState:
    cohort_id: str
    target_location_id: str
    reason: str
    created_at_ms: int
    status: PopulationMovementStatus = PopulationMovementStatus.WAITING
    wait_reason: str | None = None
    from_location_id: str | None = None
    next_location_id: str | None = None
    started_at_ms: int | None = None
    due_at_ms: int | None = None
    traversal_tags: tuple[str, ...] = ()
    gate_transfers: int = 0
    revision: int = 0

    def __post_init__(self) -> None:
        self.status = PopulationMovementStatus(self.status)
        if not self.cohort_id or not self.target_location_id or not self.reason:
            raise ValueError("population movement identity, target and reason must be non-empty")
        if self.created_at_ms < 0:
            raise ValueError("population movement creation time cannot be negative")
        if self.status is PopulationMovementStatus.ACTIVE:
            if (
                self.from_location_id is None
                or self.next_location_id is None
                or self.started_at_ms is None
                or self.due_at_ms is None
                or self.due_at_ms <= self.started_at_ms
            ):
                raise ValueError("active population movement requires a complete travel leg")
        elif any(
            value is not None
            for value in (self.from_location_id, self.next_location_id, self.started_at_ms, self.due_at_ms)
        ):
            raise ValueError("waiting population movement cannot contain an active travel leg")
        if self.gate_transfers < 0:
            raise ValueError("population movement gate_transfers cannot be negative")

    @property
    def active(self) -> bool:
        return self.status is PopulationMovementStatus.ACTIVE

    def wait(self, reason: str) -> None:
        if not reason:
            raise ValueError("population movement wait reason must be non-empty")
        if self.active:
            raise ValueError("active population movement cannot become waiting before its leg resolves")
        self.status = PopulationMovementStatus.WAITING
        self.wait_reason = reason
        self.revision += 1

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
            raise ValueError("population movement already has an active travel leg")
        if due_at_ms <= started_at_ms:
            raise ValueError("population movement due time must follow its start")
        self.status = PopulationMovementStatus.ACTIVE
        self.wait_reason = None
        self.from_location_id = from_location_id
        self.next_location_id = next_location_id
        self.started_at_ms = started_at_ms
        self.due_at_ms = due_at_ms
        self.traversal_tags = traversal_tags
        self.revision += 1

    def finish_leg(self) -> None:
        if not self.active:
            raise ValueError("population movement has no active leg")
        self.status = PopulationMovementStatus.WAITING
        self.from_location_id = None
        self.next_location_id = None
        self.started_at_ms = None
        self.due_at_ms = None
        self.traversal_tags = ()
        self.revision += 1

    def record_gate_transfer(self) -> None:
        if self.active:
            raise ValueError("population gate transfer cannot occur during a graph edge")
        self.gate_transfers += 1
        self.wait_reason = None
        self.revision += 1


class PlayerPopulationState:
    """Authoritative ledger for unmaterialized player cohorts only.

    Named/materialized player actors remain ordinary runtime actors. Cohorts never mirror those
    actors. ``registered_total`` is the conservation anchor for the anonymous population:
    registered_total == current cohort headcount + cumulative deaths.
    """

    def __init__(self) -> None:
        self.cohorts: dict[str, PopulationCohortState] = {}
        self.registered_total = 0
        self.cumulative_deaths = 0

    def assert_conservation(self) -> None:
        if self.registered_total < 0 or self.cumulative_deaths < 0:
            raise RuntimeError("population conservation counters cannot be negative")
        living = self.living_count()
        if living + self.cumulative_deaths != self.registered_total:
            raise RuntimeError(
                "background population conservation failed: "
                f"living={living} deaths={self.cumulative_deaths} registered={self.registered_total}"
            )

    def add(self, cohort: PopulationCohortState) -> PopulationCohortState:
        if cohort.cohort_id in self.cohorts:
            raise ValueError(f"population cohort already exists: {cohort.cohort_id}")
        if cohort.headcount <= 0:
            raise ValueError("new population cohort headcount must be positive")
        if not cohort.settled:
            raise ValueError("new population cohorts must begin at a settled world location")
        self.cohorts[cohort.cohort_id] = cohort
        self.registered_total += cohort.headcount
        self.assert_conservation()
        return cohort

    def split(self, cohort_id: str, count: int, new_cohort_id: str) -> PopulationCohortState:
        source = self.cohorts[cohort_id]
        if not source.settled:
            raise ValueError("population cohort must be settled before it can split")
        if count <= 0 or count >= source.headcount:
            raise ValueError("population split count must be positive and smaller than the source cohort")
        if not new_cohort_id or new_cohort_id in self.cohorts:
            raise ValueError("population split requires a new unique cohort_id")
        source.headcount -= count
        split = PopulationCohortState(
            cohort_id=new_cohort_id,
            segment=source.segment,
            headcount=count,
            floor_number=source.floor_number,
            location_id=source.location_id,
            average_level=source.average_level,
            activity=source.activity,
            provenance=source.provenance,
        )
        self.cohorts[new_cohort_id] = split
        self.assert_conservation()
        return split

    def reclassify(
        self,
        cohort_id: str,
        segment: PlayerPopulationSegment,
        *,
        count: int | None = None,
        new_cohort_id: str | None = None,
        activity: str | None = None,
    ) -> tuple[PopulationCohortState, PopulationCohortState | None]:
        cohort = self.cohorts[cohort_id]
        moved = cohort.headcount if count is None else count
        if moved <= 0 or moved > cohort.headcount:
            raise ValueError("population reclassification count must be within the source cohort")
        segment = PlayerPopulationSegment(segment)

        if moved == cohort.headcount:
            cohort.segment = segment
            if activity is not None:
                if not activity:
                    raise ValueError("population cohort activity must be non-empty")
                cohort.activity = activity
            self.assert_conservation()
            return cohort, None

        if not new_cohort_id:
            raise ValueError("partial population reclassification requires new_cohort_id")
        split = self.split(cohort_id, moved, new_cohort_id)
        split.segment = segment
        if activity is not None:
            if not activity:
                raise ValueError("population cohort activity must be non-empty")
            split.activity = activity
        self.assert_conservation()
        return cohort, split

    def reinforce(self, source_cohort_id: str, target_cohort_id: str, count: int) -> tuple[PopulationCohortState, PopulationCohortState]:
        source = self.cohorts[source_cohort_id]
        target = self.cohorts[target_cohort_id]
        if source_cohort_id == target_cohort_id:
            raise ValueError("population reinforcement requires different source and target cohorts")
        if not source.settled or not target.settled:
            raise ValueError("population reinforcement requires settled cohorts")
        if source.location_id != target.location_id:
            raise ValueError("population reinforcement cohorts must be colocated")
        if count <= 0 or count > source.headcount:
            raise ValueError("population reinforcement count must be within the source cohort")
        if source.provenance != target.provenance:
            raise ValueError("population reinforcement cannot merge different provenance classes")
        moved_level_sum = source.average_level * count
        target_level_sum = target.average_level * target.headcount
        source.headcount -= count
        target.headcount += count
        target.average_level = (target_level_sum + moved_level_sum) / target.headcount
        self.assert_conservation()
        return source, target

    def apply_losses(self, cohort_id: str, deaths: int) -> PopulationCohortState:
        cohort = self.cohorts[cohort_id]
        if deaths <= 0 or deaths > cohort.headcount:
            raise ValueError("population deaths must be positive and cannot exceed cohort headcount")
        cohort.headcount -= deaths
        self.cumulative_deaths += deaths
        self.assert_conservation()
        return cohort

    def segment_totals(self) -> dict[str, int]:
        totals = {segment.value: 0 for segment in PlayerPopulationSegment}
        for cohort in self.cohorts.values():
            totals[cohort.segment.value] += cohort.headcount
        return totals

    def living_count(self) -> int:
        return sum(cohort.headcount for cohort in self.cohorts.values())

    def dump_state(self) -> dict:
        self.assert_conservation()
        return {
            "schema": PLAYER_POPULATION_SCHEMA,
            "registered_total": self.registered_total,
            "cohorts": {
                cohort_id: {
                    "cohort_id": cohort.cohort_id,
                    "segment": cohort.segment.value,
                    "headcount": cohort.headcount,
                    "floor_number": cohort.floor_number,
                    "location_id": cohort.location_id,
                    "average_level": cohort.average_level,
                    "activity": cohort.activity,
                    "provenance": cohort.provenance,
                }
                for cohort_id, cohort in self.cohorts.items()
            },
            "cumulative_deaths": self.cumulative_deaths,
        }

    def load_state(self, payload: dict) -> None:
        schema = payload.get("schema")
        if schema not in {None, PLAYER_POPULATION_SCHEMA}:
            if payload.get("cohorts") or payload.get("registered_total") or payload.get("cumulative_deaths"):
                raise ValueError(f"unsupported non-empty player population schema: {schema!r}")
        cohorts: dict[str, PopulationCohortState] = {}
        for cohort_id, row in payload.get("cohorts", {}).items():
            cohort = PopulationCohortState(
                cohort_id=row["cohort_id"],
                segment=PlayerPopulationSegment(row["segment"]),
                headcount=int(row["headcount"]),
                floor_number=(int(row["floor_number"]) if row.get("floor_number") is not None else None),
                location_id=row.get("location_id"),
                average_level=float(row["average_level"]),
                activity=row["activity"],
                provenance=row.get("provenance", "simulation"),
            )
            if cohort.cohort_id != cohort_id:
                raise ValueError(f"population cohort key/id mismatch: {cohort_id}")
            cohorts[cohort_id] = cohort
        cumulative_deaths = int(payload.get("cumulative_deaths", 0))
        if cumulative_deaths < 0:
            raise ValueError("population cumulative_deaths cannot be negative")
        living = sum(cohort.headcount for cohort in cohorts.values())
        if schema is None:
            # v1 had only surviving cohorts + cumulative deaths, so this is an exact conservation reconstruction.
            registered_total = living + cumulative_deaths
        else:
            registered_total = int(payload.get("registered_total", -1))
            if registered_total < 0:
                raise ValueError("population registered_total cannot be negative")
        self.cohorts = cohorts
        self.registered_total = registered_total
        self.cumulative_deaths = cumulative_deaths
        self.assert_conservation()
