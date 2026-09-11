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


def register_gm_tools(mcp, gm_turn_executor) -> None:
    @mcp.tool()
    def execute_gm_turn(actions: list[dict[str, Any]], world_tick_ms: int = 0) -> str:
        """Execute an already-decided structured GM action plan through existing runtime mechanics.

        This tool does not interpret natural language, select fallback actions, or roll separate outcomes.
        Action shapes are validated before execution; mechanical failures are raised by the authoritative
        runtime and already-completed mechanical actions are not rolled back. NPC and guild travel actions
        schedule concurrent activity; they do not advance the world clock by themselves. Dynamic facts enter
        an entity's knowledge only through explicit observation, inference, or an actual colocated report.
        """
        return _json(gm_turn_executor.execute(actions, world_tick_ms=world_tick_ms))

    @mcp.tool()
    def get_gm_turn_action_contract() -> str:
        """Return the exact supported structured action names and required/optional fields for execute_gm_turn."""
        return _json({"actions": gm_turn_executor.supported_actions()})

    @mcp.tool()
    def get_npc_agenda(npc_id: str) -> str:
        """Inspect one NPC's current execution activity plus actor-core goal projection and location."""
        return _json(gm_turn_executor.runtime.npc_agenda_state(npc_id))

    @mcp.tool()
    def get_npc_actor_core(npc_id: str) -> str:
        """Inspect one NPC's long-term goals, current business, short-term plan, decision inputs and authoritative resources."""
        return _json(gm_turn_executor.runtime.npc_actor_core_state(npc_id))

    @mcp.tool()
    def get_npc_scheduler(npc_id: str) -> str:
        """Inspect one NPC's world-time execution step, due time, interruptibility and goal-bound scheduler operations."""
        return _json(gm_turn_executor.runtime.npc_scheduler_state(npc_id))

    @mcp.tool()
    def get_npc_activity_history(npc_id: str | None = None) -> str:
        """Inspect completed autonomous NPC activities without mutating the world."""
        rows = gm_turn_executor.runtime.npc_activity_history
        if npc_id is not None:
            rows = [row for row in rows if row["npc_id"] == npc_id]
        return _json({"activities": rows})

    @mcp.tool()
    def get_guild_agenda(guild_id: str) -> str:
        """Inspect one guild's current strategic goal, assigned real members and concurrent travel leg."""
        return _json(gm_turn_executor.runtime.guild_agenda_state(guild_id))

    @mcp.tool()
    def get_guild_activity_history(guild_id: str | None = None) -> str:
        """Inspect completed and issued guild-operation history without mutating the world."""
        rows = gm_turn_executor.runtime.guild_activity_history
        if guild_id is not None:
            rows = [row for row in rows if row["guild_id"] == guild_id]
        return _json({"activities": rows})

    @mcp.tool()
    def get_entity_knowledge(entity_id: str) -> str:
        """Inspect the entity's current dynamic beliefs, each derived from its latest knowledge event."""
        return _json(gm_turn_executor.runtime.knowledge_state(entity_id))

    @mcp.tool()
    def get_entity_knowledge_history(entity_id: str) -> str:
        """Inspect full belief history with confidence, expiry, evidence and correction provenance."""
        runtime = gm_turn_executor.runtime
        return _json({
            "knower_id": runtime._knowledge_owner_id(entity_id),
            "events": runtime.knowledge_history(entity_id),
        })

    @mcp.tool()
    def get_knowledge_event_chain(event_id: str) -> str:
        """Trace one belief event back through the exact observations/reports/inferences that support it."""
        return _json({"events": gm_turn_executor.runtime.knowledge_event_chain(event_id)})

    @mcp.tool()
    def get_world_event_state(occurrence_id: str | None = None) -> str:
        """Inspect registered event rules and persistent world-event lifecycle occurrences."""
        return _json(gm_turn_executor.runtime.world_event_state(occurrence_id))

    @mcp.tool()
    def get_world_event_history(rule_id: str | None = None) -> str:
        """Inspect world-event lifecycle history, optionally filtered by one rule id."""
        return _json({"events": gm_turn_executor.runtime.world_event_history(rule_id)})

    @mcp.tool()
    def get_canonical_timeline_profile() -> str:
        """Inspect available canon-continuity profiles and the current non-authoritative milestone expectation overlay."""
        runtime = gm_turn_executor.runtime
        return _json(
            {
                "profiles": runtime.canonical_timeline_profiles(),
                "current": runtime.canonical_timeline_state(),
            }
        )

    @mcp.tool()
    def set_canonical_timeline_profile(profile_id: str | None, anchor_world_ms: int = 0) -> str:
        """Select a canon expectation profile, or null to disable it; this never mutates world outcomes or actor state."""
        return _json(
            gm_turn_executor.runtime.select_canonical_timeline_profile(
                profile_id,
                anchor_world_ms=anchor_world_ms,
            )
        )
