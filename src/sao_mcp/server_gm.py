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
    def execute_gm_turn(
        actions: list[dict[str, Any]],
        observer_actor_ids: list[str],
        world_tick_ms: int = 0,
    ) -> str:
        """Execute a structured GM action plan and return only player-viewpoint-gated state.

        The action plan still resolves through authoritative runtime mechanics. The returned packet does
        not expose raw action results, NPC actor-core plans, guild strategy internals, world-event
        occurrences, canonical timeline expectations or another entity's private knowledge.
        """
        return _json(
            gm_turn_executor.execute(
                actions,
                observer_actor_ids=observer_actor_ids,
                world_tick_ms=world_tick_ms,
            )
        )

    @mcp.tool()
    def get_gm_turn_action_contract() -> str:
        """Return the exact structured action names accepted by execute_gm_turn."""
        return _json({"actions": gm_turn_executor.supported_actions()})

    @mcp.tool()
    def get_gm_observation(observer_actor_ids: list[str]) -> str:
        """Return current observable state for explicit player viewpoints only."""
        return _json(gm_turn_executor.observe(observer_actor_ids))
