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
        """Materialize Argo plus the already-existing ALS/DKB cave parties and Forest Elf pursuit party, send a real persistent friend message, and link the Floor 8 incident to Nocturne."""
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
        """Acknowledge assigned emergency responders only after their real actor locations reach Frieben through ordinary teleport/travel rules."""
        return _json(emergency.arrive_frieben(instance_id))

    @mcp.tool()
    def depart_progressive9_frieben_to_sacred_woods(instance_id: str) -> str:
        """Move all assigned responders through the real Frieben -> managed-forest -> protected-woods route with one shared travel clock."""
        return _json(emergency.depart_frieben_to_sacred_woods(instance_id))

    @mcp.tool()
    def inspect_progressive9_sacred_woods_incident(instance_id: str) -> str:
        """Confirm the already-materialized frontline parties are sheltering in the cave while the live Forest Elf pursuit party remains at the damaged protected woods."""
        return _json(emergency.inspect_sacred_woods_incident(instance_id))

    @mcp.tool()
    def follow_progressive9_forest_elves_to_cave_mouth(instance_id: str) -> str:
        """Advance responders and the Forest Elf pursuit party through the same real elapsed route to the escape-cave mouth without treating them as allies."""
        return _json(emergency.follow_to_escape_cave_mouth(instance_id))

    @mcp.tool()
    def enter_progressive9_escape_cave(instance_id: str) -> str:
        """Move only the responders into the cave to meet the ALS/DKB incident parties while the Forest Elf pursuers remain outside in an unresolved standoff."""
        return _json(emergency.enter_escape_cave(instance_id))

    @mcp.tool()
    def get_progressive9_floor8_emergency_state(instance_id: str) -> str:
        """Inspect Argo's real short message, response branch, incident PartyState actors, Forest Elf pursuers, route progress and live cave standoff."""
        return _json(emergency.status(instance_id))