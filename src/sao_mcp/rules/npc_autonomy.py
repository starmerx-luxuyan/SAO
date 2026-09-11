from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sao_mcp.rules.npc_scheduler import NPCPlanActionKind


@dataclass(slots=True)
class NPCAgendaState:
    """Current execution activity only; motivation and plans live in NPCActorCoreState."""

    npc_id: str
    activity_kind: str | None = None
    from_location_id: str | None = None
    target_location_id: str | None = None
    stationary_location_id: str | None = None
    started_at_ms: int | None = None
    due_at_ms: int | None = None
    traversal_tags: tuple[str, ...] = ()
    plan_step_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    interruptible: bool = False

    @property
    def active(self) -> bool:
        return self.activity_kind is not None

    @property
    def in_transit(self) -> bool:
        return self.activity_kind == NPCPlanActionKind.TRAVEL.value

    def begin_travel(
        self,
        *,
        from_location_id: str,
        target_location_id: str,
        started_at_ms: int,
        due_at_ms: int,
        traversal_tags: tuple[str, ...],
        plan_step_id: str | None = None,
    ) -> None:
        if self.active:
            raise ValueError(f"NPC {self.npc_id} already has an active agenda activity")
        if due_at_ms <= started_at_ms:
            raise ValueError("NPC travel due time must be after its start time")
        self.activity_kind = NPCPlanActionKind.TRAVEL.value
        self.from_location_id = from_location_id
        self.target_location_id = target_location_id
        self.stationary_location_id = None
        self.started_at_ms = started_at_ms
        self.due_at_ms = due_at_ms
        self.traversal_tags = traversal_tags
        self.plan_step_id = plan_step_id
        self.payload = {}
        self.interruptible = False

    def begin_stationary(
        self,
        *,
        activity_kind: NPCPlanActionKind | str,
        location_id: str,
        started_at_ms: int,
        due_at_ms: int,
        payload: dict[str, Any],
        plan_step_id: str,
        interruptible: bool,
    ) -> None:
        if self.active:
            raise ValueError(f"NPC {self.npc_id} already has an active agenda activity")
        kind = NPCPlanActionKind(activity_kind)
        if kind is NPCPlanActionKind.TRAVEL:
            raise ValueError("stationary NPC activity cannot use travel kind")
        if due_at_ms <= started_at_ms:
            raise ValueError("NPC stationary activity due time must be after its start time")
        if not location_id:
            raise ValueError("NPC stationary activity requires location_id")
        if not plan_step_id:
            raise ValueError("NPC stationary activity requires plan_step_id")
        self.activity_kind = kind.value
        self.from_location_id = None
        self.target_location_id = None
        self.stationary_location_id = location_id
        self.started_at_ms = started_at_ms
        self.due_at_ms = due_at_ms
        self.traversal_tags = ()
        self.plan_step_id = plan_step_id
        self.payload = dict(payload)
        self.interruptible = bool(interruptible)

    def finish_activity(self) -> None:
        self.activity_kind = None
        self.from_location_id = None
        self.target_location_id = None
        self.stationary_location_id = None
        self.started_at_ms = None
        self.due_at_ms = None
        self.traversal_tags = ()
        self.plan_step_id = None
        self.payload = {}
        self.interruptible = False
