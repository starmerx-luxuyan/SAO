from __future__ import annotations

from dataclasses import asdict, replace

from sao_mcp.domain.models import EntityKind, ProvenanceKind
from sao_mcp.rules.population import PopulationBand, PopulationCohortState
from sao_mcp.rules.routing import shortest_next_hop
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


class PopulationAincradRuntime(HousingAincradRuntime):
    """Production runtime with conserved aggregate state for unmaterialized players."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.population_initial_total: int | None = None
        self.population_cohorts: dict[str, PopulationCohortState] = {}
        self.population_history: list[dict] = []
        self.register_world_advance_hook(self._resolve_due_population_movements)

    def _cohort(self, cohort_id: str) -> PopulationCohortState:
        try:
            return self.population_cohorts[cohort_id]
        except KeyError as exc:
            raise KeyError(f"unknown population cohort: {cohort_id}") from exc

    @staticmethod
    def _population_provenance(
        kind: ProvenanceKind | str,
        source_ref: str | None,
    ) -> tuple[ProvenanceKind, str | None]:
        resolved = ProvenanceKind(kind)
        if resolved is not ProvenanceKind.SIMULATION and not source_ref:
            raise ValueError("non-simulation population counts require source_ref")
        return resolved, source_ref

    def initialize_player_population(self, cohorts: list[dict]) -> dict:
        if self.population_initial_total is not None or self.population_cohorts or self.population_history:
            raise ValueError("player population has already been initialized")
        if not isinstance(cohorts, list) or not cohorts:
            raise ValueError("population initialization requires at least one cohort")

        states: dict[str, PopulationCohortState] = {}
        for index, row in enumerate(cohorts):
            if not isinstance(row, dict):
                raise ValueError(f"population cohort {index} must be an object")
            required = {
                "cohort_id",
                "band",
                "count",
                "location_id",
                "average_level",
                "activity",
            }
            missing = required - set(row)
            unknown = set(row) - required - {"provenance_kind", "source_ref"}
            if missing:
                raise ValueError(
                    f"population cohort {index} is missing fields: {', '.join(sorted(missing))}"
                )
            if unknown:
                raise ValueError(
                    f"population cohort {index} has unknown fields: {', '.join(sorted(unknown))}"
                )
            cohort_id = row["cohort_id"]
            if not isinstance(cohort_id, str) or not cohort_id:
                raise ValueError("population cohort_id must be a non-empty string")
            if cohort_id in states:
                raise ValueError(f"duplicate population cohort_id: {cohort_id}")
            count = row["count"]
            if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                raise ValueError("population cohort count must be a positive integer")
            location_id = row["location_id"]
            if not isinstance(location_id, str) or location_id not in self.world_map.locations:
                raise ValueError(f"population cohort has unknown location: {location_id!r}")
            location = self.world_map.locations[location_id]
            if not self.world.floors[location.floor_number].unlocked:
                raise ValueError("population cohort cannot initialize on a locked floor")
            average_level = float(row["average_level"])
            activity = row["activity"]
            if not isinstance(activity, str) or not activity:
                raise ValueError("population cohort activity must be a non-empty string")
            provenance_kind, source_ref = self._population_provenance(
                row.get("provenance_kind", ProvenanceKind.SIMULATION),
                row.get("source_ref"),
            )
            states[cohort_id] = PopulationCohortState(
                cohort_id=cohort_id,
                band=PopulationBand(row["band"]),
                count=count,
                location_id=location_id,
                average_level=average_level,
                activity=activity,
                provenance_kind=provenance_kind,
                source_ref=source_ref,
            )

        self.population_cohorts = states
        self.population_initial_total = sum(cohort.count for cohort in states.values())
        self.population_history.append(
            {
                "event": "population_initialized",
                "initial_total": self.population_initial_total,
                "cohort_ids": list(states),
                "at_ms": self.world.now_ms,
            }
        )
        self._assert_population_conservation()
        return self.population_state()

    def split_population_cohort(
        self,
        cohort_id: str,
        new_cohort_id: str,
        count: int,
        *,
        band: PopulationBand | str | None = None,
        activity: str | None = None,
        average_level: float | None = None,
    ) -> PopulationCohortState:
        source = self._cohort(cohort_id)
        if source.active or source.movement_target_location_id is not None or source.location_id is None:
            raise ValueError("population cohort can only split while settled")
        if not isinstance(new_cohort_id, str) or not new_cohort_id:
            raise ValueError("new population cohort_id must be non-empty")
        if new_cohort_id in self.population_cohorts:
            raise ValueError(f"population cohort already exists: {new_cohort_id}")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0 or count >= source.count:
            raise ValueError("split count must leave at least one player in the source cohort")
        if activity is not None and not activity:
            raise ValueError("population cohort activity must be non-empty")
        resolved_level = source.average_level if average_level is None else float(average_level)
        source.count -= count
        created = PopulationCohortState(
            cohort_id=new_cohort_id,
            band=PopulationBand(band) if band is not None else source.band,
            count=count,
            location_id=source.location_id,
            average_level=resolved_level,
            activity=activity if activity is not None else source.activity,
            provenance_kind=source.provenance_kind,
            source_ref=source.source_ref,
        )
        self.population_cohorts[new_cohort_id] = created
        self.population_history.append(
            {
                "event": "cohort_split",
                "source_cohort_id": cohort_id,
                "new_cohort_id": new_cohort_id,
                "count": count,
                "band": created.band.value,
                "average_level": created.average_level,
                "activity": created.activity,
                "at_ms": self.world.now_ms,
            }
        )
        self._assert_population_conservation()
        return created

    def set_population_cohort_role(
        self,
        cohort_id: str,
        band: PopulationBand | str,
        *,
        activity: str,
        average_level: float | None = None,
    ) -> PopulationCohortState:
        cohort = self._cohort(cohort_id)
        if cohort.active or cohort.movement_target_location_id is not None or cohort.location_id is None:
            raise ValueError("population cohort role can only change while settled")
        if not activity:
            raise ValueError("population cohort activity must be non-empty")
        before_band = cohort.band
        before_activity = cohort.activity
        cohort.band = PopulationBand(band)
        cohort.activity = activity
        if average_level is not None:
            cohort.average_level = float(average_level)
            if cohort.average_level < 1:
                raise ValueError("population cohort average_level must be at least 1")
        self.population_history.append(
            {
                "event": "cohort_role_changed",
                "cohort_id": cohort_id,
                "from_band": before_band.value,
                "to_band": cohort.band.value,
                "from_activity": before_activity,
                "to_activity": cohort.activity,
                "average_level": cohort.average_level,
                "at_ms": self.world.now_ms,
            }
        )
        self._assert_population_conservation()
        return cohort

    def materialize_population_member(self, cohort_id: str, actor_id: str) -> dict:
        cohort = self._cohort(cohort_id)
        if cohort.active or cohort.movement_target_location_id is not None or cohort.location_id is None:
            raise ValueError("population member can only materialize from a settled cohort")
        if cohort.count <= 0:
            raise ValueError("population cohort has no unmaterialized players remaining")
        actor = self.actors[actor_id]
        if actor.kind is not EntityKind.PLAYER:
            raise ValueError("only a real player actor can materialize from player population")
        if not actor.alive:
            raise ValueError("defeated player actor cannot materialize from living population")
        if actor.location_id != cohort.location_id:
            raise ValueError("materialized player actor must be colocated with the source population cohort")
        if actor.metadata.get("population_origin_cohort_id") is not None:
            raise ValueError("player actor has already been claimed from abstract population")

        cohort.count -= 1
        actor.metadata["population_origin_cohort_id"] = cohort_id
        actor.metadata["population_materialized_at_ms"] = self.world.now_ms
        self.population_history.append(
            {
                "event": "player_materialized",
                "cohort_id": cohort_id,
                "actor_id": actor_id,
                "at_ms": self.world.now_ms,
            }
        )
        self._assert_population_conservation()
        return {
            "cohort_id": cohort_id,
            "actor_id": actor_id,
            "remaining_unmaterialized": cohort.count,
        }

    def apply_population_losses(self, cohort_id: str, deaths: int, *, cause: str) -> PopulationCohortState:
        cohort = self._cohort(cohort_id)
        if not isinstance(deaths, int) or isinstance(deaths, bool) or deaths <= 0:
            raise ValueError("population deaths must be a positive integer")
        if deaths > cohort.count:
            raise ValueError("population losses exceed living unmaterialized cohort count")
        if not isinstance(cause, str) or not cause.strip():
            raise ValueError("population loss cause must be non-empty")
        cohort.count -= deaths
        cohort.cumulative_deaths += deaths
        self.population_history.append(
            {
                "event": "population_losses",
                "cohort_id": cohort_id,
                "deaths": deaths,
                "cause": cause.strip(),
                "location_id": cohort.location_id,
                "from_location_id": cohort.from_location_id,
                "next_location_id": cohort.next_location_id,
                "at_ms": self.world.now_ms,
            }
        )
        if cohort.count == 0 and (cohort.active or cohort.movement_target_location_id is not None):
            cohort.cancel_empty_route()
        self._assert_population_conservation()
        return cohort

    def _next_population_hop(self, cohort: PopulationCohortState) -> str | None:
        if cohort.location_id is None:
            raise RuntimeError("settled population route planning requires a location")
        target = cohort.movement_target_location_id
        if target is None:
            raise RuntimeError("population route planning requires a movement target")
        return shortest_next_hop(self.world, self.world_map, cohort.location_id, target)

    def _begin_population_leg(self, cohort: PopulationCohortState, started_at_ms: int) -> bool:
        if cohort.location_id == cohort.movement_target_location_id:
            cohort.movement_target_location_id = None
            return False
        next_hop = self._next_population_hop(cohort)
        if next_hop is None:
            return False
        origin = str(cohort.location_id)
        edges = [
            edge
            for edge in self.world_map.adjacency.get(origin, ())
            if edge.to_location_id == next_hop
        ]
        if not edges:
            raise RuntimeError("population route planner selected a non-adjacent next hop")
        edge = min(edges, key=lambda candidate: candidate.travel_ms)
        cohort.begin_leg(
            from_location_id=origin,
            next_location_id=next_hop,
            started_at_ms=started_at_ms,
            due_at_ms=started_at_ms + edge.travel_ms,
            traversal_tags=edge.traversal_tags,
        )
        return True

    def schedule_population_travel(self, cohort_id: str, destination_id: str) -> PopulationCohortState:
        cohort = self._cohort(cohort_id)
        if destination_id not in self.world_map.locations:
            raise KeyError(destination_id)
        destination = self.world_map.locations[destination_id]
        if not self.world.floors[destination.floor_number].unlocked:
            raise ValueError("population movement target floor is not unlocked")

        probe = replace(cohort)
        probe.begin_route(destination_id)
        self._next_population_hop(probe)

        cohort.begin_route(destination_id)
        self._begin_population_leg(cohort, self.world.now_ms)
        self.population_history.append(
            {
                "event": "population_movement_scheduled",
                "cohort_id": cohort_id,
                "target_location_id": destination_id,
                "count": cohort.count,
                "issued_at_ms": self.world.now_ms,
            }
        )
        return cohort

    def _finish_population_leg(self, cohort: PopulationCohortState) -> int:
        if not cohort.active or cohort.due_at_ms is None or cohort.started_at_ms is None:
            raise RuntimeError("population cohort has no complete active movement timing")
        if cohort.from_location_id is None or cohort.next_location_id is None:
            raise RuntimeError("population cohort active movement lacks route endpoints")
        completed_at_ms = cohort.due_at_ms
        origin = cohort.from_location_id
        destination_id = cohort.next_location_id
        traversal_tags = cohort.traversal_tags
        destination = self.world_map.locations[destination_id]
        floor = self.world.floors[destination.floor_number]
        newly_discovered = destination_id not in floor.discovered_locations
        floor.discovered_locations.add(destination_id)
        cohort.finish_leg()
        self.population_history.append(
            {
                "event": "population_travel_leg_completed",
                "cohort_id": cohort.cohort_id,
                "count": cohort.count,
                "from_location_id": origin,
                "to_location_id": destination_id,
                "completed_at_ms": completed_at_ms,
                "newly_discovered": newly_discovered,
                "traversal_tags": list(traversal_tags),
            }
        )
        return completed_at_ms

    def _resolve_due_population_movements(self, before_ms: int, after_ms: int) -> None:
        for cohort in self.population_cohorts.values():
            while cohort.active and cohort.due_at_ms is not None and cohort.due_at_ms <= after_ms:
                completed_at_ms = self._finish_population_leg(cohort)
                if cohort.movement_target_location_id is None or cohort.count == 0:
                    break
                self._begin_population_leg(cohort, completed_at_ms)

    def _materialized_population_actor_ids(self) -> set[str]:
        cohort_ids = set(self.population_cohorts)
        tracked: set[str] = set()
        for actor_id, actor in self.actors.items():
            origin = actor.metadata.get("population_origin_cohort_id")
            if origin is None:
                continue
            if origin not in cohort_ids:
                raise RuntimeError(
                    f"player actor {actor_id} references unknown population cohort {origin}"
                )
            if actor.kind is not EntityKind.PLAYER:
                raise RuntimeError(f"non-player actor {actor_id} cannot originate from player population")
            tracked.add(actor_id)
        return tracked

    def _assert_population_conservation(self) -> None:
        if self.population_initial_total is None:
            if self.population_cohorts:
                raise RuntimeError("population cohorts exist without an initialized population total")
            return
        abstract_alive = sum(cohort.count for cohort in self.population_cohorts.values())
        abstract_deaths = sum(cohort.cumulative_deaths for cohort in self.population_cohorts.values())
        materialized = len(self._materialized_population_actor_ids())
        accounted = abstract_alive + abstract_deaths + materialized
        if accounted != self.population_initial_total:
            raise RuntimeError(
                f"player population conservation failed: {accounted} != {self.population_initial_total}"
            )

    def population_cohort_state(self, cohort_id: str) -> dict:
        cohort = self._cohort(cohort_id)
        return {
            **asdict(cohort),
            "band": cohort.band.value,
            "provenance_kind": cohort.provenance_kind.value,
            "active": cohort.active,
            "floor_number": (
                self.world_map.locations[cohort.location_id].floor_number
                if cohort.location_id is not None
                else None
            ),
        }

    def population_state(self) -> dict:
        self._assert_population_conservation()
        materialized_ids = self._materialized_population_actor_ids()
        materialized_alive = sum(1 for actor_id in materialized_ids if self.actors[actor_id].alive)
        materialized_dead = len(materialized_ids) - materialized_alive
        all_materialized_players = {
            actor_id
            for actor_id, actor in self.actors.items()
            if actor.kind is EntityKind.PLAYER
        }
        untracked = sorted(all_materialized_players - materialized_ids)
        abstract_alive = sum(cohort.count for cohort in self.population_cohorts.values())
        abstract_deaths = sum(cohort.cumulative_deaths for cohort in self.population_cohorts.values())
        band_totals = {band.value: 0 for band in PopulationBand}
        for cohort in self.population_cohorts.values():
            band_totals[cohort.band.value] += cohort.count
        return {
            "initialized": self.population_initial_total is not None,
            "initial_population_total": self.population_initial_total,
            "abstract_alive": abstract_alive,
            "abstract_deaths": abstract_deaths,
            "materialized_from_population": len(materialized_ids),
            "materialized_from_population_alive": materialized_alive,
            "materialized_from_population_dead": materialized_dead,
            "represented_living": abstract_alive + materialized_alive,
            "represented_deaths": abstract_deaths + materialized_dead,
            "band_totals": band_totals,
            "untracked_materialized_player_actor_ids": untracked,
            "cohorts": {
                cohort_id: self.population_cohort_state(cohort_id)
                for cohort_id in sorted(self.population_cohorts)
            },
        }

    def dump_population_state(self) -> dict:
        return {
            "initial_population_total": self.population_initial_total,
            "cohorts": {
                cohort_id: {
                    **asdict(cohort),
                    "band": cohort.band.value,
                    "provenance_kind": cohort.provenance_kind.value,
                    "traversal_tags": list(cohort.traversal_tags),
                }
                for cohort_id, cohort in self.population_cohorts.items()
            },
            "history": list(self.population_history),
        }

    def load_population_state(self, payload: dict) -> None:
        initial_total = payload.get("initial_population_total")
        if initial_total is not None and (
            not isinstance(initial_total, int)
            or isinstance(initial_total, bool)
            or initial_total <= 0
        ):
            raise ValueError("population save initial_population_total must be a positive integer")
        cohorts: dict[str, PopulationCohortState] = {}
        for cohort_id, row in payload.get("cohorts", {}).items():
            if cohort_id != row.get("cohort_id"):
                raise ValueError(f"population cohort key disagrees with stored id: {cohort_id}")
            count = int(row["count"])
            deaths = int(row.get("cumulative_deaths", 0))
            if count < 0 or deaths < 0:
                raise ValueError("population save contains negative counts")
            location_id = row.get("location_id")
            if location_id is not None:
                if location_id not in self.world_map.locations:
                    raise ValueError(f"population save references unknown location: {location_id}")
                location = self.world_map.locations[location_id]
                if not self.world.floors[location.floor_number].unlocked:
                    raise ValueError(f"population cohort is on a locked floor: {cohort_id}")
            movement_target = row.get("movement_target_location_id")
            if movement_target is not None and movement_target not in self.world_map.locations:
                raise ValueError(f"population save references unknown movement target: {movement_target}")
            next_location_id = row.get("next_location_id")
            started_at_ms = row.get("started_at_ms")
            due_at_ms = row.get("due_at_ms")
            from_location_id = row.get("from_location_id")
            if next_location_id is not None:
                if movement_target is None or from_location_id is None or started_at_ms is None or due_at_ms is None:
                    raise ValueError(f"population save has incomplete active movement: {cohort_id}")
                if next_location_id not in self.world_map.locations or from_location_id not in self.world_map.locations:
                    raise ValueError(f"population save active movement references unknown route node: {cohort_id}")
                if int(due_at_ms) <= int(started_at_ms):
                    raise ValueError(f"population save active movement has invalid timing: {cohort_id}")
                if int(due_at_ms) <= self.world.now_ms:
                    raise ValueError(f"population save contains overdue active movement: {cohort_id}")
                if location_id is not None:
                    raise ValueError(f"active population movement has a settled location: {cohort_id}")
            else:
                if any(value is not None for value in (movement_target, from_location_id, started_at_ms, due_at_ms)):
                    raise ValueError(f"population save has route state without an active leg: {cohort_id}")
                if count > 0 and location_id is None:
                    raise ValueError(f"living population cohort has no settled location: {cohort_id}")
            provenance_kind = ProvenanceKind(row.get("provenance_kind", ProvenanceKind.SIMULATION))
            source_ref = row.get("source_ref")
            self._population_provenance(provenance_kind, source_ref)
            cohorts[cohort_id] = PopulationCohortState(
                cohort_id=cohort_id,
                band=PopulationBand(row["band"]),
                count=count,
                location_id=location_id,
                average_level=float(row["average_level"]),
                activity=row["activity"],
                cumulative_deaths=deaths,
                provenance_kind=provenance_kind,
                source_ref=source_ref,
                movement_target_location_id=movement_target,
                from_location_id=from_location_id,
                next_location_id=next_location_id,
                started_at_ms=started_at_ms,
                due_at_ms=due_at_ms,
                traversal_tags=tuple(row.get("traversal_tags", ())),
            )
        history = list(payload.get("history", []))
        for row in history:
            at_ms = row.get("at_ms", row.get("issued_at_ms", row.get("completed_at_ms")))
            if at_ms is not None and int(at_ms) > self.world.now_ms:
                raise ValueError("population history cannot occur after current world time")
        self.population_initial_total = initial_total
        self.population_cohorts = cohorts
        self.population_history = history
        self._assert_population_conservation()
