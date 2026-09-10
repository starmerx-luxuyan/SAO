from __future__ import annotations

from dataclasses import asdict

from sao_mcp.rules.access import require_location_access
from sao_mcp.rules.npc_autonomy import NPCAgendaState
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.travel import has_surviving_colocated_outsider, require_autonomous_travel
from sao_mcp.runtime.world_event_runtime import WorldEventAincradRuntime


class NPCAutonomyAincradRuntime(WorldEventAincradRuntime):
    """World-event runtime with persistent concurrent activities for named NPCs."""

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

    def set_npc_goal(self, npc_id: str, goal_id: str | None) -> NPCAgendaState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        agenda = self.npc_agendas.setdefault(npc_id, NPCAgendaState(npc_id))
        agenda.goal_id = goal_id
        return agenda

    def schedule_npc_travel(
        self,
        npc_id: str,
        destination_id: str,
        *,
        goal_id: str | None = None,
    ) -> NPCAgendaState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
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
            started_at_ms=self.world.now_ms,
            due_at_ms=self.world.now_ms + edge.travel_ms,
            traversal_tags=edge.traversal_tags,
            goal_id=goal_id,
        )
        if materialized is not None:
            materialized.location_id = None
        return agenda

    def _resolve_due_npc_activities(self, before_ms: int, after_ms: int) -> None:
        for npc_id, agenda in self.npc_agendas.items():
            if not agenda.active:
                continue
            if agenda.activity_kind != "travel":
                raise RuntimeError(f"unsupported NPC agenda activity: {agenda.activity_kind}")
            if agenda.due_at_ms is None or agenda.started_at_ms is None:
                raise RuntimeError(f"active NPC travel {npc_id} lacks timing")
            if agenda.from_location_id is None or agenda.target_location_id is None:
                raise RuntimeError(f"active NPC travel {npc_id} lacks route endpoints")
            if agenda.due_at_ms > after_ms:
                continue

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
                    "completed_at_ms": agenda.due_at_ms,
                    "traversal_tags": list(agenda.traversal_tags),
                }
            )
            agenda.finish_activity()

    def npc_agenda_state(self, npc_id: str) -> dict:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        agenda = self.npc_agendas.get(npc_id, NPCAgendaState(npc_id))
        return {
            **asdict(agenda),
            "active": agenda.active,
            "location_id": self.npc_location_id(npc_id),
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
