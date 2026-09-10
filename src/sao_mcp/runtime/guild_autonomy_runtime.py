from __future__ import annotations

from dataclasses import asdict

from sao_mcp.corpus.location_access import LOCATION_ACCESS_RULES
from sao_mcp.domain.models import CursorColor, EntityKind
from sao_mcp.rules.access import actor_faction_ids, require_location_access
from sao_mcp.rules.guild_autonomy import GuildAgendaState
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.routing import shortest_next_hop
from sao_mcp.rules.travel import AUTONOMOUS_TRAVEL_RESTRICTION_KEY, has_surviving_colocated_outsider
from sao_mcp.runtime.npc_autonomy_runtime import NPCAutonomyAincradRuntime


class GuildAutonomyAincradRuntime(NPCAutonomyAincradRuntime):
    """NPC-autonomy runtime plus persistent guild operations executed by real guild members."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.guild_agendas: dict[str, GuildAgendaState] = {}
        self.guild_activity_history: list[dict] = []
        self.register_world_advance_hook(self._resolve_due_guild_activities)

    def _guild(self, guild_id: str):
        try:
            return self.relationships.guilds[guild_id]
        except KeyError as exc:
            raise KeyError(f"unknown guild: {guild_id}") from exc

    def _require_guild_leader(self, guild_id: str, leader_id: str):
        guild = self._guild(guild_id)
        if guild.leader_id != leader_id:
            raise ValueError("guild strategic operations require the current guild leader")
        leader = self.actors[leader_id]
        if not leader.alive:
            raise ValueError("defeated guild leader cannot issue a strategic operation")
        return guild

    def _assigned_members(self, guild_id: str, member_ids: tuple[str, ...]):
        guild = self._guild(guild_id)
        members = []
        for actor_id in member_ids:
            if actor_id not in guild.member_ids:
                raise ValueError(f"assigned actor is not a member of guild {guild_id}: {actor_id}")
            actor = self.actors[actor_id]
            if actor.guild_id != guild_id:
                raise RuntimeError(f"guild member {actor_id} disagrees with GuildState membership")
            members.append(actor)
        return members

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

    def _operation_origin(self, agenda: GuildAgendaState) -> str:
        members = self._assigned_members(agenda.guild_id, agenda.assigned_member_ids)
        if any(not actor.alive for actor in members):
            raise ValueError("all assigned guild-operation members must be alive")
        locations = {actor.location_id for actor in members}
        if None in locations:
            raise RuntimeError("idle guild operation has an assigned member without a settled world location")
        if len(locations) != 1:
            raise ValueError("assigned guild-operation members must be colocated")
        return str(next(iter(locations)))

    def _operation_blocked_by_encounter(self, member_ids: tuple[str, ...], origin: str) -> bool:
        member_set = set(member_ids)
        return any(
            member_set.intersection(encounter.participants)
            and has_surviving_colocated_outsider(encounter, member_set, origin)
            for encounter in self.encounters.values()
        )

    def _next_operation_hop(self, agenda: GuildAgendaState, origin: str) -> str | None:
        target = agenda.target_location_id
        if target is None:
            raise RuntimeError(f"guild {agenda.guild_id} agenda has no target location")
        return shortest_next_hop(
            self.world,
            self.world_map,
            origin,
            target,
            can_enter=lambda location_id: self._members_can_enter(agenda.assigned_member_ids, location_id),
        )

    def _begin_guild_leg(self, agenda: GuildAgendaState, started_at_ms: int) -> bool:
        origin = self._operation_origin(agenda)
        if origin == agenda.target_location_id:
            return False
        if self._operation_blocked_by_encounter(agenda.assigned_member_ids, origin):
            raise ValueError("guild operation cannot depart during a live colocated encounter")
        for actor in self._assigned_members(agenda.guild_id, agenda.assigned_member_ids):
            if actor.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:
                raise ValueError("an assigned guild member has restricted autonomous travel")
            if actor.metadata.get("active_duel_id"):
                raise ValueError("an assigned guild member is in an active duel")

        next_hop = self._next_operation_hop(agenda, origin)
        if next_hop is None:
            return False
        destination = self.world_map.locations[next_hop]
        if not self.world.floors[destination.floor_number].unlocked:
            raise ValueError("guild operation next-hop floor is not unlocked")
        for actor in self._assigned_members(agenda.guild_id, agenda.assigned_member_ids):
            require_location_access(actor, next_hop)
        edges = [
            edge
            for edge in self.world_map.adjacency.get(origin, ())
            if edge.to_location_id == next_hop
        ]
        if not edges:
            raise RuntimeError("guild route planner selected a non-adjacent next hop")
        edge = min(edges, key=lambda candidate: candidate.travel_ms)
        agenda.begin_leg(
            from_location_id=origin,
            next_location_id=next_hop,
            started_at_ms=started_at_ms,
            due_at_ms=started_at_ms + edge.travel_ms,
            traversal_tags=edge.traversal_tags,
        )
        for actor in self._assigned_members(agenda.guild_id, agenda.assigned_member_ids):
            actor.location_id = None
        return True

    def assign_guild_goal(
        self,
        guild_id: str,
        leader_id: str,
        goal_id: str,
        target_location_id: str,
        assigned_member_ids: list[str] | tuple[str, ...],
        *,
        basis_fact_id: str | None = None,
    ) -> GuildAgendaState:
        guild = self._require_guild_leader(guild_id, leader_id)
        members = tuple(dict.fromkeys(assigned_member_ids))
        if len(members) != len(assigned_member_ids):
            raise ValueError("guild operation assigned_member_ids must be unique")
        self._assigned_members(guild_id, members)
        if target_location_id not in self.world_map.locations:
            raise KeyError(target_location_id)
        target = self.world_map.locations[target_location_id]
        if not self.world.floors[target.floor_number].unlocked:
            raise ValueError("guild operation target floor is not unlocked")
        if basis_fact_id is not None and self.belief(guild.leader_id, basis_fact_id) is None:
            raise ValueError("guild leader does not know the stated operation basis fact")

        agenda = self.guild_agendas.setdefault(guild_id, GuildAgendaState(guild_id))
        agenda.assign(
            goal_id=goal_id,
            target_location_id=target_location_id,
            member_ids=members,
        )
        origin = self._operation_origin(agenda)
        self._next_operation_hop(agenda, origin)
        self._begin_guild_leg(agenda, self.world.now_ms)
        self.guild_activity_history.append(
            {
                "guild_id": guild_id,
                "event": "goal_assigned",
                "goal_id": goal_id,
                "target_location_id": target_location_id,
                "assigned_member_ids": list(members),
                "issued_by_actor_id": leader_id,
                "basis_fact_id": basis_fact_id,
                "issued_at_ms": self.world.now_ms,
            }
        )
        return agenda

    def clear_guild_goal(self, guild_id: str, leader_id: str) -> GuildAgendaState:
        self._require_guild_leader(guild_id, leader_id)
        agenda = self.guild_agendas.setdefault(guild_id, GuildAgendaState(guild_id))
        if agenda.active:
            raise ValueError("cannot clear a guild goal while assigned members are in transit")
        agenda.complete_goal()
        self.guild_activity_history.append(
            {
                "guild_id": guild_id,
                "event": "goal_cleared",
                "issued_by_actor_id": leader_id,
                "at_ms": self.world.now_ms,
            }
        )
        return agenda

    def _finish_guild_leg(self, agenda: GuildAgendaState) -> int:
        if agenda.activity_kind != "travel":
            raise RuntimeError(f"unsupported guild activity: {agenda.activity_kind}")
        if agenda.due_at_ms is None or agenda.started_at_ms is None:
            raise RuntimeError(f"active guild operation {agenda.guild_id} lacks timing")
        if agenda.from_location_id is None or agenda.next_location_id is None:
            raise RuntimeError(f"active guild operation {agenda.guild_id} lacks route endpoints")
        members = self._assigned_members(agenda.guild_id, agenda.assigned_member_ids)
        if any(not actor.alive for actor in members):
            raise RuntimeError("a guild-operation member was defeated while in transit")
        if any(actor.location_id is not None for actor in members):
            raise RuntimeError("a travelling guild-operation member unexpectedly has a settled location")

        completed_at_ms = agenda.due_at_ms
        destination_id = agenda.next_location_id
        destination = self.world_map.locations[destination_id]
        floor = self.world.floors[destination.floor_number]
        newly_discovered = destination_id not in floor.discovered_locations
        floor.discovered_locations.add(destination_id)
        for actor in members:
            actor.location_id = destination_id
            if actor.kind is EntityKind.PLAYER:
                self.quests.record_event(
                    actor.actor_id,
                    kind=QuestObjectiveKind.DISCOVER,
                    target_id=destination_id,
                )
        self.guild_activity_history.append(
            {
                "guild_id": agenda.guild_id,
                "event": "travel_leg_completed",
                "goal_id": agenda.goal_id,
                "assigned_member_ids": list(agenda.assigned_member_ids),
                "from_location_id": agenda.from_location_id,
                "to_location_id": destination_id,
                "started_at_ms": agenda.started_at_ms,
                "completed_at_ms": completed_at_ms,
                "newly_discovered": newly_discovered,
                "traversal_tags": list(agenda.traversal_tags),
            }
        )
        agenda.finish_leg()
        return completed_at_ms

    def _resolve_due_guild_activities(self, before_ms: int, after_ms: int) -> None:
        for agenda in self.guild_agendas.values():
            while agenda.active and agenda.due_at_ms is not None and agenda.due_at_ms <= after_ms:
                completed_at_ms = self._finish_guild_leg(agenda)
                if agenda.target_location_id == self._operation_origin(agenda):
                    break
                self._begin_guild_leg(agenda, completed_at_ms)

    def guild_agenda_state(self, guild_id: str) -> dict:
        guild = self._guild(guild_id)
        agenda = self.guild_agendas.get(guild_id, GuildAgendaState(guild_id))
        member_locations = {
            actor_id: self.actors[actor_id].location_id
            for actor_id in agenda.assigned_member_ids
        }
        goal_reached = bool(
            agenda.goal_id is not None
            and not agenda.active
            and agenda.target_location_id is not None
            and member_locations
            and set(member_locations.values()) == {agenda.target_location_id}
        )
        return {
            **asdict(agenda),
            "leader_id": guild.leader_id,
            "active": agenda.active,
            "goal_reached": goal_reached,
            "member_locations": member_locations,
        }

    def dump_guild_autonomy_state(self) -> dict:
        return {
            "agendas": {
                guild_id: asdict(agenda)
                for guild_id, agenda in self.guild_agendas.items()
            },
            "history": list(self.guild_activity_history),
        }

    def load_guild_autonomy_state(self, payload: dict) -> None:
        agendas: dict[str, GuildAgendaState] = {}
        for guild_id, row in payload.get("agendas", {}).items():
            guild = self._guild(guild_id)
            agenda = GuildAgendaState(
                guild_id=guild_id,
                goal_id=row.get("goal_id"),
                target_location_id=row.get("target_location_id"),
                assigned_member_ids=tuple(row.get("assigned_member_ids", ())),
                activity_kind=row.get("activity_kind"),
                from_location_id=row.get("from_location_id"),
                next_location_id=row.get("next_location_id"),
                started_at_ms=row.get("started_at_ms"),
                due_at_ms=row.get("due_at_ms"),
                traversal_tags=tuple(row.get("traversal_tags", ())),
            )
            self._assigned_members(guild_id, agenda.assigned_member_ids)
            if agenda.active:
                if agenda.due_at_ms is None or agenda.due_at_ms <= self.world.now_ms:
                    raise ValueError(f"guild autonomy save contains overdue active travel: {guild_id}")
                if any(self.actors[actor_id].location_id is not None for actor_id in agenda.assigned_member_ids):
                    raise ValueError(f"active guild autonomy save has settled travelling members: {guild_id}")
            if agenda.goal_id is not None and guild.leader_id not in guild.member_ids:
                raise RuntimeError(f"guild {guild_id} leader is missing from its own member list")
            agendas[guild_id] = agenda
        self.guild_agendas = agendas
        self.guild_activity_history = list(payload.get("history", []))
