from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from sao_mcp.domain.models import DefenseMode


_ACTION_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "travel": (frozenset({"actor_id", "destination_id"}), frozenset()),
    "teleport": (
        frozenset({"actor_id", "crystal_instance_id", "destination_id"}),
        frozenset({"encounter_id"}),
    ),
    "move_encounter": (
        frozenset({"encounter_id", "actor_id", "x", "y"}),
        frozenset(),
    ),
    "timeline_attack": (
        frozenset({"encounter_id", "attacker_id", "target_id"}),
        frozenset({"sword_skill_id", "defense", "seed"}),
    ),
    "process_timeline": (frozenset({"encounter_id"}), frozenset()),
    "switch": (
        frozenset({"encounter_id", "outgoing_id", "incoming_id", "target_id"}),
        frozenset(),
    ),
    "use_item": (
        frozenset({"actor_id", "instance_id"}),
        frozenset({"encounter_id"}),
    ),
    "equip": (frozenset({"actor_id", "instance_id"}), frozenset()),
    "unequip": (frozenset({"actor_id", "slot"}), frozenset()),
    "interact_npc": (frozenset({"actor_id", "npc_id"}), frozenset()),
    "accept_quest": (frozenset({"actor_id", "quest_id"}), frozenset()),
    "claim_quest": (frozenset({"actor_id", "quest_id"}), frozenset()),
    "set_npc_goal": (
        frozenset({"npc_id", "goal_id", "target_location_id"}),
        frozenset(),
    ),
    "clear_npc_goal": (frozenset({"npc_id"}), frozenset()),
    "schedule_npc_travel": (
        frozenset({"npc_id", "destination_id"}),
        frozenset(),
    ),
    "assign_guild_goal": (
        frozenset({"guild_id", "leader_id", "goal_id", "target_location_id", "assigned_member_ids"}),
        frozenset({"basis_fact_id"}),
    ),
    "clear_guild_goal": (
        frozenset({"guild_id", "leader_id"}),
        frozenset(),
    ),
    "initialize_population": (
        frozenset({"cohorts"}),
        frozenset(),
    ),
    "split_population_cohort": (
        frozenset({"cohort_id", "new_cohort_id", "count"}),
        frozenset({"band", "provenance_kind", "source_ref"}),
    ),
    "schedule_population_travel": (
        frozenset({"cohort_id", "destination_id"}),
        frozenset(),
    ),
    "apply_population_losses": (
        frozenset({"cohort_id", "deaths", "cause"}),
        frozenset(),
    ),
    "materialize_population_member": (
        frozenset({"cohort_id", "actor_id"}),
        frozenset(),
    ),
    "observe_fact": (
        frozenset({"entity_id", "fact_id", "value"}),
        frozenset({"source_id"}),
    ),
    "infer_fact": (
        frozenset({"entity_id", "fact_id", "value"}),
        frozenset({"source_id"}),
    ),
    "share_fact": (
        frozenset({"sender_id", "recipient_id", "fact_id"}),
        frozenset(),
    ),
    "advance_world": (frozenset({"elapsed_ms"}), frozenset()),
    "advance_encounter": (
        frozenset({"encounter_id", "elapsed_ms"}),
        frozenset(),
    ),
}


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    return value


def _observable_actor(actor) -> dict:
    return {
        "actor_id": actor.actor_id,
        "name": actor.name,
        "kind": actor.kind.value,
        "level": actor.level,
        "hp": actor.hp,
        "max_hp": actor.max_hp,
        "alive": actor.alive,
        "location_id": actor.location_id,
        "cursor": actor.cursor.value,
        "col": actor.col,
        "equipment": dict(actor.equipment),
        "statuses": [status.status_type.value for status in actor.statuses],
        "committed_until_ms": actor.committed_until_ms,
        "recovery_until_ms": actor.recovery_until_ms,
    }


