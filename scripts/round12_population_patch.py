from pathlib import Path

POPULATION_RULES = r'''from __future__ import annotations

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
'''

POPULATION_RUNTIME = r'''from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.population import (
    PlayerPopulationSegment,
    PlayerPopulationState,
    PopulationCohortState,
    PopulationMovementState,
    PopulationMovementStatus,
)
from sao_mcp.rules.routing import shortest_route
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


POPULATION_RUNTIME_SCHEMA = "population-runtime.v2"


class PopulationAincradRuntime(HousingAincradRuntime):
    """Authoritative coarse background-player population with world-time migration."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.population = PlayerPopulationState()
        self.population_movements: dict[str, PopulationMovementState] = {}
        self.population_history: list[dict[str, Any]] = []
        self.register_world_advance_hook(self._resolve_due_population_activities)

    def _movement(self, cohort_id: str) -> PopulationMovementState | None:
        return self.population_movements.get(cohort_id)

    def _active_population_gates(self, floor_number: int) -> list[str]:
        floor = self.world.floors[floor_number]
        if not floor.unlocked or not floor.main_town_gate_active:
            return []
        return sorted(
            location_id
            for location_id, location in self.world_map.locations.items()
            if location.floor_number == floor_number and location.teleport_gate
        )

    def _route(self, origin: str, target: str) -> tuple[tuple[str, ...], int]:
        return shortest_route(self.world, self.world_map, origin, target)

    def _best_gate_from(self, origin: str, floor_number: int) -> tuple[str, tuple[str, ...], int] | None:
        choices: list[tuple[int, str, tuple[str, ...]]] = []
        for gate_id in self._active_population_gates(floor_number):
            try:
                path, cost = self._route(origin, gate_id)
            except ValueError:
                continue
            choices.append((cost, gate_id, path))
        if not choices:
            return None
        cost, gate_id, path = min(choices)
        return gate_id, path, cost

    def _best_gate_to_target(self, floor_number: int, target_location_id: str) -> tuple[str, tuple[str, ...], int] | None:
        choices: list[tuple[int, str, tuple[str, ...]]] = []
        for gate_id in self._active_population_gates(floor_number):
            try:
                path, cost = self._route(gate_id, target_location_id)
            except ValueError:
                continue
            choices.append((cost, gate_id, path))
        if not choices:
            return None
        cost, gate_id, path = min(choices)
        return gate_id, path, cost

    def _edge(self, from_location_id: str, to_location_id: str):
        edges = [
            edge
            for edge in self.world_map.adjacency.get(from_location_id, ())
            if edge.to_location_id == to_location_id
        ]
        if not edges:
            raise RuntimeError("population route selected a non-adjacent world edge")
        return min(edges, key=lambda edge: edge.travel_ms)

    def _record_population_event(self, event: str, **fields: Any) -> None:
        self.population_history.append({"event": event, **fields, "at_ms": self.world.now_ms})

    def add_population_cohort(
        self,
        cohort_id: str,
        segment: PlayerPopulationSegment | str,
        headcount: int,
        location_id: str,
        average_level: float,
        activity: str,
        *,
        provenance: str = "simulation",
    ) -> PopulationCohortState:
        if location_id not in self.world_map.locations:
            raise KeyError(location_id)
        location = self.world_map.locations[location_id]
        if not self.world.floors[location.floor_number].unlocked:
            raise ValueError("population cohort location floor is not unlocked")
        cohort = PopulationCohortState(
            cohort_id=cohort_id,
            segment=PlayerPopulationSegment(segment),
            headcount=headcount,
            floor_number=location.floor_number,
            location_id=location_id,
            average_level=average_level,
            activity=activity,
            provenance=provenance,
        )
        self.population.add(cohort)
        self._record_population_event(
            "cohort_added",
            cohort_id=cohort_id,
            segment=cohort.segment.value,
            headcount=headcount,
            location_id=location_id,
        )
        return cohort

    def reclassify_population_cohort(
        self,
        cohort_id: str,
        segment: PlayerPopulationSegment | str,
        *,
        count: int | None = None,
        new_cohort_id: str | None = None,
        activity: str | None = None,
    ) -> tuple[PopulationCohortState, PopulationCohortState | None]:
        movement = self._movement(cohort_id)
        if movement is not None and movement.active:
            raise ValueError("in-transit population cohort cannot be reclassified")
        if movement is not None and count is not None and count != self.population.cohorts[cohort_id].headcount:
            raise ValueError("population cohort with a movement plan cannot be partially reclassified")
        source_before = self.population.cohorts[cohort_id]
        before_segment = source_before.segment.value
        moved = source_before.headcount if count is None else count
        source, split = self.population.reclassify(
            cohort_id,
            PlayerPopulationSegment(segment),
            count=count,
            new_cohort_id=new_cohort_id,
            activity=activity,
        )
        self._record_population_event(
            "cohort_reclassified",
            source_cohort_id=cohort_id,
            new_cohort_id=split.cohort_id if split is not None else None,
            from_segment=before_segment,
            to_segment=PlayerPopulationSegment(segment).value,
            headcount=moved,
            location_id=source.location_id,
        )
        return source, split

    def reinforce_population_cohort(
        self,
        source_cohort_id: str,
        target_cohort_id: str,
        count: int,
    ) -> tuple[PopulationCohortState, PopulationCohortState]:
        if self._movement(source_cohort_id) is not None or self._movement(target_cohort_id) is not None:
            raise ValueError("population reinforcement cannot mutate a cohort with a movement plan")
        source = self.population.cohorts[source_cohort_id]
        target = self.population.cohorts[target_cohort_id]
        from_segment = source.segment.value
        to_segment = target.segment.value
        source, target = self.population.reinforce(source_cohort_id, target_cohort_id, count)
        self._record_population_event(
            "cohort_reinforced",
            source_cohort_id=source_cohort_id,
            target_cohort_id=target_cohort_id,
            headcount=count,
            from_segment=from_segment,
            to_segment=to_segment,
            location_id=target.location_id,
        )
        return source, target

    def apply_population_losses(self, cohort_id: str, deaths: int, *, cause: str) -> PopulationCohortState:
        if not cause:
            raise ValueError("population loss cause must be non-empty")
        cohort = self.population.apply_losses(cohort_id, deaths)
        movement = self._movement(cohort_id)
        self._record_population_event(
            "cohort_losses",
            cohort_id=cohort_id,
            deaths=deaths,
            cause=cause,
            location_id=cohort.location_id,
            movement_target_location_id=(movement.target_location_id if movement is not None else None),
        )
        if cohort.headcount == 0 and movement is not None:
            self.population_movements.pop(cohort_id)
            self._record_population_event(
                "movement_cancelled",
                cohort_id=cohort_id,
                target_location_id=movement.target_location_id,
                reason="cohort_extinguished",
            )
        return cohort

    def schedule_population_movement(
        self,
        cohort_id: str,
        target_location_id: str,
        *,
        reason: str,
        count: int | None = None,
        new_cohort_id: str | None = None,
    ) -> PopulationMovementState | None:
        if target_location_id not in self.world_map.locations:
            raise KeyError(target_location_id)
        if not reason:
            raise ValueError("population movement reason must be non-empty")
        if cohort_id in self.population_movements:
            raise ValueError("population cohort already has a movement plan")
        source = self.population.cohorts[cohort_id]
        if not source.settled:
            raise ValueError("population movement can begin only from a settled cohort")
        if source.headcount <= 0:
            raise ValueError("empty population cohort cannot move")
        moved = source.headcount if count is None else count
        moving = source
        if moved != source.headcount:
            if not new_cohort_id:
                raise ValueError("partial population movement requires new_cohort_id")
            moving = self.population.split(cohort_id, moved, new_cohort_id)
            self._record_population_event(
                "cohort_split_for_movement",
                source_cohort_id=cohort_id,
                new_cohort_id=moving.cohort_id,
                headcount=moved,
                location_id=moving.location_id,
            )
        movement = PopulationMovementState(
            cohort_id=moving.cohort_id,
            target_location_id=target_location_id,
            reason=reason,
            created_at_ms=self.world.now_ms,
        )
        self.population_movements[moving.cohort_id] = movement
        self._record_population_event(
            "movement_planned",
            cohort_id=moving.cohort_id,
            target_location_id=target_location_id,
            headcount=moving.headcount,
            reason=reason,
        )
        self._progress_population_movement(moving.cohort_id, self.world.now_ms)
        return self.population_movements.get(moving.cohort_id)

    def _wait_population_movement(self, movement: PopulationMovementState, reason: str) -> None:
        if movement.wait_reason == reason and movement.status is PopulationMovementStatus.WAITING:
            return
        movement.wait(reason)
        self._record_population_event(
            "movement_waiting",
            cohort_id=movement.cohort_id,
            target_location_id=movement.target_location_id,
            reason=reason,
        )

    def _complete_population_movement(self, cohort_id: str) -> None:
        movement = self.population_movements.pop(cohort_id)
        cohort = self.population.cohorts[cohort_id]
        if cohort.location_id != movement.target_location_id:
            raise RuntimeError("population movement completed away from its target")
        self._record_population_event(
            "movement_completed",
            cohort_id=cohort_id,
            target_location_id=movement.target_location_id,
            headcount=cohort.headcount,
            gate_transfers=movement.gate_transfers,
        )

    def _begin_population_leg(
        self,
        cohort: PopulationCohortState,
        movement: PopulationMovementState,
        next_location_id: str,
        started_at_ms: int,
    ) -> None:
        if cohort.location_id is None:
            raise RuntimeError("population graph travel requires a settled cohort")
        origin = cohort.location_id
        edge = self._edge(origin, next_location_id)
        movement.begin_leg(
            from_location_id=origin,
            next_location_id=next_location_id,
            started_at_ms=started_at_ms,
            due_at_ms=started_at_ms + edge.travel_ms,
            traversal_tags=edge.traversal_tags,
        )
        cohort.depart()
        self._record_population_event(
            "movement_leg_started",
            cohort_id=cohort.cohort_id,
            from_location_id=origin,
            to_location_id=next_location_id,
            headcount=cohort.headcount,
            started_at_ms=started_at_ms,
            due_at_ms=movement.due_at_ms,
            traversal_tags=list(edge.traversal_tags),
        )

    def _progress_population_movement(self, cohort_id: str, at_ms: int) -> None:
        movement = self.population_movements.get(cohort_id)
        if movement is None or movement.active:
            return
        cohort = self.population.cohorts[cohort_id]
        if cohort.headcount <= 0:
            self.population_movements.pop(cohort_id)
            return
        if not cohort.settled or cohort.floor_number is None or cohort.location_id is None:
            raise RuntimeError("waiting population movement must have a settled cohort")
        target = self.world_map.locations[movement.target_location_id]
        if cohort.location_id == movement.target_location_id:
            self._complete_population_movement(cohort_id)
            return

        if cohort.floor_number != target.floor_number:
            target_floor = self.world.floors[target.floor_number]
            if not target_floor.unlocked or not target_floor.main_town_gate_active:
                self._wait_population_movement(movement, "target_floor_gate_inactive")
                return
            source_floor = self.world.floors[cohort.floor_number]
            if not source_floor.unlocked or not source_floor.main_town_gate_active:
                self._wait_population_movement(movement, "origin_floor_gate_inactive")
                return
            source_choice = self._best_gate_from(cohort.location_id, cohort.floor_number)
            if source_choice is None:
                self._wait_population_movement(movement, "origin_gate_unreachable")
                return
            source_gate_id, source_path, _ = source_choice
            if cohort.location_id != source_gate_id:
                self._begin_population_leg(cohort, movement, source_path[0], at_ms)
                return
            target_choice = self._best_gate_to_target(target.floor_number, movement.target_location_id)
            if target_choice is None:
                self._wait_population_movement(movement, "target_gate_unreachable")
                return
            target_gate_id, _, _ = target_choice
            from_gate = cohort.location_id
            cohort.settle(floor_number=target.floor_number, location_id=target_gate_id)
            movement.record_gate_transfer()
            self._record_population_event(
                "movement_gate_transfer",
                cohort_id=cohort_id,
                from_location_id=from_gate,
                to_location_id=target_gate_id,
                from_floor_number=source_floor.number,
                to_floor_number=target.floor_number,
                headcount=cohort.headcount,
            )
            self._progress_population_movement(cohort_id, at_ms)
            return

        try:
            path, _ = self._route(cohort.location_id, movement.target_location_id)
        except ValueError:
            self._wait_population_movement(movement, "route_unreachable")
            return
        if not path:
            self._complete_population_movement(cohort_id)
            return
        self._begin_population_leg(cohort, movement, path[0], at_ms)

    def _finish_population_leg(self, movement: PopulationMovementState) -> int:
        if not movement.active:
            raise RuntimeError("population movement has no active leg to finish")
        if movement.due_at_ms is None or movement.started_at_ms is None:
            raise RuntimeError("active population movement lacks timing")
        if movement.from_location_id is None or movement.next_location_id is None:
            raise RuntimeError("active population movement lacks route endpoints")
        cohort = self.population.cohorts[movement.cohort_id]
        if cohort.settled:
            raise RuntimeError("in-transit population cohort unexpectedly has a settled location")
        completed_at_ms = movement.due_at_ms
        started_at_ms = movement.started_at_ms
        from_location_id = movement.from_location_id
        destination_id = movement.next_location_id
        traversal_tags = movement.traversal_tags
        destination = self.world_map.locations[destination_id]
        cohort.settle(floor_number=destination.floor_number, location_id=destination_id)
        movement.finish_leg()
        self._record_population_event(
            "movement_leg_completed",
            cohort_id=cohort.cohort_id,
            from_location_id=from_location_id,
            to_location_id=destination_id,
            headcount=cohort.headcount,
            started_at_ms=started_at_ms,
            completed_at_ms=completed_at_ms,
            traversal_tags=list(traversal_tags),
        )
        self._progress_population_movement(cohort.cohort_id, completed_at_ms)
        return completed_at_ms

    def _evaluate_waiting_population_movements(self, at_ms: int) -> None:
        for cohort_id in sorted(tuple(self.population_movements)):
            movement = self.population_movements.get(cohort_id)
            if movement is not None and not movement.active:
                self._progress_population_movement(cohort_id, at_ms)

    def _resolve_due_population_activities(self, before_ms: int, after_ms: int) -> None:
        for cohort_id in sorted(tuple(self.population_movements)):
            movement = self.population_movements.get(cohort_id)
            while movement is not None and movement.active and movement.due_at_ms is not None and movement.due_at_ms <= after_ms:
                self._finish_population_leg(movement)
                movement = self.population_movements.get(cohort_id)
        self._evaluate_waiting_population_movements(after_ms)

    def _scheduled_gate_time_for_floor(self, floor_number: int) -> int | None:
        if floor_number <= 1:
            return None
        floor = self.world.floors[floor_number]
        if floor.unlocked and floor.main_town_gate_active:
            return None
        return self.world.floors[floor_number - 1].scheduled_gate_activation_at_ms

    def _next_scheduler_boundary(self, target_ms: int) -> int:
        boundary = super()._next_scheduler_boundary(target_ms)
        now = self.world.now_ms
        candidates: list[int] = []
        for movement in self.population_movements.values():
            if movement.active and movement.due_at_ms is not None and now < movement.due_at_ms <= target_ms:
                candidates.append(movement.due_at_ms)
                continue
            cohort = self.population.cohorts[movement.cohort_id]
            target = self.world_map.locations[movement.target_location_id]
            for floor_number in {cohort.floor_number, target.floor_number}:
                if floor_number is None:
                    continue
                when = self._scheduled_gate_time_for_floor(floor_number)
                if when is not None and now < when <= target_ms:
                    candidates.append(when)
        return min([boundary, *candidates]) if candidates else boundary

    def advance_world(self, elapsed_ms: int) -> list[int]:
        self._evaluate_waiting_population_movements(self.world.now_ms)
        activated = super().advance_world(elapsed_ms)
        self._evaluate_waiting_population_movements(self.world.now_ms)
        return activated

    def population_movement_state(self, cohort_id: str) -> dict[str, Any] | None:
        movement = self.population_movements.get(cohort_id)
        if movement is None:
            return None
        row = asdict(movement)
        row["status"] = movement.status.value
        row["traversal_tags"] = list(movement.traversal_tags)
        return row

    def _settled_cohorts_at(self, location_id: str) -> list[PopulationCohortState]:
        return [
            cohort
            for cohort in self.population.cohorts.values()
            if cohort.location_id == location_id and self._movement(cohort.cohort_id) is None
        ]

    @staticmethod
    def _cohort_summary(cohorts: list[PopulationCohortState]) -> dict[str, Any]:
        totals = {segment.value: 0 for segment in PlayerPopulationSegment}
        headcount = 0
        level_sum = 0.0
        for cohort in cohorts:
            totals[cohort.segment.value] += cohort.headcount
            headcount += cohort.headcount
            level_sum += cohort.average_level * cohort.headcount
        return {
            "headcount": headcount,
            "segment_totals": totals,
            "weighted_average_level": (level_sum / headcount if headcount else None),
            "cohort_ids": sorted(cohort.cohort_id for cohort in cohorts),
        }

    def population_location_state(self, location_id: str) -> dict[str, Any]:
        if location_id not in self.world_map.locations:
            raise KeyError(location_id)
        location = self.world_map.locations[location_id]
        cohorts = self._settled_cohorts_at(location_id)
        return {
            "location_id": location_id,
            "floor_number": location.floor_number,
            **self._cohort_summary(cohorts),
        }

    def population_floor_state(self, floor_number: int) -> dict[str, Any]:
        if floor_number not in self.world.floors:
            raise KeyError(floor_number)
        cohorts = [
            cohort
            for cohort in self.population.cohorts.values()
            if cohort.floor_number == floor_number and self._movement(cohort.cohort_id) is None
        ]
        locations = {
            location_id: self.population_location_state(location_id)
            for location_id in sorted({cohort.location_id for cohort in cohorts if cohort.location_id is not None})
        }
        return {
            "floor_number": floor_number,
            "unlocked": self.world.floors[floor_number].unlocked,
            **self._cohort_summary(cohorts),
            "locations": locations,
        }

    def player_population_state(self) -> dict[str, Any]:
        self._assert_population_authority()
        materialized_alive = [
            actor.actor_id
            for actor in self.actors.values()
            if actor.kind is EntityKind.PLAYER and actor.alive
        ]
        materialized_dead = [
            actor.actor_id
            for actor in self.actors.values()
            if actor.kind is EntityKind.PLAYER and not actor.alive
        ]
        abstract_living = self.population.living_count()
        movement_rows = {
            cohort_id: self.population_movement_state(cohort_id)
            for cohort_id in sorted(self.population_movements)
        }
        in_transit = sum(
            self.population.cohorts[cohort_id].headcount
            for cohort_id, movement in self.population_movements.items()
            if movement.active
        )
        waiting = sum(
            self.population.cohorts[cohort_id].headcount
            for cohort_id, movement in self.population_movements.items()
            if not movement.active
        )
        settled_locations = sorted(
            {
                cohort.location_id
                for cohort in self.population.cohorts.values()
                if cohort.location_id is not None and self._movement(cohort.cohort_id) is None
            }
        )
        settled_floors = sorted(
            {
                cohort.floor_number
                for cohort in self.population.cohorts.values()
                if cohort.floor_number is not None and self._movement(cohort.cohort_id) is None
            }
        )
        return {
            "abstract_registered_players": self.population.registered_total,
            "abstract_living_players": abstract_living,
            "abstract_cumulative_deaths": self.population.cumulative_deaths,
            "conservation_balance": self.population.registered_total - abstract_living - self.population.cumulative_deaths,
            "segment_totals": self.population.segment_totals(),
            "abstract_in_transit_players": in_transit,
            "abstract_waiting_movement_players": waiting,
            "materialized_alive_players": len(materialized_alive),
            "materialized_dead_players": len(materialized_dead),
            "total_living_players_represented": abstract_living + len(materialized_alive),
            "cohorts": self.population.dump_state()["cohorts"],
            "movements": movement_rows,
            "locations": {
                location_id: self.population_location_state(location_id)
                for location_id in settled_locations
            },
            "floors": {
                str(floor_number): self.population_floor_state(floor_number)
                for floor_number in settled_floors
            },
        }

    def _assert_population_authority(self) -> None:
        self.population.assert_conservation()
        for cohort_id, cohort in self.population.cohorts.items():
            movement = self.population_movements.get(cohort_id)
            if movement is None:
                if not cohort.settled or cohort.location_id not in self.world_map.locations:
                    raise RuntimeError(f"settled population cohort lacks an authoritative location: {cohort_id}")
                location = self.world_map.locations[cohort.location_id]
                if cohort.floor_number != location.floor_number:
                    raise RuntimeError(f"population cohort floor/location mismatch: {cohort_id}")
                if not self.world.floors[location.floor_number].unlocked:
                    raise RuntimeError(f"population cohort is settled on a locked floor: {cohort_id}")
                continue
            if movement.cohort_id != cohort_id or movement.target_location_id not in self.world_map.locations:
                raise RuntimeError(f"population movement registry is inconsistent: {cohort_id}")
            if movement.active:
                if cohort.settled:
                    raise RuntimeError(f"in-transit population cohort has a settled location: {cohort_id}")
                if movement.from_location_id not in self.world_map.locations or movement.next_location_id not in self.world_map.locations:
                    raise RuntimeError(f"population movement route references unknown locations: {cohort_id}")
                if movement.started_at_ms is None or movement.due_at_ms is None:
                    raise RuntimeError(f"population movement route lacks timing: {cohort_id}")
                if not (movement.started_at_ms <= self.world.now_ms < movement.due_at_ms):
                    raise RuntimeError(f"population movement route timing is invalid: {cohort_id}")
                self._edge(movement.from_location_id, movement.next_location_id)
            else:
                if not cohort.settled or cohort.location_id not in self.world_map.locations:
                    raise RuntimeError(f"waiting population movement is not settled: {cohort_id}")
                location = self.world_map.locations[cohort.location_id]
                if cohort.floor_number != location.floor_number:
                    raise RuntimeError(f"waiting population cohort floor/location mismatch: {cohort_id}")

    def dump_population_state(self) -> dict[str, Any]:
        self._assert_population_authority()
        return {
            "schema": POPULATION_RUNTIME_SCHEMA,
            "ledger": self.population.dump_state(),
            "movements": {
                cohort_id: asdict(movement)
                for cohort_id, movement in self.population_movements.items()
            },
            "history": list(self.population_history),
        }

    def load_population_state(self, payload: dict[str, Any]) -> None:
        if not payload:
            self.population = PlayerPopulationState()
            self.population_movements = {}
            self.population_history = []
            return
        schema = payload.get("schema")
        if schema not in {None, POPULATION_RUNTIME_SCHEMA}:
            if payload.get("ledger") or payload.get("movements") or payload.get("history"):
                raise ValueError(f"unsupported non-empty population runtime schema: {schema!r}")
        self.population.load_state(payload.get("ledger", {}))
        movements: dict[str, PopulationMovementState] = {}
        if schema is None:
            if payload.get("movements"):
                raise ValueError("legacy population runtime cannot contain movement state")
        else:
            for cohort_id, row in payload.get("movements", {}).items():
                movement = PopulationMovementState(
                    cohort_id=row["cohort_id"],
                    target_location_id=row["target_location_id"],
                    reason=row["reason"],
                    created_at_ms=int(row["created_at_ms"]),
                    status=PopulationMovementStatus(row["status"]),
                    wait_reason=row.get("wait_reason"),
                    from_location_id=row.get("from_location_id"),
                    next_location_id=row.get("next_location_id"),
                    started_at_ms=(int(row["started_at_ms"]) if row.get("started_at_ms") is not None else None),
                    due_at_ms=(int(row["due_at_ms"]) if row.get("due_at_ms") is not None else None),
                    traversal_tags=tuple(row.get("traversal_tags", ())),
                    gate_transfers=int(row.get("gate_transfers", 0)),
                    revision=int(row.get("revision", 0)),
                )
                if movement.cohort_id != cohort_id:
                    raise ValueError(f"population movement key/id mismatch: {cohort_id}")
                if cohort_id not in self.population.cohorts:
                    raise ValueError(f"population movement references unknown cohort: {cohort_id}")
                if movement.created_at_ms > self.world.now_ms:
                    raise ValueError("population movement cannot be created after current world time")
                if movement.active and (movement.due_at_ms is None or movement.due_at_ms <= self.world.now_ms):
                    raise ValueError(f"population save contains overdue movement: {cohort_id}")
                movements[cohort_id] = movement
        self.population_movements = movements
        history = list(payload.get("history", []))
        for row in history:
            at_ms = int(row["at_ms"])
            if at_ms < 0 or at_ms > self.world.now_ms:
                raise ValueError("population history event has invalid world time")
        self.population_history = history
        self._assert_population_authority()
'''

