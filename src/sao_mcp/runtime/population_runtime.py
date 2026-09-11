from __future__ import annotations

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
            if cohort.location_id == location_id
            and (self._movement(cohort.cohort_id) is None or not self._movement(cohort.cohort_id).active)
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
            if cohort.floor_number == floor_number
            and (self._movement(cohort.cohort_id) is None or not self._movement(cohort.cohort_id).active)
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
                if cohort.location_id is not None
                and (self._movement(cohort.cohort_id) is None or not self._movement(cohort.cohort_id).active)
            }
        )
        settled_floors = sorted(
            {
                cohort.floor_number
                for cohort in self.population.cohorts.values()
                if cohort.floor_number is not None
                and (self._movement(cohort.cohort_id) is None or not self._movement(cohort.cohort_id).active)
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
                if cohort.headcount == 0 and not cohort.settled:
                    if cohort.floor_number is not None or cohort.location_id is not None:
                        raise RuntimeError(f"extinct population cohort has partial location state: {cohort_id}")
                    continue
                if not cohort.settled or cohort.location_id not in self.world_map.locations:
                    raise RuntimeError(f"living settled population cohort lacks an authoritative location: {cohort_id}")
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
