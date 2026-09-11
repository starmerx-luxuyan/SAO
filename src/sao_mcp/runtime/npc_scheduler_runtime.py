from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.rules.npc_actor_core import NPCPlanStep
from sao_mcp.rules.npc_scheduler import (
    NPCPlanActionKind,
    NPCScheduledActionSpec,
    NPCSchedulerGoalState,
)
from sao_mcp.runtime.npc_autonomy_runtime import NPCAutonomyAincradRuntime


NPC_SCHEDULER_SCHEMA = "npc-scheduler.v1"


class NPCSchedulerAincradRuntime(NPCAutonomyAincradRuntime):
    """Actor-core runtime whose plans execute on authoritative world-time boundaries."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.npc_scheduler_goals: dict[str, dict[str, NPCSchedulerGoalState]] = {}
        self._scheduler_advancing = False

    def _scheduler_goal(self, npc_id: str, goal_id: str) -> NPCSchedulerGoalState | None:
        return self.npc_scheduler_goals.get(npc_id, {}).get(goal_id)

    @staticmethod
    def _action_spec_from_payload(row: dict[str, Any]) -> NPCScheduledActionSpec:
        if not isinstance(row, dict):
            raise ValueError("NPC scheduled action must be an object")
        allowed = {"action_kind", "duration_ms", "payload", "interruptible"}
        unknown = set(row) - allowed
        if unknown:
            raise ValueError(f"NPC scheduled action has unknown fields: {sorted(unknown)}")
        if "action_kind" not in row:
            raise ValueError("NPC scheduled action requires action_kind")
        return NPCScheduledActionSpec(
            action_kind=NPCPlanActionKind(row["action_kind"]),
            duration_ms=int(row.get("duration_ms", 0)),
            payload=dict(row.get("payload", {})),
            interruptible=bool(row.get("interruptible", True)),
        )

    def _validate_action_payload(self, spec: NPCScheduledActionSpec) -> None:
        payload = spec.payload
        kind = spec.action_kind
        if kind is NPCPlanActionKind.WAIT:
            if payload:
                raise ValueError("NPC wait action does not accept payload fields")
            return
        if kind is NPCPlanActionKind.INVESTIGATE:
            if not isinstance(payload.get("fact_id"), str) or not payload["fact_id"]:
                raise ValueError("NPC investigate action requires fact_id")
            if "value" not in payload:
                raise ValueError("NPC investigate action requires value")
            allowed = {"fact_id", "value", "source_id", "confidence", "expires_after_ms"}
        elif kind is NPCPlanActionKind.CONTACT:
            if not isinstance(payload.get("recipient_id"), str) or not payload["recipient_id"]:
                raise ValueError("NPC contact action requires recipient_id")
            fact_ids = payload.get("fact_ids")
            if not isinstance(fact_ids, list) or not fact_ids or any(
                not isinstance(fact_id, str) or not fact_id for fact_id in fact_ids
            ):
                raise ValueError("NPC contact action requires a non-empty fact_ids string list")
            if len(set(fact_ids)) != len(fact_ids):
                raise ValueError("NPC contact fact_ids must be unique")
            allowed = {"recipient_id", "fact_ids"}
        elif kind is NPCPlanActionKind.TRADE_VENDOR:
            operation = payload.get("operation")
            if operation not in {"buy", "sell"}:
                raise ValueError("NPC vendor trade operation must be buy or sell")
            if not isinstance(payload.get("vendor_id"), str) or not payload["vendor_id"]:
                raise ValueError("NPC vendor trade requires vendor_id")
            if operation == "buy":
                if not isinstance(payload.get("template_id"), str) or not payload["template_id"]:
                    raise ValueError("NPC vendor buy requires template_id")
                quantity = payload.get("quantity")
                if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
                    raise ValueError("NPC vendor buy quantity must be a positive integer")
                allowed = {"operation", "vendor_id", "template_id", "quantity"}
            else:
                if not isinstance(payload.get("instance_id"), str) or not payload["instance_id"]:
                    raise ValueError("NPC vendor sell requires instance_id")
                quantity = payload.get("quantity")
                if quantity is not None and (
                    not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0
                ):
                    raise ValueError("NPC vendor sell quantity must be null or a positive integer")
                allowed = {"operation", "vendor_id", "instance_id", "quantity"}
        elif kind is NPCPlanActionKind.ENGAGE:
            if not isinstance(payload.get("target_actor_id"), str) or not payload["target_actor_id"]:
                raise ValueError("NPC engage action requires target_actor_id")
            allowed = {"target_actor_id"}
        elif kind is NPCPlanActionKind.ATTACK:
            if not isinstance(payload.get("target_actor_id"), str) or not payload["target_actor_id"]:
                raise ValueError("NPC attack action requires target_actor_id")
            allowed = {"target_actor_id", "sword_skill_id", "defense", "seed"}
        else:
            raise ValueError(f"unsupported NPC scheduler action: {kind.value}")
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"NPC {kind.value} action has unknown payload fields: {sorted(unknown)}")

    def _store_scheduler_goal(
        self,
        npc_id: str,
        goal_id: str,
        scheduled_actions: list[dict[str, Any]],
    ) -> NPCSchedulerGoalState:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        specs = tuple(self._action_spec_from_payload(row) for row in scheduled_actions)
        for spec in specs:
            self._validate_action_payload(spec)
        state = NPCSchedulerGoalState(npc_id=npc_id, goal_id=goal_id, actions=specs)
        self.npc_scheduler_goals.setdefault(npc_id, {})[goal_id] = state
        return state

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
        scheduled_actions: list[dict[str, Any]] | None = None,
    ):
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        if target_location_id not in self.world_map.locations:
            raise KeyError(target_location_id)
        location = self.world_map.locations[target_location_id]
        if not self.world.floors[location.floor_number].unlocked:
            raise ValueError("NPC goal target floor is not unlocked")
        if relationship_actor_id is not None and relationship_actor_id not in self.actors:
            raise KeyError(relationship_actor_id)
        for resource_id, amount in dict(resource_requirements or {}).items():
            self._validate_resource_requirement_id(resource_id)
            if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                raise ValueError("NPC actor-core resource requirement amounts must be positive integers")
        if scheduled_actions is not None:
            self._store_scheduler_goal(npc_id, goal_id, scheduled_actions)
        core = super().set_npc_goal(
            npc_id,
            goal_id,
            target_location_id,
            priority=priority,
            business_id=business_id,
            required_fact_id=required_fact_id,
            required_fact_value=required_fact_value,
            relationship_actor_id=relationship_actor_id,
            min_relationship=min_relationship,
            resource_requirements=resource_requirements,
        )
        self._maybe_preempt_current_activity(npc_id, reason="goal_set_or_updated")
        return core

    def clear_npc_goal(self, npc_id: str):
        core = self._ensure_actor_core(npc_id)
        manual_goal_ids = [
            goal_id for goal_id, goal in core.long_term_goals.items() if goal.source.value == "manual"
        ]
        result = super().clear_npc_goal(npc_id)
        table = self.npc_scheduler_goals.get(npc_id, {})
        for goal_id in manual_goal_ids:
            table.pop(goal_id, None)
        if not table:
            self.npc_scheduler_goals.pop(npc_id, None)
        return result

    def resume_npc_scheduler_goal(self, npc_id: str, goal_id: str) -> dict[str, Any]:
        state = self._scheduler_goal(npc_id, goal_id)
        if state is None:
            raise KeyError(f"NPC scheduler goal is not registered: {npc_id}/{goal_id}")
        state.resume()
        if not self._agenda(npc_id).active:
            self._evaluate_npc_decision(npc_id, self.world.now_ms)
        return self.npc_scheduler_state(npc_id)

    def _goal_is_eligible(self, npc_id: str, goal) -> bool:
        state = self._scheduler_goal(npc_id, goal.goal_id)
        if state is not None and state.suspended:
            return False
        return super()._goal_is_eligible(npc_id, goal)

    def _replace_goal_plan(self, npc_id: str, goal) -> None:
        core = self._ensure_actor_core(npc_id)
        target = goal.target_location_id
        origin = self._stationary_npc_location_id(npc_id)
        path = self._shortest_path(npc_id, origin, target) if target is not None else ()
        revision = core.revision
        steps: list[NPCPlanStep] = [
            NPCPlanStep(
                step_id=f"{goal.goal_id}:rev{revision}:travel{index}",
                action_kind=NPCPlanActionKind.TRAVEL,
                target_location_id=location_id,
            )
            for index, location_id in enumerate(path, start=1)
        ]
        scheduled = self._scheduler_goal(npc_id, goal.goal_id)
        if scheduled is not None and not scheduled.suspended:
            for index, action in enumerate(scheduled.actions, start=1):
                steps.append(
                    NPCPlanStep(
                        step_id=f"{goal.goal_id}:rev{revision}:action{index}",
                        action_kind=action.action_kind,
                        target_location_id=target,
                        duration_ms=action.duration_ms,
                        payload=dict(action.payload),
                        interruptible=action.interruptible,
                    )
                )
        core.replace_plan(steps)

    def _active_encounter_for_pair(self, actor_id: str, target_actor_id: str):
        matches = [
            encounter
            for encounter in self.encounters.values()
            if encounter.active
            and actor_id in encounter.participants
            and target_actor_id in encounter.participants
        ]
        if len(matches) > 1:
            raise RuntimeError("actor pair belongs to multiple active encounters")
        return matches[0] if matches else None

    def _validate_stationary_start(self, npc_id: str, step: NPCPlanStep) -> tuple[str, object | None]:
        location_id = self._stationary_npc_location_id(npc_id)
        if step.target_location_id is not None and location_id != step.target_location_id:
            raise ValueError("NPC scheduler action requires the NPC to be at its plan-step location")
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is not None and not materialized.alive:
            raise ValueError("defeated NPC cannot start a scheduled activity")
        if step.action_kind in {
            NPCPlanActionKind.TRADE_VENDOR,
            NPCPlanActionKind.ENGAGE,
            NPCPlanActionKind.ATTACK,
        } and materialized is None:
            raise ValueError(f"NPC {step.action_kind.value} requires a materialized actor")
        return location_id, materialized

    def _begin_scheduler_step(self, npc_id: str, step: NPCPlanStep, started_at_ms: int) -> None:
        agenda = self._agenda(npc_id)
        if agenda.active:
            raise ValueError(f"NPC {npc_id} already has an active agenda activity")
        location_id, materialized = self._validate_stationary_start(npc_id, step)
        payload = dict(step.payload)
        due_at_ms = started_at_ms + step.duration_ms

        if step.action_kind is NPCPlanActionKind.CONTACT:
            recipient_id = payload["recipient_id"]
            recipient_location = self._knowledge_entity_location_id(recipient_id)
            if recipient_location != location_id:
                raise ValueError("NPC contact target is not colocated at activity start")
        elif step.action_kind is NPCPlanActionKind.TRADE_VENDOR:
            economy = getattr(self, "economy", None)
            if economy is None:
                raise RuntimeError("NPC vendor trade requires the authoritative economy runtime")
            vendor = economy.vendor_catalog(payload["vendor_id"])
            if vendor.location_id != location_id:
                raise ValueError("NPC is not at the scheduled vendor")
        elif step.action_kind is NPCPlanActionKind.ENGAGE:
            target = self.actors[payload["target_actor_id"]]
            if target.location_id != location_id or not target.alive:
                raise ValueError("NPC engage target is not a living colocated actor")
            if self._active_encounter_for_pair(materialized.actor_id, target.actor_id) is not None:
                raise ValueError("NPC engage target is already in the same active encounter")
        elif step.action_kind is NPCPlanActionKind.ATTACK:
            target_actor_id = payload["target_actor_id"]
            encounter = self._active_encounter_for_pair(materialized.actor_id, target_actor_id)
            if encounter is None:
                raise ValueError("NPC attack requires an active encounter with the target")
            if self.timeline_state(encounter.encounter_id)["bossEvents"]:
                raise ValueError("NPC scheduler attack will not bypass pending Boss timeline events")
            queued = self.queue_player_attack(
                encounter.encounter_id,
                materialized.actor_id,
                target_actor_id,
                sword_skill_id=payload.get("sword_skill_id"),
                defense=payload.get("defense", "auto"),
                seed=payload.get("seed"),
            )
            due_at_ms = started_at_ms + (queued.impact_at_ms - encounter.time_ms)
            payload["scheduler_encounter_id"] = encounter.encounter_id
            payload["timeline_action_id"] = queued.action_id

        agenda.begin_stationary(
            activity_kind=step.action_kind,
            location_id=location_id,
            started_at_ms=started_at_ms,
            due_at_ms=due_at_ms,
            payload=payload,
            plan_step_id=step.step_id,
            interruptible=step.interruptible,
        )

    def _suspend_current_scheduler_goal(self, npc_id: str, reason: str) -> None:
        core = self._ensure_actor_core(npc_id)
        goal_id = core.current_goal_id
        if goal_id is not None:
            state = self._scheduler_goal(npc_id, goal_id)
            if state is not None:
                state.suspend(reason=reason, at_ms=self.world.now_ms)
        core.replace_plan([])
        core.select_goal(None, decided_at_ms=self.world.now_ms)
        core.set_decision_basis_events(())

    def _plan_goal_step(self, npc_id: str, started_at_ms: int) -> bool:
        agenda = self._agenda(npc_id)
        core = self._ensure_actor_core(npc_id)
        step = core.current_plan_step
        if agenda.active or core.current_goal is None:
            return False
        if step is None:
            return False
        if step.action_kind is NPCPlanActionKind.TRAVEL:
            return super()._plan_goal_step(npc_id, started_at_ms)
        try:
            self._begin_scheduler_step(npc_id, step, started_at_ms)
        except (ValueError, KeyError) as exc:
            self._suspend_current_scheduler_goal(npc_id, f"{step.action_kind.value}_start_failed:{exc}")
            return False
        return True

    def _record_stationary_history(
        self,
        npc_id: str,
        agenda,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        core = self._ensure_actor_core(npc_id)
        self.npc_activity_history.append(
            {
                "npc_id": npc_id,
                "goal_id": core.current_goal_id,
                "business_id": core.current_business_id,
                "plan_step_id": agenda.plan_step_id,
                "activity_kind": agenda.activity_kind,
                "location_id": agenda.stationary_location_id,
                "started_at_ms": agenda.started_at_ms,
                "completed_at_ms": self.world.now_ms,
                "scheduled_due_at_ms": agenda.due_at_ms,
                "status": status,
                "reason": reason,
                "result": dict(result or {}),
            }
        )

    def _resolve_stationary_effect(self, npc_id: str, agenda) -> dict[str, Any]:
        kind = NPCPlanActionKind(agenda.activity_kind)
        payload = agenda.payload
        location_id = self._stationary_npc_location_id(npc_id)
        if location_id != agenda.stationary_location_id:
            raise ValueError("NPC left the stationary activity location before completion")
        materialized = self._materialized_npc_actor(npc_id)

        if kind is NPCPlanActionKind.WAIT:
            return {"waited_ms": agenda.due_at_ms - agenda.started_at_ms}
        if kind is NPCPlanActionKind.INVESTIGATE:
            event = self.record_observation(
                npc_id,
                payload["fact_id"],
                payload["value"],
                observation_location_id=location_id,
                source_id=payload.get("source_id"),
                confidence=float(payload.get("confidence", 1.0)),
                expires_after_ms=payload.get("expires_after_ms"),
            )
            return {"knowledge_event_id": event.event_id, "fact_id": event.fact_id}
        if kind is NPCPlanActionKind.CONTACT:
            event_ids = [
                self.share_known_fact(npc_id, payload["recipient_id"], fact_id).event_id
                for fact_id in payload["fact_ids"]
            ]
            return {"recipient_id": payload["recipient_id"], "knowledge_event_ids": event_ids}
        if kind is NPCPlanActionKind.TRADE_VENDOR:
            if materialized is None:
                raise RuntimeError("materialized NPC disappeared during vendor trade")
            economy = getattr(self, "economy", None)
            if economy is None:
                raise RuntimeError("NPC vendor trade requires the authoritative economy runtime")
            if payload["operation"] == "buy":
                resolution = economy.buy_from_vendor(
                    materialized,
                    payload["vendor_id"],
                    payload["template_id"],
                    int(payload["quantity"]),
                    self.catalog,
                    actor_location_id=materialized.location_id,
                )
            else:
                resolution = economy.sell_to_vendor(
                    materialized,
                    payload["vendor_id"],
                    payload["instance_id"],
                    self.catalog,
                    quantity=payload.get("quantity"),
                    actor_location_id=materialized.location_id,
                )
            return asdict(resolution)
        if kind is NPCPlanActionKind.ENGAGE:
            if materialized is None:
                raise RuntimeError("materialized NPC disappeared before engagement")
            target = self.actors[payload["target_actor_id"]]
            if not target.alive or target.location_id != location_id:
                raise ValueError("NPC engage target left or was defeated before engagement")
            encounter = self.start_encounter([materialized.actor_id, target.actor_id], zone_id=location_id)
            return {"encounter_id": encounter.encounter_id, "target_actor_id": target.actor_id}
        if kind is NPCPlanActionKind.ATTACK:
            encounter_id = payload["scheduler_encounter_id"]
            expected_action_id = payload["timeline_action_id"]
            encounter = self.require_active_encounter(encounter_id)
            if materialized is None or materialized.actor_id not in encounter.participants:
                raise ValueError("NPC attacker left the scheduled encounter")
            result = self.process_next_timeline_event(encounter_id)
            if result.get("actionId") != expected_action_id:
                raise RuntimeError("NPC scheduler attack did not resolve its queued timeline action")
            return result
        raise RuntimeError(f"unsupported NPC scheduled activity kind: {kind.value}")

    def _finish_travel_leg(self, npc_id: str, agenda) -> int:
        if agenda.activity_kind == NPCPlanActionKind.TRAVEL.value:
            completed_at_ms = super()._finish_travel_leg(npc_id, agenda)
            if self.npc_activity_history:
                self.npc_activity_history[-1].setdefault("status", "completed")
            return completed_at_ms

        if agenda.due_at_ms is None or agenda.started_at_ms is None or agenda.plan_step_id is None:
            raise RuntimeError(f"active NPC scheduler activity {npc_id} lacks timing or plan-step authority")
        completed_at_ms = agenda.due_at_ms
        core = self._ensure_actor_core(npc_id)
        step_id = agenda.plan_step_id
        try:
            result = self._resolve_stationary_effect(npc_id, agenda)
        except (ValueError, KeyError) as exc:
            reason = f"{agenda.activity_kind}_completion_failed:{exc}"
            self._record_stationary_history(npc_id, agenda, status="failed", reason=reason)
            agenda.finish_activity()
            self._suspend_current_scheduler_goal(npc_id, reason)
            return completed_at_ms

        self._record_stationary_history(npc_id, agenda, status="completed", result=result)
        if core.current_plan_step is None or core.current_plan_step.step_id != step_id:
            raise RuntimeError("NPC scheduler completed an activity that is not the current actor-core plan step")
        core.complete_plan_step(step_id)
        agenda.finish_activity()
        return completed_at_ms

    def _cancel_queued_scheduler_attack(self, agenda, reason: str) -> None:
        if agenda.activity_kind != NPCPlanActionKind.ATTACK.value:
            return
        encounter_id = agenda.payload.get("scheduler_encounter_id")
        action_id = agenda.payload.get("timeline_action_id")
        if not isinstance(encounter_id, str) or not isinstance(action_id, str):
            raise RuntimeError("NPC scheduler attack agenda lacks queued timeline identity")
        for action in tuple(self._queue(encounter_id)):
            if action.action_id == action_id:
                action.interrupted_reason = reason
                self._remove_action(encounter_id, action)
                return
        raise RuntimeError("NPC scheduler attack queue entry is missing during interruption")

    def _interrupt_current_activity(
        self,
        npc_id: str,
        *,
        reason: str,
        suspend_goal: bool,
    ) -> None:
        agenda = self._agenda(npc_id)
        if not agenda.active:
            raise ValueError("NPC has no active activity to interrupt")
        if agenda.in_transit or not agenda.interruptible:
            raise ValueError("NPC activity is not interruptible at the current execution point")
        self._cancel_queued_scheduler_attack(agenda, reason)
        self._record_stationary_history(npc_id, agenda, status="interrupted", reason=reason)
        core = self._ensure_actor_core(npc_id)
        goal_id = core.current_goal_id
        agenda.finish_activity()
        core.replace_plan([])
        if suspend_goal and goal_id is not None:
            state = self._scheduler_goal(npc_id, goal_id)
            if state is not None:
                state.suspend(reason=reason, at_ms=self.world.now_ms)
        core.select_goal(None, decided_at_ms=self.world.now_ms)
        core.set_decision_basis_events(())

    def interrupt_npc_activity(
        self,
        npc_id: str,
        *,
        reason: str,
        suspend_goal: bool = True,
    ) -> dict[str, Any]:
        if not reason:
            raise ValueError("NPC activity interruption requires a reason")
        self._interrupt_current_activity(npc_id, reason=reason, suspend_goal=suspend_goal)
        self._evaluate_npc_decision(npc_id, self.world.now_ms)
        return self.npc_scheduler_state(npc_id)

    def _maybe_preempt_current_activity(self, npc_id: str, *, reason: str) -> bool:
        agenda = self._agenda(npc_id)
        if not agenda.active or agenda.in_transit or not agenda.interruptible:
            return False
        core = self._ensure_actor_core(npc_id)
        selected = self._select_goal(npc_id)
        selected_id = selected.goal_id if selected is not None else None
        if selected_id == core.current_goal_id:
            return False
        self._interrupt_current_activity(npc_id, reason=reason, suspend_goal=False)
        self._evaluate_npc_decision(npc_id, self.world.now_ms)
        return True

    def _on_knowledge_update(self, event) -> None:
        if event.knower_id not in self.npcs.definitions:
            return
        if not self._knowledge_event_affects_goal_selection(event.knower_id, event.fact_id):
            return
        if self._maybe_preempt_current_activity(
            event.knower_id,
            reason=f"decision_belief_updated:{event.fact_id}",
        ):
            return
        if not self._agenda(event.knower_id).active:
            self._evaluate_npc_decision(event.knower_id, self.world.now_ms)

    def _next_scheduler_boundary(self, target_ms: int) -> int:
        now = self.world.now_ms
        candidates = [
            agenda.due_at_ms
            for agenda in self.npc_agendas.values()
            if agenda.active and agenda.due_at_ms is not None and now < agenda.due_at_ms <= target_ms
        ]
        for npc_id, core in self.npc_actor_cores.items():
            for goal in core.long_term_goals.values():
                if goal.required_fact_id is None:
                    continue
                belief = self.belief(npc_id, goal.required_fact_id)
                if (
                    belief is not None
                    and belief.expires_at_ms is not None
                    and now < belief.expires_at_ms <= target_ms
                ):
                    candidates.append(belief.expires_at_ms)
        return min(candidates) if candidates else target_ms

    def advance_world(self, elapsed_ms: int) -> list[int]:
        if not isinstance(elapsed_ms, int) or isinstance(elapsed_ms, bool) or elapsed_ms < 0:
            raise ValueError("elapsed_ms must be a non-negative integer")
        if self._scheduler_advancing:
            return super().advance_world(elapsed_ms)
        target_ms = self.world.now_ms + elapsed_ms
        activated: list[int] = []
        self._scheduler_advancing = True
        try:
            self._evaluate_npc_decisions(self.world.now_ms)
            while self.world.now_ms < target_ms:
                boundary = self._next_scheduler_boundary(target_ms)
                delta = boundary - self.world.now_ms
                if delta <= 0:
                    raise RuntimeError("NPC scheduler produced a non-forward world-time boundary")
                activated.extend(super().advance_world(delta))
            if elapsed_ms == 0:
                self._evaluate_npc_decisions(self.world.now_ms)
            return activated
        finally:
            self._scheduler_advancing = False

    def npc_scheduler_state(self, npc_id: str) -> dict[str, Any]:
        if npc_id not in self.npcs.definitions:
            raise KeyError(npc_id)
        core_state = self.npc_actor_core_state(npc_id)
        operations = {
            goal_id: {
                "npc_id": state.npc_id,
                "goal_id": state.goal_id,
                "actions": [asdict(action) for action in state.actions],
                "suspended": state.suspended,
                "failure_reason": state.failure_reason,
                "failed_at_ms": state.failed_at_ms,
                "revision": state.revision,
            }
            for goal_id, state in sorted(self.npc_scheduler_goals.get(npc_id, {}).items())
        }
        return {
            "npc_id": npc_id,
            "world_now_ms": self.world.now_ms,
            "current_goal_id": core_state["current_goal_id"],
            "current_business_id": core_state["current_business_id"],
            "current_plan_step": core_state["current_plan_step"],
            "activity": core_state["activity"],
            "location_id": core_state["location_id"],
            "operations": operations,
        }

    def _assert_npc_scheduler_authority(self) -> None:
        for npc_id, table in self.npc_scheduler_goals.items():
            if npc_id not in self.npcs.definitions:
                raise RuntimeError(f"NPC scheduler references unknown NPC: {npc_id}")
            core = self._ensure_actor_core(npc_id)
            for goal_id, state in table.items():
                if state.npc_id != npc_id or state.goal_id != goal_id:
                    raise RuntimeError("NPC scheduler registry key disagrees with scheduler goal state")
                if goal_id not in core.long_term_goals:
                    raise RuntimeError(f"NPC scheduler references missing actor-core goal: {npc_id}/{goal_id}")
        for npc_id, agenda in self.npc_agendas.items():
            if not agenda.active or agenda.plan_step_id is None:
                continue
            core = self._ensure_actor_core(npc_id)
            step = core.current_plan_step
            if step is None or step.step_id != agenda.plan_step_id:
                raise RuntimeError(f"NPC scheduler activity disagrees with actor-core plan: {npc_id}")
            if step.action_kind.value != agenda.activity_kind:
                raise RuntimeError(f"NPC scheduler activity kind disagrees with actor-core plan: {npc_id}")
            if agenda.in_transit:
                if step.target_location_id != agenda.target_location_id:
                    raise RuntimeError(f"NPC travel target disagrees with scheduler plan: {npc_id}")
            elif agenda.stationary_location_id != self._stationary_npc_location_id(npc_id):
                raise RuntimeError(f"NPC stationary scheduler activity lost its settled location: {npc_id}")

    def dump_npc_scheduler_state(self) -> dict[str, Any]:
        self._assert_npc_scheduler_authority()
        return {
            "schema": NPC_SCHEDULER_SCHEMA,
            "goals": {
                npc_id: {
                    goal_id: {
                        "npc_id": state.npc_id,
                        "goal_id": state.goal_id,
                        "actions": [asdict(action) for action in state.actions],
                        "suspended": state.suspended,
                        "failure_reason": state.failure_reason,
                        "failed_at_ms": state.failed_at_ms,
                        "revision": state.revision,
                    }
                    for goal_id, state in table.items()
                }
                for npc_id, table in self.npc_scheduler_goals.items()
            },
        }

    def load_npc_scheduler_state(self, payload: dict[str, Any]) -> None:
        if not payload:
            self.npc_scheduler_goals = {}
            return
        if payload.get("schema") != NPC_SCHEDULER_SCHEMA:
            if payload.get("goals"):
                raise ValueError("unsupported non-empty NPC scheduler schema")
            self.npc_scheduler_goals = {}
            return
        restored: dict[str, dict[str, NPCSchedulerGoalState]] = {}
        for npc_id, table in payload.get("goals", {}).items():
            if npc_id not in self.npcs.definitions:
                raise ValueError(f"NPC scheduler save references unknown NPC: {npc_id}")
            for goal_id, row in table.items():
                if row.get("npc_id") != npc_id or row.get("goal_id") != goal_id:
                    raise ValueError("NPC scheduler save key disagrees with stored identity")
                if goal_id not in self._ensure_actor_core(npc_id).long_term_goals:
                    raise ValueError(f"NPC scheduler save references missing goal: {npc_id}/{goal_id}")
                actions = tuple(self._action_spec_from_payload(action) for action in row.get("actions", []))
                for action in actions:
                    self._validate_action_payload(action)
                state = NPCSchedulerGoalState(
                    npc_id=npc_id,
                    goal_id=goal_id,
                    actions=actions,
                    suspended=bool(row.get("suspended", False)),
                    failure_reason=row.get("failure_reason"),
                    failed_at_ms=(int(row["failed_at_ms"]) if row.get("failed_at_ms") is not None else None),
                    revision=int(row.get("revision", 0)),
                )
                if state.failed_at_ms is not None and state.failed_at_ms > self.world.now_ms:
                    raise ValueError("NPC scheduler failure time cannot be in the future")
                restored.setdefault(npc_id, {})[goal_id] = state
        self.npc_scheduler_goals = restored
        self._assert_npc_scheduler_authority()
