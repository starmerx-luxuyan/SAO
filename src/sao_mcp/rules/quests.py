from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import CombatantState, ItemInstance, Provenance, ProvenanceKind
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.progression import ExperienceGain, grant_experience


class QuestObjectiveKind(StrEnum):
    COLLECT = "collect"
    KILL = "kill"
    DISCOVER = "discover"
    TALK = "talk"
    CRAFT = "craft"
    ENHANCE = "enhance"
    BOSS = "boss"


@dataclass(slots=True, frozen=True)
class QuestObjectiveDefinition:
    objective_id: str
    kind: QuestObjectiveKind
    target_id: str
    required: int = 1
    consume_on_turn_in: bool = False
    required_for_completion: bool = True


@dataclass(slots=True, frozen=True)
class QuestRewardItem:
    template_id: str
    quantity: int = 1
    max_enhancement_attempts: int = 0


@dataclass(slots=True, frozen=True)
class QuestReward:
    col: int = 0
    xp: int = 0
    items: tuple[QuestRewardItem, ...] = ()


@dataclass(slots=True, frozen=True)
class QuestDefinition:
    quest_id: str
    name: str
    floor_number: int
    giver_id: str
    turn_in_id: str
    objectives: tuple[QuestObjectiveDefinition, ...]
    reward: QuestReward
    repeatable: bool = False
    global_accept_cooldown_ms: int = 0
    prerequisites: tuple[str, ...] = ()
    provenance: Provenance = Provenance(ProvenanceKind.SIMULATION)


@dataclass(slots=True)
class QuestProgress:
    quest_id: str
    accepted_at_ms: int
    counters: dict[str, int] = field(default_factory=dict)
    claimed: bool = False
    claimed_at_ms: int | None = None
    terminated_status: str | None = None
    terminated_at_ms: int | None = None
    termination_reason: str | None = None

    @property
    def terminated(self) -> bool:
        return self.terminated_status is not None


@dataclass(slots=True, frozen=True)
class QuestClaimResolution:
    quest_id: str
    col: int
    experience: ExperienceGain
    item_instance_ids: tuple[str, ...]


