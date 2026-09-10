from __future__ import annotations

import json
from typing import Any


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def register_population_tools(mcp, runtime) -> None:
    @mcp.tool()
    def get_player_population_state() -> str:
        """Inspect conserved aggregate cohorts for players that have not been materialized as actors."""
        return _json(runtime.population_state())

    @mcp.tool()
    def get_player_population_history(cohort_id: str | None = None) -> str:
        """Inspect population initialization, splits, role changes, travel, losses and actor materialization history."""
        rows = runtime.population_history
        if cohort_id is not None:
            rows = [
                row
                for row in rows
                if row.get("cohort_id") == cohort_id
                or row.get("source_cohort_id") == cohort_id
                or row.get("new_cohort_id") == cohort_id
            ]
        return _json({"events": rows})

    @mcp.tool()
    def initialize_player_population(cohorts: list[dict[str, Any]]) -> str:
        """Initialize the tracked abstract player population exactly once from explicit cohort records."""
        return _json(runtime.initialize_player_population(cohorts))

    @mcp.tool()
    def split_player_population_cohort(
        cohort_id: str,
        new_cohort_id: str,
        count: int,
        band: str | None = None,
        activity: str | None = None,
        average_level: float | None = None,
    ) -> str:
        """Move part of one settled cohort into a new cohort without changing tracked population total."""
        runtime.split_population_cohort(
            cohort_id,
            new_cohort_id,
            count,
            band=band,
            activity=activity,
            average_level=average_level,
        )
        return _json(runtime.population_cohort_state(new_cohort_id))

    @mcp.tool()
    def set_player_population_cohort_role(
        cohort_id: str,
        band: str,
        activity: str,
        average_level: float | None = None,
    ) -> str:
        """Change a whole settled cohort's strategic role/activity without creating or destroying players."""
        runtime.set_population_cohort_role(
            cohort_id,
            band,
            activity=activity,
            average_level=average_level,
        )
        return _json(runtime.population_cohort_state(cohort_id))

    @mcp.tool()
    def schedule_player_population_travel(cohort_id: str, destination_id: str) -> str:
        """Schedule a settled cohort to move concurrently over the authoritative world graph."""
        runtime.schedule_population_travel(cohort_id, destination_id)
        return _json(runtime.population_cohort_state(cohort_id))

    @mcp.tool()
    def apply_player_population_losses(cohort_id: str, deaths: int, cause: str) -> str:
        """Record deaths among unmaterialized players in one cohort; tracked population remains conserved."""
        runtime.apply_population_losses(cohort_id, deaths, cause=cause)
        return _json(runtime.population_cohort_state(cohort_id))

    @mcp.tool()
    def materialize_player_population_member(cohort_id: str, actor_id: str) -> str:
        """Claim one existing living PLAYER actor from a settled abstract cohort, decrementing that cohort by one."""
        return _json(runtime.materialize_population_member(cohort_id, actor_id))
