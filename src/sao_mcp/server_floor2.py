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


def register_floor2_tools(mcp, taurus_raid, martial_arts) -> None:
    @mcp.tool()
    def start_floor2_taurus_raid(player_ids: list[str]) -> str:
        """Begin the Floor 2 Taurus raid with Nato and Baran in the Boss Room; Asterius enters automatically after both fall."""
        return _json(taurus_raid.start_raid(player_ids))

    @mcp.tool()
    def get_floor2_taurus_raid(instance_id: str) -> str:
        """Inspect the current Floor 2 Taurus raid stage and combatant state."""
        return _json(taurus_raid.status(instance_id))

    @mcp.tool()
    def start_floor2_martial_arts_trial(actor_id: str) -> str:
        """Accept the mountain-top rock trial, applying the quest's persistent whisker paint."""
        return _json(martial_arts.start_trial(actor_id))

    @mcp.tool()
    def practice_floor2_martial_arts_rock(actor_id: str, hours: int = 1) -> str:
        """Practice palm strikes against the nearly unbreakable rock and advance world time."""
        return _json(martial_arts.practice_palm_strikes(actor_id, hours=hours))

    @mcp.tool()
    def get_floor2_martial_arts_trial(actor_id: str) -> str:
        """Inspect rock progress, whisker paint and Martial Arts acquisition state."""
        return _json(martial_arts.status(actor_id))
