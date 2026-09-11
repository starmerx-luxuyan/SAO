from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EpistemicBasis(StrEnum):
    OBSERVED = "observed"
    REPORTED = "reported"
    INFERRED = "inferred"


@dataclass(slots=True, frozen=True)
class KnowledgeEvent:
    event_id: str
    knower_id: str
    fact_id: str
    value: Any
    basis: EpistemicBasis
    source_id: str | None
    learned_at_ms: int
    confidence: float
    expires_at_ms: int | None
    learned_location_id: str | None
    evidence_event_ids: tuple[str, ...] = ()
    supersedes_event_id: str | None = None
    transmission_depth: int = 0

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("knowledge event_id must be non-empty")
        if not self.knower_id:
            raise ValueError("knowledge knower_id must be non-empty")
        if not self.fact_id:
            raise ValueError("knowledge fact_id must be non-empty")
        if self.learned_at_ms < 0:
            raise ValueError("knowledge learned_at_ms cannot be negative")
        if not 0.0 < self.confidence <= 1.0:
            raise ValueError("knowledge confidence must be in (0, 1]")
        if self.expires_at_ms is not None and self.expires_at_ms <= self.learned_at_ms:
            raise ValueError("knowledge expiry must be after learning time")
        if self.transmission_depth < 0:
            raise ValueError("knowledge transmission_depth cannot be negative")
        if len(set(self.evidence_event_ids)) != len(self.evidence_event_ids):
            raise ValueError("knowledge evidence_event_ids must be unique")

    def stale_at(self, now_ms: int) -> bool:
        if now_ms < 0:
            raise ValueError("knowledge staleness time cannot be negative")
        return self.expires_at_ms is not None and now_ms >= self.expires_at_ms
