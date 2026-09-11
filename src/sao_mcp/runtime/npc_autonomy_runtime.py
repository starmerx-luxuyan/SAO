from __future__ import annotations

import heapq
from dataclasses import asdict
from typing import Any

from sao_mcp.corpus.location_access import LOCATION_ACCESS_RULES
from sao_mcp.rules.access import actor_faction_ids, require_location_access
from sao_mcp.rules.npc_actor_core import (
    NPCActorCoreState,
    NPCGoalSource,
    NPCGoalState,
    NPCPlanStep,
)
from sao_mcp.rules.npc_autonomy import NPCAgendaState
from sao_mcp.rules.travel import (
    AUTONOMOUS_TRAVEL_RESTRICTION_KEY,
    has_surviving_colocated_outsider,
)
from sao_mcp.runtime.world_event_runtime import WorldEventAincradRuntime


LOCATION_UNAVAILABLE_FACT_PREFIX = "location_unavailable:"
SHOP_RETURN_GOAL_ID = "routine:return_to_shop"
NPC_AUTONOMY_SCHEMA = "npc-autonomy.v2"


class NPCAutonomyAincradRuntime(WorldEventAincradRuntime):
    """Persistent NPC actor cores plus concurrent execution activities."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.npc_actor_cores: dict[str, NPCActorCoreState] = {}
        self.npc_agendas: dict[str, NPCAgendaState] = {}
        self.npc_activity_history: list[dict] = []
        for npc_id in self.npcs.definitions:
            self._ensure_actor_core(npc_id)
        self.register_world_advance_hook(self._resolve_due_npc_activities)

    def _ensure_actor_core(self, npc_id: str) -> NPCActorCoreState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        existing = self.npc_actor_cores.get(npc_id)
        if existing is not None:
            return existing
        core = NPCActorCoreState(npc_id=npc_id)
        definition = self.npcs.definitions[npc_id]
        if "shop_owner" in definition.roles:
            core.upsert_goal(
                NPCGoalState(
                    goal_id=SHOP_RETURN_GOAL_ID,
                    priority=10,
                    target_location_id=definition.home_location_id,
                    business_id="operate_shop",
                    source=NPCGoalSource.ROLE,
                )
            )
        self.npc_actor_cores[npc_id] = core
        return core

    def _agenda(self, npc_id: str) -> NPCAgendaState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        return self.npc_agendas.setdefault(npc_id, NPCAgendaState(npc_id))

    def _stationary_npc_location_id(self, npc_id: str) -> str:
        location_id = super().npc_location_id(npc_id)
        if location_id is None:
            raise RuntimeError(f"NPC {npc_id} has no settled world location")
        return location_id

    def npc_location_id(self, npc_id: str) -> str | None:
        agenda = self.npc_agendas.get(npc_id)
        if agenda is not None and agenda.active:
            return None
        return super().npc_location_id(npc_id)

    def _location_accessible_to_npc(self, npc_id: str, location_id: str) -> bool:
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is None:
            return True
        rule = LOCATION_ACCESS_RULES.get(location_id)
        if rule is None:
            return True
        return not set(actor_faction_ids(materialized)).intersection(rule.forbidden_faction_ids)

    def _shortest_path(self, npc_id: str, origin: str, target: str) -> tuple[str, ...]:
        if origin == target:
            return ()
        queue: list[tuple[int, str, tuple[str, ...]]] = [(0, origin, ())]
        best = {origin: 0}
        while queue:
            elapsed, node_id, path = heapq.heappop(queue)
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
                next_path = path + (edge.to_location_id,)
                if edge.to_location_id == target:
                    return next_path
                best[edge.to_location_id] = total
                heapq.heappush(queue, (total, edge.to_location_id, next_path))
        raise ValueError(f"NPC goal target is unreachable from {origin}: {target}")

    def _shortest_next_hop(self, npc_id: str, origin: str, target: str) -> str | None:
        path = self._shortest_path(npc_id, origin, target)
        return path[0] if path else None

    def _blocked_from_starting_goal_travel(self, npc_id: str, origin: str) -> bool:
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is None:
            return False
        if not materialized.alive:
            return True
        if self.legal.custody_for(materialized.actor_id) is not None:
            return True
        if materialized.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:
            return True
        member_ids = {materialized.actor_id}
        return any(
            materialized.actor_id in encounter.participants
            and has_surviving_colocated_outsider(encounter, member_ids, origin)
            for encounter in self.encounters.values()
        )

    def _npc_resource_snapshot(self, npc_id: str) -> dict[str, Any]:
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is None:
            return {
                "materialized": False,
                "col": 0,
                "hp": 0,
                "max_hp": 0,
                "inventory_templates": {},
            }
        inventory_templates: dict[str, int] = {}
        for item in materialized.inventory.values():
            inventory_templates[item.template_id] = inventory_templates.get(item.template_id, 0) + item.quantity
        return {
            "materialized": True,
            "actor_id": materialized.actor_id,
            "col": materialized.col,
            "hp": materialized.hp,
            "max_hp": materialized.max_hp,
            "inventory_templates": inventory_templates,
        }

    def _validate_resource_requirement_id(self, resource_id: str) -> None:
        if resource_id in {"col", "hp"}:
            return
        prefix = "inventory:"
        if resource_id.startswith(prefix) and len(resource_id) > len(prefix):
            template_id = resource_id[len(prefix):]
            self.catalog.item(template_id)
            return
        raise ValueError(f"unsupported NPC actor-core resource id: {resource_id}")

    def _npc_resource_quantity(self, npc_id: str, resource_id: str) -> int:
        self._validate_resource_requirement_id(resource_id)
        resources = self._npc_resource_snapshot(npc_id)
        if resource_id == "col":
            return int(resources["col"])
        if resource_id == "hp":
            return int(resources["hp"])
        template_id = resource_id.split(":", 1)[1]
        return int(resources["inventory_templates"].get(template_id, 0))

    def _goal_is_eligible(self, npc_id: str, goal: NPCGoalState) -> bool:
        if not goal.enabled:
            return False
        if goal.target_location_id is not None:
            location = self.world_map.locations.get(goal.target_location_id)
            if location is None or not self.world.floors[location.floor_number].unlocked:
                return False
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is not None and not materialized.alive:
            return False
        if goal.required_fact_id is not None:
            belief = self.belief(npc_id, goal.required_fact_id)
            if belief is None or belief.value != goal.required_fact_value:
                return False
        if goal.relationship_actor_id is not None:
            score = self.npcs.states[npc_id].relationship_by_actor.get(goal.relationship_actor_id, 0)
            threshold = goal.min_relationship if goal.min_relationship is not None else 0
            if score < threshold:
                return False
        for resource_id, amount in goal.resource_requirements.items():
            if self._npc_resource_quantity(npc_id, resource_id) < amount:
                return False
        if goal.goal_id == SHOP_RETURN_GOAL_ID:
            home = self.npcs.definitions[npc_id].home_location_id
            if self._shop_home_unavailable(npc_id, home):
                return False
            current = self._stationary_npc_location_id(npc_id)
            if self.world_map.locations[current].floor_number != self.world_map.locations[home].floor_number:
                return False
        return True

    def _select_goal(self, npc_id: str) -> NPCGoalState | None:
        core = self._ensure_actor_core(npc_id)
        eligible = [goal for goal in core.long_term_goals.values() if self._goal_is_eligible(npc_id, goal)]
        if not eligible:
            return None
        return min(eligible, key=lambda goal: (-goal.priority, goal.goal_id))

    def _replace_goal_plan(self, npc_id: str, goal: NPCGoalState) -> None:
        core = self._ensure_actor_core(npc_id)
        target = goal.target_location_id
        if target is None:
            core.replace_plan([])
            return
        origin = self._stationary_npc_location_id(npc_id)
        path = self._shortest_path(npc_id, origin, target)
        steps = [
            NPCPlanStep(
                step_id=f"{goal.goal_id}:rev{core.revision}:step{index}",
                action_kind="travel",
                target_location_id=location_id,
            )
            for index, location_id in enumerate(path, start=1)
        ]
        core.replace_plan(steps)

    def _begin_npc_travel_at(
        self,
        npc_id: str,
        destination_id: str,
        started_at_ms: int,
        *,
        plan_step_id: str | None = None,
    ) -> NPCAgendaState:
        agenda = self._agenda(npc_id)
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
            self.require_actor_autonomous_travel(materialized.actor_id)
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
            plan_step_id=plan_step_id,
        )
        if materialized is not None:
            materialized.location_id = None
        return agenda

    def schedule_npc_travel(self, npc_id: str, destination_id: str) -> NPCAgendaState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        return self._begin_npc_travel_at(npc_id, destination_id, self.world.now_ms)

    def _plan_goal_step(self, npc_id: str, started_at_ms: int) -> bool:
        agenda = self._agenda(npc_id)
        core = self._ensure_actor_core(npc_id)
        goal = core.current_goal
        if agenda.active or goal is None or goal.target_location_id is None:
            return False
        origin = self._stationary_npc_location_id(npc_id)
        if origin == goal.target_location_id:
            if core.current_plan_step is not None:
                core.replace_plan([])
            return False
        if self._blocked_from_starting_goal_travel(npc_id, origin):
            return False
        step = core.current_plan_step
        if step is None:
            self._replace_goal_plan(npc_id, goal)
            step = core.current_plan_step
        if step is None:
            return False
        directly_connected = any(
            edge.to_location_id == step.target_location_id
            for edge in self.world_map.adjacency.get(origin, ())
        )
        if not directly_connected:
            self._replace_goal_plan(npc_id, goal)
            step = core.current_plan_step
            if step is None:
                return False
        self._begin_npc_travel_at(
            npc_id,
            step.target_location_id,
            started_at_ms,
            plan_step_id=step.step_id,
        )
        return True

    def set_npc_goal(
        self,
        npc_id: str,
        goal_id: str,
        target_location_id: str,
        *,
        priority: int = 100,
        business_id: str | None = None,
        required_fact_id: str | None = None,
        required_fact_value: Any = True,
        relationship_actor_id: str | None = None,
        min_relationship: int | None = None,
        resource_requirements: dict[str, int] | None = None,
    ) -> NPCActorCoreState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        if target_location_id not in self.world_map.locations:
            raise KeyError(target_location_id)
        target = self.world_map.locations[target_location_id]
        if not self.world.floors[target.floor_number].unlocked:
            raise ValueError("NPC goal target floor is not unlocked")
        if relationship_actor_id is not None and relationship_actor_id not in self.actors:
            raise KeyError(relationship_actor_id)
        requirements = dict(resource_requirements or {})
        for resource_id, amount in requirements.items():
            self._validate_resource_requirement_id(resource_id)
            if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                raise ValueError("NPC actor-core resource requirement amounts must be positive integers")
        core = self._ensure_actor_core(npc_id)
        core.upsert_goal(
            NPCGoalState(
                goal_id=goal_id,
                priority=int(priority),
                target_location_id=target_location_id,
                business_id=business_id or f"pursue:{goal_id}",
                source=NPCGoalSource.MANUAL,
                required_fact_id=required_fact_id,
                required_fact_value=required_fact_value,
                relationship_actor_id=relationship_actor_id,
                min_relationship=min_relationship,
                resource_requirements=requirements,
            )
        )
        self._evaluate_npc_decision(npc_id, self.world.now_ms)
        return core

    def clear_npc_goal(self, npc_id: str) -> NPCActorCoreState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        agenda = self._agenda(npc_id)
        if agenda.active:
            raise ValueError(f"NPC {npc_id} cannot clear manual goals during an active activity")
        core = self._ensure_actor_core(npc_id)
        manual_goal_ids = [
            goal_id
            for goal_id, goal in core.long_term_goals.items()
            if goal.source is NPCGoalSource.MANUAL
        ]
        for goal_id in manual_goal_ids:
            core.remove_goal(goal_id)
        self._evaluate_npc_decision(npc_id, self.world.now_ms)
        return core

    def _shop_home_unavailable(self, npc_id: str, home_location_id: str) -> bool:
        belief = self.belief(npc_id, f"{LOCATION_UNAVAILABLE_FACT_PREFIX}{home_location_id}")
        if belief is None:
            return False
        if not isinstance(belief.value, bool):
            raise RuntimeError("location_unavailable belief value must be boolean")
        return belief.value

    def _evaluate_npc_decision(self, npc_id: str, decision_at_ms: int) -> None:
        agenda = self._agenda(npc_id)
        core = self._ensure_actor_core(npc_id)
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is not None and not materialized.alive:
            if not agenda.active:
                core.select_goal(None, decided_at_ms=decision_at_ms)
            return
        if agenda.active:
            return

        selected = self._select_goal(npc_id)
        selected_id = selected.goal_id if selected is not None else None
        previous_id = core.current_goal_id
        core.select_goal(selected_id, decided_at_ms=decision_at_ms)
        if selected is None:
            return
        needs_plan = previous_id != selected_id or (
            core.current_plan_step is None
            and selected.target_location_id is not None
            and self._stationary_npc_location_id(npc_id) != selected.target_location_id
        )
        if needs_plan:
            self._replace_goal_plan(npc_id, selected)
        self._plan_goal_step(npc_id, decision_at_ms)

    def _evaluate_npc_decisions(self, decision_at_ms: int) -> None:
        for npc_id in self.npcs.definitions:
            self._evaluate_npc_decision(npc_id, decision_at_ms)

    def advance_world(self, elapsed_ms: int) -> list[int]:
        self._evaluate_npc_decisions(self.world.now_ms)
        return super().advance_world(elapsed_ms)

    def travel_actor(self, actor_id: str, destination_id: str):
        self._evaluate_npc_decisions(self.world.now_ms)
        return super().travel_actor(actor_id, destination_id)

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

        core = self._ensure_actor_core(npc_id)
        goal_id = core.current_goal_id if agenda.plan_step_id is not None else None
        self.npc_activity_history.append(
            {
                "npc_id": npc_id,
                "goal_id": goal_id,
                "business_id": core.current_business_id if goal_id is not None else None,
                "plan_step_id": agenda.plan_step_id,
                "activity_kind": "travel",
                "from_location_id": agenda.from_location_id,
                "to_location_id": agenda.target_location_id,
                "started_at_ms": agenda.started_at_ms,
                "completed_at_ms": completed_at_ms,
                "traversal_tags": list(agenda.traversal_tags),
            }
        )
        if agenda.plan_step_id is not None:
            core.complete_plan_step(agenda.plan_step_id)
        agenda.finish_activity()
        return completed_at_ms

    def _resolve_due_npc_activities(self, before_ms: int, after_ms: int) -> None:
        for npc_id, agenda in list(self.npc_agendas.items()):
            while agenda.active and agenda.due_at_ms is not None and agenda.due_at_ms <= after_ms:
                completed_at_ms = self._finish_travel_leg(npc_id, agenda)
                self._evaluate_npc_decision(npc_id, completed_at_ms)
            if not agenda.active:
                self._evaluate_npc_decision(npc_id, after_ms)
        self._evaluate_npc_decisions(after_ms)

    def npc_actor_core_state(self, npc_id: str) -> dict[str, Any]:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        core = self._ensure_actor_core(npc_id)
        agenda = self._agenda(npc_id)
        location_id = self.npc_location_id(npc_id)
        goal = core.current_goal
        beliefs = {
            fact_id: (
                asdict(belief) if (belief := self.belief(npc_id, fact_id)) is not None else None
            )
            for fact_id in core.decision_basis_fact_ids
        }
        relationships = {
            actor_id: self.npcs.states[npc_id].relationship_by_actor.get(actor_id, 0)
            for actor_id in core.decision_relation_actor_ids
        }
        goals = {
            goal_id: {
                **asdict(candidate),
                "source": candidate.source.value,
                "eligible": self._goal_is_eligible(npc_id, candidate) if not agenda.active else None,
            }
            for goal_id, candidate in core.long_term_goals.items()
        }
        return {
            "npc_id": npc_id,
            "current_goal_id": core.current_goal_id,
            "current_business_id": core.current_business_id,
            "goal_target_location_id": goal.target_location_id if goal is not None else None,
            "long_term_goals": goals,
            "short_term_plan": [asdict(step) for step in core.short_term_plan],
            "plan_cursor": core.plan_cursor,
            "current_plan_step": asdict(core.current_plan_step) if core.current_plan_step is not None else None,
            "decision_basis_fact_ids": list(core.decision_basis_fact_ids),
            "decision_relation_actor_ids": list(core.decision_relation_actor_ids),
            "decision_beliefs": beliefs,
            "decision_relationships": relationships,
            "last_decision_at_ms": core.last_decision_at_ms,
            "revision": core.revision,
            "resources": self._npc_resource_snapshot(npc_id),
            "activity": asdict(agenda),
            "active": agenda.active,
            "location_id": location_id,
            "goal_reached": bool(
                goal is not None
                and goal.target_location_id is not None
                and not agenda.active
                and location_id == goal.target_location_id
            ),
        }

    def npc_agenda_state(self, npc_id: str) -> dict:
        state = self.npc_actor_core_state(npc_id)
        activity = state["activity"]
        return {
            **activity,
            "goal_id": state["current_goal_id"],
            "goal_target_location_id": state["goal_target_location_id"],
            "current_business_id": state["current_business_id"],
            "active": state["active"],
            "location_id": state["location_id"],
            "goal_reached": state["goal_reached"],
        }

    def _assert_npc_actor_core_authority(self) -> None:
        unknown = sorted(set(self.npc_actor_cores) - set(self.npcs.definitions))
        if unknown:
            raise RuntimeError(f"NPC actor cores reference unknown NPCs: {unknown}")
        for npc_id in self.npcs.definitions:
            core = self._ensure_actor_core(npc_id)
            if core.current_goal_id is not None:
                goal = core.long_term_goals.get(core.current_goal_id)
                if goal is None:
                    raise RuntimeError(f"NPC {npc_id} current goal is missing from actor core")
                if core.current_business_id != goal.business_id:
                    raise RuntimeError(f"NPC {npc_id} current business disagrees with current goal")
            elif core.current_business_id is not None:
                raise RuntimeError(f"NPC {npc_id} has current business without a current goal")
            if core.plan_cursor < 0 or core.plan_cursor > len(core.short_term_plan):
                raise RuntimeError(f"NPC {npc_id} actor-core plan cursor is invalid")
            for goal in core.long_term_goals.values():
                if goal.target_location_id is not None and goal.target_location_id not in self.world_map.locations:
                    raise RuntimeError(f"NPC {npc_id} goal references unknown location {goal.target_location_id}")
                for resource_id in goal.resource_requirements:
                    self._validate_resource_requirement_id(resource_id)

            agenda = self.npc_agendas.get(npc_id)
            if agenda is None or not agenda.active:
                continue
            if agenda.plan_step_id is not None:
                step = core.current_plan_step
                if step is None or step.step_id != agenda.plan_step_id:
                    raise RuntimeError(f"NPC {npc_id} active agenda is not executing the current actor-core plan step")
                if step.target_location_id != agenda.target_location_id:
                    raise RuntimeError(f"NPC {npc_id} agenda target disagrees with actor-core plan step")

    def dump_npc_autonomy_state(self) -> dict:
        self._assert_npc_actor_core_authority()
        return {
            "schema": NPC_AUTONOMY_SCHEMA,
            "actor_cores": {
                npc_id: asdict(core)
                for npc_id, core in self.npc_actor_cores.items()
            },
            "agendas": {
                npc_id: asdict(agenda)
                for npc_id, agenda in self.npc_agendas.items()
            },
            "history": list(self.npc_activity_history),
        }

    def load_npc_autonomy_state(self, payload: dict) -> None:
        if not payload:
            self.npc_actor_cores = {}
            self.npc_agendas = {}
            self.npc_activity_history = []
            for npc_id in self.npcs.definitions:
                self._ensure_actor_core(npc_id)
            return
        schema = payload.get("schema")
        if schema != NPC_AUTONOMY_SCHEMA:
            if payload.get("agendas"):
                raise ValueError(
                    "legacy NPC autonomy state mixes goals into agenda activities and cannot be migrated exactly"
                )
            self.npc_actor_cores = {}
            self.npc_agendas = {}
            self.npc_activity_history = list(payload.get("history", []))
            for npc_id in self.npcs.definitions:
                self._ensure_actor_core(npc_id)
            return

        cores: dict[str, NPCActorCoreState] = {}
        for npc_id, row in payload.get("actor_cores", {}).items():
            if npc_id not in self.npcs.definitions:
                raise ValueError(f"NPC actor-core save references unknown NPC: {npc_id}")
            goals = {
                goal_id: NPCGoalState(
                    goal_id=goal_row["goal_id"],
                    priority=int(goal_row["priority"]),
                    target_location_id=goal_row.get("target_location_id"),
                    business_id=goal_row["business_id"],
                    source=NPCGoalSource(goal_row["source"]),
                    required_fact_id=goal_row.get("required_fact_id"),
                    required_fact_value=goal_row.get("required_fact_value"),
                    relationship_actor_id=goal_row.get("relationship_actor_id"),
                    min_relationship=(
                        int(goal_row["min_relationship"])
                        if goal_row.get("min_relationship") is not None
                        else None
                    ),
                    resource_requirements={
                        str(resource_id): int(amount)
                        for resource_id, amount in goal_row.get("resource_requirements", {}).items()
                    },
                    enabled=bool(goal_row.get("enabled", True)),
                )
                for goal_id, goal_row in row.get("long_term_goals", {}).items()
            }
            if any(goal.goal_id != goal_id for goal_id, goal in goals.items()):
                raise ValueError(f"NPC actor-core goal key disagrees with goal_id: {npc_id}")
            core = NPCActorCoreState(
                npc_id=npc_id,
                long_term_goals=goals,
                current_goal_id=row.get("current_goal_id"),
                current_business_id=row.get("current_business_id"),
                short_term_plan=[NPCPlanStep(**step) for step in row.get("short_term_plan", [])],
                plan_cursor=int(row.get("plan_cursor", 0)),
                decision_basis_fact_ids=tuple(row.get("decision_basis_fact_ids", ())),
                decision_relation_actor_ids=tuple(row.get("decision_relation_actor_ids", ())),
                last_decision_at_ms=row.get("last_decision_at_ms"),
                revision=int(row.get("revision", 0)),
            )
            cores[npc_id] = core
        self.npc_actor_cores = cores
        for npc_id in self.npcs.definitions:
            self._ensure_actor_core(npc_id)

        agendas: dict[str, NPCAgendaState] = {}
        for npc_id, row in payload.get("agendas", {}).items():
            if npc_id not in self.npcs.definitions:
                raise ValueError(f"NPC autonomy save references unknown NPC: {npc_id}")
            agenda = NPCAgendaState(
                npc_id=npc_id,
                activity_kind=row.get("activity_kind"),
                from_location_id=row.get("from_location_id"),
                target_location_id=row.get("target_location_id"),
                started_at_ms=row.get("started_at_ms"),
                due_at_ms=row.get("due_at_ms"),
                traversal_tags=tuple(row.get("traversal_tags", ())),
                plan_step_id=row.get("plan_step_id"),
            )
            if agenda.active and (agenda.due_at_ms is None or agenda.due_at_ms <= self.world.now_ms):
                raise ValueError(f"NPC autonomy save contains overdue active travel: {npc_id}")
            agendas[npc_id] = agenda
        self.npc_agendas = agendas
        self.npc_activity_history = list(payload.get("history", []))
        self._assert_npc_actor_core_authority()