SERVER_POPULATION = r'''from __future__ import annotations

import json


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def register_population_tools(mcp, runtime) -> None:
    @mcp.tool()
    def get_player_population_state() -> str:
        """Inspect conserved background cohorts, migration state and separate materialized-player counts."""
        return _json(runtime.player_population_state())

    @mcp.tool()
    def get_player_population_history() -> str:
        """Inspect committed cohort registration, role, movement, reinforcement and loss events."""
        return _json({"events": runtime.population_history})

    @mcp.tool()
    def get_player_population_at_location(location_id: str) -> str:
        """Return the settled anonymous-player population at one authoritative world location."""
        return _json(runtime.population_location_state(location_id))

    @mcp.tool()
    def get_player_population_on_floor(floor_number: int) -> str:
        """Return settled anonymous-player cohorts on one floor, grouped by location and segment."""
        return _json(runtime.population_floor_state(floor_number))

    @mcp.tool()
    def add_player_population_cohort(
        cohort_id: str,
        segment: str,
        headcount: int,
        location_id: str,
        average_level: float,
        activity: str,
        provenance: str = "simulation",
    ) -> str:
        """Register one unmaterialized player cohort; named/materialized actors are never included."""
        runtime.add_population_cohort(
            cohort_id,
            segment,
            headcount,
            location_id,
            average_level,
            activity,
            provenance=provenance,
        )
        return _json(runtime.player_population_state())

    @mcp.tool()
    def reclassify_player_population_cohort(
        cohort_id: str,
        segment: str,
        count: int | None = None,
        new_cohort_id: str | None = None,
        activity: str | None = None,
    ) -> str:
        """Move all or part of one abstract cohort between frontline/production/mid-tier/casual roles."""
        runtime.reclassify_population_cohort(
            cohort_id,
            segment,
            count=count,
            new_cohort_id=new_cohort_id,
            activity=activity,
        )
        return _json(runtime.player_population_state())

    @mcp.tool()
    def reinforce_player_population_cohort(source_cohort_id: str, target_cohort_id: str, count: int) -> str:
        """Transfer settled anonymous players between colocated cohorts without changing total population."""
        runtime.reinforce_population_cohort(source_cohort_id, target_cohort_id, count)
        return _json(runtime.player_population_state())

    @mcp.tool()
    def move_player_population_cohort(
        cohort_id: str,
        target_location_id: str,
        reason: str,
        count: int | None = None,
        new_cohort_id: str | None = None,
    ) -> str:
        """Plan all or part of a cohort through graph travel and active cross-floor teleport gates."""
        runtime.schedule_population_movement(
            cohort_id,
            target_location_id,
            reason=reason,
            count=count,
            new_cohort_id=new_cohort_id,
        )
        return _json(runtime.player_population_state())

    @mcp.tool()
    def apply_player_population_losses(cohort_id: str, deaths: int, cause: str) -> str:
        """Commit deaths to one abstract cohort; conservation is checked against registered population."""
        runtime.apply_population_losses(cohort_id, deaths, cause=cause)
        return _json(runtime.player_population_state())
'''

