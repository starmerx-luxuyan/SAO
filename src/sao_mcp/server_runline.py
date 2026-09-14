from __future__ import annotations

import json
from enum import Enum
from typing import Any

from sao_mcp.runtime.player_runline import PlayerRunline


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_player_runline_tools(mcp, runline: PlayerRunline) -> None:
    @mcp.tool()
    def get_turn_contract() -> str:
        """Return the single public ordinary-play action contract and fixed server-owned runline."""
        return _json(runline.contract())

    @mcp.tool()
    def turn_execute(actor_id: str, actions: list[dict[str, Any]]) -> str:
        """Execute ordinary play through the fixed observe->gate->execute->settle->refresh pipeline."""
        return _json(runline.execute(actor_id, actions))
