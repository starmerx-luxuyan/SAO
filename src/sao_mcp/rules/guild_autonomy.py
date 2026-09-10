from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GuildAgendaState:
    guild_id: str
    goal_id: str | None = None
    target_location_id: str | None = None
    assigned_member_ids: tuple[str, ...] = ()
    activity_kind: str | None = None
    from_location_id: str | None = None
    next_location_id: str | None = None
    started_at_ms: int | None = None
    due_at_ms: int | None = None
    traversal_tags: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return self.activity_kind is not None

    def assign(
        self,
        *,
        goal_id: str,
        target_location_id: str,
        member_ids: tuple[str, ...],
    ) -> None:
        if self.active:
            raise ValueError(f"guild {self.guild_id} already has an active operation")
        if not goal_id:
            raise ValueError("guild goal_id must be non-empty")
        if not member_ids:
            raise ValueError("guild operation requires at least one assigned member")
        self.goal_id = goal_id
        self.target_location_id = target_location_id
        self.assigned_member_ids = member_ids

    def begin_leg(
        self,
        *,
        from_location_id: str,
        next_location_id: str,
        started_at_ms: int,
        due_at_ms: int,
        traversal_tags: tuple[str, ...],
    ) -> None:
        if self.active:
            raise ValueError(f"guild {self.guild_id} already has an active operation leg")
        if due_at_ms <= started_at_ms:
            raise ValueError("guild operation travel due time must be after its start time")
        self.activity_kind = "travel"
        self.from_location_id = from_location_id
        self.next_location_id = next_location_id
        self.started_at_ms = started_at_ms
        self.due_at_ms = due_at_ms
        self.traversal_tags = traversal_tags

    def finish_leg(self) -> None:
        self.activity_kind = None
        self.from_location_id = None
        self.next_location_id = None
        self.started_at_ms = None
        self.due_at_ms = None
        self.traversal_tags = ()

    def complete_goal(self) -> None:
        if self.active:
            raise ValueError("cannot complete a guild goal while a travel leg is active")
        self.goal_id = None
        self.target_location_id = None
        self.assigned_member_ids = ()
