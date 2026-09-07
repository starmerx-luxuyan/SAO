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


def register_communication_tools(mcp, runtime) -> None:
    @mcp.tool()
    def learn_player_identity(observer_id: str, target_id: str) -> str:
        """Register a player identity only after an actual meeting/shared encounter."""
        return _json(runtime.learn_player_identity(observer_id, target_id))

    @mcp.tool()
    def send_short_message(sender_id: str, target_id: str, text: str) -> str:
        """Send an Aincrad short message using stranger/friend/guild/spouse permissions."""
        message = runtime.send_short_message(sender_id, target_id, text)
        row = asdict(message)
        if not message.delivery_confirmation_visible:
            row["deliveryConfirmed"] = None
            row.pop("recipient_id", None)
        else:
            row["deliveryConfirmed"] = True
        return _json(row)

    @mcp.tool()
    def get_message_inbox(actor_id: str, unread_only: bool = False) -> str:
        """Return persistent inbox messages visible to one player."""
        return _json({"actorId": actor_id, "messages": [asdict(row) for row in runtime.message_inbox(actor_id, unread_only=unread_only)]})

    @mcp.tool()
    def read_short_message(actor_id: str, message_id: str) -> str:
        """Mark one received system message as read."""
        return _json(asdict(runtime.read_message(actor_id, message_id)))

    @mcp.tool()
    def get_message_outbox(actor_id: str) -> str:
        """Return sent-message history; stranger instant messages do not expose delivery confirmation."""
        rows = []
        for message in runtime.message_outbox(actor_id):
            row = asdict(message)
            row["deliveryConfirmed"] = True if message.delivery_confirmation_visible else None
            rows.append(row)
        return _json({"actorId": actor_id, "messages": rows})
