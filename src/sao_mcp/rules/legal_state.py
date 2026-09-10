from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class SentenceKind(StrEnum):
    IMPRISONMENT = "imprisonment"
    EXECUTION = "execution"


class SentenceStatus(StrEnum):
    ORDERED = "ordered"
    ACTIVE = "active"


@dataclass(slots=True)
class CustodyState:
    custody_id: str
    actor_id: str
    authority_id: str
    case_id: str
    restriction_code: str
    reason: str
    started_at_ms: int


@dataclass(slots=True)
class SentenceState:
    sentence_id: str
    actor_id: str
    case_id: str
    authority_id: str
    kind: SentenceKind
    status: SentenceStatus
    issued_at_ms: int
    started_at_ms: int | None = None
    release_at_ms: int | None = None


class LegalStateLedger:
    """Authoritative current custody and sentence state.

    Scenario dockets describe why a case exists. This ledger alone decides whether an actor is
    currently detained or under an unresolved sentence order. Completed/released states are moved
    to history and no longer participate in runtime decisions.
    """

    def __init__(self) -> None:
        self.custody_by_actor: dict[str, CustodyState] = {}
        self.sentence_by_actor: dict[str, SentenceState] = {}
        self.history: list[dict] = []

    def custody_for(self, actor_id: str) -> CustodyState | None:
        return self.custody_by_actor.get(actor_id)

    def sentence_for(self, actor_id: str) -> SentenceState | None:
        return self.sentence_by_actor.get(actor_id)

    def take_custody(
        self,
        *,
        custody_id: str,
        actor_id: str,
        authority_id: str,
        case_id: str,
        restriction_code: str,
        reason: str,
        started_at_ms: int,
    ) -> CustodyState:
        if actor_id in self.custody_by_actor:
            raise ValueError(f"actor {actor_id} is already in custody")
        if not custody_id or not authority_id or not case_id or not restriction_code or not reason:
            raise ValueError("custody identity, authority, case, restriction and reason are required")
        if started_at_ms < 0:
            raise ValueError("custody start time cannot be negative")
        state = CustodyState(
            custody_id=custody_id,
            actor_id=actor_id,
            authority_id=authority_id,
            case_id=case_id,
            restriction_code=restriction_code,
            reason=reason,
            started_at_ms=started_at_ms,
        )
        self.custody_by_actor[actor_id] = state
        self.history.append({"event": "custody_started", **asdict(state), "at_ms": started_at_ms})
        return state

    def release_custody(self, actor_id: str, *, resolution: str, released_at_ms: int) -> CustodyState:
        if not resolution:
            raise ValueError("custody release resolution is required")
        state = self.custody_by_actor.pop(actor_id)
        if released_at_ms < state.started_at_ms:
            self.custody_by_actor[actor_id] = state
            raise ValueError("custody release cannot precede custody start")
        self.history.append(
            {
                "event": "custody_released",
                **asdict(state),
                "resolution": resolution,
                "released_at_ms": released_at_ms,
                "at_ms": released_at_ms,
            }
        )
        return state

    def issue_sentence(
        self,
        *,
        sentence_id: str,
        actor_id: str,
        case_id: str,
        authority_id: str,
        kind: SentenceKind | str,
        issued_at_ms: int,
    ) -> SentenceState:
        if actor_id in self.sentence_by_actor:
            raise ValueError(f"actor {actor_id} already has an unresolved sentence")
        if not sentence_id or not case_id or not authority_id:
            raise ValueError("sentence identity, case and authority are required")
        if issued_at_ms < 0:
            raise ValueError("sentence issue time cannot be negative")
        state = SentenceState(
            sentence_id=sentence_id,
            actor_id=actor_id,
            case_id=case_id,
            authority_id=authority_id,
            kind=SentenceKind(kind),
            status=SentenceStatus.ORDERED,
            issued_at_ms=issued_at_ms,
        )
        self.sentence_by_actor[actor_id] = state
        self.history.append({"event": "sentence_ordered", **asdict(state), "at_ms": issued_at_ms})
        return state

    def begin_imprisonment(self, actor_id: str, *, started_at_ms: int, duration_ms: int) -> SentenceState:
        state = self.sentence_by_actor[actor_id]
        if state.kind is not SentenceKind.IMPRISONMENT:
            raise ValueError("only an imprisonment order can begin an imprisonment term")
        if state.status is not SentenceStatus.ORDERED:
            raise ValueError("imprisonment term has already started")
        if duration_ms < 1:
            raise ValueError("imprisonment duration must be positive")
        if started_at_ms < state.issued_at_ms:
            raise ValueError("imprisonment cannot start before sentence issue")
        state.status = SentenceStatus.ACTIVE
        state.started_at_ms = started_at_ms
        state.release_at_ms = started_at_ms + duration_ms
        self.history.append(
            {
                "event": "imprisonment_started",
                "sentence_id": state.sentence_id,
                "actor_id": actor_id,
                "case_id": state.case_id,
                "started_at_ms": started_at_ms,
                "release_at_ms": state.release_at_ms,
                "duration_ms": duration_ms,
                "at_ms": started_at_ms,
            }
        )
        return state

    def complete_imprisonment(self, actor_id: str, *, completed_at_ms: int) -> SentenceState:
        state = self.sentence_by_actor[actor_id]
        if state.kind is not SentenceKind.IMPRISONMENT or state.status is not SentenceStatus.ACTIVE:
            raise ValueError("actor has no active imprisonment term")
        if state.release_at_ms is None or completed_at_ms < state.release_at_ms:
            raise ValueError("the active imprisonment term has not reached its release time")
        self.sentence_by_actor.pop(actor_id)
        self.history.append(
            {
                "event": "imprisonment_completed",
                **asdict(state),
                "completed_at_ms": completed_at_ms,
                "at_ms": completed_at_ms,
            }
        )
        return state

    def dump_state(self) -> dict:
        return {
            "custody": {actor_id: asdict(state) for actor_id, state in self.custody_by_actor.items()},
            "sentences": {actor_id: asdict(state) for actor_id, state in self.sentence_by_actor.items()},
            "history": list(self.history),
        }

    def load_state(self, payload: dict) -> None:
        self.custody_by_actor = {
            actor_id: CustodyState(**row)
            for actor_id, row in payload.get("custody", {}).items()
        }
        self.sentence_by_actor = {
            actor_id: SentenceState(
                sentence_id=row["sentence_id"],
                actor_id=row["actor_id"],
                case_id=row["case_id"],
                authority_id=row["authority_id"],
                kind=SentenceKind(row["kind"]),
                status=SentenceStatus(row["status"]),
                issued_at_ms=int(row["issued_at_ms"]),
                started_at_ms=row.get("started_at_ms"),
                release_at_ms=row.get("release_at_ms"),
            )
            for actor_id, row in payload.get("sentences", {}).items()
        }
        self.history = list(payload.get("history", []))
