from pathlib import Path


def write(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


write(
    "src/sao_mcp/rules/guild_autonomy.py",
    r'''from __future__ import annotations

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
''',
)


write(
    "src/sao_mcp/runtime/guild_autonomy_runtime.py",
    r'''from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Any

from sao_mcp.corpus.location_access import LOCATION_ACCESS_RULES
from sao_mcp.domain.models import CursorColor, EntityKind
from sao_mcp.rules.access import actor_faction_ids, require_location_access
from sao_mcp.rules.guild_autonomy import (
    GuildGoalSource,
    GuildOperationState,
    GuildOperationStatus,
    GuildStrategicGoalState,
    TERMINAL_GUILD_OPERATION_STATUSES,
)
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.routing import shortest_next_hop
from sao_mcp.rules.state_authority import authoritative_guild_id
from sao_mcp.rules.travel import AUTONOMOUS_TRAVEL_RESTRICTION_KEY, has_surviving_colocated_outsider
from sao_mcp.runtime.npc_scheduler_runtime import NPCSchedulerAincradRuntime


GUILD_AUTONOMY_SCHEMA = "guild-autonomy.v2"


class GuildAutonomyAincradRuntime(NPCSchedulerAincradRuntime):
    """Persistent guild strategy that dispatches real members into concurrent world operations."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.guild_strategic_goals: dict[str, dict[str, GuildStrategicGoalState]] = {}
        self.guild_operations: dict[str, GuildOperationState] = {}
        self.guild_activity_history: list[dict[str, Any]] = []
        self._guild_operation_sequence = 0
        self.register_world_advance_hook(self._resolve_due_guild_activities)

    def _guild(self, guild_id: str):
        try:
            return self.relationships.guilds[guild_id]
        except KeyError as exc:
            raise KeyError(f"unknown guild: {guild_id}") from exc

    def _require_guild_leader(self, guild_id: str, leader_id: str):
        guild = self._guild(guild_id)
        if guild.leader_id != leader_id:
            raise ValueError("guild strategic goals require the current guild leader")
        leader = self.actors[leader_id]
        if not leader.alive:
            raise ValueError("defeated guild leader cannot issue a strategic goal")
        if authoritative_guild_id(self, leader_id) != guild_id:
            raise RuntimeError("guild leader is not an authoritative GuildState member")
        return guild

    def _assigned_members(self, guild_id: str, member_ids: tuple[str, ...]):
        guild = self._guild(guild_id)
        members = []
        for actor_id in member_ids:
            if actor_id not in guild.member_ids:
                raise ValueError(f"assigned actor is not a member of guild {guild_id}: {actor_id}")
            if authoritative_guild_id(self, actor_id) != guild_id:
                raise RuntimeError(f"GuildState membership projection is inconsistent for {actor_id}")
            members.append(self.actors[actor_id])
        return members

    def _next_guild_operation_id(self) -> str:
        self._guild_operation_sequence += 1
        return f"guildop_{self._guild_operation_sequence:08d}"

    def _goal(self, guild_id: str, goal_id: str) -> GuildStrategicGoalState:
        try:
            return self.guild_strategic_goals[guild_id][goal_id]
        except KeyError as exc:
            raise KeyError(f"unknown guild strategic goal: {guild_id}/{goal_id}") from exc

    def _operation(self, guild_id: str, operation_id: str) -> GuildOperationState:
        operation = self.guild_operations[operation_id]
        if operation.guild_id != guild_id:
            raise ValueError("guild operation belongs to another guild")
        return operation

    def _validate_member_resource_id(self, resource_id: str) -> None:
        if resource_id in {"col", "hp"}:
            return
        prefix = "inventory:"
        if resource_id.startswith(prefix) and len(resource_id) > len(prefix):
            self.catalog.item(resource_id[len(prefix):])
            return
        raise ValueError(f"unsupported guild member resource id: {resource_id}")

    def _validate_guild_resource_id(self, resource_id: str) -> None:
        if resource_id == "vault_col":
            return
        prefix = "storage:"
        if resource_id.startswith(prefix) and len(resource_id) > len(prefix):
            self.catalog.item(resource_id[len(prefix):])
            return
        raise ValueError(f"unsupported guild resource id: {resource_id}")

    def _guild_resource_snapshot(self, guild_id: str) -> dict[str, Any]:
        guild = self._guild(guild_id)
        storage = self.relationships.storages[guild.storage_id]
        templates: dict[str, int] = {}
        for item in storage.items.values():
            templates[item.template_id] = templates.get(item.template_id, 0) + item.quantity
        return {
            "vault_col": guild.vault_col,
            "storage_id": guild.storage_id,
            "storage_templates": templates,
        }

    def _guild_resource_quantity(self, guild_id: str, resource_id: str) -> int:
        self._validate_guild_resource_id(resource_id)
        snapshot = self._guild_resource_snapshot(guild_id)
        if resource_id == "vault_col":
            return int(snapshot["vault_col"])
        template_id = resource_id.split(":", 1)[1]
        return int(snapshot["storage_templates"].get(template_id, 0))

    def _member_resource_quantity(self, actor_id: str, resource_id: str) -> int:
        self._validate_member_resource_id(resource_id)
        actor = self.actors[actor_id]
        if resource_id == "col":
            return int(actor.col)
        if resource_id == "hp":
            return int(actor.hp)
        template_id = resource_id.split(":", 1)[1]
        return sum(item.quantity for item in actor.inventory.values() if item.template_id == template_id)

    def _goal_basis_event(self, goal: GuildStrategicGoalState):
        if goal.basis_fact_id is None:
            return None
        guild = self._guild(goal.guild_id)
        return self.belief(guild.leader_id, goal.basis_fact_id)

    def _goal_shared_resources_satisfied(self, goal: GuildStrategicGoalState) -> bool:
        return all(
            self._guild_resource_quantity(goal.guild_id, resource_id) >= amount
            for resource_id, amount in goal.guild_resource_requirements.items()
        )

    def _actor_in_live_encounter(self, actor_id: str) -> bool:
        return any(
            encounter.active and actor_id in encounter.participants
            for encounter in self.encounters.values()
        )

    def _actor_in_other_guild_operation(
        self,
        actor_id: str,
        *,
        exclude_operation_id: str | None = None,
    ) -> bool:
        return any(
            operation.operation_id != exclude_operation_id
            and not operation.terminal
            and actor_id in operation.assigned_member_ids
            for operation in self.guild_operations.values()
        )

    def _member_available_for_goal(
        self,
        guild_id: str,
        actor_id: str,
        goal: GuildStrategicGoalState,
        *,
        exclude_operation_id: str | None = None,
    ) -> bool:
        guild = self._guild(guild_id)
        if actor_id not in guild.member_ids or actor_id not in self.actors:
            return False
        if actor_id == guild.leader_id and not goal.allow_leader_assignment:
            return False
        actor = self.actors[actor_id]
        if authoritative_guild_id(self, actor_id) != guild_id:
            return False
        if not actor.alive or actor.location_id is None:
            return False
        if self.legal.custody_for(actor_id) is not None:
            return False
        if actor.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:
            return False
        if actor.metadata.get("active_duel_id"):
            return False
        if self._actor_in_live_encounter(actor_id):
            return False
        npc_id = actor.metadata.get("npc_definition_id")
        if isinstance(npc_id, str):
            agenda = self.npc_agendas.get(npc_id)
            if agenda is not None and agenda.active:
                return False
        if self._actor_in_other_guild_operation(actor_id, exclude_operation_id=exclude_operation_id):
            return False
        if goal.required_member_fact_id is not None and self.belief(actor_id, goal.required_member_fact_id) is None:
            return False
        return all(
            self._member_resource_quantity(actor_id, resource_id) >= amount
            for resource_id, amount in goal.member_resource_requirements.items()
        )

    def _eligible_member_groups(
        self,
        goal: GuildStrategicGoalState,
    ) -> list[tuple[str, list[str]]]:
        guild = self._guild(goal.guild_id)
        by_location: dict[str, list[str]] = defaultdict(list)
        for actor_id in guild.member_ids:
            if self._member_available_for_goal(goal.guild_id, actor_id, goal):
                location_id = self.actors[actor_id].location_id
                if location_id is None:
                    raise RuntimeError("eligible guild member lost settled location during grouping")
                by_location[location_id].append(actor_id)
        return sorted(by_location.items(), key=lambda row: (-len(row[1]), row[0]))

    def _members_can_enter(self, member_ids: tuple[str, ...], location_id: str) -> bool:
        location = self.world_map.locations[location_id]
        members = [self.actors[actor_id] for actor_id in member_ids]
        if location.safe_zone and any(actor.cursor is CursorColor.ORANGE for actor in members):
            return False
        rule = LOCATION_ACCESS_RULES.get(location_id)
        if rule is None:
            return True
        forbidden = set(rule.forbidden_faction_ids)
        return all(not forbidden.intersection(actor_faction_ids(actor)) for actor in members)

    def _operation_origin(self, operation: GuildOperationState) -> str:
        members = self._assigned_members(operation.guild_id, operation.assigned_member_ids)
        if any(not actor.alive for actor in members):
            raise RuntimeError("guild operation contains a defeated member at a settled decision point")
        locations = {actor.location_id for actor in members}
        if None in locations:
            raise RuntimeError("settled guild operation has a member without a world location")
        if len(locations) != 1:
            raise RuntimeError("guild operation members are not colocated at a decision point")
        return str(next(iter(locations)))

    def _operation_blocked_by_encounter(self, member_ids: tuple[str, ...], origin: str) -> bool:
        member_set = set(member_ids)
        return any(
            member_set.intersection(encounter.participants)
            and has_surviving_colocated_outsider(encounter, member_set, origin)
            for encounter in self.encounters.values()
        )

    def _operation_target(self, operation: GuildOperationState) -> str:
        if operation.status is GuildOperationStatus.WITHDRAWING:
            if operation.regroup_location_id is None:
                raise RuntimeError("withdrawing guild operation lacks regroup location")
            return operation.regroup_location_id
        return operation.target_location_id

    def _finalize_operation_if_at_target(self, operation: GuildOperationState, at_ms: int) -> bool:
        origin = self._operation_origin(operation)
        target = self._operation_target(operation)
        if origin != target:
            return False
        if operation.status is GuildOperationStatus.WITHDRAWING:
            operation.withdraw(at_ms=at_ms)
            event = "operation_withdrawn"
        else:
            operation.complete(at_ms=at_ms)
            event = "operation_completed"
        self.guild_activity_history.append({
            "guild_id": operation.guild_id,
            "operation_id": operation.operation_id,
            "goal_id": operation.goal_id,
            "event": event,
            "location_id": origin,
            "assigned_member_ids": list(operation.assigned_member_ids),
            "at_ms": at_ms,
        })
        return True

    def _fail_operation_at_node(self, operation: GuildOperationState, reason: str, at_ms: int) -> None:
        if operation.active:
            raise RuntimeError("guild operation failure must wait for the current travel leg to resolve")
        operation.fail(reason=reason, at_ms=at_ms)
        self.guild_activity_history.append({
            "guild_id": operation.guild_id,
            "operation_id": operation.operation_id,
            "goal_id": operation.goal_id,
            "event": "operation_failed",
            "reason": reason,
            "assigned_member_ids": list(operation.assigned_member_ids),
            "at_ms": at_ms,
        })

    def _begin_operation_leg(self, operation: GuildOperationState, started_at_ms: int) -> bool:
        if operation.terminal or operation.status is GuildOperationStatus.PAUSED:
            return False
        if operation.active:
            raise ValueError("guild operation already has an active travel leg")
        origin = self._operation_origin(operation)
        if self._finalize_operation_if_at_target(operation, started_at_ms):
            return False
        if self._operation_blocked_by_encounter(operation.assigned_member_ids, origin):
            self._fail_operation_at_node(operation, "live_colocated_encounter_blocks_departure", started_at_ms)
            return False
        goal = self._goal(operation.guild_id, operation.goal_id)
        for actor in self._assigned_members(operation.guild_id, operation.assigned_member_ids):
            if not self._member_available_for_goal(
                operation.guild_id,
                actor.actor_id,
                goal,
                exclude_operation_id=operation.operation_id,
            ):
                self._fail_operation_at_node(
                    operation,
                    f"member_unavailable:{actor.actor_id}",
                    started_at_ms,
                )
                return False
            self.require_actor_autonomous_travel(actor.actor_id)

        target = self._operation_target(operation)
        try:
            next_hop = shortest_next_hop(
                self.world,
                self.world_map,
                origin,
                target,
                can_enter=lambda location_id: self._members_can_enter(operation.assigned_member_ids, location_id),
            )
        except ValueError as exc:
            self._fail_operation_at_node(operation, f"route_unreachable:{exc}", started_at_ms)
            return False
        if next_hop is None:
            return self._finalize_operation_if_at_target(operation, started_at_ms)
        destination = self.world_map.locations[next_hop]
        if not self.world.floors[destination.floor_number].unlocked:
            self._fail_operation_at_node(operation, "next_hop_floor_locked", started_at_ms)
            return False
        for actor in self._assigned_members(operation.guild_id, operation.assigned_member_ids):
            require_location_access(actor, next_hop)
        edges = [
            edge
            for edge in self.world_map.adjacency.get(origin, ())
            if edge.to_location_id == next_hop
        ]
        if not edges:
            raise RuntimeError("guild route planner selected a non-adjacent next hop")
        edge = min(edges, key=lambda candidate: candidate.travel_ms)
        operation.begin_leg(
            from_location_id=origin,
            next_location_id=next_hop,
            started_at_ms=started_at_ms,
            due_at_ms=started_at_ms + edge.travel_ms,
            traversal_tags=edge.traversal_tags,
        )
        for actor in self._assigned_members(operation.guild_id, operation.assigned_member_ids):
            actor.location_id = None
        self.guild_activity_history.append({
            "guild_id": operation.guild_id,
            "operation_id": operation.operation_id,
            "goal_id": operation.goal_id,
            "event": "travel_leg_started",
            "assigned_member_ids": list(operation.assigned_member_ids),
            "from_location_id": origin,
            "to_location_id": next_hop,
            "started_at_ms": started_at_ms,
            "due_at_ms": operation.due_at_ms,
        })
        return True

    def _create_operation(
        self,
        goal: GuildStrategicGoalState,
        member_ids: tuple[str, ...],
        *,
        created_at_ms: int,
    ) -> GuildOperationState:
        if len(member_ids) < goal.min_members or len(member_ids) > goal.max_members:
            raise ValueError("guild operation member count violates strategic goal bounds")
        if len(set(member_ids)) != len(member_ids):
            raise ValueError("guild operation member ids must be unique")
        for actor_id in member_ids:
            if not self._member_available_for_goal(goal.guild_id, actor_id, goal):
                raise ValueError(f"guild member is not eligible for operation: {actor_id}")
        locations = {self.actors[actor_id].location_id for actor_id in member_ids}
        if None in locations or len(locations) != 1:
            raise ValueError("guild operation members must begin colocated at one settled location")
        basis_event = self._goal_basis_event(goal)
        if goal.basis_fact_id is not None and basis_event is None:
            raise ValueError("guild leader no longer knows the strategic basis fact")
        operation = GuildOperationState(
            operation_id=self._next_guild_operation_id(),
            guild_id=goal.guild_id,
            goal_id=goal.goal_id,
            target_location_id=goal.target_location_id,
            origin_location_id=str(next(iter(locations))),
            assigned_member_ids=member_ids,
            status=GuildOperationStatus.ACTIVE,
            created_at_ms=created_at_ms,
            basis_event_id=(basis_event.event_id if basis_event is not None else None),
        )
        self.guild_operations[operation.operation_id] = operation
        goal.register_operation(operation.operation_id)
        self.guild_activity_history.append({
            "guild_id": goal.guild_id,
            "operation_id": operation.operation_id,
            "goal_id": goal.goal_id,
            "event": "operation_dispatched",
            "target_location_id": goal.target_location_id,
            "assigned_member_ids": list(member_ids),
            "basis_event_id": operation.basis_event_id,
            "at_ms": created_at_ms,
        })
        self._begin_operation_leg(operation, created_at_ms)
        return operation

    def _live_operations_for_goal(self, guild_id: str, goal_id: str) -> list[GuildOperationState]:
        return [
            operation
            for operation in self.guild_operations.values()
            if operation.guild_id == guild_id
            and operation.goal_id == goal_id
            and not operation.terminal
        ]

    def _evaluate_guild_goal(self, goal: GuildStrategicGoalState, at_ms: int) -> list[str]:
        if not goal.enabled:
            return []
        if len(goal.launched_operation_ids) >= goal.desired_squads:
            return []
        if goal.basis_fact_id is not None and self._goal_basis_event(goal) is None:
            return []
        if not self._goal_shared_resources_satisfied(goal):
            return []
        live_count = len(self._live_operations_for_goal(goal.guild_id, goal.goal_id))
        slots = min(
            goal.max_concurrent_squads - live_count,
            goal.desired_squads - len(goal.launched_operation_ids),
        )
        if slots <= 0:
            return []
        dispatched: list[str] = []
        while slots > 0:
            groups = self._eligible_member_groups(goal)
            selected: tuple[str, ...] | None = None
            for _, actor_ids in groups:
                if len(actor_ids) < goal.min_members:
                    continue
                selected = tuple(actor_ids[: goal.max_members])
                break
            if selected is None:
                break
            operation = self._create_operation(goal, selected, created_at_ms=at_ms)
            dispatched.append(operation.operation_id)
            slots -= 1
        return dispatched

    def _evaluate_guild_strategies(self, at_ms: int) -> list[str]:
        dispatched: list[str] = []
        for guild_id in sorted(self.guild_strategic_goals):
            goals = sorted(
                self.guild_strategic_goals[guild_id].values(),
                key=lambda goal: (-goal.priority, goal.created_at_ms, goal.goal_id),
            )
            for goal in goals:
                dispatched.extend(self._evaluate_guild_goal(goal, at_ms))
        return dispatched

    def set_guild_strategy_goal(
        self,
        guild_id: str,
        leader_id: str,
        goal_id: str,
        target_location_id: str,
        *,
        priority: int = 100,
        basis_fact_id: str | None = None,
        required_member_fact_id: str | None = None,
        member_resource_requirements: dict[str, int] | None = None,
        guild_resource_requirements: dict[str, int] | None = None,
        min_members: int = 1,
        max_members: int = 6,
        desired_squads: int = 1,
        max_concurrent_squads: int = 1,
        allow_leader_assignment: bool = False,
        source: GuildGoalSource | str = GuildGoalSource.LEADER,
        auto_dispatch: bool = True,
    ) -> GuildStrategicGoalState:
        self._require_guild_leader(guild_id, leader_id)
        if not goal_id:
            raise ValueError("guild strategic goal_id must be non-empty")
        if goal_id in self.guild_strategic_goals.get(guild_id, {}):
            raise ValueError(f"guild strategic goal already exists: {guild_id}/{goal_id}")
        if target_location_id not in self.world_map.locations:
            raise KeyError(target_location_id)
        target = self.world_map.locations[target_location_id]
        if not self.world.floors[target.floor_number].unlocked:
            raise ValueError("guild strategic target floor is not unlocked")
        member_requirements = dict(member_resource_requirements or {})
        guild_requirements = dict(guild_resource_requirements or {})
        for resource_id, amount in member_requirements.items():
            self._validate_member_resource_id(resource_id)
            if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                raise ValueError("guild member resource requirement must be a positive integer")
        for resource_id, amount in guild_requirements.items():
            self._validate_guild_resource_id(resource_id)
            if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                raise ValueError("guild shared resource requirement must be a positive integer")
        goal = GuildStrategicGoalState(
            guild_id=guild_id,
            goal_id=goal_id,
            target_location_id=target_location_id,
            priority=int(priority),
            source=GuildGoalSource(source),
            created_at_ms=self.world.now_ms,
            basis_fact_id=basis_fact_id,
            required_member_fact_id=required_member_fact_id,
            member_resource_requirements=member_requirements,
            guild_resource_requirements=guild_requirements,
            min_members=int(min_members),
            max_members=int(max_members),
            desired_squads=int(desired_squads),
            max_concurrent_squads=int(max_concurrent_squads),
            allow_leader_assignment=bool(allow_leader_assignment),
        )
        self.guild_strategic_goals.setdefault(guild_id, {})[goal_id] = goal
        self.guild_activity_history.append({
            "guild_id": guild_id,
            "event": "strategic_goal_created",
            "goal_id": goal_id,
            "target_location_id": target_location_id,
            "issued_by_actor_id": leader_id,
            "basis_fact_id": basis_fact_id,
            "at_ms": self.world.now_ms,
        })
        if auto_dispatch:
            self._evaluate_guild_goal(goal, self.world.now_ms)
        return goal

    def assign_guild_goal(
        self,
        guild_id: str,
        leader_id: str,
        goal_id: str,
        target_location_id: str,
        assigned_member_ids: list[str] | tuple[str, ...] | None = None,
        *,
        basis_fact_id: str | None = None,
        required_member_fact_id: str | None = None,
        member_resource_requirements: dict[str, int] | None = None,
        guild_resource_requirements: dict[str, int] | None = None,
        min_members: int = 1,
        max_members: int = 6,
        desired_squads: int = 1,
        max_concurrent_squads: int = 1,
        allow_leader_assignment: bool = False,
        priority: int = 100,
    ):
        explicit = None if assigned_member_ids is None else tuple(dict.fromkeys(assigned_member_ids))
        if explicit is not None and len(explicit) != len(assigned_member_ids):
            raise ValueError("guild operation assigned_member_ids must be unique")
        if explicit is not None:
            min_members = len(explicit)
            max_members = len(explicit)
            desired_squads = max(1, int(desired_squads))
            max_concurrent_squads = max(1, min(int(max_concurrent_squads), desired_squads))
            if self._guild(guild_id).leader_id in explicit:
                allow_leader_assignment = True
        goal = self.set_guild_strategy_goal(
            guild_id,
            leader_id,
            goal_id,
            target_location_id,
            priority=priority,
            basis_fact_id=basis_fact_id,
            required_member_fact_id=required_member_fact_id,
            member_resource_requirements=member_resource_requirements,
            guild_resource_requirements=guild_resource_requirements,
            min_members=min_members,
            max_members=max_members,
            desired_squads=desired_squads,
            max_concurrent_squads=max_concurrent_squads,
            allow_leader_assignment=allow_leader_assignment,
            auto_dispatch=(explicit is None),
        )
        if explicit is not None:
            operation = self._create_operation(goal, explicit, created_at_ms=self.world.now_ms)
            if desired_squads > 1:
                self._evaluate_guild_goal(goal, self.world.now_ms)
            return operation
        return goal

    def dispatch_guild_operation(
        self,
        guild_id: str,
        leader_id: str,
        goal_id: str,
        assigned_member_ids: list[str] | tuple[str, ...] | None = None,
    ) -> GuildOperationState:
        self._require_guild_leader(guild_id, leader_id)
        goal = self._goal(guild_id, goal_id)
        if not goal.enabled:
            raise ValueError("disabled guild strategic goal cannot dispatch")
        if len(goal.launched_operation_ids) >= goal.desired_squads:
            raise ValueError("guild strategic goal already launched its desired number of squads")
        if assigned_member_ids is None:
            groups = self._eligible_member_groups(goal)
            selected = next(
                (tuple(actor_ids[: goal.max_members]) for _, actor_ids in groups if len(actor_ids) >= goal.min_members),
                None,
            )
            if selected is None:
                raise ValueError("no eligible colocated guild squad satisfies this strategic goal")
        else:
            selected = tuple(dict.fromkeys(assigned_member_ids))
            if len(selected) != len(assigned_member_ids):
                raise ValueError("guild operation assigned_member_ids must be unique")
        return self._create_operation(goal, selected, created_at_ms=self.world.now_ms)

    def clear_guild_goal(self, guild_id: str, leader_id: str, goal_id: str | None = None):
        self._require_guild_leader(guild_id, leader_id)
        goals = self.guild_strategic_goals.get(guild_id, {})
        selected = [goal for key, goal in goals.items() if goal_id is None or key == goal_id]
        if goal_id is not None and not selected:
            raise KeyError(f"unknown guild strategic goal: {guild_id}/{goal_id}")
        if not selected:
            return self.guild_agenda_state(guild_id)
        selected_ids = {goal.goal_id for goal in selected}
        live = [
            operation.operation_id
            for operation in self.guild_operations.values()
            if operation.guild_id == guild_id
            and operation.goal_id in selected_ids
            and not operation.terminal
        ]
        if live:
            raise ValueError(f"cannot clear guild goals with live operations: {sorted(live)}")
        for goal in selected:
            goal.disable()
            self.guild_activity_history.append({
                "guild_id": guild_id,
                "event": "strategic_goal_cleared",
                "goal_id": goal.goal_id,
                "issued_by_actor_id": leader_id,
                "at_ms": self.world.now_ms,
            })
        return self.guild_agenda_state(guild_id)

    def request_guild_operation_withdrawal(
        self,
        guild_id: str,
        leader_id: str,
        operation_id: str,
        *,
        regroup_location_id: str | None = None,
    ) -> GuildOperationState:
        guild = self._require_guild_leader(guild_id, leader_id)
        operation = self._operation(guild_id, operation_id)
        if operation.terminal:
            raise ValueError("terminal guild operation cannot withdraw")
        regroup = regroup_location_id or guild.headquarters_location_id or operation.origin_location_id
        if regroup not in self.world_map.locations:
            raise KeyError(regroup)
        destination = self.world_map.locations[regroup]
        if not self.world.floors[destination.floor_number].unlocked:
            raise ValueError("guild regroup floor is not unlocked")
        operation.request_withdrawal(regroup)
        self.guild_activity_history.append({
            "guild_id": guild_id,
            "operation_id": operation_id,
            "goal_id": operation.goal_id,
            "event": "withdrawal_requested",
            "regroup_location_id": regroup,
            "issued_by_actor_id": leader_id,
            "at_ms": self.world.now_ms,
        })
        if not operation.active:
            operation.status = GuildOperationStatus.WITHDRAWING
            operation.withdraw_requested = False
            self._begin_operation_leg(operation, self.world.now_ms)
        return operation

    def hold_guild_operation(self, guild_id: str, leader_id: str, operation_id: str) -> GuildOperationState:
        self._require_guild_leader(guild_id, leader_id)
        operation = self._operation(guild_id, operation_id)
        operation.request_hold()
        self.guild_activity_history.append({
            "guild_id": guild_id,
            "operation_id": operation_id,
            "goal_id": operation.goal_id,
            "event": "hold_requested",
            "issued_by_actor_id": leader_id,
            "at_ms": self.world.now_ms,
        })
        if not operation.active:
            operation.hold_at_next_node = False
            operation.status = GuildOperationStatus.PAUSED
        return operation

    def reorganize_guild_operation(
        self,
        guild_id: str,
        leader_id: str,
        operation_id: str,
        assigned_member_ids: list[str] | tuple[str, ...],
    ) -> GuildOperationState:
        self._require_guild_leader(guild_id, leader_id)
        operation = self._operation(guild_id, operation_id)
        if operation.status is not GuildOperationStatus.PAUSED or operation.active:
            raise ValueError("guild operation can reorganize only while paused at a route node")
        member_ids = tuple(dict.fromkeys(assigned_member_ids))
        if not member_ids or len(member_ids) != len(assigned_member_ids):
            raise ValueError("guild reorganization requires unique assigned_member_ids")
        goal = self._goal(guild_id, operation.goal_id)
        if not goal.min_members <= len(member_ids) <= goal.max_members:
            raise ValueError("guild reorganization member count violates strategic goal bounds")
        current_location = self._operation_origin(operation)
        for actor_id in member_ids:
            if not self._member_available_for_goal(
                guild_id,
                actor_id,
                goal,
                exclude_operation_id=operation_id,
            ):
                raise ValueError(f"guild reorganization member is unavailable: {actor_id}")
            if self.actors[actor_id].location_id != current_location:
                raise ValueError("guild reorganization members must be colocated at the paused route node")
        previous = operation.assigned_member_ids
        operation.replace_members(member_ids)
        self.guild_activity_history.append({
            "guild_id": guild_id,
            "operation_id": operation_id,
            "goal_id": operation.goal_id,
            "event": "operation_reorganized",
            "previous_member_ids": list(previous),
            "assigned_member_ids": list(member_ids),
            "location_id": current_location,
            "issued_by_actor_id": leader_id,
            "at_ms": self.world.now_ms,
        })
        self._begin_operation_leg(operation, self.world.now_ms)
        return operation

    def _finish_operation_leg(self, operation: GuildOperationState) -> int:
        if operation.activity_kind != "travel":
            raise RuntimeError(f"unsupported guild operation activity: {operation.activity_kind}")
        if operation.due_at_ms is None or operation.started_at_ms is None:
            raise RuntimeError("active guild operation lacks route timing")
        if operation.from_location_id is None or operation.next_location_id is None:
            raise RuntimeError("active guild operation lacks route endpoints")
        members = self._assigned_members(operation.guild_id, operation.assigned_member_ids)
        if any(not actor.alive for actor in members):
            raise RuntimeError("guild operation member was defeated while unresolved in transit")
        if any(actor.location_id is not None for actor in members):
            raise RuntimeError("travelling guild operation member unexpectedly has a settled location")
        completed_at_ms = operation.due_at_ms
        from_location_id = operation.from_location_id
        destination_id = operation.next_location_id
        traversal_tags = operation.traversal_tags
        destination = self.world_map.locations[destination_id]
        floor = self.world.floors[destination.floor_number]
        newly_discovered = destination_id not in floor.discovered_locations
        floor.discovered_locations.add(destination_id)
        for actor in members:
            actor.location_id = destination_id
            if actor.kind is EntityKind.PLAYER:
                self.quests.record_event(actor.actor_id, kind=QuestObjectiveKind.DISCOVER, target_id=destination_id)
        operation.finish_leg()
        self.guild_activity_history.append({
            "guild_id": operation.guild_id,
            "operation_id": operation.operation_id,
            "goal_id": operation.goal_id,
            "event": "travel_leg_completed",
            "assigned_member_ids": list(operation.assigned_member_ids),
            "from_location_id": from_location_id,
            "to_location_id": destination_id,
            "started_at_ms": operation.started_at_ms,
            "completed_at_ms": completed_at_ms,
            "newly_discovered": newly_discovered,
            "traversal_tags": list(traversal_tags),
        })
        if operation.withdraw_requested:
            operation.withdraw_requested = False
            operation.status = GuildOperationStatus.WITHDRAWING
        if operation.hold_at_next_node and operation.status is not GuildOperationStatus.WITHDRAWING:
            operation.hold_at_next_node = False
            operation.status = GuildOperationStatus.PAUSED
            self.guild_activity_history.append({
                "guild_id": operation.guild_id,
                "operation_id": operation.operation_id,
                "goal_id": operation.goal_id,
                "event": "operation_paused",
                "location_id": destination_id,
                "assigned_member_ids": list(operation.assigned_member_ids),
                "at_ms": completed_at_ms,
            })
            return completed_at_ms
        self._begin_operation_leg(operation, completed_at_ms)
        return completed_at_ms

    def _resolve_due_guild_activities(self, before_ms: int, after_ms: int) -> None:
        for operation in sorted(self.guild_operations.values(), key=lambda row: row.operation_id):
            while operation.active and operation.due_at_ms is not None and operation.due_at_ms <= after_ms:
                self._finish_operation_leg(operation)
        self._evaluate_guild_strategies(after_ms)

    def _next_scheduler_boundary(self, target_ms: int) -> int:
        boundary = super()._next_scheduler_boundary(target_ms)
        now = self.world.now_ms
        due = [
            operation.due_at_ms
            for operation in self.guild_operations.values()
            if operation.active
            and operation.due_at_ms is not None
            and now < operation.due_at_ms <= target_ms
        ]
        return min([boundary, *due]) if due else boundary

    def advance_world(self, elapsed_ms: int) -> list[int]:
        self._evaluate_guild_strategies(self.world.now_ms)
        activated = super().advance_world(elapsed_ms)
        self._evaluate_guild_strategies(self.world.now_ms)
        return activated

    def _on_knowledge_update(self, event) -> None:
        super()._on_knowledge_update(event)
        affected: set[str] = set()
        for guild_id, goals in self.guild_strategic_goals.items():
            guild = self._guild(guild_id)
            if event.knower_id == guild.leader_id and any(
                goal.basis_fact_id == event.fact_id for goal in goals.values()
            ):
                affected.add(guild_id)
            if event.knower_id in guild.member_ids and any(
                goal.required_member_fact_id == event.fact_id for goal in goals.values()
            ):
                affected.add(guild_id)
        for guild_id in sorted(affected):
            for goal in sorted(
                self.guild_strategic_goals[guild_id].values(),
                key=lambda row: (-row.priority, row.created_at_ms, row.goal_id),
            ):
                self._evaluate_guild_goal(goal, self.world.now_ms)

    def guild_operation_state(self, operation_id: str) -> dict[str, Any]:
        operation = self.guild_operations[operation_id]
        row = asdict(operation)
        row["status"] = operation.status.value
        row["active"] = operation.active
        row["terminal"] = operation.terminal
        row["member_locations"] = {
            actor_id: self.actors[actor_id].location_id
            for actor_id in operation.assigned_member_ids
        }
        return row

    def guild_agenda_state(self, guild_id: str) -> dict[str, Any]:
        guild = self._guild(guild_id)
        goals = self.guild_strategic_goals.get(guild_id, {})
        operations = sorted(
            (operation for operation in self.guild_operations.values() if operation.guild_id == guild_id),
            key=lambda row: (row.created_at_ms, row.operation_id),
        )
        live = [operation for operation in operations if not operation.terminal]
        primary = live[0] if len(live) == 1 else (operations[-1] if len(operations) == 1 else None)
        goal_rows = {}
        for goal_id, goal in sorted(goals.items()):
            eligible_groups = self._eligible_member_groups(goal) if goal.enabled else []
            goal_rows[goal_id] = {
                **asdict(goal),
                "source": goal.source.value,
                "basis_current": (goal.basis_fact_id is None or self._goal_basis_event(goal) is not None),
                "shared_resources_satisfied": self._goal_shared_resources_satisfied(goal),
                "eligible_member_groups": [
                    {"location_id": location_id, "actor_ids": actor_ids}
                    for location_id, actor_ids in eligible_groups
                ],
            }
        state = {
            "guild_id": guild_id,
            "leader_id": guild.leader_id,
            "resources": self._guild_resource_snapshot(guild_id),
            "strategic_goals": goal_rows,
            "operations": {
                operation.operation_id: self.guild_operation_state(operation.operation_id)
                for operation in operations
            },
            "live_operation_ids": [operation.operation_id for operation in live],
            "active": any(operation.active for operation in live),
        }
        if primary is None:
            state.update({
                "operation_id": None,
                "goal_id": None,
                "target_location_id": None,
                "assigned_member_ids": [],
                "activity_kind": None,
                "from_location_id": None,
                "next_location_id": None,
                "started_at_ms": None,
                "due_at_ms": None,
                "traversal_tags": [],
                "goal_reached": False,
            })
            return state
        goal = goals.get(primary.goal_id)
        visible_goal = primary.goal_id if goal is not None and goal.enabled else None
        state.update({
            "operation_id": primary.operation_id,
            "goal_id": visible_goal,
            "target_location_id": primary.target_location_id,
            "assigned_member_ids": list(primary.assigned_member_ids),
            "activity_kind": primary.activity_kind,
            "from_location_id": primary.from_location_id,
            "next_location_id": primary.next_location_id,
            "started_at_ms": primary.started_at_ms,
            "due_at_ms": primary.due_at_ms,
            "traversal_tags": list(primary.traversal_tags),
            "goal_reached": (
                visible_goal is not None and primary.status is GuildOperationStatus.COMPLETED
            ),
            "status": primary.status.value,
            "member_locations": {
                actor_id: self.actors[actor_id].location_id
                for actor_id in primary.assigned_member_ids
            },
        })
        return state

    def _assert_guild_autonomy_authority(self) -> None:
        assigned_live: dict[str, str] = {}
        for guild_id, goals in self.guild_strategic_goals.items():
            self._guild(guild_id)
            for goal_id, goal in goals.items():
                if goal.guild_id != guild_id or goal.goal_id != goal_id:
                    raise RuntimeError("guild strategic goal registry key disagrees with stored identity")
                if goal.target_location_id not in self.world_map.locations:
                    raise RuntimeError("guild strategic goal references unknown target location")
                for resource_id in goal.member_resource_requirements:
                    self._validate_member_resource_id(resource_id)
                for resource_id in goal.guild_resource_requirements:
                    self._validate_guild_resource_id(resource_id)
                for operation_id in goal.launched_operation_ids:
                    operation = self.guild_operations.get(operation_id)
                    if operation is None or operation.guild_id != guild_id or operation.goal_id != goal_id:
                        raise RuntimeError("guild strategic goal launched-operation history is inconsistent")
        for operation_id, operation in self.guild_operations.items():
            if operation.operation_id != operation_id:
                raise RuntimeError("guild operation registry key disagrees with operation_id")
            goal = self._goal(operation.guild_id, operation.goal_id)
            if operation_id not in goal.launched_operation_ids:
                raise RuntimeError("guild operation is absent from its strategic goal launch history")
            self._assigned_members(operation.guild_id, operation.assigned_member_ids)
            if operation.basis_event_id is not None:
                event = self.knowledge_event(operation.basis_event_id)
                guild = self._guild(operation.guild_id)
                if event.knower_id != guild.leader_id or event.fact_id != goal.basis_fact_id:
                    raise RuntimeError("guild operation basis event does not belong to its leader/goal")
            if operation.terminal:
                if operation.active or operation.completed_at_ms is None:
                    raise RuntimeError("terminal guild operation has unresolved activity or completion time")
                continue
            for actor_id in operation.assigned_member_ids:
                previous = assigned_live.setdefault(actor_id, operation_id)
                if previous != operation_id:
                    raise RuntimeError(f"actor {actor_id} belongs to multiple live guild operations")
            if operation.active:
                if operation.activity_kind != "travel":
                    raise RuntimeError("guild operation has unsupported active activity")
                if operation.from_location_id not in self.world_map.locations or operation.next_location_id not in self.world_map.locations:
                    raise RuntimeError("guild operation route references unknown location")
                if operation.started_at_ms is None or operation.due_at_ms is None:
                    raise RuntimeError("guild operation active route lacks timing")
                if not (operation.started_at_ms <= self.world.now_ms < operation.due_at_ms):
                    raise RuntimeError("guild operation active route timing is invalid")
                if any(self.actors[actor_id].location_id is not None for actor_id in operation.assigned_member_ids):
                    raise RuntimeError("travelling guild operation member has a settled location")
            elif operation.status is not GuildOperationStatus.PAUSED:
                raise RuntimeError("nonterminal guild operation without a route must be paused")
            else:
                self._operation_origin(operation)
        if self._guild_operation_sequence < max(
            [int(operation_id.removeprefix("guildop_")) for operation_id in self.guild_operations]
            or [0]
        ):
            raise RuntimeError("guild operation sequence precedes persisted operation ids")

    def dump_guild_autonomy_state(self) -> dict[str, Any]:
        self._assert_guild_autonomy_authority()
        return {
            "schema": GUILD_AUTONOMY_SCHEMA,
            "sequence": self._guild_operation_sequence,
            "goals": {
                guild_id: {
                    goal_id: asdict(goal)
                    for goal_id, goal in goals.items()
                }
                for guild_id, goals in self.guild_strategic_goals.items()
            },
            "operations": {
                operation_id: asdict(operation)
                for operation_id, operation in self.guild_operations.items()
            },
            "history": list(self.guild_activity_history),
        }

    def load_guild_autonomy_state(self, payload: dict[str, Any]) -> None:
        if not payload:
            self.guild_strategic_goals = {}
            self.guild_operations = {}
            self.guild_activity_history = []
            self._guild_operation_sequence = 0
            return
        if payload.get("schema") != GUILD_AUTONOMY_SCHEMA:
            if payload.get("agendas") or payload.get("goals") or payload.get("operations"):
                raise ValueError("legacy non-empty guild autonomy state cannot be migrated exactly to multi-operation authority")
            self.guild_strategic_goals = {}
            self.guild_operations = {}
            self.guild_activity_history = list(payload.get("history", []))
            self._guild_operation_sequence = 0
            return
        sequence = int(payload.get("sequence", 0))
        if sequence < 0:
            raise ValueError("guild operation sequence cannot be negative")
        goals: dict[str, dict[str, GuildStrategicGoalState]] = {}
        for guild_id, table in payload.get("goals", {}).items():
            self._guild(guild_id)
            for goal_id, row in table.items():
                goal = GuildStrategicGoalState(
                    guild_id=row["guild_id"],
                    goal_id=row["goal_id"],
                    target_location_id=row["target_location_id"],
                    priority=int(row["priority"]),
                    source=GuildGoalSource(row["source"]),
                    created_at_ms=int(row["created_at_ms"]),
                    basis_fact_id=row.get("basis_fact_id"),
                    required_member_fact_id=row.get("required_member_fact_id"),
                    member_resource_requirements={str(k): int(v) for k, v in row.get("member_resource_requirements", {}).items()},
                    guild_resource_requirements={str(k): int(v) for k, v in row.get("guild_resource_requirements", {}).items()},
                    min_members=int(row.get("min_members", 1)),
                    max_members=int(row.get("max_members", 6)),
                    desired_squads=int(row.get("desired_squads", 1)),
                    max_concurrent_squads=int(row.get("max_concurrent_squads", 1)),
                    allow_leader_assignment=bool(row.get("allow_leader_assignment", False)),
                    enabled=bool(row.get("enabled", True)),
                    launched_operation_ids=list(row.get("launched_operation_ids", [])),
                    revision=int(row.get("revision", 0)),
                )
                if goal.guild_id != guild_id or goal.goal_id != goal_id:
                    raise ValueError("guild strategic goal save key disagrees with stored identity")
                goals.setdefault(guild_id, {})[goal_id] = goal
        operations: dict[str, GuildOperationState] = {}
        max_sequence = 0
        for operation_id, row in payload.get("operations", {}).items():
            if not operation_id.startswith("guildop_"):
                raise ValueError(f"invalid guild operation id: {operation_id}")
            try:
                max_sequence = max(max_sequence, int(operation_id.removeprefix("guildop_")))
            except ValueError as exc:
                raise ValueError(f"invalid guild operation id: {operation_id}") from exc
            operation = GuildOperationState(
                operation_id=row["operation_id"],
                guild_id=row["guild_id"],
                goal_id=row["goal_id"],
                target_location_id=row["target_location_id"],
                origin_location_id=row["origin_location_id"],
                assigned_member_ids=tuple(row["assigned_member_ids"]),
                status=GuildOperationStatus(row["status"]),
                created_at_ms=int(row["created_at_ms"]),
                basis_event_id=row.get("basis_event_id"),
                activity_kind=row.get("activity_kind"),
                from_location_id=row.get("from_location_id"),
                next_location_id=row.get("next_location_id"),
                started_at_ms=(int(row["started_at_ms"]) if row.get("started_at_ms") is not None else None),
                due_at_ms=(int(row["due_at_ms"]) if row.get("due_at_ms") is not None else None),
                traversal_tags=tuple(row.get("traversal_tags", ())),
                withdraw_requested=bool(row.get("withdraw_requested", False)),
                regroup_location_id=row.get("regroup_location_id"),
                hold_at_next_node=bool(row.get("hold_at_next_node", False)),
                failure_reason=row.get("failure_reason"),
                completed_at_ms=(int(row["completed_at_ms"]) if row.get("completed_at_ms") is not None else None),
                revision=int(row.get("revision", 0)),
            )
            if operation.operation_id != operation_id:
                raise ValueError("guild operation save key disagrees with operation_id")
            operations[operation_id] = operation
        if sequence < max_sequence:
            raise ValueError("guild operation sequence precedes persisted operation ids")
        self.guild_strategic_goals = goals
        self.guild_operations = operations
        self.guild_activity_history = list(payload.get("history", []))
        self._guild_operation_sequence = sequence
        self._assert_guild_autonomy_authority()
''',
)


replace_once(
    "src/sao_mcp/rules/live_state.py",
    '''    guild_agendas = getattr(runtime, "guild_agendas", {})\n    for guild_id, agenda in guild_agendas.items():\n        if agenda.active and actor_id in agenda.assigned_member_ids:\n            matches.append(\n                {\n                    "kind": "guild_travel",\n                    "owner_id": guild_id,\n                    "actor_ids": list(agenda.assigned_member_ids),\n                    "from_location_id": agenda.from_location_id,\n                    "to_location_id": agenda.next_location_id,\n                    "started_at_ms": agenda.started_at_ms,\n                    "due_at_ms": agenda.due_at_ms,\n                    "traversal_tags": list(agenda.traversal_tags),\n                }\n            )\n''',
    '''    guild_operations = getattr(runtime, "guild_operations", {})\n    for operation_id, operation in guild_operations.items():\n        if operation.active and actor_id in operation.assigned_member_ids:\n            matches.append(\n                {\n                    "kind": "guild_travel",\n                    "owner_id": operation_id,\n                    "guild_id": operation.guild_id,\n                    "actor_ids": list(operation.assigned_member_ids),\n                    "from_location_id": operation.from_location_id,\n                    "to_location_id": operation.next_location_id,\n                    "started_at_ms": operation.started_at_ms,\n                    "due_at_ms": operation.due_at_ms,\n                    "traversal_tags": list(operation.traversal_tags),\n                }\n            )\n''',
)
replace_once(
    "src/sao_mcp/rules/live_state.py",
    '''    scheduler_assert = getattr(runtime, "_assert_npc_scheduler_authority", None)\n    if scheduler_assert is not None:\n        scheduler_assert()\n\n''',
    '''    scheduler_assert = getattr(runtime, "_assert_npc_scheduler_authority", None)\n    if scheduler_assert is not None:\n        scheduler_assert()\n    guild_assert = getattr(runtime, "_assert_guild_autonomy_authority", None)\n    if guild_assert is not None:\n        guild_assert()\n\n''',
)
replace_once(
    "src/sao_mcp/rules/live_state.py",
    '''    guild_agendas = getattr(runtime, "guild_agendas", {})\n    for guild_id, agenda in guild_agendas.items():\n        if not agenda.active:\n            continue\n        if agenda.activity_kind != "travel":\n            raise RuntimeError(f"guild {guild_id} has unsupported active activity {agenda.activity_kind!r}")\n        if agenda.from_location_id not in runtime.world_map.locations or agenda.next_location_id not in runtime.world_map.locations:\n            raise RuntimeError(f"guild {guild_id} active route references an unknown location")\n        if not _has_direct_edge(runtime, agenda.from_location_id, agenda.next_location_id):\n            raise RuntimeError(f"guild {guild_id} active route is not a world-graph edge")\n        if agenda.started_at_ms is None or agenda.due_at_ms is None or not (agenda.started_at_ms <= now < agenda.due_at_ms):\n            raise RuntimeError(f"guild {guild_id} has invalid active-route timing")\n        for actor_id in agenda.assigned_member_ids:\n            actor = runtime.actors[actor_id]\n            if actor.location_id is not None:\n                raise RuntimeError(f"travelling guild member {actor_id} has a settled location")\n            previous = route_actor.setdefault(actor_id, f"guild:{guild_id}")\n            if previous != f"guild:{guild_id}":\n                raise RuntimeError(f"actor {actor_id} has multiple active route authorities")\n''',
    '''    guild_operations = getattr(runtime, "guild_operations", {})\n    for operation_id, operation in guild_operations.items():\n        if not operation.active:\n            continue\n        if operation.activity_kind != "travel":\n            raise RuntimeError(f"guild operation {operation_id} has unsupported active activity {operation.activity_kind!r}")\n        if operation.from_location_id not in runtime.world_map.locations or operation.next_location_id not in runtime.world_map.locations:\n            raise RuntimeError(f"guild operation {operation_id} active route references an unknown location")\n        if not _has_direct_edge(runtime, operation.from_location_id, operation.next_location_id):\n            raise RuntimeError(f"guild operation {operation_id} active route is not a world-graph edge")\n        if operation.started_at_ms is None or operation.due_at_ms is None or not (operation.started_at_ms <= now < operation.due_at_ms):\n            raise RuntimeError(f"guild operation {operation_id} has invalid active-route timing")\n        for actor_id in operation.assigned_member_ids:\n            actor = runtime.actors[actor_id]\n            if actor.location_id is not None:\n                raise RuntimeError(f"travelling guild member {actor_id} has a settled location")\n            previous = route_actor.setdefault(actor_id, f"guild:{operation_id}")\n            if previous != f"guild:{operation_id}":\n                raise RuntimeError(f"actor {actor_id} has multiple active route authorities")\n''',
)


replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''    "assign_guild_goal": (\n        frozenset({"guild_id", "leader_id", "goal_id", "target_location_id", "assigned_member_ids"}),\n        frozenset({"basis_fact_id"}),\n    ),\n    "clear_guild_goal": (\n        frozenset({"guild_id", "leader_id"}),\n        frozenset(),\n    ),\n''',
    '''    "assign_guild_goal": (\n        frozenset({"guild_id", "leader_id", "goal_id", "target_location_id"}),\n        frozenset({\n            "assigned_member_ids",\n            "basis_fact_id",\n            "required_member_fact_id",\n            "member_resource_requirements",\n            "guild_resource_requirements",\n            "min_members",\n            "max_members",\n            "desired_squads",\n            "max_concurrent_squads",\n            "allow_leader_assignment",\n            "priority",\n        }),\n    ),\n    "clear_guild_goal": (\n        frozenset({"guild_id", "leader_id"}),\n        frozenset({"goal_id"}),\n    ),\n    "withdraw_guild_operation": (\n        frozenset({"guild_id", "leader_id", "operation_id"}),\n        frozenset({"regroup_location_id"}),\n    ),\n    "hold_guild_operation": (\n        frozenset({"guild_id", "leader_id", "operation_id"}),\n        frozenset(),\n    ),\n    "reorganize_guild_operation": (\n        frozenset({"guild_id", "leader_id", "operation_id", "assigned_member_ids"}),\n        frozenset(),\n    ),\n''',
)
replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''            if op == "assign_guild_goal":\n                member_ids = action["assigned_member_ids"]\n                if not isinstance(member_ids, list) or not member_ids or any(\n                    not isinstance(actor_id, str) for actor_id in member_ids\n                ):\n                    raise ValueError(\n                        f"GM turn action {index} (assign_guild_goal) assigned_member_ids must be a non-empty string list"\n                    )\n''',
    '''            if op in {"assign_guild_goal", "reorganize_guild_operation"} and "assigned_member_ids" in action:\n                member_ids = action["assigned_member_ids"]\n                if not isinstance(member_ids, list) or not member_ids or any(\n                    not isinstance(actor_id, str) or not actor_id for actor_id in member_ids\n                ):\n                    raise ValueError(\n                        f"GM turn action {index} ({op}) assigned_member_ids must be a non-empty string list"\n                    )\n''',
)
replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''        if op == "assign_guild_goal":\n            return runtime.assign_guild_goal(\n                action["guild_id"],\n                action["leader_id"],\n                action["goal_id"],\n                action["target_location_id"],\n                action["assigned_member_ids"],\n                basis_fact_id=action.get("basis_fact_id"),\n            )\n        if op == "clear_guild_goal":\n            return runtime.clear_guild_goal(action["guild_id"], action["leader_id"])\n''',
    '''        if op == "assign_guild_goal":\n            return runtime.assign_guild_goal(\n                action["guild_id"],\n                action["leader_id"],\n                action["goal_id"],\n                action["target_location_id"],\n                action.get("assigned_member_ids"),\n                basis_fact_id=action.get("basis_fact_id"),\n                required_member_fact_id=action.get("required_member_fact_id"),\n                member_resource_requirements=action.get("member_resource_requirements"),\n                guild_resource_requirements=action.get("guild_resource_requirements"),\n                min_members=int(action.get("min_members", 1)),\n                max_members=int(action.get("max_members", 6)),\n                desired_squads=int(action.get("desired_squads", 1)),\n                max_concurrent_squads=int(action.get("max_concurrent_squads", 1)),\n                allow_leader_assignment=bool(action.get("allow_leader_assignment", False)),\n                priority=int(action.get("priority", 100)),\n            )\n        if op == "clear_guild_goal":\n            return runtime.clear_guild_goal(\n                action["guild_id"],\n                action["leader_id"],\n                action.get("goal_id"),\n            )\n        if op == "withdraw_guild_operation":\n            return runtime.request_guild_operation_withdrawal(\n                action["guild_id"],\n                action["leader_id"],\n                action["operation_id"],\n                regroup_location_id=action.get("regroup_location_id"),\n            )\n        if op == "hold_guild_operation":\n            return runtime.hold_guild_operation(\n                action["guild_id"],\n                action["leader_id"],\n                action["operation_id"],\n            )\n        if op == "reorganize_guild_operation":\n            return runtime.reorganize_guild_operation(\n                action["guild_id"],\n                action["leader_id"],\n                action["operation_id"],\n                action["assigned_member_ids"],\n            )\n''',
)


replace_once(
    "src/sao_mcp/server_gm.py",
    '''    @mcp.tool()\n    def get_guild_agenda(guild_id: str) -> str:\n        """Inspect one guild's current strategic goal, assigned real members and concurrent travel leg."""\n        return _json(gm_turn_executor.runtime.guild_agenda_state(guild_id))\n\n''',
    '''    @mcp.tool()\n    def get_guild_agenda(guild_id: str) -> str:\n        """Inspect one guild's strategic goals, eligible member groups, resources and concurrent operations."""\n        return _json(gm_turn_executor.runtime.guild_agenda_state(guild_id))\n\n    @mcp.tool()\n    def get_guild_operation(operation_id: str) -> str:\n        """Inspect one real guild squad operation, including route, members, status and withdrawal state."""\n        return _json(gm_turn_executor.runtime.guild_operation_state(operation_id))\n\n''',
)


write(
    "tests/test_guild_autonomy_integration.py",
    r'''from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


