from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NPCAgendaState:
    """Current execution activity only; motivation and plans live in NPCActorCoreState."""

    npc_id: str
    activity_kind: str | None = None
    from_location_id: str | None = None
    target_location_id: str | None = None
    started_at_ms: int | None = None
    due_at_ms: int | None = None
    traversal_tags: tuple[str, ...] = ()
    plan_step_id: str | None = None

    @property
    def active(self) -> bool:
        return self.activity_kind is not None

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
        self.activity_kind = "travel"
        self.from_location_id = from_location_id
        self.target_location_id = target_location_id
        self.started_at_ms = started_at_ms
        self.due_at_ms = due_at_ms
        self.traversal_tags = traversal_tags
        self.plan_step_id = plan_step_id

    def finish_activity(self) -> None:
        self.activity_kind = None
        self.from_location_id = None
        self.target_location_id = None
        self.started_at_ms = None
        self.due_at_ms = None
        self.traversal_tags = ()
        self.plan_step_id = None
