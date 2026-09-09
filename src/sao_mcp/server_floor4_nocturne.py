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


def register_floor4_nocturne_tools(mcp, nocturne) -> None:
    @mcp.tool()
    def open_progressive9_five_key_backtrack(harin_instance_id: str, aghyellr_instance_id: str) -> str:
        """Continue the validated five-sacred-key Elf War state into Progressive 9, where the trail unexpectedly points back to Floor 4."""
        return _json(nocturne.open_five_key_backtrack(harin_instance_id, aghyellr_instance_id))

    @mcp.tool()
    def arrive_progressive9_yofel_castle(instance_id: str) -> str:
        """After players use normal gates and Floor 4 roads, acknowledge the complete pursuit group at Yofel Castle and meet the existing Lavik actor."""
        return _json(nocturne.arrive_yofel_castle(instance_id))

    @mcp.tool()
    def accept_progressive9_lavik_request(instance_id: str, actor_id: str) -> str:
        """Accept Lavik's Progressive 9 request at Yofel Castle without replacing the existing five-key pursuit state."""
        return _json(nocturne.accept_lavik_request(instance_id, actor_id))

    @mcp.tool()
    def meet_progressive9_yofilis(instance_id: str, actor_id: str) -> str:
        """Meet Viscount Yofilis at Yofel Castle and open the ancient elven-dispute thread documented for Progressive 9."""
        return _json(nocturne.meet_yofilis(instance_id, actor_id))

    @mcp.tool()
    def embark_progressive9_lake_yofel(instance_id: str) -> str:
        """Move the complete Nocturne pursuit group from Yofel Castle onto the real Lake Yofel world node."""
        return _json(nocturne.embark_lake_yofel(instance_id))

    @mcp.tool()
    def follow_progressive9_river_ull_to_hideout(instance_id: str) -> str:
        """Follow Lake Yofel, River Ull, the caldera and Bear Forest route to the existing submerged Floor 4 Fallen Elf hideout."""
        return _json(nocturne.follow_river_ull_to_fallen_hideout(instance_id))

    @mcp.tool()
    def get_progressive9_nocturne_state(instance_id: str) -> str:
        """Inspect the Floor 7 handoff sources, real five-key assets, Lavik/Yofilis state and Floor 4 Nocturne route progress."""
        return _json(nocturne.status(instance_id))
