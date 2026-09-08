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


def register_floor2_tools(mcp, scenario) -> None:
    @mcp.tool()
    def start_floor2_taurus_raid(player_ids: list[str]) -> str:
        """Begin the Floor 2 Taurus raid with Nato and Baran in the Boss Room."""
        return _json(scenario.start_raid(player_ids))

    @mcp.tool()
    def unleash_floor2_asterius(instance_id: str) -> str:
        """After Nato and Baran are defeated, bring Asterius the Taurus King into the same encounter."""
        return _json(scenario.unleash_asterius(instance_id))

    @mcp.tool()
    def get_floor2_taurus_raid(instance_id: str) -> str:
        """Inspect the current Floor 2 Taurus raid stage and combatant state."""
        return _json(scenario.status(instance_id))