TOWN = "floor_1_town_of_beginnings"
WEST = "floor_1_west_field"
TOLBANA = "floor_1_tolbana"


def _guild_with_members(runtime: HousingAincradRuntime, count: int = 1):
    leader = runtime.create_character("GuildLeader", level=12)
    guild = runtime.create_guild(leader.actor_id, "RouteGuild")
    members = []
    for index in range(count):
        member = runtime.create_character(f"GuildScout{index + 1}", level=11)
        invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
        runtime.accept_guild_invite(invite.invite_id, member.actor_id)
        members.append(member)
    return guild, leader, members


def test_authoritative_runtime_executes_and_persists_explicit_guild_operation():
    runtime = HousingAincradRuntime(seed=401)
    guild, leader, members = _guild_with_members(runtime, 1)
    member = members[0]
    executor = GMTurnExecutor(runtime)

    assigned = executor.execute([
        {
            "op": "assign_guild_goal",
            "guild_id": guild.guild_id,
            "leader_id": leader.actor_id,
            "goal_id": "scout_tolbana",
            "target_location_id": TOLBANA,
            "assigned_member_ids": [member.actor_id],
        }
    ])
    agenda = assigned["guild_agendas"][guild.guild_id]
    assert agenda["active"] is True
    assert agenda["from_location_id"] == TOWN
    assert agenda["next_location_id"] == WEST
    assert member.location_id is None

    restored = import_runtime(export_runtime(runtime))
    restored_agenda = restored.guild_agenda_state(guild.guild_id)
    assert restored_agenda["active"] is True
    assert restored_agenda["next_location_id"] == WEST
    assert restored.actors[member.actor_id].location_id is None

    restored.advance_world(12 * 60_000)
    second_leg = restored.guild_agenda_state(guild.guild_id)
    assert second_leg["active"] is True
    assert second_leg["from_location_id"] == WEST
    assert second_leg["next_location_id"] == TOLBANA

    restored.advance_world(42 * 60_000)
    reached = restored.guild_agenda_state(guild.guild_id)
    assert reached["active"] is False
    assert reached["goal_reached"] is True
    assert restored.actors[member.actor_id].location_id == TOLBANA

    restored_executor = GMTurnExecutor(restored)
    cleared = restored_executor.execute([
        {
            "op": "clear_guild_goal",
            "guild_id": guild.guild_id,
            "leader_id": leader.actor_id,
            "goal_id": "scout_tolbana",
        }
    ])
    assert cleared["guild_agendas"][guild.guild_id]["goal_id"] is None


