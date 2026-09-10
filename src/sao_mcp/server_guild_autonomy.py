from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def _default(value: Any):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_guild_autonomy_tools(mcp, runtime) -> None:
    @mcp.tool()
    def assign_guild_operation(
        guild_id: str,
        leader_id: str,
        goal_id: str,
        target_location_id: str,
        assigned_member_ids: list[str],
        basis_fact_id: str | None = None,
    ) -> str:
        """Assign one persistent guild operation through the guild's current leader authority."""
        agenda = runtime.assign_guild_goal(
            guild_id,
            leader_id,
            goal_id,
            target_location_id,
            assigned_member_ids,
            basis_fact_id=basis_fact_id,
        )
        return _json(runtime.guild_agenda_state(agenda.guild_id))

    @mcp.tool()
    def clear_guild_operation(guild_id: str, leader_id: str) -> str:
        """Clear a completed or idle guild operation through the guild's current leader authority."""
        runtime.clear_guild_goal(guild_id, leader_id)
        return _json(runtime.guild_agenda_state(guild_id))

    @mcp.tool()
    def get_guild_agenda(guild_id: str) -> str:
        """Inspect a guild's current strategic goal, assigned members and concurrent movement state."""
        return _json(runtime.guild_agenda_state(guild_id))

    @mcp.tool()
    def get_guild_activity_history(guild_id: str | None = None) -> str:
        """Inspect committed guild-operation history without mutating world state."""
        rows = runtime.guild_activity_history
        if guild_id is not None:
            rows = [row for row in rows if row["guild_id"] == guild_id]
        return _json({"activities": rows})
