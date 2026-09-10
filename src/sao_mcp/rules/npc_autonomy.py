from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NPCAgendaState:
    npc_id: str
    goal_id: str | None = None
    goal_target_location_id: str | None = None
    activity_kind: str | None = None
    from_location_id: str | None = None
    target_location_id: str | None = None
    started_at_ms: int | None = None
    due_at_ms: int | None = None
    traversal_tags: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return self.activity_kind is not None

    def set_goal(self, goal_id: str, target_location_id: str) -> None:
        if self.active:
            raise ValueError(f"NPC {self.npc_id} cannot change goal during an active activity")
        if not goal_id:
            raise ValueError("NPC goal_id must be non-empty")
        self.goal_id = goal_id
        self.goal_target_location_id = target_location_id

    def clear_goal(self) -> None:
        if self.active:
            raise ValueError(f"NPC {self.npc_id} cannot clear goal during an active activity")
        self.goal_id = None
        self.goal_target_location_id = None

    def begin_travel(
        self,
        *,
        from_location_id: str,
        target_location_id: str,
        started_at_ms: int,
        due_at_ms: int,
        traversal_tags: tuple[str, ...],
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

    def finish_activity(self) -> None:
        self.activity_kind = None
        self.from_location_id = None
        self.target_location_id = None
        self.started_at_ms = None
        self.due_at_ms = None
        self.traversal_tags = ()
