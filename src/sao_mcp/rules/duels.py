from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from sao_mcp.domain.models import CombatantState, EntityKind


class DuelMode(StrEnum):
    FIRST_STRIKE = "first_strike"
    HALF_LOSS = "half_loss"
    TOTAL_LOSS = "total_loss"


class DuelStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class DuelState:
    duel_id: str
    challenger_id: str
    target_id: str
    mode: DuelMode
    status: DuelStatus
    created_at_ms: int
    accepted_at_ms: int | None = None
    completed_at_ms: int | None = None
    starting_hp: dict[str, int] = field(default_factory=dict)
    damage_by_actor: dict[str, int] = field(default_factory=dict)
    winner_id: str | None = None
    loser_id: str | None = None
    completion_reason: str | None = None


@dataclass(slots=True, frozen=True)
class DuelEvaluation:
    duel_id: str
    completed: bool
    winner_id: str | None = None
    loser_id: str | None = None
    reason: str | None = None


class DuelRuntime:
    """Persistent authorized PvP contracts. Numeric First-Strike threshold follows canon references."""

    def __init__(self) -> None:
        self.duels: dict[str, DuelState] = {}

    @staticmethod
    def _validate_player(actor: CombatantState) -> None:
        if actor.kind is not EntityKind.PLAYER:
            raise ValueError("duels are between player characters")
        if not actor.alive:
            raise ValueError("defeated players cannot enter a duel")

    def _open_for_actor(self, actor_id: str) -> DuelState | None:
        for duel in self.duels.values():
            if duel.status in (DuelStatus.PENDING, DuelStatus.ACTIVE) and actor_id in (duel.challenger_id, duel.target_id):
                return duel
        return None

    def challenge(
        self,
        challenger: CombatantState,
        target: CombatantState,
        mode: DuelMode | str,
        *,
        now_ms: int,
    ) -> DuelState:
        self._validate_player(challenger)
        self._validate_player(target)
        if challenger.actor_id == target.actor_id:
            raise ValueError("cannot duel oneself")
        if self._open_for_actor(challenger.actor_id) or self._open_for_actor(target.actor_id):
            raise ValueError("one of the players already has an open duel")
        duel = DuelState(
            duel_id=f"duel_{uuid.uuid4().hex[:12]}",
            challenger_id=challenger.actor_id,
            target_id=target.actor_id,
            mode=DuelMode(mode),
            status=DuelStatus.PENDING,
            created_at_ms=now_ms,
        )
        self.duels[duel.duel_id] = duel
        return duel

    @staticmethod
    def _authorize(actor: CombatantState, opponent_id: str) -> None:
        opponents = set(actor.metadata.get("authorized_duel_opponents", ()))
        opponents.add(opponent_id)
        actor.metadata["authorized_duel_opponents"] = sorted(opponents)

    @staticmethod
    def _deauthorize(actor: CombatantState, opponent_id: str) -> None:
        opponents = set(actor.metadata.get("authorized_duel_opponents", ()))
        opponents.discard(opponent_id)
        if opponents:
            actor.metadata["authorized_duel_opponents"] = sorted(opponents)
        else:
            actor.metadata.pop("authorized_duel_opponents", None)

    def accept(
        self,
        duel_id: str,
        challenger: CombatantState,
        target: CombatantState,
        *,
        accepter_id: str,
        now_ms: int,
    ) -> DuelState:
        duel = self.duels[duel_id]
        if duel.status is not DuelStatus.PENDING:
            raise ValueError("duel request is not pending")
        if accepter_id != duel.target_id:
            raise ValueError("only the challenged player can accept")
        if challenger.actor_id != duel.challenger_id or target.actor_id != duel.target_id:
            raise ValueError("duel participant state does not match request")
        self._validate_player(challenger)
        self._validate_player(target)
        duel.status = DuelStatus.ACTIVE
        duel.accepted_at_ms = now_ms
        duel.starting_hp = {challenger.actor_id: challenger.hp, target.actor_id: target.hp}
        duel.damage_by_actor = {challenger.actor_id: 0, target.actor_id: 0}
        self._authorize(challenger, target.actor_id)
        self._authorize(target, challenger.actor_id)
        challenger.metadata["active_duel_id"] = duel_id
        target.metadata["active_duel_id"] = duel_id
        return duel

    def decline(self, duel_id: str, *, target_id: str) -> DuelState:
        duel = self.duels[duel_id]
        if duel.status is not DuelStatus.PENDING or duel.target_id != target_id:
            raise ValueError("duel request cannot be declined by this player")
        duel.status = DuelStatus.DECLINED
        return duel

    def active_between(self, actor_id: str, target_id: str) -> DuelState | None:
        for duel in self.duels.values():
            if duel.status is not DuelStatus.ACTIVE:
                continue
            if {duel.challenger_id, duel.target_id} == {actor_id, target_id}:
                return duel
        return None

    def _complete(
        self,
        duel: DuelState,
        actors: dict[str, CombatantState],
        *,
        winner_id: str,
        loser_id: str,
        reason: str,
        now_ms: int,
    ) -> DuelEvaluation:
        duel.status = DuelStatus.COMPLETED
        duel.winner_id = winner_id
        duel.loser_id = loser_id
        duel.completion_reason = reason
        duel.completed_at_ms = now_ms
        winner = actors[winner_id]
        loser = actors[loser_id]
        self._deauthorize(winner, loser_id)
        self._deauthorize(loser, winner_id)
        if winner.metadata.get("active_duel_id") == duel.duel_id:
            winner.metadata.pop("active_duel_id", None)
        if loser.metadata.get("active_duel_id") == duel.duel_id:
            loser.metadata.pop("active_duel_id", None)
        return DuelEvaluation(duel.duel_id, True, winner_id, loser_id, reason)

    def evaluate_attack(
        self,
        attacker: CombatantState,
        target: CombatantState,
        *,
        damage: int,
        clean_hit: bool,
        now_ms: int,
        actors: dict[str, CombatantState],
    ) -> DuelEvaluation | None:
        duel = self.active_between(attacker.actor_id, target.actor_id)
        if duel is None:
            return None
        duel.damage_by_actor[attacker.actor_id] = duel.damage_by_actor.get(attacker.actor_id, 0) + max(0, damage)
        target_start = max(1, duel.starting_hp.get(target.actor_id, target.max_hp))

        if duel.mode is DuelMode.FIRST_STRIKE:
            clean_threshold = max(1, math.ceil(target.max_hp * 0.10))
            if clean_hit and damage >= clean_threshold:
                return self._complete(
                    duel, actors, winner_id=attacker.actor_id, loser_id=target.actor_id,
                    reason="first clean strike", now_ms=now_ms,
                )
            if target.hp <= target_start / 2:
                return self._complete(
                    duel, actors, winner_id=attacker.actor_id, loser_id=target.actor_id,
                    reason="opponent reduced to half starting HP", now_ms=now_ms,
                )
        elif duel.mode is DuelMode.HALF_LOSS:
            if target.hp <= target_start / 2:
                return self._complete(
                    duel, actors, winner_id=attacker.actor_id, loser_id=target.actor_id,
                    reason="half-loss threshold reached", now_ms=now_ms,
                )
        elif duel.mode is DuelMode.TOTAL_LOSS and target.hp <= 0:
            return self._complete(
                duel, actors, winner_id=attacker.actor_id, loser_id=target.actor_id,
                reason="total-loss HP depletion", now_ms=now_ms,
            )
        return DuelEvaluation(duel.duel_id, False)

    def resign(self, duel_id: str, actor_id: str, actors: dict[str, CombatantState], *, now_ms: int) -> DuelEvaluation:
        duel = self.duels[duel_id]
        if duel.status is not DuelStatus.ACTIVE or actor_id not in (duel.challenger_id, duel.target_id):
            raise ValueError("actor is not in this active duel")
        winner_id = duel.target_id if actor_id == duel.challenger_id else duel.challenger_id
        return self._complete(duel, actors, winner_id=winner_id, loser_id=actor_id, reason="resignation", now_ms=now_ms)

    def dump_state(self) -> dict:
        return {duel_id: asdict(duel) for duel_id, duel in self.duels.items()}

    def load_state(self, payload: dict, actors: dict[str, CombatantState]) -> None:
        self.duels = {}
        for duel_id, row in payload.items():
            duel = DuelState(
                duel_id=duel_id,
                challenger_id=str(row["challenger_id"]),
                target_id=str(row["target_id"]),
                mode=DuelMode(row["mode"]),
                status=DuelStatus(row["status"]),
                created_at_ms=int(row["created_at_ms"]),
                accepted_at_ms=row.get("accepted_at_ms"),
                completed_at_ms=row.get("completed_at_ms"),
                starting_hp={k: int(v) for k, v in row.get("starting_hp", {}).items()},
                damage_by_actor={k: int(v) for k, v in row.get("damage_by_actor", {}).items()},
                winner_id=row.get("winner_id"),
                loser_id=row.get("loser_id"),
                completion_reason=row.get("completion_reason"),
            )
            self.duels[duel_id] = duel
            if duel.status is DuelStatus.ACTIVE and duel.challenger_id in actors and duel.target_id in actors:
                self._authorize(actors[duel.challenger_id], duel.target_id)
                self._authorize(actors[duel.target_id], duel.challenger_id)
                actors[duel.challenger_id].metadata["active_duel_id"] = duel_id
                actors[duel.target_id].metadata["active_duel_id"] = duel_id