TESTS = r'''import pytest

from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime


TOWN = "floor_1_town_of_beginnings"
WEST_FIELD = "floor_1_west_field"
TOLBANA = "floor_1_tolbana"
URBUS = "floor_2_urbus"
MINUTE = 60_000


def test_population_cohorts_conserve_reclassification_reinforcement_and_losses():
    runtime = PopulationAincradRuntime(seed=503)
    named_player = runtime.create_character("NamedPlayer", level=7)
    runtime.add_population_cohort("frontline_main", "frontline", 120, WEST_FIELD, 8.0, "frontline_clearing")
    runtime.add_population_cohort("production_main", "production", 300, TOWN, 4.0, "crafting_and_trade")
    runtime.add_population_cohort("mid_tier_main", "mid_tier", 800, TOWN, 5.0, "leveling_and_material_hunting")
    runtime.add_population_cohort("casual_main", "casual", 1_800, TOWN, 2.0, "town_life_and_safe_hunting")

    initial = runtime.player_population_state()
    assert initial["abstract_registered_players"] == 3_020
    assert initial["abstract_living_players"] == 3_020
    assert initial["conservation_balance"] == 0
    assert initial["materialized_alive_players"] == 1
    assert initial["total_living_players_represented"] == 3_021

    runtime.reclassify_population_cohort(
        "mid_tier_main", "frontline", count=50, new_cohort_id="frontline_recruits", activity="frontline_training"
    )
    after_reclassification = runtime.player_population_state()
    assert after_reclassification["abstract_registered_players"] == 3_020
    assert after_reclassification["segment_totals"]["frontline"] == 170
    assert after_reclassification["segment_totals"]["mid_tier"] == 750

    runtime.reinforce_population_cohort("production_main", "casual_main", 20)
    after_reinforcement = runtime.player_population_state()
    assert after_reinforcement["abstract_registered_players"] == 3_020
    assert after_reinforcement["abstract_living_players"] == 3_020
    assert after_reinforcement["segment_totals"]["production"] == 280
    assert after_reinforcement["segment_totals"]["casual"] == 1_820

    runtime.apply_population_losses("frontline_recruits", 3, cause="field_combat")
    after_losses = runtime.player_population_state()
    assert after_losses["abstract_registered_players"] == 3_020
    assert after_losses["abstract_living_players"] == 3_017
    assert after_losses["abstract_cumulative_deaths"] == 3
    assert after_losses["conservation_balance"] == 0
    assert named_player.actor_id in runtime.actors

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, PopulationAincradRuntime)
    assert restored.player_population_state() == after_losses
    assert restored.population_history == runtime.population_history


def test_population_graph_movement_uses_exact_world_time_and_no_settled_location_in_transit():
    runtime = PopulationAincradRuntime(seed=509)
    runtime.add_population_cohort("frontline", "frontline", 40, TOWN, 7.0, "clearing")
    movement = runtime.schedule_population_movement("frontline", TOLBANA, reason="frontline_advance")
    assert movement is not None and movement.active
    assert movement.from_location_id == TOWN
    assert movement.next_location_id == WEST_FIELD
    assert runtime.population.cohorts["frontline"].location_id is None
    assert runtime.player_population_state()["abstract_in_transit_players"] == 40
    assert runtime.population_location_state(TOWN)["headcount"] == 0

    runtime.advance_world(12 * MINUTE)
    movement = runtime.population_movements["frontline"]
    assert movement.active
    assert movement.from_location_id == WEST_FIELD
    assert movement.next_location_id == TOLBANA
    assert movement.started_at_ms == 12 * MINUTE
    assert movement.due_at_ms == 54 * MINUTE
    assert runtime.population.cohorts["frontline"].location_id is None

    runtime.advance_world(42 * MINUTE)
    cohort = runtime.population.cohorts["frontline"]
    assert cohort.location_id == TOLBANA and cohort.floor_number == 1
    assert "frontline" not in runtime.population_movements
    assert runtime.population_location_state(TOLBANA)["headcount"] == 40
    completed = [row for row in runtime.population_history if row["event"] == "movement_leg_completed"]
    assert [(row["from_location_id"], row["to_location_id"], row["completed_at_ms"]) for row in completed] == [
        (TOWN, WEST_FIELD, 12 * MINUTE),
        (WEST_FIELD, TOLBANA, 54 * MINUTE),
    ]


def test_partial_population_migration_splits_without_creating_or_losing_players():
    runtime = PopulationAincradRuntime(seed=510)
    runtime.add_population_cohort("mid_pool", "mid_tier", 100, TOWN, 5.0, "leveling")
    runtime.schedule_population_movement(
        "mid_pool",
        WEST_FIELD,
        reason="field_training",
        count=30,
        new_cohort_id="field_detachment",
    )
    state = runtime.player_population_state()
    assert state["abstract_registered_players"] == 100
    assert state["abstract_living_players"] == 100
    assert runtime.population.cohorts["mid_pool"].headcount == 70
    assert runtime.population.cohorts["field_detachment"].headcount == 30
    assert runtime.population.cohorts["mid_pool"].location_id == TOWN
    assert runtime.population.cohorts["field_detachment"].location_id is None

    runtime.advance_world(12 * MINUTE)
    assert runtime.population.cohorts["field_detachment"].location_id == WEST_FIELD
    assert runtime.player_population_state()["conservation_balance"] == 0


def test_cross_floor_population_waits_for_real_gate_activation_then_transfers():
    runtime = PopulationAincradRuntime(seed=511)
    runtime.add_population_cohort("frontier", "frontline", 25, TOWN, 10.0, "next_floor_push")
    movement = runtime.schedule_population_movement("frontier", URBUS, reason="floor2_frontier")
    assert movement is not None and not movement.active
    assert movement.wait_reason == "target_floor_gate_inactive"
    assert runtime.population.cohorts["frontier"].location_id == TOWN

    runtime.floor_boss_defeated(1)
    runtime.advance_world(2 * 60 * MINUTE)
    cohort = runtime.population.cohorts["frontier"]
    assert runtime.world.floors[2].unlocked is True
    assert cohort.location_id == URBUS and cohort.floor_number == 2
    assert "frontier" not in runtime.population_movements
    gate_rows = [row for row in runtime.population_history if row["event"] == "movement_gate_transfer"]
    assert len(gate_rows) == 1
    assert gate_rows[0]["from_location_id"] == TOWN
    assert gate_rows[0]["to_location_id"] == URBUS
    assert gate_rows[0]["at_ms"] == 2 * 60 * MINUTE


def test_active_population_movement_round_trips_and_preserves_due_boundary():
    runtime = PopulationAincradRuntime(seed=512)
    runtime.add_population_cohort("travellers", "casual", 12, TOWN, 2.0, "relocation")
    runtime.schedule_population_movement("travellers", TOLBANA, reason="relocation")
    restored = import_runtime(export_runtime(runtime))
    movement = restored.population_movements["travellers"]
    assert movement.active and movement.due_at_ms == 12 * MINUTE
    assert restored.population.cohorts["travellers"].location_id is None
    restored.advance_world(12 * MINUTE)
    assert restored.population_movements["travellers"].from_location_id == WEST_FIELD
    assert restored.population.registered_total == 12


def test_population_location_and_floor_interfaces_are_background_only():
    runtime = PopulationAincradRuntime(seed=513)
    named = runtime.create_character("NamedGuildCandidate", level=5)
    runtime.add_population_cohort("producers", "production", 60, TOWN, 4.0, "market_supply")
    runtime.add_population_cohort("casuals", "casual", 140, TOWN, 2.0, "consumer_life")
    location = runtime.population_location_state(TOWN)
    assert location["headcount"] == 200
    assert location["segment_totals"]["production"] == 60
    assert location["segment_totals"]["casual"] == 140
    floor = runtime.population_floor_state(1)
    assert floor["headcount"] == 200
    assert named.actor_id not in location["cohort_ids"]
    assert runtime.player_population_state()["materialized_alive_players"] == 1


def test_population_cohorts_require_authoritative_world_locations_and_safe_splits():
    runtime = PopulationAincradRuntime(seed=514)
    with pytest.raises(KeyError):
        runtime.add_population_cohort("nowhere", "casual", 10, "not_a_world_location", 2.0, "idle")
    runtime.add_population_cohort("mid_tier_pool", "mid_tier", 20, TOWN, 4.0, "leveling")
    with pytest.raises(ValueError, match="new_cohort_id"):
        runtime.reclassify_population_cohort("mid_tier_pool", "frontline", count=5)
    assert runtime.player_population_state()["abstract_living_players"] == 20
'''

