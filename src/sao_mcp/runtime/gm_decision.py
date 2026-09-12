from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any


MAX_DECISION_ACTIONS = 1
PLAYER_DECISION_OPS = frozenset({
    "travel",
    "teleport",
    "move_encounter",
    "engage_monster",
    "timeline_attack",
    "process_timeline",
    "switch",
    "use_item",
    "equip",
    "unequip",
    "interact_npc",
    "accept_quest",
    "claim_quest",
    "share_fact",
    "advance_encounter",
})


@dataclass(slots=True, frozen=True)
class GMDecisionPlan:
    decision_id: str
    observation_digest: str
    observer_actor_ids: tuple[str, ...]
    actions: tuple[dict[str, Any], ...]
    world_tick_ms: int
    grounding: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["observer_actor_ids"] = list(self.observer_actor_ids)
        row["actions"] = [deepcopy(action) for action in self.actions]
        row["grounding"] = list(self.grounding)
        return row


class GMDecisionRuntime:
    """Pure decision gate over an already player-viewpoint-gated observation packet.

    This object deliberately has no game runtime reference. It cannot inspect actors, maps, NPC
    goals, guild operations, events or canonical overlays. The host may propose a small ordinary
    player-action batch; this runtime accepts only references that are actually present in the
    supplied observation packet and returns an auditable plan bound to that packet digest.
    """

    def __init__(self, action_contract: dict[str, dict[str, list[str]]]) -> None:
        self._action_contract = {
            op: {
                "required": tuple(row.get("required", ())),
                "optional": tuple(row.get("optional", ())),
            }
            for op, row in action_contract.items()
            if op in PLAYER_DECISION_OPS
        }
        missing = PLAYER_DECISION_OPS.difference(self._action_contract)
        if missing:
            raise ValueError(f"decision runtime action contract is missing: {', '.join(sorted(missing))}")

    @staticmethod
    def _canonical_json(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("GM decision inputs must be JSON-serializable") from exc

    @classmethod
    def observation_digest(cls, observation: dict[str, Any]) -> str:
        return sha256(cls._canonical_json(observation).encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_observation(observation: dict[str, Any]) -> tuple[str, ...]:
        if not isinstance(observation, dict):
            raise ValueError("GM decision requires an observation packet object")
        observer_ids = observation.get("observer_actor_ids")
        viewpoints = observation.get("viewpoints")
        if not isinstance(observer_ids, list) or not observer_ids:
            raise ValueError("GM decision observation lacks explicit player viewpoints")
        if len(set(observer_ids)) != len(observer_ids) or any(
            not isinstance(actor_id, str) or not actor_id for actor_id in observer_ids
        ):
            raise ValueError("GM decision observation has invalid viewpoint IDs")
        if not isinstance(viewpoints, dict) or set(viewpoints) != set(observer_ids):
            raise ValueError("GM decision observation viewpoints disagree with observer IDs")
        for actor_id in observer_ids:
            view = viewpoints[actor_id]
            if not isinstance(view, dict) or not isinstance(view.get("capabilities"), dict):
                raise ValueError("GM decision observation lacks capability projection")
        return tuple(observer_ids)

    def contract(self) -> dict[str, Any]:
        return {
            "max_actions": MAX_DECISION_ACTIONS,
            "allowed_ops": sorted(self._action_contract),
            "actions": {
                op: {
                    "required": list(self._action_contract[op]["required"]),
                    "optional": list(self._action_contract[op]["optional"]),
                }
                for op in sorted(self._action_contract)
            },
            "requires_fresh_observation": True,
            "freshness_boundary": "one ordinary player action per observation; re-observe before the next action",
            "world_progression": "world_tick_ms only; direct advance_world is not a decision action",
        }

    def _validate_action_shape(self, action: dict[str, Any], index: int) -> None:
        if not isinstance(action, dict):
            raise ValueError(f"GM decision action {index} must be an object")
        op = action.get("op")
        if op not in self._action_contract:
            raise ValueError(f"GM decision action is not player-observable/allowed: {op!r}")
        required = set(self._action_contract[op]["required"])
        optional = set(self._action_contract[op]["optional"])
        keys = set(action) - {"op"}
        missing = required - keys
        unknown = keys - required - optional
        if missing:
            raise ValueError(f"GM decision action {index} ({op}) is missing: {', '.join(sorted(missing))}")
        if unknown:
            raise ValueError(f"GM decision action {index} ({op}) has unknown fields: {', '.join(sorted(unknown))}")

    @staticmethod
    def _view_for_actor(observation: dict[str, Any], actor_id: str) -> dict[str, Any]:
        view = observation["viewpoints"].get(actor_id)
        if view is None:
            raise ValueError("GM decision may only control an explicit player viewpoint actor")
        return view

    @staticmethod
    def _encounter_view(observation: dict[str, Any], encounter_id: str) -> tuple[str, dict[str, Any]]:
        for observer_id, view in observation["viewpoints"].items():
            encounter = view.get("encounters", {}).get(encounter_id)
            if encounter is not None:
                return observer_id, encounter
        raise ValueError("GM decision references an encounter outside all player viewpoints")

    @staticmethod
    def _stable_visible_recipients(view: dict[str, Any]) -> set[str]:
        recipients = {
            row["actor_id"]
            for row in view.get("visible_entities", [])
            if isinstance(row, dict) and isinstance(row.get("actor_id"), str)
        }
        recipients.update(
            row["npc_id"]
            for row in view.get("visible_entities", [])
            if isinstance(row, dict) and isinstance(row.get("npc_id"), str)
        )
        return recipients

    def _ground_action(self, observation: dict[str, Any], action: dict[str, Any], index: int) -> str:
        op = action["op"]
        if op == "travel":
            actor_id = action["actor_id"]
            view = self._view_for_actor(observation, actor_id)
            allowed = {row["destination_id"] for row in view["capabilities"].get("travel_options", [])}
            if action["destination_id"] not in allowed:
                raise ValueError("travel destination is not present in the player's current observable travel options")
            return f"viewpoints.{actor_id}.capabilities.travel_options"

        if op == "engage_monster":
            actor_id = action["actor_id"]
            view = self._view_for_actor(observation, actor_id)
            allowed = {
                row["monster_id"]
                for row in view["capabilities"].get("encounter_options", [])
                if isinstance(row, dict) and isinstance(row.get("monster_id"), str)
            }
            if action["monster_id"] not in allowed:
                raise ValueError("monster is not present in the player's current encounter options")
            return f"viewpoints.{actor_id}.capabilities.encounter_options"

        if op == "teleport":
            actor_id = action["actor_id"]
            view = self._view_for_actor(observation, actor_id)
            caps = view["capabilities"]
            allowed_destinations = {row["destination_id"] for row in caps.get("teleport_options", [])}
            if action["destination_id"] not in allowed_destinations:
                raise ValueError("teleport destination is not present in the player's current UI options")
            if action["crystal_instance_id"] not in set(caps.get("teleport_crystal_instance_ids", [])):
                raise ValueError("teleport crystal is not in the player's observable inventory")
            encounter_id = action.get("encounter_id")
            if encounter_id is not None:
                _, encounter = self._encounter_view(observation, encounter_id)
                if actor_id not in encounter.get("participants", {}):
                    raise ValueError("controlled player is not a participant in the referenced encounter")
            return f"viewpoints.{actor_id}.capabilities.teleport_options"

        if op in {"move_encounter", "timeline_attack", "use_item", "equip", "unequip", "interact_npc", "accept_quest", "claim_quest"}:
            actor_key = "attacker_id" if op == "timeline_attack" else "actor_id"
            actor_id = action[actor_key]
            view = self._view_for_actor(observation, actor_id)
            caps = view["capabilities"]
            if op in {"move_encounter", "timeline_attack"}:
                encounter_id = action["encounter_id"]
                _, encounter = self._encounter_view(observation, encounter_id)
                if actor_id not in encounter.get("participants", {}):
                    raise ValueError("controlled player is not an observable participant in this encounter")
                if op == "timeline_attack" and action["target_id"] not in encounter.get("participants", {}):
                    raise ValueError("attack target is not an observable encounter participant")
                return f"viewpoints.{actor_id}.encounters.{encounter_id}"
            if op in {"use_item", "equip"}:
                if action["instance_id"] not in set(caps.get("inventory_instance_ids", [])):
                    raise ValueError("item instance is not in the player's observable inventory")
                if op == "use_item" and action.get("encounter_id") is not None:
                    _, encounter = self._encounter_view(observation, action["encounter_id"])
                    if actor_id not in encounter.get("participants", {}):
                        raise ValueError("controlled player is not a participant in the referenced encounter")
                return f"viewpoints.{actor_id}.capabilities.inventory_instance_ids"
            if op == "unequip":
                if action["slot"] not in set(caps.get("equipped_slots", [])):
                    raise ValueError("equipment slot is not currently observable as equipped")
                return f"viewpoints.{actor_id}.capabilities.equipped_slots"
            if op == "interact_npc":
                if action["npc_id"] not in set(caps.get("interactable_npc_ids", [])):
                    raise ValueError("NPC is not currently observable/interactable")
                return f"viewpoints.{actor_id}.capabilities.interactable_npc_ids"
            quest_key = "available_quest_ids" if op == "accept_quest" else "claimable_quest_ids"
            if action["quest_id"] not in set(caps.get(quest_key, [])):
                raise ValueError(f"quest is not present in the player's current {quest_key}")
            return f"viewpoints.{actor_id}.capabilities.{quest_key}"

        if op == "switch":
            encounter_id = action["encounter_id"]
            _, encounter = self._encounter_view(observation, encounter_id)
            observer_ids = set(observation["observer_actor_ids"])
            if action["outgoing_id"] not in observer_ids or action["incoming_id"] not in observer_ids:
                raise ValueError("Switch may only control player actors explicitly supplied as viewpoints")
            participants = encounter.get("participants", {})
            if action["outgoing_id"] not in participants or action["incoming_id"] not in participants:
                raise ValueError("Switch players are not both participants in the referenced encounter")
            if action["target_id"] not in participants:
                raise ValueError("Switch target is not an observable encounter participant")
            return f"viewpoints.*.encounters.{encounter_id}"

        if op in {"process_timeline", "advance_encounter"}:
            encounter_id = action["encounter_id"]
            observer_id, _ = self._encounter_view(observation, encounter_id)
            return f"viewpoints.{observer_id}.encounters.{encounter_id}"

        if op == "share_fact":
            sender_id = action["sender_id"]
            view = self._view_for_actor(observation, sender_id)
            caps = view["capabilities"]
            if action["fact_id"] not in set(caps.get("knowledge_fact_ids", [])):
                raise ValueError("shared fact is not in the sender's current observable knowledge")
            if action["recipient_id"] not in self._stable_visible_recipients(view):
                raise ValueError("knowledge recipient is not a currently visible stable entity")
            return f"viewpoints.{sender_id}.knowledge.facts.{action['fact_id']}"

        raise RuntimeError(f"decision grounding missing for validated op {op} at {index}")

    def decide(
        self,
        observation: dict[str, Any],
        proposed_actions: list[dict[str, Any]],
        *,
        world_tick_ms: int = 0,
    ) -> GMDecisionPlan:
        observer_ids = self._validate_observation(observation)
        if not isinstance(world_tick_ms, int) or isinstance(world_tick_ms, bool) or world_tick_ms < 0:
            raise ValueError("world_tick_ms must be a non-negative integer")
        if not isinstance(proposed_actions, list):
            raise ValueError("proposed_actions must be a list")
        if len(proposed_actions) > MAX_DECISION_ACTIONS:
            raise ValueError(f"GM decision may contain at most {MAX_DECISION_ACTIONS} actions")
        if not proposed_actions and world_tick_ms == 0:
            raise ValueError("GM decision must execute an observable player action or advance world time")

        normalized = json.loads(self._canonical_json(proposed_actions))
        grounding: list[str] = []
        for index, action in enumerate(normalized):
            self._validate_action_shape(action, index)
            grounding.append(self._ground_action(observation, action, index))

        observation_digest = self.observation_digest(observation)
        decision_payload = {
            "observation_digest": observation_digest,
            "observer_actor_ids": list(observer_ids),
            "actions": normalized,
            "world_tick_ms": world_tick_ms,
            "grounding": grounding,
        }
        decision_id = "gmdec_" + sha256(
            self._canonical_json(decision_payload).encode("utf-8")
        ).hexdigest()[:20]
        return GMDecisionPlan(
            decision_id=decision_id,
            observation_digest=observation_digest,
            observer_actor_ids=observer_ids,
            actions=tuple(deepcopy(normalized)),
            world_tick_ms=world_tick_ms,
            grounding=tuple(grounding),
        )
