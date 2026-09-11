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


def register_social_autonomy_tools(mcp, runtime) -> None:
    @mcp.tool()
    def send_known_fact_message(sender_id: str, target_id: str, fact_id: str, text: str) -> str:
        """Send a short message carrying one fact the sender actually knows; knowledge transfers only when read."""
        return _json(asdict(runtime.send_known_fact_message(sender_id, target_id, fact_id, text)))

    @mcp.tool()
    def post_guild_fact_notice(sender_id: str, guild_id: str, fact_id: str) -> str:
        """Post one known fact to current authoritative guild members with delayed delivery."""
        rows = runtime.post_guild_fact_notice(sender_id, guild_id, fact_id)
        return _json({"deliveryIds": [row.delivery_id for row in rows]})

    @mcp.tool()
    def spread_local_rumor(sender_id: str, fact_id: str) -> str:
        """Start a local rumor from one current belief; recipients must still be colocated when it arrives."""
        rows = runtime.spread_local_rumor(sender_id, fact_id)
        return _json({"deliveryIds": [row.delivery_id for row in rows]})

    @mcp.tool()
    def subscribe_argo_intelligence(actor_id: str) -> str:
        """Subscribe after an actual meeting with Argo; reports only contain information Argo herself acquired."""
        return _json(runtime.subscribe_argo_intelligence(actor_id))

    @mcp.tool()
    def unsubscribe_argo_intelligence(actor_id: str) -> str:
        """End an Argo intelligence subscription."""
        return _json(runtime.unsubscribe_argo_intelligence(actor_id))

    @mcp.tool()
    def brief_argo(sender_id: str, fact_id: str) -> str:
        """Give Argo one fact in a real colocated conversation, allowing her broker network to relay it."""
        return _json(asdict(runtime.brief_argo(sender_id, fact_id)))

    @mcp.tool()
    def get_social_communication_state() -> str:
        """Inspect delayed social transmissions and Argo subscription state."""
        return _json(runtime.social_communication_state())

    @mcp.tool()
    def get_social_communication_history(limit: int = 100) -> str:
        """Inspect recent notice, rumor, broker and delivery events."""
        if limit < 1:
            raise ValueError("social communication history limit must be positive")
        return _json({"events": runtime.social_history[-limit:]})