class QuestRuntime:
    """Persistent quest progress plus a runtime-local registry of corpus and dynamic definitions."""

    def __init__(self, definitions: dict[str, QuestDefinition]) -> None:
        self.definitions = dict(definitions)
        self.progress_by_actor: dict[str, dict[str, QuestProgress]] = {}
        self.completed_by_actor: dict[str, set[str]] = {}
        self.global_accept_block_until_ms: dict[str, int] = {}

    def accept(self, actor_id: str, quest_id: str, *, now_ms: int) -> QuestProgress:
        definition = self.definitions[quest_id]
        completed = self.completed_by_actor.setdefault(actor_id, set())
        if any(required not in completed for required in definition.prerequisites):
            raise ValueError("quest prerequisites are not complete")
        existing = self.progress_by_actor.setdefault(actor_id, {}).get(quest_id)
        if existing and not existing.claimed and not existing.terminated:
            return existing
        if quest_id in completed and not definition.repeatable:
            raise ValueError("quest is not repeatable")
        if now_ms < self.global_accept_block_until_ms.get(quest_id, 0):
            raise ValueError("quest is currently unavailable due to its global cooldown")
        progress = QuestProgress(
            quest_id,
            now_ms,
            {objective.objective_id: 0 for objective in definition.objectives},
        )
        self.progress_by_actor[actor_id][quest_id] = progress
        if definition.global_accept_cooldown_ms > 0:
            self.global_accept_block_until_ms[quest_id] = now_ms + definition.global_accept_cooldown_ms
        return progress

    def record_event(
        self,
        actor_id: str,
        *,
        kind: QuestObjectiveKind | str,
        target_id: str,
        quantity: int = 1,
    ) -> list[str]:
        event_kind = QuestObjectiveKind(kind)
        updated: list[str] = []
        for quest_id, progress in self.progress_by_actor.get(actor_id, {}).items():
            if progress.claimed or progress.terminated:
                continue
            definition = self.definitions[quest_id]
            for objective in definition.objectives:
                if objective.kind is event_kind and objective.target_id == target_id:
                    current = progress.counters.get(objective.objective_id, 0)
                    progress.counters[objective.objective_id] = min(
                        objective.required,
                        current + max(0, quantity),
                    )
                    updated.append(quest_id)
        return updated

    def _inventory_count(self, actor: CombatantState, template_id: str) -> int:
        return sum(
            item.quantity
            for item in actor.inventory.values()
            if item.template_id == template_id
        )

    def refresh_collect_objectives(self, actor: CombatantState, quest_id: str) -> QuestProgress:
        progress = self.progress_by_actor[actor.actor_id][quest_id]
        if progress.terminated:
            return progress
        definition = self.definitions[quest_id]
        for objective in definition.objectives:
            if objective.kind is QuestObjectiveKind.COLLECT:
                progress.counters[objective.objective_id] = min(
                    objective.required,
                    self._inventory_count(actor, objective.target_id),
                )
        return progress

    def ready_to_claim(self, actor: CombatantState, quest_id: str) -> bool:
        progress = self.refresh_collect_objectives(actor, quest_id)
        if progress.claimed or progress.terminated:
            return False
        definition = self.definitions[quest_id]
        return all(
            progress.counters.get(objective.objective_id, 0) >= objective.required
            for objective in definition.objectives
            if objective.required_for_completion
        )

    def _consume_template(self, actor: CombatantState, template_id: str, quantity: int) -> None:
        remaining = quantity
        for instance_id, item in list(actor.inventory.items()):
            if item.template_id != template_id:
                continue
            used = min(item.quantity, remaining)
            item.quantity -= used
            remaining -= used
            if item.quantity <= 0:
                if instance_id in actor.equipment.values():
                    raise ValueError("quest objective item is currently equipped")
                actor.inventory.pop(instance_id)
            if remaining <= 0:
                return
        raise ValueError("required quest items are missing")

    def claim(
        self,
        actor: CombatantState,
        quest_id: str,
        catalog: Catalog,
        *,
        now_ms: int,
    ) -> QuestClaimResolution:
        progress = self.progress_by_actor.get(actor.actor_id, {}).get(quest_id)
        if progress is None:
            raise ValueError("quest has not been accepted")
        if progress.claimed:
            raise ValueError("quest reward has already been claimed")
        if progress.terminated:
            raise ValueError(f"quest progress is {progress.terminated_status}: {progress.termination_reason}")
        if not self.ready_to_claim(actor, quest_id):
            raise ValueError("quest objectives are incomplete")

        definition = self.definitions[quest_id]
        for objective in definition.objectives:
            if (
                objective.consume_on_turn_in
                and progress.counters.get(objective.objective_id, 0) >= objective.required
            ):
                self._consume_template(actor, objective.target_id, objective.required)

        actor.col += definition.reward.col
        xp = grant_experience(actor, definition.reward.xp)
        created: list[str] = []
        for reward in definition.reward.items:
            template = catalog.item(reward.template_id)
            if template.stack_limit > 1 and reward.max_enhancement_attempts == 0:
                item = ItemInstance(
                    instance_id=f"item_{uuid.uuid4().hex[:12]}",
                    template_id=reward.template_id,
                    owner_id=actor.actor_id,
                    quantity=reward.quantity,
                )
                add_item(actor, item, catalog, allow_overweight=True)
                created.append(item.instance_id)
                continue
            for _ in range(reward.quantity):
                durability = getattr(template, "base_durability", None)
                item = ItemInstance(
                    instance_id=f"item_{uuid.uuid4().hex[:12]}",
                    template_id=reward.template_id,
                    owner_id=actor.actor_id,
                    quantity=1,
                    durability=durability,
                    max_durability=durability,
                    max_enhancement_attempts=reward.max_enhancement_attempts,
                )
                add_item(actor, item, catalog, allow_overweight=True)
                created.append(item.instance_id)

        progress.claimed = True
        progress.claimed_at_ms = now_ms
        self.completed_by_actor.setdefault(actor.actor_id, set()).add(quest_id)
        return QuestClaimResolution(quest_id, definition.reward.col, xp, tuple(created))

    def terminate(
        self,
        actor_id: str,
        quest_id: str,
        *,
        status: str,
        at_ms: int,
        reason: str,
    ) -> QuestProgress:
        if status not in {"failed", "expired", "interrupted"}:
            raise ValueError("quest termination status must be failed, expired or interrupted")
        if at_ms < 0 or not reason:
            raise ValueError("quest termination requires non-negative time and reason")
        progress = self.progress_by_actor.get(actor_id, {}).get(quest_id)
        if progress is None:
            raise KeyError((actor_id, quest_id))
        if progress.claimed:
            raise ValueError("claimed quest progress cannot be terminated")
        if progress.terminated:
            return progress
        progress.terminated_status = status
        progress.terminated_at_ms = at_ms
        progress.termination_reason = reason
        return progress

    def dump_state(self) -> dict:
        return {
            "progress": {
                actor_id: {
                    quest_id: {
                        "quest_id": progress.quest_id,
                        "accepted_at_ms": progress.accepted_at_ms,
                        "counters": dict(progress.counters),
                        "claimed": progress.claimed,
                        "claimed_at_ms": progress.claimed_at_ms,
                        "terminated_status": progress.terminated_status,
                        "terminated_at_ms": progress.terminated_at_ms,
                        "termination_reason": progress.termination_reason,
                    }
                    for quest_id, progress in quests.items()
                }
                for actor_id, quests in self.progress_by_actor.items()
            },
            "completed": {
                actor_id: sorted(quest_ids)
                for actor_id, quest_ids in self.completed_by_actor.items()
            },
            "global_accept_block_until_ms": dict(self.global_accept_block_until_ms),
        }

    def load_state(self, payload: dict) -> None:
        self.progress_by_actor = {
            actor_id: {
                quest_id: QuestProgress(
                    quest_id=value["quest_id"],
                    accepted_at_ms=int(value["accepted_at_ms"]),
                    counters={k: int(v) for k, v in value.get("counters", {}).items()},
                    claimed=bool(value.get("claimed", False)),
                    claimed_at_ms=value.get("claimed_at_ms"),
                    terminated_status=value.get("terminated_status"),
                    terminated_at_ms=value.get("terminated_at_ms"),
                    termination_reason=value.get("termination_reason"),
                )
                for quest_id, value in quests.items()
            }
            for actor_id, quests in payload.get("progress", {}).items()
        }
        self.completed_by_actor = {
            actor_id: set(quest_ids)
            for actor_id, quest_ids in payload.get("completed", {}).items()
        }
        self.global_accept_block_until_ms = {
            quest_id: int(until)
            for quest_id, until in payload.get("global_accept_block_until_ms", {}).items()
        }