class GMTurnExecutor:
    """Ordered GM action dispatcher over the existing authoritative runtime.

    This component does not interpret natural language or resolve mechanics itself. The host model
    supplies an already-decided structured action plan. Each action calls the same runtime method
    used by the dedicated MCP tools; no alternative combat/travel/item/knowledge rules exist here.
    """

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    @staticmethod
    def supported_actions() -> dict[str, dict[str, list[str]]]:
        return {
            op: {
                "required": sorted(required),
                "optional": sorted(optional),
            }
            for op, (required, optional) in _ACTION_FIELDS.items()
        }

    @staticmethod
    def _validate_plan(actions: list[dict[str, Any]], world_tick_ms: int) -> None:
        if not isinstance(actions, list) or not actions:
            raise ValueError("GM turn requires a non-empty actions list")
        if not isinstance(world_tick_ms, int) or world_tick_ms < 0:
            raise ValueError("world_tick_ms must be a non-negative integer")
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                raise ValueError(f"GM turn action {index} must be an object")
            op = action.get("op")
            if not isinstance(op, str) or op not in _ACTION_FIELDS:
                raise ValueError(f"unsupported GM turn action at index {index}: {op!r}")
            required, optional = _ACTION_FIELDS[op]
            keys = set(action) - {"op"}
            missing = required - keys
            unknown = keys - required - optional
            if missing:
                raise ValueError(
                    f"GM turn action {index} ({op}) is missing fields: {', '.join(sorted(missing))}"
                )
            if unknown:
                raise ValueError(
                    f"GM turn action {index} ({op}) has unknown fields: {', '.join(sorted(unknown))}"
                )
            if op == "assign_guild_goal":
                member_ids = action["assigned_member_ids"]
                if not isinstance(member_ids, list) or not member_ids or any(
                    not isinstance(actor_id, str) for actor_id in member_ids
                ):
                    raise ValueError(
                        f"GM turn action {index} (assign_guild_goal) assigned_member_ids must be a non-empty string list"
                    )

    def _execute_action(self, action: dict[str, Any]) -> Any:
        op = action["op"]
        runtime = self.runtime
        if op == "travel":
            return runtime.travel_actor(action["actor_id"], action["destination_id"])
        if op == "teleport":
            return runtime.teleport_actor(
                action["actor_id"],
                action["crystal_instance_id"],
                action["destination_id"],
                encounter_id=action.get("encounter_id"),
            )
        if op == "move_encounter":
            return runtime.move_encounter_actor(
                action["encounter_id"],
                action["actor_id"],
                float(action["x"]),
                float(action["y"]),
            )
        if op == "timeline_attack":
            return runtime.attack_or_queue_authoritative(
                action["encounter_id"],
                action["attacker_id"],
                action["target_id"],
                sword_skill_id=action.get("sword_skill_id"),
                defense=DefenseMode(action.get("defense", "auto")),
                seed=action.get("seed"),
            )
        if op == "process_timeline":
            return runtime.process_next_timeline_event(action["encounter_id"])
        if op == "switch":
            return runtime.switch(
                action["encounter_id"],
                action["outgoing_id"],
                action["incoming_id"],
                action["target_id"],
            )
        if op == "use_item":
            return runtime.use_inventory_item(
                action["actor_id"],
                action["instance_id"],
                encounter_id=action.get("encounter_id"),
            )
        if op == "equip":
            return runtime.equip_item(action["actor_id"], action["instance_id"])
        if op == "unequip":
            return runtime.unequip_item(action["actor_id"], action["slot"])
        if op == "interact_npc":
            return runtime.interact_npc(action["actor_id"], action["npc_id"])
        if op == "accept_quest":
            return runtime.accept_quest(action["actor_id"], action["quest_id"])
        if op == "claim_quest":
            return runtime.claim_quest(action["actor_id"], action["quest_id"])
        if op == "set_npc_goal":
            return runtime.set_npc_goal(
                action["npc_id"],
                action["goal_id"],
                action["target_location_id"],
            )
        if op == "clear_npc_goal":
            return runtime.clear_npc_goal(action["npc_id"])
        if op == "schedule_npc_travel":
            return runtime.schedule_npc_travel(
                action["npc_id"],
                action["destination_id"],
            )
        if op == "assign_guild_goal":
            return runtime.assign_guild_goal(
                action["guild_id"],
                action["leader_id"],
                action["goal_id"],
                action["target_location_id"],
                action["assigned_member_ids"],
                basis_fact_id=action.get("basis_fact_id"),
            )
        if op == "clear_guild_goal":
            return runtime.clear_guild_goal(action["guild_id"], action["leader_id"])
        if op == "initialize_population":
            return runtime.initialize_player_population(action["cohorts"])
        if op == "split_population_cohort":
            return runtime.split_population_cohort(
                action["cohort_id"],
                action["new_cohort_id"],
                int(action["count"]),
                band=action.get("band"),
                provenance_kind=action.get("provenance_kind", "simulation"),
                source_ref=action.get("source_ref"),
            )
        if op == "schedule_population_travel":
            return runtime.schedule_population_travel(
                action["cohort_id"],
                action["destination_id"],
            )
        if op == "apply_population_losses":
            return runtime.apply_population_losses(
                action["cohort_id"],
                int(action["deaths"]),
                cause=action["cause"],
            )
        if op == "materialize_population_member":
            return runtime.materialize_population_member(action["cohort_id"], action["actor_id"])
        if op == "observe_fact":
            return runtime.record_observation(
                action["entity_id"],
                action["fact_id"],
                action["value"],
                source_id=action.get("source_id"),
            )
        if op == "infer_fact":
            return runtime.record_inference(
                action["entity_id"],
                action["fact_id"],
                action["value"],
                source_id=action.get("source_id"),
            )
        if op == "share_fact":
            return runtime.share_known_fact(
                action["sender_id"],
                action["recipient_id"],
                action["fact_id"],
            )
        if op == "advance_world":
            return {"activated_floor_gates": runtime.advance_world(int(action["elapsed_ms"]))}
        if op == "advance_encounter":
            encounter = runtime.advance_encounter(
                action["encounter_id"],
                int(action["elapsed_ms"]),
            )
            return {
                "encounter_id": encounter.encounter_id,
                "time_ms": encounter.time_ms,
            }
        raise RuntimeError(f"validated GM turn action has no executor: {op}")

    @staticmethod
    def _actor_ids(actions: list[dict[str, Any]]) -> set[str]:
        scalar_fields = {
            "actor_id",
            "attacker_id",
            "target_id",
            "outgoing_id",
            "incoming_id",
            "leader_id",
        }
        actor_ids = {
            value
            for action in actions
            for key, value in action.items()
            if key in scalar_fields and isinstance(value, str)
        }
        for action in actions:
            member_ids = action.get("assigned_member_ids")
            if isinstance(member_ids, list):
                actor_ids.update(actor_id for actor_id in member_ids if isinstance(actor_id, str))
        return actor_ids

    @staticmethod
    def _encounter_ids(actions: list[dict[str, Any]]) -> set[str]:
        return {
            value
            for action in actions
            for key, value in action.items()
            if key == "encounter_id" and isinstance(value, str)
        }

    @staticmethod
    def _knowledge_entity_ids(actions: list[dict[str, Any]]) -> set[str]:
        fields = {"entity_id", "sender_id", "recipient_id"}
        return {
            value
            for action in actions
            for key, value in action.items()
            if key in fields and isinstance(value, str)
        }

    @staticmethod
    def _guild_ids(actions: list[dict[str, Any]]) -> set[str]:
        return {
            action["guild_id"]
            for action in actions
            if isinstance(action.get("guild_id"), str)
        }

    @staticmethod
    def _has_population_actions(actions: list[dict[str, Any]]) -> bool:
        return any(
            action.get("op") in {
                "initialize_population",
                "split_population_cohort",
                "schedule_population_travel",
                "apply_population_losses",
                "materialize_population_member",
            }
            for action in actions
        )

    def execute(self, actions: list[dict[str, Any]], *, world_tick_ms: int = 0) -> dict:
        self._validate_plan(actions, world_tick_ms)
        runtime = self.runtime
        world_before = runtime.world.now_ms
        event_counts = {
            encounter_id: len(encounter.events)
            for encounter_id, encounter in runtime.encounters.items()
        }

        steps = []
        for index, action in enumerate(actions):
            result = self._execute_action(action)
            steps.append(
                {
                    "index": index,
                    "op": action["op"],
                    "result": _plain(result),
                }
            )

        activated = runtime.advance_world(world_tick_ms) if world_tick_ms else []
        actor_ids = self._actor_ids(actions)
        encounter_ids = self._encounter_ids(actions)
        knowledge_entity_ids = self._knowledge_entity_ids(actions)
        guild_ids = self._guild_ids(actions)
        new_events = {}
        for encounter_id, encounter in runtime.encounters.items():
            start = event_counts.get(encounter_id, 0)
            if len(encounter.events) > start:
                new_events[encounter_id] = _plain(encounter.events[start:])

        encounters = {}
        for encounter_id in sorted(encounter_ids):
            encounter = runtime.encounters[encounter_id]
            row = {
                "encounter_id": encounter_id,
                "time_ms": encounter.time_ms,
                "zone_id": encounter.zone_id,
                "participants": {
                    actor_id: {
                        "hp": actor.hp,
                        "max_hp": actor.max_hp,
                        "alive": actor.alive,
                    }
                    for actor_id, actor in encounter.participants.items()
                },
            }
            if hasattr(runtime, "timeline_state"):
                row["timeline"] = _plain(runtime.timeline_state(encounter_id))
            encounters[encounter_id] = row

        npc_ids = {
            action["npc_id"]
            for action in actions
            if isinstance(action.get("npc_id"), str)
        }
        return {
            "world_time_before_ms": world_before,
            "world_time_after_ms": runtime.world.now_ms,
            "final_world_tick_ms": world_tick_ms,
            "activated_floor_gates": list(activated),
            "steps": steps,
            "new_events": new_events,
            "actors": {
                actor_id: _observable_actor(runtime.actors[actor_id])
                for actor_id in sorted(actor_ids)
                if actor_id in runtime.actors
            },
            "npc_agendas": {
                npc_id: runtime.npc_agenda_state(npc_id)
                for npc_id in sorted(npc_ids)
            },
            "guild_agendas": {
                guild_id: runtime.guild_agenda_state(guild_id)
                for guild_id in sorted(guild_ids)
            },
            "population": runtime.population_state() if self._has_population_actions(actions) else None,
            "knowledge": {
                entity_id: runtime.knowledge_state(entity_id)
                for entity_id in sorted(knowledge_entity_ids)
            },
            "encounters": encounters,
        }
