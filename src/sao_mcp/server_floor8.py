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


def register_floor8_tools(mcp, emergency) -> None:
    @mcp.tool()
    def trigger_progressive9_floor8_forest_emergency(nocturne_instance_id: str, recipient_actor_id: str) -> str:
        """Materialize Argo in Frieben, create the authoritative friend contact if needed, send a real persistent cross-floor message, and link the sacred-woods cave incident to Nocturne."""
        return _json(emergency.trigger_from_nocturne(nocturne_instance_id, recipient_actor_id))

    @mcp.tool()
    def assign_progressive9_floor8_response_split(
        instance_id: str,
        floor8_actor_ids: list[str],
        hideout_actor_ids: list[str],
    ) -> str:
        """Assign every Nocturne player exactly once to the Floor 8 emergency or Floor 4 sacred-key branch; no canon split is forced."""
        return _json(emergency.assign_response_split(instance_id, floor8_actor_ids, hideout_actor_ids))

    @mcp.tool()
    def arrive_progressive9_floor8_frieben(instance_id: str) -> str:
        """Acknowledge the assigned emergency responders only after their real actor locations have reached Frieben through ordinary travel/teleport rules."""
        return _json(emergency.arrive_frieben(instance_id))

    @mcp.tool()
    def get_progressive9_floor8_emergency_state(instance_id: str) -> str:
        """Inspect Argo's real short message, branch assignment, responder locations and the still-live Forest Elf cave incident."""
        return _json(emergency.status(instance_id))