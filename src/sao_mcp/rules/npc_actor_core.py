from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class NPCGoalSource(StrEnum):
    ROLE = "role"
    MANUAL = "manual"
    AUTONOMOUS = "autonomous"


@dataclass(slots=True)
class NPCGoalState:
    goal_id: str
    priority: int
    target_location_id: str | None
    business_id: str
    source: NPCGoalSource
    required_fact_id: str | None = None
    required_fact_value: Any = None
    relationship_actor_id: str | None = None
    min_relationship: int | None = None
    resource_requirements: dict[str, int] = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.goal_id:
            raise ValueError("NPC goal_id must be non-empty")
        if not self.business_id:
            raise ValueError("NPC business_id must be non-empty")
        if self.min_relationship is not None and self.relationship_actor_id is None:
            raise ValueError("NPC min_relationship requires relationship_actor_id")
        if any(not resource_id or amount <= 0 for resource_id, amount in self.resource_requirements.items()):
            raise ValueError("NPC resource requirements must use non-empty ids and positive amounts")


@dataclass(slots=True)
class NPCPlanStep:
    step_id: str
    action_kind: str
    target_location_id: str

    def __post_init__(self) -> None:
        if not self.step_id:
            raise ValueError("NPC plan step_id must be non-empty")
        if self.action_kind != "travel":
            raise ValueError(f"unsupported NPC plan action_kind: {self.action_kind}")
        if not self.target_location_id:
            raise ValueError("NPC plan target_location_id must be non-empty")


@dataclass(slots=True)
class NPCActorCoreState:
    """Persistent motivation and plan state; execution timing lives in NPCAgendaState."""

    npc_id: str
    long_term_goals: dict[str, NPCGoalState] = field(default_factory=dict)
    current_goal_id: str | None = None
    current_business_id: str | None = None
    short_term_plan: list[NPCPlanStep] = field(default_factory=list)
    plan_cursor: int = 0
    decision_basis_fact_ids: tuple[str, ...] = ()
    decision_relation_actor_ids: tuple[str, ...] = ()
    last_decision_at_ms: int | None = None
    revision: int = 0

    @property
    def current_goal(self) -> NPCGoalState | None:
        if self.current_goal_id is None:
            return None
        return self.long_term_goals[self.current_goal_id]

    @property
    def current_plan_step(self) -> NPCPlanStep | None:
        if self.plan_cursor >= len(self.short_term_plan):
            return None
        return self.short_term_plan[self.plan_cursor]

    def upsert_goal(self, goal: NPCGoalState) -> None:
        self.long_term_goals[goal.goal_id] = goal
        self.revision += 1

    def remove_goal(self, goal_id: str) -> None:
        if goal_id not in self.long_term_goals:
            raise KeyError(goal_id)
        self.long_term_goals.pop(goal_id)
        if self.current_goal_id == goal_id:
            self.clear_current_goal()
        self.revision += 1

    def select_goal(self, goal_id: str | None, *, decided_at_ms: int) -> None:
        if decided_at_ms < 0:
            raise ValueError("NPC decision time cannot be negative")
        if goal_id is not None and goal_id not in self.long_term_goals:
            raise KeyError(goal_id)
        if self.current_goal_id != goal_id:
            self.current_goal_id = goal_id
            self.current_business_id = (
                self.long_term_goals[goal_id].business_id if goal_id is not None else None
            )
            self.short_term_plan = []
            self.plan_cursor = 0
            self.revision += 1
        self.last_decision_at_ms = decided_at_ms
        goal = self.current_goal
        self.decision_basis_fact_ids = (
            (goal.required_fact_id,) if goal is not None and goal.required_fact_id is not None else ()
        )
        self.decision_relation_actor_ids = (
            (goal.relationship_actor_id,)
            if goal is not None and goal.relationship_actor_id is not None
            else ()
        )

    def clear_current_goal(self) -> None:
        self.current_goal_id = None
        self.current_business_id = None
        self.short_term_plan = []
        self.plan_cursor = 0
        self.decision_basis_fact_ids = ()
        self.decision_relation_actor_ids = ()

    def replace_plan(self, steps: list[NPCPlanStep]) -> None:
        self.short_term_plan = list(steps)
        self.plan_cursor = 0
        self.revision += 1

    def complete_plan_step(self, step_id: str) -> None:
        step = self.current_plan_step
        if step is None or step.step_id != step_id:
            raise RuntimeError(
                f"NPC {self.npc_id} completed plan step {step_id!r} but current step is "
                f"{step.step_id if step is not None else None!r}"
            )
        self.plan_cursor += 1
        self.revision += 1
