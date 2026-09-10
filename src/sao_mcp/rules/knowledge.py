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
    knower_id: str
    fact_id: str
    value: Any
    basis: EpistemicBasis
    source_id: str | None
    learned_at_ms: int
