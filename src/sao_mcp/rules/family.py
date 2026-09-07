from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class DivorceMode(StrEnum):
    AUTO_PERCENTAGE = "auto_percentage"
    ITEM_SELECTION = "item_selection"
    SURRENDER_ALL = "surrender_all"


class DivorceStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class DivorceProposal:
    proposal_id: str
    marriage_id: str
    proposer_id: str
    target_id: str
    mode: DivorceMode
    proposer_percent: int
    selected_item_ids: list[str] = field(default_factory=list)
    status: DivorceStatus = DivorceStatus.PENDING
    created_at_ms: int = 0
    completed_at_ms: int | None = None

    def dump(self) -> dict:
        return asdict(self)

    @classmethod
    def create(
        cls,
        marriage_id: str,
        proposer_id: str,
        target_id: str,
        mode: DivorceMode | str,
        *,
        proposer_percent: int,
        selected_item_ids: list[str] | None,
        now_ms: int,
    ) -> "DivorceProposal":
        resolved = DivorceMode(mode)
        if not 0 <= proposer_percent <= 100:
            raise ValueError("proposer_percent must be in 0..100")
        if resolved is DivorceMode.SURRENDER_ALL and proposer_percent != 0:
            raise ValueError("surrender_all requires proposer_percent=0")
        return cls(
            proposal_id=f"divorce_{uuid.uuid4().hex[:12]}",
            marriage_id=marriage_id,
            proposer_id=proposer_id,
            target_id=target_id,
            mode=resolved,
            proposer_percent=proposer_percent,
            selected_item_ids=list(dict.fromkeys(selected_item_ids or [])),
            created_at_ms=now_ms,
        )
