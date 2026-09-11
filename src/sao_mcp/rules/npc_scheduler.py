from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class NPCPlanActionKind(StrEnum):
    TRAVEL = "travel"
    WAIT = "wait"
    INVESTIGATE = "investigate"
    CONTACT = "contact"
    TRADE_VENDOR = "trade_vendor"
    ENGAGE = "engage"
    ATTACK = "attack"


@dataclass(slots=True, frozen=True)
class NPCScheduledActionSpec:
    action_kind: NPCPlanActionKind
    duration_ms: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    interruptible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_kind", NPCPlanActionKind(self.action_kind))
        if not isinstance(self.duration_ms, int) or isinstance(self.duration_ms, bool) or self.duration_ms < 0:
            raise ValueError("NPC scheduled action duration_ms must be a non-negative integer")
        if self.action_kind is NPCPlanActionKind.TRAVEL:
            raise ValueError("NPC scheduler action specs cannot bypass world-graph travel planning")
        if self.action_kind is NPCPlanActionKind.ATTACK:
            if self.duration_ms != 0:
                raise ValueError("NPC attack timing is owned by the combat timeline and must use duration_ms=0")
        elif self.duration_ms <= 0:
            raise ValueError("stationary NPC scheduled actions require positive duration_ms")
        if not isinstance(self.payload, dict):
            raise ValueError("NPC scheduled action payload must be an object")


@dataclass(slots=True)
class NPCSchedulerGoalState:
    npc_id: str
    goal_id: str
    actions: tuple[NPCScheduledActionSpec, ...] = ()
    suspended: bool = False
    failure_reason: str | None = None
    failed_at_ms: int | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.npc_id:
            raise ValueError("NPC scheduler npc_id must be non-empty")
        if not self.goal_id:
            raise ValueError("NPC scheduler goal_id must be non-empty")

    def suspend(self, *, reason: str, at_ms: int) -> None:
        if not reason:
            raise ValueError("NPC scheduler suspension requires a reason")
        if at_ms < 0:
            raise ValueError("NPC scheduler suspension time cannot be negative")
        self.suspended = True
        self.failure_reason = reason
        self.failed_at_ms = at_ms
        self.revision += 1

    def resume(self) -> None:
        if self.suspended or self.failure_reason is not None or self.failed_at_ms is not None:
            self.suspended = False
            self.failure_reason = None
            self.failed_at_ms = None
            self.revision += 1
