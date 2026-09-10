from __future__ import annotations

import json


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def register_population_tools(mcp, runtime) -> None:
    @mcp.tool()
    def get_player_population_state() -> str:
        """Inspect background player cohorts and materialized-player counts from authoritative state."""
        return _json(runtime.player_population_state())

    @mcp.tool()
    def get_player_population_history() -> str:
        """Inspect committed background-population reclassification and loss events."""
        return _json({"events": runtime.population_history})

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
        """Register an unmaterialized player cohort at one authoritative world location."""
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
    def apply_player_population_losses(cohort_id: str, deaths: int, cause: str) -> str:
        """Commit deaths to one abstract cohort without materializing individual background players."""
        runtime.apply_population_losses(cohort_id, deaths, cause=cause)
        return _json(runtime.player_population_state())
