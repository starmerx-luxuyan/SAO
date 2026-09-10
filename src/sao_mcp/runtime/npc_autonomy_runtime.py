from __future__ import annotations

import heapq
from dataclasses import asdict

from sao_mcp.corpus.location_access import LOCATION_ACCESS_RULES
from sao_mcp.rules.access import actor_faction_ids, require_location_access
from sao_mcp.rules.npc_autonomy import NPCAgendaState
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.travel import (
    AUTONOMOUS_TRAVEL_RESTRICTION_KEY,
    has_surviving_colocated_outsider,
    require_autonomous_travel,
)
from sao_mcp.runtime.world_event_runtime import WorldEventAincradRuntime


class NPCAutonomyAincradRuntime(WorldEventAincradRuntime):
    """World-event runtime with persistent concurrent activities and location goals for named NPCs."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.npc_agendas: dict[str, NPCAgendaState] = {}
        self.npc_activity_history: list[dict] = []
        self.register_world_advance_hook(self._resolve_due_npc_activities)

    def _materialized_npc_actor(self, npc_id: str):
        matches = [
            actor
            for actor in self.actors.values()
            if actor.metadata.get("npc_definition_id") == npc_id
        ]
        if len(matches) > 1:
            raise RuntimeError(f"multiple materialized actors exist for NPC {npc_id}")
        return matches[0] if matches else None

    def _stationary_npc_location_id(self, npc_id: str) -> str:
        if npc_id not in self.npcs.states:
            raise KeyError(npc_id)
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is None:
            return self.npcs.states[npc_id].location_id
        if materialized.location_id is None:
            raise RuntimeError(f"materialized NPC {npc_id} has no settled world location")
        return materialized.location_id

    def npc_location_id(self, npc_id: str) -> str | None:
        agenda = self.npc_agendas.get(npc_id)
        if agenda is not None and agenda.active:
            return None
        return self._stationary_npc_location_id(npc_id)

    def interact_npc(self, actor_id: str, npc_id: str):
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is not None and not materialized.alive:
            raise ValueError("materialized NPC is not alive for interaction")
        actor = self.actors[actor_id]
        interaction = self.npcs.interact_at(
            actor_id,
            npc_id,
            actor_location_id=actor.location_id,
            npc_location_id=self.npc_location_id(npc_id),
            now_ms=self.world.now_ms,
            quests=self.quests,
        )
        self.quests.record_event(
            actor_id,
            kind=QuestObjectiveKind.TALK,
            target_id=npc_id,
        )
        return interaction

    def claim_quest(self, actor_id: str, quest_id: str):
        actor = self.actors[actor_id]
        definition = self.quests.definitions[quest_id]
        materialized = self._materialized_npc_actor(definition.turn_in_id)
        if materialized is not None and not materialized.alive:
            raise ValueError("materialized quest turn-in NPC is not alive")
        if actor.location_id != self.npc_location_id(definition.turn_in_id):
            raise ValueError("quest must be turned in to the designated NPC")
        return self.quests.claim(actor, quest_id, self.catalog, now_ms=self.world.now_ms)

    def _location_accessible_to_npc(self, npc_id: str, location_id: str) -> bool:
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is None:
            return True
        rule = LOCATION_ACCESS_RULES.get(location_id)
        if rule is None:
            return True
        return not set(actor_faction_ids(materialized)).intersection(rule.forbidden_faction_ids)

    def _shortest_next_hop(self, npc_id: str, origin: str, target: str) -> str | None:
        if origin == target:
            return None
        queue: list[tuple[int, str, str | None]] = [(0, origin, None)]
        best = {origin: 0}
        while queue:
            elapsed, node_id, first_hop = heapq.heappop(queue)
            if elapsed != best.get(node_id):
                continue
            for edge in self.world_map.adjacency.get(node_id, ()):
                destination = self.world_map.locations[edge.to_location_id]
                if edge.requires_floor_unlocked and not self.world.floors[destination.floor_number].unlocked:
                    continue
                if not self._location_accessible_to_npc(npc_id, edge.to_location_id):
                    continue
                total = elapsed + edge.travel_ms
                if total >= best.get(edge.to_location_id, 2**63 - 1):
                    continue
                next_first = edge.to_location_id if first_hop is None else first_hop
                if edge.to_location_id == target:
                    return next_first
                best[edge.to_location_id] = total
                heapq.heappush(queue, (total, edge.to_location_id, next_first))
        raise ValueError(f"NPC goal target is unreachable from {origin}: {target}")

    def _blocked_from_starting_goal_travel(self, npc_id: str, origin: str) -> bool:
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is None:
            return False
        if not materialized.alive:
            return True
        if materialized.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:
            return True
        member_ids = {materialized.actor_id}
        return any(
            materialized.actor_id in encounter.participants
            and has_surviving_colocated_outsider(encounter, member_ids, origin)
            for encounter in self.encounters.values()
        )

    def _begin_npc_travel_at(self, npc_id: str, destination_id: str, started_at_ms: int) -> NPCAgendaState:
        agenda = self.npc_agendas.setdefault(npc_id, NPCAgendaState(npc_id))
        if agenda.active:
            raise ValueError(f"NPC {npc_id} already has an active agenda activity")
        origin = self._stationary_npc_location_id(npc_id)
        if destination_id not in self.world_map.locations:
            raise KeyError(destination_id)
        destination = self.world_map.locations[destination_id]
        if not self.world.floors[destination.floor_number].unlocked:
            raise ValueError("destination floor is not unlocked")
        candidates = [
            edge
            for edge in self.world_map.adjacency.get(origin, ())
            if edge.to_location_id == destination_id
        ]
        if not candidates:
            raise ValueError("NPC destination is not directly connected to the current location")
        edge = min(candidates, key=lambda value: value.travel_ms)

        materialized = self._materialized_npc_actor(npc_id)
        if materialized is not None:
            if not materialized.alive:
                raise ValueError("defeated NPC cannot start autonomous travel")
            require_autonomous_travel(materialized)
            member_ids = {materialized.actor_id}
            for encounter in self.encounters.values():
                if materialized.actor_id not in encounter.participants:
                    continue
                if has_surviving_colocated_outsider(encounter, member_ids, origin):
                    raise ValueError("NPC autonomous travel is unavailable during a live colocated encounter")
            require_location_access(materialized, destination_id)

        agenda.begin_travel(
            from_location_id=origin,
            target_location_id=destination_id,
            started_at_ms=started_at_ms,
            due_at_ms=started_at_ms + edge.travel_ms,
            traversal_tags=edge.traversal_tags,
        )
        if materialized is not None:
            materialized.location_id = None
        return agenda

    def schedule_npc_travel(self, npc_id: str, destination_id: str) -> NPCAgendaState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        return self._begin_npc_travel_at(npc_id, destination_id, self.world.now_ms)

    def _plan_goal_step(self, npc_id: str, started_at_ms: int) -> bool:
        agenda = self.npc_agendas[npc_id]
        target = agenda.goal_target_location_id
        if agenda.active or target is None:
            return False
        origin = self._stationary_npc_location_id(npc_id)
        if origin == target:
            return False
        if self._blocked_from_starting_goal_travel(npc_id, origin):
            return False
        next_hop = self._shortest_next_hop(npc_id, origin, target)
        if next_hop is None:
            return False
        self._begin_npc_travel_at(npc_id, next_hop, started_at_ms)
        return True

    def set_npc_goal(self, npc_id: str, goal_id: str, target_location_id: str) -> NPCAgendaState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        if target_location_id not in self.world_map.locations:
            raise KeyError(target_location_id)
        target = self.world_map.locations[target_location_id]
        if not self.world.floors[target.floor_number].unlocked:
            raise ValueError("NPC goal target floor is not unlocked")
        agenda = self.npc_agendas.setdefault(npc_id, NPCAgendaState(npc_id))
        agenda.set_goal(goal_id, target_location_id)
        self._shortest_next_hop(npc_id, self._stationary_npc_location_id(npc_id), target_location_id)
        self._plan_goal_step(npc_id, self.world.now_ms)
        return agenda

    def clear_npc_goal(self, npc_id: str) -> NPCAgendaState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        agenda = self.npc_agendas.setdefault(npc_id, NPCAgendaState(npc_id))
        agenda.clear_goal()
        return agenda

    def _finish_travel_leg(self, npc_id: str, agenda: NPCAgendaState) -> int:
        if agenda.activity_kind != "travel":
            raise RuntimeError(f"unsupported NPC agenda activity: {agenda.activity_kind}")
        if agenda.due_at_ms is None or agenda.started_at_ms is None:
            raise RuntimeError(f"active NPC travel {npc_id} lacks timing")
        if agenda.from_location_id is None or agenda.target_location_id is None:
            raise RuntimeError(f"active NPC travel {npc_id} lacks route endpoints")
        completed_at_ms = agenda.due_at_ms
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is None:
            self.npcs.states[npc_id].location_id = agenda.target_location_id
        else:
            if not materialized.alive:
                raise RuntimeError(f"defeated NPC {npc_id} still has an active travel activity")
            if materialized.location_id is not None:
                raise RuntimeError(f"travelling NPC {npc_id} unexpectedly has a settled world location")
            materialized.location_id = agenda.target_location_id

        self.npc_activity_history.append(
            {
                "npc_id": npc_id,
                "goal_id": agenda.goal_id,
                "activity_kind": "travel",
                "from_location_id": agenda.from_location_id,
                "to_location_id": agenda.target_location_id,
                "started_at_ms": agenda.started_at_ms,
                "completed_at_ms": completed_at_ms,
                "traversal_tags": list(agenda.traversal_tags),
            }
        )
        agenda.finish_activity()
        return completed_at_ms

    def _resolve_due_npc_activities(self, before_ms: int, after_ms: int) -> None:
        for npc_id, agenda in self.npc_agendas.items():
            while agenda.active and agenda.due_at_ms is not None and agenda.due_at_ms <= after_ms:
                completed_at_ms = self._finish_travel_leg(npc_id, agenda)
                self._plan_goal_step(npc_id, completed_at_ms)
            if not agenda.active and agenda.goal_target_location_id is not None:
                self._plan_goal_step(npc_id, after_ms)

    def npc_agenda_state(self, npc_id: str) -> dict:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        agenda = self.npc_agendas.get(npc_id, NPCAgendaState(npc_id))
        location_id = self.npc_location_id(npc_id)
        return {
            **asdict(agenda),
            "active": agenda.active,
            "location_id": location_id,
            "goal_reached": bool(
                agenda.goal_target_location_id is not None
                and not agenda.active
                and location_id == agenda.goal_target_location_id
            ),
        }

    def dump_npc_autonomy_state(self) -> dict:
        return {
            "agendas": {
                npc_id: asdict(agenda)
                for npc_id, agenda in self.npc_agendas.items()
            },
            "history": list(self.npc_activity_history),
        }

    def load_npc_autonomy_state(self, payload: dict) -> None:
        agendas: dict[str, NPCAgendaState] = {}
        for npc_id, row in payload.get("agendas", {}).items():
            if npc_id not in self.npcs.definitions:
                raise ValueError(f"NPC autonomy save references unknown NPC: {npc_id}")
            agenda = NPCAgendaState(
                npc_id=npc_id,
                goal_id=row.get("goal_id"),
                goal_target_location_id=row.get("goal_target_location_id"),
                activity_kind=row.get("activity_kind"),
                from_location_id=row.get("from_location_id"),
                target_location_id=row.get("target_location_id"),
                started_at_ms=row.get("started_at_ms"),
                due_at_ms=row.get("due_at_ms"),
                traversal_tags=tuple(row.get("traversal_tags", ())),
            )
            if agenda.active and (agenda.due_at_ms is None or agenda.due_at_ms <= self.world.now_ms):
                raise ValueError(f"NPC autonomy save contains overdue active travel: {npc_id}")
            agendas[npc_id] = agenda
        self.npc_agendas = agendas
        self.npc_activity_history = list(payload.get("history", []))
