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


def register_gm_tools(mcp, gm_turn_executor, gm_decision_runtime) -> None:
    @mcp.tool()
    def preview_gm_decision(
        proposed_actions: list[dict[str, Any]],
        observer_actor_ids: list[str],
        world_tick_ms: int = 0,
    ) -> str:
        """Validate a proposed ordinary GM plan strictly against a fresh player-viewpoint observation.

        This is a pure preview. It does not mutate the campaign and does not expose raw runtime state.
        """
        observation = gm_turn_executor.observe(observer_actor_ids)
        decision = gm_decision_runtime.decide(
            observation,
            proposed_actions,
            world_tick_ms=world_tick_ms,
        )
        return _json(decision.to_dict())

    @mcp.tool()
    def execute_gm_decision(
        proposed_actions: list[dict[str, Any]],
        observer_actor_ids: list[str],
        world_tick_ms: int = 0,
    ) -> str:
        """Ground a proposed ordinary player-action plan in a fresh observation, then execute it.

        The decision runtime receives only the gated observation packet. Hidden NPC goals, guild strategy,
        world-event state and other server-only authorities cannot be used as decision inputs.
        """
        observation = gm_turn_executor.observe(observer_actor_ids)
        decision = gm_decision_runtime.decide(
            observation,
            proposed_actions,
            world_tick_ms=world_tick_ms,
        )
        execution = gm_turn_executor.execute(
            list(decision.actions),
            observer_actor_ids=list(decision.observer_actor_ids),
            world_tick_ms=decision.world_tick_ms,
        )
        return _json({"decision": decision.to_dict(), "execution": execution})

    @mcp.tool()
    def get_gm_decision_contract() -> str:
        """Return the player-observable action surface accepted by the GM decision gate."""
        return _json(gm_decision_runtime.contract())

    @mcp.tool()
    def get_gm_observation(observer_actor_ids: list[str]) -> str:
        """Return current observable state and decision capabilities for explicit player viewpoints."""
        return _json(gm_turn_executor.observe(observer_actor_ids))
