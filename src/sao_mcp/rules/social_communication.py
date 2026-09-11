from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


SOCIAL_TICK_MS = 5 * 60 * 1000
GUILD_NOTICE_DELAY_MS = 60 * 1000
LOCAL_RUMOR_DELAY_MS = 10 * 60 * 1000
ARGO_REPORT_DELAY_MS = 2 * 60 * 1000
TERMINAL_NOTICE_TTL_MS = 6 * 60 * 60 * 1000
MAX_AUTONOMOUS_RUMOR_DEPTH = 3


class SocialDeliveryChannel(StrEnum):
    GUILD_NOTICE = "guild_notice"
    LOCAL_RUMOR = "local_rumor"
    ARGO_INTELLIGENCE = "argo_intelligence"


class SocialDeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass(slots=True)
class SocialDeliveryState:
    delivery_id: str
    channel: SocialDeliveryChannel
    sender_id: str
    recipient_id: str
    source_event_id: str
    fact_id: str
    created_at_ms: int
    due_at_ms: int
    confidence_factor: float
    scope_id: str | None = None
    status: SocialDeliveryStatus = SocialDeliveryStatus.PENDING
    delivered_at_ms: int | None = None
    received_event_id: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.delivery_id or not self.sender_id or not self.recipient_id:
            raise ValueError("social delivery requires delivery, sender and recipient IDs")
        if not self.source_event_id or not self.fact_id:
            raise ValueError("social delivery requires source knowledge event and fact IDs")
        if self.created_at_ms < 0 or self.due_at_ms <= self.created_at_ms:
            raise ValueError("social delivery due time must follow creation")
        if not 0.0 < self.confidence_factor <= 1.0:
            raise ValueError("social delivery confidence factor must be in (0, 1]")
        if self.status is SocialDeliveryStatus.PENDING:
            if self.delivered_at_ms is not None or self.received_event_id is not None or self.failure_reason is not None:
                raise ValueError("pending social delivery cannot carry terminal fields")
        elif self.status is SocialDeliveryStatus.DELIVERED:
            if self.delivered_at_ms is None or self.received_event_id is None or self.failure_reason is not None:
                raise ValueError("delivered social delivery requires time and received event")
        else:
            if self.delivered_at_ms is None or not self.failure_reason or self.received_event_id is not None:
                raise ValueError("failed social delivery requires time and failure reason only")

    @property
    def pending(self) -> bool:
        return self.status is SocialDeliveryStatus.PENDING

    def deliver(self, *, received_event_id: str, at_ms: int) -> None:
        if not self.pending:
            raise ValueError("only pending social delivery can deliver")
        if at_ms < self.due_at_ms:
            raise ValueError("social delivery cannot complete before due time")
        if not received_event_id:
            raise ValueError("delivered social fact requires received knowledge event")
        self.status = SocialDeliveryStatus.DELIVERED
        self.delivered_at_ms = at_ms
        self.received_event_id = received_event_id

    def fail(self, *, reason: str, at_ms: int) -> None:
        if not self.pending:
            raise ValueError("only pending social delivery can fail")
        if at_ms < self.due_at_ms:
            raise ValueError("social delivery cannot fail before due time")
        if not reason:
            raise ValueError("social delivery failure reason is required")
        self.status = SocialDeliveryStatus.FAILED
        self.delivered_at_ms = at_ms
        self.failure_reason = reason