AUTHORITY_TESTS = r'''from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.population import PopulationCohortState, PopulationMovementState


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_population_goal_and_route_state_do_not_duplicate_cohort_headcount_or_segment():
    movement_fields = set(PopulationMovementState.__dataclass_fields__)
    cohort_fields = set(PopulationCohortState.__dataclass_fields__)
    assert "headcount" not in movement_fields
    assert "segment" not in movement_fields
    assert "target_location_id" not in cohort_fields
    assert "due_at_ms" not in cohort_fields


def test_scenarios_cannot_mutate_population_ledgers_directly():
    forbidden = {
        "population",
        "population_movements",
        "_progress_population_movement",
        "_begin_population_leg",
        "_finish_population_leg",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []


def test_population_runtime_exposes_neutral_location_and_floor_interfaces_for_later_systems():
    source = (ROOT / "src/sao_mcp/runtime/population_runtime.py").read_text(encoding="utf-8")
    assert "def population_location_state" in source
    assert "def population_floor_state" in source
    assert "abstract_in_transit_players" in source
    assert "registered_total" in source
'''

path = Path("src/sao_mcp/rules/population.py")
path.write_text(POPULATION_RULES, encoding="utf-8")
Path("src/sao_mcp/runtime/population_runtime.py").write_text(POPULATION_RUNTIME, encoding="utf-8")
Path("src/sao_mcp/server_population.py").write_text(SERVER_POPULATION, encoding="utf-8")
Path("tests/test_population_abstraction.py").write_text(TESTS, encoding="utf-8")
Path("tests/test_population_authority.py").write_text(AUTHORITY_TESTS, encoding="utf-8")

