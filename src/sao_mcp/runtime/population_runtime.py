from __future__ import annotations

from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.population import (
    PlayerPopulationSegment,
    PlayerPopulationState,
    PopulationCohortState,
)
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


class PopulationAincradRuntime(HousingAincradRuntime):
    """Authoritative runtime with coarse unmaterialized player-population cohorts."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.population = PlayerPopulationState()
        self.population_history: list[dict] = []

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
        self.population_history.append(
            {
                "event": "cohort_added",
                "cohort_id": cohort_id,
                "segment": cohort.segment.value,
                "headcount": headcount,
                "location_id": location_id,
                "at_ms": self.world.now_ms,
            }
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
        self.population_history.append(
            {
                "event": "cohort_reclassified",
                "source_cohort_id": cohort_id,
                "new_cohort_id": split.cohort_id if split is not None else None,
                "from_segment": before_segment,
                "to_segment": PlayerPopulationSegment(segment).value,
                "headcount": moved,
                "location_id": source.location_id,
                "at_ms": self.world.now_ms,
            }
        )
        return source, split

    def apply_population_losses(self, cohort_id: str, deaths: int, *, cause: str) -> PopulationCohortState:
        if not cause:
            raise ValueError("population loss cause must be non-empty")
        cohort = self.population.apply_losses(cohort_id, deaths)
        self.population_history.append(
            {
                "event": "cohort_losses",
                "cohort_id": cohort_id,
                "deaths": deaths,
                "cause": cause,
                "location_id": cohort.location_id,
                "at_ms": self.world.now_ms,
            }
        )
        return cohort

    def player_population_state(self) -> dict:
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
        return {
            "abstract_living_players": abstract_living,
            "abstract_cumulative_deaths": self.population.cumulative_deaths,
            "segment_totals": self.population.segment_totals(),
            "materialized_alive_players": len(materialized_alive),
            "materialized_dead_players": len(materialized_dead),
            "total_living_players_represented": abstract_living + len(materialized_alive),
            "cohorts": self.population.dump_state()["cohorts"],
        }

    def dump_population_state(self) -> dict:
        return {
            "ledger": self.population.dump_state(),
            "history": list(self.population_history),
        }

    def load_population_state(self, payload: dict) -> None:
        self.population.load_state(payload.get("ledger", {}))
        for cohort in self.population.cohorts.values():
            if cohort.location_id not in self.world_map.locations:
                raise ValueError(f"population save references unknown location: {cohort.location_id}")
            location = self.world_map.locations[cohort.location_id]
            if location.floor_number != cohort.floor_number:
                raise ValueError(f"population cohort floor/location mismatch: {cohort.cohort_id}")
            if not self.world.floors[cohort.floor_number].unlocked:
                raise ValueError(f"population cohort is on a locked floor: {cohort.cohort_id}")
        history = list(payload.get("history", []))
        for row in history:
            at_ms = int(row["at_ms"])
            if at_ms > self.world.now_ms:
                raise ValueError("population history cannot occur after current world time")
        self.population_history = history