def test_strategy_autonomously_splits_two_real_squads_without_member_reuse():
    runtime = HousingAincradRuntime(seed=402)
    guild, leader, members = _guild_with_members(runtime, 4)
    goal = runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "two_squad_scout",
        TOLBANA,
        min_members=2,
        max_members=2,
        desired_squads=2,
        max_concurrent_squads=2,
    )
    assert goal.goal_id == "two_squad_scout"
    state = runtime.guild_agenda_state(guild.guild_id)
    assert len(state["live_operation_ids"]) == 2
    operations = [state["operations"][operation_id] for operation_id in state["live_operation_ids"]]
    assigned = [actor_id for operation in operations for actor_id in operation["assigned_member_ids"]]
    assert set(assigned) == {member.actor_id for member in members}
    assert len(assigned) == len(set(assigned)) == 4
    assert all(operation["next_location_id"] == WEST for operation in operations)
    assert all(runtime.actors[actor_id].location_id is None for actor_id in assigned)


def test_strategy_waits_for_leader_knowledge_member_knowledge_and_real_resources():
    runtime = HousingAincradRuntime(seed=403)
    guild, leader, members = _guild_with_members(runtime, 2)
    guild.vault_col = 10
    for member in members:
        member.col = 20

    runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "verified_supply_scout",
        TOLBANA,
        basis_fact_id="route_open",
        required_member_fact_id="route_map_understood",
        member_resource_requirements={"col": 50},
        guild_resource_requirements={"vault_col": 100},
        min_members=1,
        max_members=1,
        desired_squads=1,
    )
    assert runtime.guild_agenda_state(guild.guild_id)["live_operation_ids"] == []

    runtime.record_observation(
        leader.actor_id,
        "route_open",
        True,
        observation_location_id=TOWN,
        source_id="guild_board",
    )
    runtime.record_observation(
        members[0].actor_id,
        "route_map_understood",
        True,
        observation_location_id=TOWN,
        source_id="route_briefing",
    )
    members[0].col = 80
    guild.vault_col = 150
    runtime.advance_world(0)

    state = runtime.guild_agenda_state(guild.guild_id)
    assert len(state["live_operation_ids"]) == 1
    operation = state["operations"][state["live_operation_ids"][0]]
    assert operation["assigned_member_ids"] == [members[0].actor_id]
    assert operation["basis_event_id"] is not None
    assert state["resources"]["vault_col"] == 150


