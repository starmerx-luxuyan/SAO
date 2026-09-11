from __future__ import annotations

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
