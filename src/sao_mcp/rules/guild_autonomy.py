from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class GuildGoalSource(StrEnum):
    LEADER = "leader"
    AUTONOMOUS = "autonomous"


class GuildOperationStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    WITHDRAWING = "withdrawing"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"
    FAILED = "failed"


TERMINAL_GUILD_OPERATION_STATUSES = frozenset({
    GuildOperationStatus.COMPLETED,
    GuildOperationStatus.WITHDRAWN,
    GuildOperationStatus.FAILED,
})


@dataclass(slots=True)
class GuildStrategicGoalState:
    guild_id: str
    goal_id: str
    target_location_id: str
    priority: int
    source: GuildGoalSource
    created_at_ms: int
    basis_fact_id: str | None = None
    required_member_fact_id: str | None = None
    member_resource_requirements: dict[str, int] = field(default_factory=dict)
    guild_resource_requirements: dict[str, int] = field(default_factory=dict)
    min_members: int = 1
    max_members: int = 6
    desired_squads: int = 1
    max_concurrent_squads: int = 1
    allow_leader_assignment: bool = False
    enabled: bool = True
    launched_operation_ids: list[str] = field(default_factory=list)
    revision: int = 0

    def __post_init__(self) -> None:
        self.source = GuildGoalSource(self.source)
        if not self.guild_id or not self.goal_id or not self.target_location_id:
            raise ValueError("guild strategic goal identity and target must be non-empty")
        if self.created_at_ms < 0:
            raise ValueError("guild strategic goal creation time cannot be negative")
        if self.min_members < 1 or self.max_members < self.min_members:
            raise ValueError("guild strategic goal member bounds are invalid")
        if self.desired_squads < 1:
            raise ValueError("guild strategic goal desired_squads must be >= 1")
        if not 1 <= self.max_concurrent_squads <= self.desired_squads:
            raise ValueError("guild strategic goal max_concurrent_squads is invalid")
        for table in (self.member_resource_requirements, self.guild_resource_requirements):
            if any(not key or not isinstance(value, int) or isinstance(value, bool) or value <= 0 for key, value in table.items()):
                raise ValueError("guild strategic resource requirements must use positive integer amounts")
        if len(set(self.launched_operation_ids)) != len(self.launched_operation_ids):
            raise ValueError("guild strategic goal launched operation ids must be unique")

    def register_operation(self, operation_id: str) -> None:
        if operation_id in self.launched_operation_ids:
            raise ValueError("guild strategic goal operation was registered twice")
        self.launched_operation_ids.append(operation_id)
        self.revision += 1

    def disable(self) -> None:
        if self.enabled:
            self.enabled = False
            self.revision += 1


@dataclass(slots=True)
class GuildOperationState:
    operation_id: str
    guild_id: str
    goal_id: str
    target_location_id: str
    origin_location_id: str
    assigned_member_ids: tuple[str, ...]
    status: GuildOperationStatus
    created_at_ms: int
    basis_event_id: str | None = None
    activity_kind: str | None = None
    from_location_id: str | None = None
    next_location_id: str | None = None
    started_at_ms: int | None = None
    due_at_ms: int | None = None
    traversal_tags: tuple[str, ...] = ()
    withdraw_requested: bool = False
    regroup_location_id: str | None = None
    hold_at_next_node: bool = False
    failure_reason: str | None = None
    completed_at_ms: int | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        self.status = GuildOperationStatus(self.status)
        if not self.operation_id or not self.guild_id or not self.goal_id:
            raise ValueError("guild operation identity must be non-empty")
        if not self.target_location_id or not self.origin_location_id:
            raise ValueError("guild operation locations must be non-empty")
        if not self.assigned_member_ids or len(set(self.assigned_member_ids)) != len(self.assigned_member_ids):
            raise ValueError("guild operation requires unique assigned members")
        if self.created_at_ms < 0:
            raise ValueError("guild operation creation time cannot be negative")
        if self.completed_at_ms is not None and self.completed_at_ms < self.created_at_ms:
            raise ValueError("guild operation completion cannot precede creation")

    @property
    def active(self) -> bool:
        return self.activity_kind is not None

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_GUILD_OPERATION_STATUSES

    def begin_leg(
        self,
        *,
        from_location_id: str,
        next_location_id: str,
        started_at_ms: int,
        due_at_ms: int,
        traversal_tags: tuple[str, ...],
    ) -> None:
        if self.terminal:
            raise ValueError("terminal guild operation cannot start another travel leg")
        if self.active:
            raise ValueError("guild operation already has an active travel leg")
        if due_at_ms <= started_at_ms:
            raise ValueError("guild operation travel due time must be after its start time")
        self.activity_kind = "travel"
        self.from_location_id = from_location_id
        self.next_location_id = next_location_id
        self.started_at_ms = started_at_ms
        self.due_at_ms = due_at_ms
        self.traversal_tags = traversal_tags
        self.revision += 1

    def finish_leg(self) -> None:
        if not self.active:
            raise ValueError("guild operation has no active travel leg")
        self.activity_kind = None
        self.from_location_id = None
        self.next_location_id = None
        self.started_at_ms = None
        self.due_at_ms = None
        self.traversal_tags = ()
        self.revision += 1

    def request_withdrawal(self, regroup_location_id: str) -> None:
        if self.terminal:
            raise ValueError("terminal guild operation cannot withdraw")
        self.withdraw_requested = True
        self.regroup_location_id = regroup_location_id
        self.hold_at_next_node = False
        self.revision += 1

    def request_hold(self) -> None:
        if self.terminal or self.status is GuildOperationStatus.WITHDRAWING:
            raise ValueError("guild operation cannot be held in its current status")
        self.hold_at_next_node = True
        self.revision += 1

    def replace_members(self, member_ids: tuple[str, ...]) -> None:
        if self.status is not GuildOperationStatus.PAUSED or self.active:
            raise ValueError("guild operation can reorganize only while paused at a settled node")
        if not member_ids or len(set(member_ids)) != len(member_ids):
            raise ValueError("guild operation reorganization requires unique members")
        self.assigned_member_ids = member_ids
        self.status = GuildOperationStatus.ACTIVE
        self.revision += 1

    def complete(self, *, at_ms: int) -> None:
        if self.active:
            raise ValueError("guild operation cannot complete during a travel leg")
        self.status = GuildOperationStatus.COMPLETED
        self.completed_at_ms = at_ms
        self.withdraw_requested = False
        self.hold_at_next_node = False
        self.revision += 1

    def withdraw(self, *, at_ms: int) -> None:
        if self.active:
            raise ValueError("guild operation cannot finish withdrawal during a travel leg")
        self.status = GuildOperationStatus.WITHDRAWN
        self.completed_at_ms = at_ms
        self.withdraw_requested = False
        self.hold_at_next_node = False
        self.revision += 1

    def fail(self, *, reason: str, at_ms: int) -> None:
        if self.active:
            raise ValueError("guild operation cannot fail while members are unresolved in transit")
        if not reason:
            raise ValueError("guild operation failure requires a reason")
        self.status = GuildOperationStatus.FAILED
        self.failure_reason = reason
        self.completed_at_ms = at_ms
        self.withdraw_requested = False
        self.hold_at_next_node = False
        self.revision += 1