def test_withdrawal_waits_for_next_real_route_node_then_returns_to_regroup():
    runtime = HousingAincradRuntime(seed=404)
    guild, leader, members = _guild_with_members(runtime, 1)
    member = members[0]
    operation = runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "withdrawable_scout",
        TOLBANA,
        [member.actor_id],
    )
    runtime.request_guild_operation_withdrawal(
        guild.guild_id,
        leader.actor_id,
        operation.operation_id,
        regroup_location_id=TOWN,
    )
    assert runtime.guild_operation_state(operation.operation_id)["withdraw_requested"] is True
    assert member.location_id is None

    runtime.advance_world(12 * 60_000)
    returning = runtime.guild_operation_state(operation.operation_id)
    assert returning["status"] == "withdrawing"
    assert returning["from_location_id"] == WEST
    assert returning["next_location_id"] == TOWN
    assert member.location_id is None

    runtime.advance_world(12 * 60_000)
    withdrawn = runtime.guild_operation_state(operation.operation_id)
    assert withdrawn["status"] == "withdrawn"
    assert withdrawn["terminal"] is True
    assert member.location_id == TOWN


def test_hold_and_reorganize_changes_members_only_at_a_settled_node():
    runtime = HousingAincradRuntime(seed=405)
    guild, leader, members = _guild_with_members(runtime, 3)
    a, b, reserve = members
    operation = runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "reorganize_scout",
        TOLBANA,
        [a.actor_id, b.actor_id],
    )
    runtime.hold_guild_operation(guild.guild_id, leader.actor_id, operation.operation_id)
    runtime.advance_world(12 * 60_000)
    paused = runtime.guild_operation_state(operation.operation_id)
    assert paused["status"] == "paused"
    assert a.location_id == b.location_id == WEST

    runtime.travel_actor(reserve.actor_id, WEST)
    resumed = runtime.reorganize_guild_operation(
        guild.guild_id,
        leader.actor_id,
        operation.operation_id,
        [b.actor_id, reserve.actor_id],
    )
    assert resumed.status.value == "active"
    assert set(resumed.assigned_member_ids) == {b.actor_id, reserve.actor_id}
    assert a.location_id == WEST
    assert b.location_id is None and reserve.location_id is None


