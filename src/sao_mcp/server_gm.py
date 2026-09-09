from __future__ import annotations

import json
from enum import Enum
from typing import Any


def _default(value: Any):
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
        runtime and already-completed mechanical actions are not rolled back.
        """
        return _json(gm_turn_executor.execute(actions, world_tick_ms=world_tick_ms))

    @mcp.tool()
    def get_gm_turn_action_contract() -> str:
        """Return the exact supported structured action names and required/optional fields for execute_gm_turn."""
        return _json({"actions": gm_turn_executor.supported_actions()})