routing = Path("src/sao_mcp/rules/routing.py")
text = routing.read_text(encoding="utf-8")
old = '''def shortest_next_hop(\n    world: WorldState,\n    world_map: WorldMapCatalog,\n    origin: str,\n    target: str,\n    *,\n    can_enter: LocationPredicate | None = None,\n) -> str | None:\n    \"\"\"Return the first edge on the minimum-travel-time route through the current world graph.\"\"\"\n    if origin not in world_map.locations:\n        raise KeyError(origin)\n    if target not in world_map.locations:\n        raise KeyError(target)\n    if origin == target:\n        return None\n\n    queue: list[tuple[int, str, str | None]] = [(0, origin, None)]\n    best = {origin: 0}\n    while queue:\n        elapsed, node_id, first_hop = heapq.heappop(queue)\n        if elapsed != best.get(node_id):\n            continue\n        # Dijkstra is final only when a node is removed from the minimum-priority queue.\n        # Returning when the target is first *discovered* can select a slower direct edge\n        # before a shorter multi-edge dynamic route (for example a boss shortcut) is explored.\n        if node_id == target:\n            return first_hop\n        for edge in world_map.adjacency.get(node_id, ()):\n            destination = world_map.locations[edge.to_location_id]\n            if edge.requires_floor_unlocked and not world.floors[destination.floor_number].unlocked:\n                continue\n            if can_enter is not None and not can_enter(edge.to_location_id):\n                continue\n            total = elapsed + edge.travel_ms\n            if total >= best.get(edge.to_location_id, 2**63 - 1):\n                continue\n            next_first = edge.to_location_id if first_hop is None else first_hop\n            best[edge.to_location_id] = total\n            heapq.heappush(queue, (total, edge.to_location_id, next_first))\n    raise ValueError(f\"destination is unreachable from {origin}: {target}\")\n'''
new = '''def shortest_route(\n    world: WorldState,\n    world_map: WorldMapCatalog,\n    origin: str,\n    target: str,\n    *,\n    can_enter: LocationPredicate | None = None,\n) -> tuple[tuple[str, ...], int]:\n    \"\"\"Return the minimum-travel-time graph route (excluding origin) and its elapsed ms.\"\"\"\n    if origin not in world_map.locations:\n        raise KeyError(origin)\n    if target not in world_map.locations:\n        raise KeyError(target)\n    if origin == target:\n        return (), 0\n\n    queue: list[tuple[int, str, tuple[str, ...]]] = [(0, origin, ())]\n    best = {origin: 0}\n    while queue:\n        elapsed, node_id, path = heapq.heappop(queue)\n        if elapsed != best.get(node_id):\n            continue\n        if node_id == target:\n            return path, elapsed\n        for edge in world_map.adjacency.get(node_id, ()):\n            destination = world_map.locations[edge.to_location_id]\n            if edge.requires_floor_unlocked and not world.floors[destination.floor_number].unlocked:\n                continue\n            if can_enter is not None and not can_enter(edge.to_location_id):\n                continue\n            total = elapsed + edge.travel_ms\n            if total >= best.get(edge.to_location_id, 2**63 - 1):\n                continue\n            best[edge.to_location_id] = total\n            heapq.heappush(queue, (total, edge.to_location_id, path + (edge.to_location_id,)))\n    raise ValueError(f\"destination is unreachable from {origin}: {target}\")\n\n\ndef shortest_next_hop(\n    world: WorldState,\n    world_map: WorldMapCatalog,\n    origin: str,\n    target: str,\n    *,\n    can_enter: LocationPredicate | None = None,\n) -> str | None:\n    \"\"\"Return the first edge on the minimum-travel-time route through the current world graph.\"\"\"\n    route, _ = shortest_route(world, world_map, origin, target, can_enter=can_enter)\n    return route[0] if route else None\n'''
if text.count(old) != 1:
    raise RuntimeError(f"routing replacement anchor count={text.count(old)}")
routing.write_text(text.replace(old, new, 1), encoding="utf-8")