def test_multi_operation_state_round_trips_without_reusing_members():
    runtime = HousingAincradRuntime(seed=406)
    guild, leader, members = _guild_with_members(runtime, 4)
    runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "persist_two_squads",
        TOLBANA,
        min_members=2,
        max_members=2,
        desired_squads=2,
        max_concurrent_squads=2,
    )
    restored = import_runtime(export_runtime(runtime))
    state = restored.guild_agenda_state(guild.guild_id)
    assert len(state["live_operation_ids"]) == 2
    assigned = [
        actor_id
        for operation_id in state["live_operation_ids"]
        for actor_id in state["operations"][operation_id]["assigned_member_ids"]
    ]
    assert len(assigned) == len(set(assigned)) == 4
''',
)


write(
    "tests/test_guild_autonomy_authority.py",
    r'''from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.guild_autonomy import GuildOperationStatus, GuildStrategicGoalState
from sao_mcp.runtime.gm_turn import GMTurnExecutor


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_guild_operation_lifecycle_supports_real_pause_withdrawal_failure_and_completion():
    assert {status.value for status in GuildOperationStatus} == {
        "active", "paused", "withdrawing", "completed", "withdrawn", "failed"
    }


def test_guild_strategy_model_owns_dispatch_constraints_not_actor_or_route_state():
    fields = set(GuildStrategicGoalState.__dataclass_fields__)
    assert {
        "basis_fact_id",
        "required_member_fact_id",
        "member_resource_requirements",
        "guild_resource_requirements",
        "min_members",
        "max_members",
        "desired_squads",
        "max_concurrent_squads",
        "launched_operation_ids",
    } <= fields
    assert "assigned_member_ids" not in fields
    assert "from_location_id" not in fields


def test_gm_contract_can_auto_dispatch_and_manage_real_operations():
    contract = GMTurnExecutor.supported_actions()
    assign = contract["assign_guild_goal"]
    assert set(assign["required"]) == {"guild_id", "leader_id", "goal_id", "target_location_id"}
    assert "assigned_member_ids" in assign["optional"]
    assert {"withdraw_guild_operation", "hold_guild_operation", "reorganize_guild_operation"} <= set(contract)


def test_scenarios_cannot_reach_into_guild_strategy_or_operation_authority():
    forbidden = {
        "guild_strategic_goals",
        "guild_operations",
        "_create_operation",
        "_begin_operation_leg",
        "_finish_operation_leg",
        "_evaluate_guild_strategies",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []
''',
)
