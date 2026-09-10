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
        runtime and already-completed mechanical actions are not rolled back. NPC travel actions schedule
        concurrent activity; they do not advance the world clock by themselves. Dynamic facts enter an
        entity's knowledge only through explicit observation, inference, or an actual colocated report.
        """
        return _json(gm_turn_executor.execute(actions, world_tick_ms=world_tick_ms))

    @mcp.tool()
    def get_gm_turn_action_contract() -> str:
        """Return the exact supported structured action names and required/optional fields for execute_gm_turn."""
        return _json({"actions": gm_turn_executor.supported_actions()})

    @mcp.tool()
    def get_npc_agenda(npc_id: str) -> str:
        """Inspect one NPC's current goal, concurrent activity and authoritative settled/in-transit location."""
        return _json(gm_turn_executor.runtime.npc_agenda_state(npc_id))

    @mcp.tool()
    def get_npc_activity_history(npc_id: str | None = None) -> str:
        """Inspect completed autonomous NPC activities without mutating the world."""
        rows = gm_turn_executor.runtime.npc_activity_history
        if npc_id is not None:
            rows = [row for row in rows if row["npc_id"] == npc_id]
        return _json({"activities": rows})

    @mcp.tool()
    def get_entity_knowledge(entity_id: str) -> str:
        """Inspect the entity's current dynamic beliefs, each derived from its latest knowledge event."""
        return _json(gm_turn_executor.runtime.knowledge_state(entity_id))

    @mcp.tool()
    def get_entity_knowledge_history(entity_id: str) -> str:
        """Inspect the entity's full dynamic knowledge history, preserving rumors, mistakes and corrections."""
        knower_id = gm_turn_executor.runtime._knowledge_owner_id(entity_id)
        rows = [
            event
            for event in gm_turn_executor.runtime.knowledge_events
            if event.knower_id == knower_id
        ]
        return _json({"knower_id": knower_id, "events": rows})
