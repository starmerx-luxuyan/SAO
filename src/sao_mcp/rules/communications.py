from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum

from sao_mcp.domain.models import CombatantState


MAX_SHORT_MESSAGE_CHARS = 96  # Simulation UI cap; canon only establishes a very short message limit.


class MessageChannel(StrEnum):
    STRANGER_INSTANT = "stranger_instant"
    FRIEND = "friend"
    GUILD = "guild"
    SPOUSE = "spouse"


@dataclass(slots=True)
class ShortMessage:
    message_id: str
    sender_id: str
    recipient_id: str
    channel: MessageChannel
    text: str
    sent_at_ms: int
    read_at_ms: int | None = None
    delivery_confirmation_visible: bool = True


class CommunicationsRuntime:
    """Persistent system messages. Permission checks remain in the enclosing game runtime."""

    def __init__(self) -> None:
        self.messages: dict[str, ShortMessage] = {}
        self.inbox_by_actor: dict[str, list[str]] = {}
        self.outbox_by_actor: dict[str, list[str]] = {}

    @staticmethod
    def validate_text(text: str) -> str:
        clean = " ".join(text.strip().split())
        if not clean:
            raise ValueError("message text is empty")
        if len(clean) > MAX_SHORT_MESSAGE_CHARS:
            raise ValueError(f"short message exceeds runtime cap of {MAX_SHORT_MESSAGE_CHARS} characters")
        return clean

    def send(
        self,
        sender: CombatantState,
        recipient: CombatantState,
        channel: MessageChannel | str,
        text: str,
        *,
        now_ms: int,
        delivery_confirmation_visible: bool,
    ) -> ShortMessage:
        clean = self.validate_text(text)
        message = ShortMessage(
            message_id=f"msg_{uuid.uuid4().hex[:12]}",
            sender_id=sender.actor_id,
            recipient_id=recipient.actor_id,
            channel=MessageChannel(channel),
            text=clean,
            sent_at_ms=now_ms,
            delivery_confirmation_visible=delivery_confirmation_visible,
        )
        self.messages[message.message_id] = message
        self.inbox_by_actor.setdefault(recipient.actor_id, []).append(message.message_id)
        self.outbox_by_actor.setdefault(sender.actor_id, []).append(message.message_id)
        return message

    def inbox(self, actor_id: str, *, unread_only: bool = False) -> list[ShortMessage]:
        rows = [self.messages[mid] for mid in self.inbox_by_actor.get(actor_id, []) if mid in self.messages]
        if unread_only:
            rows = [row for row in rows if row.read_at_ms is None]
        return rows

    def outbox(self, actor_id: str) -> list[ShortMessage]:
        return [self.messages[mid] for mid in self.outbox_by_actor.get(actor_id, []) if mid in self.messages]

    def mark_read(self, actor_id: str, message_id: str, *, now_ms: int) -> ShortMessage:
        message = self.messages[message_id]
        if message.recipient_id != actor_id:
            raise ValueError("only the recipient can read this message")
        if message.read_at_ms is None:
            message.read_at_ms = now_ms
        return message

    def dump_state(self) -> dict:
        return {
            "messages": {message_id: asdict(message) for message_id, message in self.messages.items()},
            "inbox_by_actor": {actor_id: list(ids) for actor_id, ids in self.inbox_by_actor.items()},
            "outbox_by_actor": {actor_id: list(ids) for actor_id, ids in self.outbox_by_actor.items()},
        }

    def load_state(self, payload: dict) -> None:
        self.messages = {
            message_id: ShortMessage(
                message_id=row["message_id"],
                sender_id=row["sender_id"],
                recipient_id=row["recipient_id"],
                channel=MessageChannel(row["channel"]),
                text=row["text"],
                sent_at_ms=int(row["sent_at_ms"]),
                read_at_ms=row.get("read_at_ms"),
                delivery_confirmation_visible=bool(row.get("delivery_confirmation_visible", True)),
            )
            for message_id, row in payload.get("messages", {}).items()
        }
        self.inbox_by_actor = {
            actor_id: [mid for mid in ids if mid in self.messages]
            for actor_id, ids in payload.get("inbox_by_actor", {}).items()
        }
        self.outbox_by_actor = {
            actor_id: [mid for mid in ids if mid in self.messages]
            for actor_id, ids in payload.get("outbox_by_actor", {}).items()
        }
