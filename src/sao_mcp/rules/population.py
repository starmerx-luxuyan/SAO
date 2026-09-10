from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PlayerPopulationSegment(str, Enum):
    FRONTLINE = "frontline"
    PRODUCTION = "production"
    MID_TIER = "mid_tier"
    CASUAL = "casual"


@dataclass(slots=True)
class PopulationCohortState:
    cohort_id: str
    segment: PlayerPopulationSegment
    headcount: int
    floor_number: int
    location_id: str
    average_level: float
    activity: str
    provenance: str = "simulation"

    def __post_init__(self) -> None:
        if not self.cohort_id:
            raise ValueError("population cohort_id must be non-empty")
        if self.headcount < 0:
            raise ValueError("population cohort headcount cannot be negative")
        if not 1 <= self.floor_number <= 100:
            raise ValueError("population cohort floor_number must be between 1 and 100")
        if not self.location_id:
            raise ValueError("population cohort location_id must be non-empty")
        if self.average_level < 1:
            raise ValueError("population cohort average_level must be at least 1")
        if not self.activity:
            raise ValueError("population cohort activity must be non-empty")
        if self.provenance not in {"canon", "canon_inferred", "simulation"}:
            raise ValueError("population cohort provenance must be canon, canon_inferred, or simulation")


class PlayerPopulationState:
    """Authoritative ledger for unmaterialized player cohorts.

    Named/materialized player actors remain ordinary runtime actors. Cohorts represent only the
    background players that are intentionally not materialized one-by-one, so the two populations
    never mirror the same person.
    """

    def __init__(self) -> None:
        self.cohorts: dict[str, PopulationCohortState] = {}
        self.cumulative_deaths = 0

    def add(self, cohort: PopulationCohortState) -> PopulationCohortState:
        if cohort.cohort_id in self.cohorts:
            raise ValueError(f"population cohort already exists: {cohort.cohort_id}")
        self.cohorts[cohort.cohort_id] = cohort
        return cohort

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

        if moved == cohort.headcount:
            cohort.segment = segment
            if activity is not None:
                if not activity:
                    raise ValueError("population cohort activity must be non-empty")
                cohort.activity = activity
            return cohort, None

        if not new_cohort_id:
            raise ValueError("partial population reclassification requires new_cohort_id")
        if new_cohort_id in self.cohorts:
            raise ValueError(f"population cohort already exists: {new_cohort_id}")
        cohort.headcount -= moved
        split = PopulationCohortState(
            cohort_id=new_cohort_id,
            segment=segment,
            headcount=moved,
            floor_number=cohort.floor_number,
            location_id=cohort.location_id,
            average_level=cohort.average_level,
            activity=activity or cohort.activity,
            provenance=cohort.provenance,
        )
        self.cohorts[split.cohort_id] = split
        return cohort, split

    def apply_losses(self, cohort_id: str, deaths: int) -> PopulationCohortState:
        cohort = self.cohorts[cohort_id]
        if deaths <= 0 or deaths > cohort.headcount:
            raise ValueError("population deaths must be positive and cannot exceed cohort headcount")
        cohort.headcount -= deaths
        self.cumulative_deaths += deaths
        return cohort

    def segment_totals(self) -> dict[str, int]:
        totals = {segment.value: 0 for segment in PlayerPopulationSegment}
        for cohort in self.cohorts.values():
            totals[cohort.segment.value] += cohort.headcount
        return totals

    def living_count(self) -> int:
        return sum(cohort.headcount for cohort in self.cohorts.values())

    def dump_state(self) -> dict:
        return {
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
        cohorts: dict[str, PopulationCohortState] = {}
        for cohort_id, row in payload.get("cohorts", {}).items():
            cohort = PopulationCohortState(
                cohort_id=row["cohort_id"],
                segment=PlayerPopulationSegment(row["segment"]),
                headcount=int(row["headcount"]),
                floor_number=int(row["floor_number"]),
                location_id=row["location_id"],
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
        self.cohorts = cohorts
        self.cumulative_deaths = cumulative_deaths
