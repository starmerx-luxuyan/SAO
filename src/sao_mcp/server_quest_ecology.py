from __future__ import annotations

import json
from dataclasses import asdict
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


def register_quest_ecology_tools(mcp, runtime) -> None:
    @mcp.tool()
    def list_ecological_quests(actor_id: str) -> str:
        """List active living-world contracts posted at the player's current task board."""
        actor = runtime.actors[actor_id]
        if actor.location_id is None:
            return _json({"actorId": actor_id, "locationId": None, "contracts": []})
        rows = []
        for contract_id, contract in sorted(runtime.quest_contracts.items()):
            occurrence = runtime.world_events.occurrences[contract.occurrence_id]
            if contract.posting_location_id != actor.location_id or occurrence.status.value != "active":
                continue
            row = runtime.quest_contract_state(contract_id)
            rows.append(row)
        return _json({"actorId": actor_id, "locationId": actor.location_id, "contracts": rows})

    @mcp.tool()
    def get_quest_ecology_state(contract_id: str | None = None) -> str:
        """Inspect living quest contracts and their authoritative WorldEvent lifecycle."""
        return _json(runtime.quest_ecology_state(contract_id))

    @mcp.tool()
    def get_quest_ecology_history(limit: int = 100) -> str:
        """Inspect recent contract publication, competition, termination and resolution events."""
        if limit < 1:
            raise ValueError("quest ecology history limit must be positive")
        return _json({"events": runtime.quest_ecology_history[-limit:]})

    @mcp.tool()
    def accept_ecological_quest(actor_id: str, contract_id: str) -> str:
        """Accept one currently active living-world contract at its real posting location."""
        return _json(asdict(runtime.accept_quest_contract(actor_id, contract_id)))

    @mcp.tool()
    def claim_ecological_quest(actor_id: str, contract_id: str) -> str:
        """Turn in a won/completed living-world contract at its posting location."""
        return _json(asdict(runtime.claim_quest(actor_id, contract_id)))
