from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sao_mcp.domain.models import Provenance, ProvenanceKind
from sao_mcp.rules.quests import (
    QuestDefinition,
    QuestObjectiveDefinition,
    QuestObjectiveKind,
    QuestReward,
)


QUEST_ECOLOGY_TICK_MS = 60 * 60 * 1000
MONSTER_CONTRACT_DURATION_MS = 4 * QUEST_ECOLOGY_TICK_MS
MARKET_CONTRACT_DURATION_MS = 3 * QUEST_ECOLOGY_TICK_MS
QUEST_ECOLOGY_WORLD_EVENT_RULE_ID = "quest_ecology_contract"


class QuestContractSource(StrEnum):
    MONSTER_PRESSURE = "monster_pressure"
    MARKET_SHORTAGE = "market_shortage"


@dataclass(slots=True)
class QuestContractState:
    contract_id: str
    occurrence_id: str
    source_kind: QuestContractSource
    source_ref_id: str
    source_location_id: str
    posting_location_id: str
    quest_id: str
    objective_kind: QuestObjectiveKind
    target_id: str
    required: int
    created_at_ms: int
    expires_at_ms: int
    reward_col: int
    reward_xp: int
    world_progress: int = 0
    winner_kind: str | None = None
    winner_ids: tuple[str, ...] = ()
    winner_ref_id: str | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        for value, label in (
            (self.contract_id, "contract id"),
            (self.occurrence_id, "occurrence id"),
            (self.source_ref_id, "source ref"),
            (self.source_location_id, "source location"),
            (self.posting_location_id, "posting location"),
            (self.quest_id, "quest id"),
            (self.target_id, "target id"),
        ):
            if not value:
                raise ValueError(f"quest contract {label} is required")
        if self.required <= 0:
            raise ValueError("quest contract required progress must be positive")
        if self.created_at_ms < 0 or self.expires_at_ms <= self.created_at_ms:
            raise ValueError("quest contract expiry must follow creation")
        if self.reward_col < 0 or self.reward_xp < 0:
            raise ValueError("quest contract rewards cannot be negative")
        if not 0 <= self.world_progress <= self.required:
            raise ValueError("quest contract world progress is outside its objective range")
        if self.revision < 0:
            raise ValueError("quest contract revision cannot be negative")
        if len(set(self.winner_ids)) != len(self.winner_ids):
            raise ValueError("quest contract winner ids must be unique")

    def advance_world_progress(self, quantity: int) -> int:
        if quantity <= 0:
            return 0
        remaining = self.required - self.world_progress
        added = min(remaining, quantity)
        if added:
            self.world_progress += added
            self.revision += 1
        return added

    def mark_winner(
        self,
        *,
        winner_kind: str,
        winner_ids: tuple[str, ...] = (),
        winner_ref_id: str | None = None,
    ) -> None:
        if not winner_kind:
            raise ValueError("quest contract winner kind is required")
        if self.winner_kind is not None:
            raise RuntimeError("quest contract already has a winner")
        if len(set(winner_ids)) != len(winner_ids):
            raise ValueError("quest contract winner ids must be unique")
        self.winner_kind = winner_kind
        self.winner_ids = winner_ids
        self.winner_ref_id = winner_ref_id
        self.revision += 1

    def quest_definition(self, *, floor_number: int) -> QuestDefinition:
        consume = self.objective_kind is QuestObjectiveKind.COLLECT
        return QuestDefinition(
            quest_id=self.quest_id,
            name=(
                f"Ecological Cull: {self.target_id}"
                if self.objective_kind is QuestObjectiveKind.KILL
                else f"Supply Request: {self.target_id}"
            ),
            floor_number=floor_number,
            giver_id=f"quest_board:{self.posting_location_id}",
            turn_in_id=f"quest_board:{self.posting_location_id}",
            objectives=(
                QuestObjectiveDefinition(
                    objective_id="contract_objective",
                    kind=self.objective_kind,
                    target_id=self.target_id,
                    required=self.required,
                    consume_on_turn_in=consume,
                ),
            ),
            reward=QuestReward(col=self.reward_col, xp=self.reward_xp),
            repeatable=False,
            provenance=Provenance(
                ProvenanceKind.SIMULATION,
                notes=(
                    "Runtime-generated living-world contract. The contract exists because current ecology or "
                    "regional market state created demand; it is not a canon quest identity."
                ),
            ),
        )
