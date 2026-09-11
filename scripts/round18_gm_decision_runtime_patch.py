from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/sao_mcp"
TESTS = ROOT / "tests"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing replacement anchor in {path}: {old[:100]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"replacement anchor not unique in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


write(SRC / "runtime/gm_decision.py", r'''from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any


MAX_DECISION_ACTIONS = 8
PLAYER_DECISION_OPS = frozenset({
    "travel",
    "teleport",
    "move_encounter",
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
                self._encounter_view(observation, encounter_id)
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
                    self._encounter_view(observation, action["encounter_id"])
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
            if action["target_id"] not in encounter.get("participants", {}):
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
''')

# Add capability projection to the observation gate.
obs = SRC / "runtime/gm_observation.py"
replace_once(
    obs,
    "from sao_mcp.domain.models import EntityKind\nfrom sao_mcp.rules.state_authority import authoritative_guild_id\n",
    "from sao_mcp.domain.models import EntityKind, QuestObjectiveKind\nfrom sao_mcp.rules.access import require_location_access\nfrom sao_mcp.rules.state_authority import authoritative_guild_id\nfrom sao_mcp.rules.travel import AUTONOMOUS_TRAVEL_RESTRICTION_KEY\n",
)
replace_once(
    obs,
    "    def _messages(self, observer_id: str) -> list[dict[str, Any]]:\n",
    r'''    def _travel_options(self, observer_id: str) -> list[dict[str, Any]]:
        actor = self.runtime.actors[observer_id]
        if not actor.alive or actor.location_id is None:
            return []
        if actor.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:
            return []
        if any(
            encounter.active and observer_id in encounter.participants
            for encounter in self.runtime.encounters.values()
        ):
            return []
        rows = []
        for edge in self.runtime.world_map.adjacency.get(actor.location_id, ()):
            destination = self.runtime.world_map.locations[edge.to_location_id]
            floor = self.runtime.world.floors[destination.floor_number]
            if edge.requires_floor_unlocked and not floor.unlocked:
                continue
            try:
                require_location_access(actor, destination.location_id)
            except ValueError:
                continue
            rows.append({
                "destination_id": destination.location_id,
                "name": destination.name,
                "travel_ms": edge.travel_ms,
                "traversal_tags": list(edge.traversal_tags),
            })
        return sorted(rows, key=lambda row: (row["travel_ms"], row["destination_id"]))

    def _teleport_options(self, observer_id: str) -> tuple[list[str], list[dict[str, Any]]]:
        actor = self.runtime.actors[observer_id]
        crystals = sorted(
            item.instance_id
            for item in actor.inventory.values()
            if item.template_id == "teleport_crystal" and item.quantity > 0
        )
        if not crystals or not actor.alive or actor.location_id is None:
            return crystals, []
        if actor.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:
            return crystals, []
        rows = []
        for destination in self.runtime.world_map.locations.values():
            if not destination.teleport_gate:
                continue
            floor = self.runtime.world.floors[destination.floor_number]
            if not floor.unlocked or not floor.main_town_gate_active:
                continue
            try:
                require_location_access(actor, destination.location_id)
            except ValueError:
                continue
            rows.append({
                "destination_id": destination.location_id,
                "name": destination.name,
                "floor_number": destination.floor_number,
            })
        return crystals, sorted(rows, key=lambda row: (row["floor_number"], row["destination_id"]))

    def _available_quest_ids(self, observer_id: str, local_npc_ids: set[str]) -> list[str]:
        active = self.runtime.quests.progress_by_actor.get(observer_id, {})
        completed = self.runtime.quests.completed_by_actor.get(observer_id, set())
        rows = []
        for quest_id, definition in self.runtime.quests.definitions.items():
            if definition.giver_id not in local_npc_ids:
                continue
            progress = active.get(quest_id)
            if progress is not None and not progress.claimed and not progress.terminated:
                continue
            if quest_id in completed and not definition.repeatable:
                continue
            if self.runtime.world.now_ms < self.runtime.quests.global_accept_block_until_ms.get(quest_id, 0):
                continue
            if any(required not in completed for required in definition.prerequisites):
                continue
            rows.append(quest_id)
        return sorted(rows)

    def _claimable_quest_ids(self, observer_id: str, local_npc_ids: set[str]) -> list[str]:
        actor = self.runtime.actors[observer_id]
        rows = []
        for quest_id, progress in self.runtime.quests.progress_by_actor.get(observer_id, {}).items():
            if progress.claimed or progress.terminated:
                continue
            definition = self.runtime.quests.definitions[quest_id]
            if definition.turn_in_id not in local_npc_ids:
                continue
            ready = True
            for objective in definition.objectives:
                if not objective.required_for_completion:
                    continue
                if objective.kind is QuestObjectiveKind.COLLECT:
                    current = sum(
                        item.quantity
                        for item in actor.inventory.values()
                        if item.template_id == objective.target_id
                    )
                else:
                    current = progress.counters.get(objective.objective_id, 0)
                if current < objective.required:
                    ready = False
                    break
            if ready:
                rows.append(quest_id)
        return sorted(rows)

    def _capabilities(self, observer_id: str, visible_entities: list[dict[str, Any]], encounters: dict[str, Any]) -> dict[str, Any]:
        actor = self.runtime.actors[observer_id]
        local_npc_ids = {
            row["npc_id"]
            for row in visible_entities
            if isinstance(row, dict) and isinstance(row.get("npc_id"), str)
        }
        crystals, teleport_options = self._teleport_options(observer_id)
        knowledge = self.runtime.knowledge_state(observer_id)
        return {
            "travel_options": self._travel_options(observer_id),
            "teleport_crystal_instance_ids": crystals,
            "teleport_options": teleport_options,
            "interactable_npc_ids": sorted(local_npc_ids),
            "inventory_instance_ids": sorted(actor.inventory),
            "equipped_slots": sorted(actor.equipment),
            "knowledge_fact_ids": sorted(knowledge.get("facts", {})),
            "available_quest_ids": self._available_quest_ids(observer_id, local_npc_ids),
            "claimable_quest_ids": self._claimable_quest_ids(observer_id, local_npc_ids),
            "encounter_ids": sorted(encounters),
        }

    def _messages(self, observer_id: str) -> list[dict[str, Any]]:
''',
)
replace_once(
    obs,
    r'''        viewpoints = {}
        for observer_id in observer_ids:
            viewpoints[observer_id] = {
                "observer": self._self_actor(observer_id),
                "location": self._location(observer_id),
                "visible_entities": self._visible_entities(observer_id),
                "knowledge": self.runtime.knowledge_state(observer_id),
                "quest_log": self._quest_log(observer_id),
                "guild": self._guild(observer_id),
                "relationships": self._relationships(observer_id),
                "messages": self._messages(observer_id),
                "encounters": self._encounters(
                    observer_id,
                    allowed_encounter_ids=allowed_encounters,
                    event_offsets=event_offsets,
                ),
            }
''',
    r'''        viewpoints = {}
        for observer_id in observer_ids:
            visible_entities = self._visible_entities(observer_id)
            encounters = self._encounters(
                observer_id,
                allowed_encounter_ids=allowed_encounters,
                event_offsets=event_offsets,
            )
            viewpoints[observer_id] = {
                "observer": self._self_actor(observer_id),
                "location": self._location(observer_id),
                "visible_entities": visible_entities,
                "knowledge": self.runtime.knowledge_state(observer_id),
                "quest_log": self._quest_log(observer_id),
                "guild": self._guild(observer_id),
                "relationships": self._relationships(observer_id),
                "messages": self._messages(observer_id),
                "encounters": encounters,
                "capabilities": self._capabilities(observer_id, visible_entities, encounters),
            }
''',
)

# Let a validated decision advance only world time, while preserving the old nonempty-plan rule otherwise.
gm_turn = SRC / "runtime/gm_turn.py"
replace_once(
    gm_turn,
    '        if not isinstance(actions, list) or not actions:\n            raise ValueError("GM turn requires a non-empty actions list")\n        if not isinstance(world_tick_ms, int) or world_tick_ms < 0:\n',
    '        if not isinstance(actions, list):\n            raise ValueError("GM turn actions must be a list")\n        if not isinstance(world_tick_ms, int) or world_tick_ms < 0:\n',
)
replace_once(
    gm_turn,
    '            raise ValueError("world_tick_ms must be a non-negative integer")\n        for index, action in enumerate(actions):\n',
    '            raise ValueError("world_tick_ms must be a non-negative integer")\n        if not actions and world_tick_ms == 0:\n            raise ValueError("GM turn requires an action or positive world_tick_ms")\n        for index, action in enumerate(actions):\n',
)

write(SRC / "server_gm.py", r'''from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def _default(value: Any):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_gm_tools(mcp, gm_turn_executor, gm_decision_runtime) -> None:
    @mcp.tool()
    def preview_gm_decision(
        proposed_actions: list[dict[str, Any]],
        observer_actor_ids: list[str],
        world_tick_ms: int = 0,
    ) -> str:
        """Validate a proposed ordinary GM plan strictly against a fresh player-viewpoint observation.

        This is a pure preview. It does not mutate the campaign and does not expose raw runtime state.
        """
        observation = gm_turn_executor.observe(observer_actor_ids)
        decision = gm_decision_runtime.decide(
            observation,
            proposed_actions,
            world_tick_ms=world_tick_ms,
        )
        return _json(decision.to_dict())

    @mcp.tool()
    def execute_gm_decision(
        proposed_actions: list[dict[str, Any]],
        observer_actor_ids: list[str],
        world_tick_ms: int = 0,
    ) -> str:
        """Ground a proposed ordinary player-action plan in a fresh observation, then execute it.

        The decision runtime receives only the gated observation packet. Hidden NPC goals, guild strategy,
        world-event state and other server-only authorities cannot be used as decision inputs.
        """
        observation = gm_turn_executor.observe(observer_actor_ids)
        decision = gm_decision_runtime.decide(
            observation,
            proposed_actions,
            world_tick_ms=world_tick_ms,
        )
        execution = gm_turn_executor.execute(
            list(decision.actions),
            observer_actor_ids=list(decision.observer_actor_ids),
            world_tick_ms=decision.world_tick_ms,
        )
        return _json({"decision": decision.to_dict(), "execution": execution})

    @mcp.tool()
    def get_gm_decision_contract() -> str:
        """Return the player-observable action surface accepted by the GM decision gate."""
        return _json(gm_decision_runtime.contract())

    @mcp.tool()
    def get_gm_observation(observer_actor_ids: list[str]) -> str:
        """Return current observable state and decision capabilities for explicit player viewpoints."""
        return _json(gm_turn_executor.observe(observer_actor_ids))
''')

bootstrap = SRC / "server_bootstrap.py"
replace_once(
    bootstrap,
    "from sao_mcp.runtime.gm_turn import GMTurnExecutor\n",
    "from sao_mcp.runtime.gm_decision import GMDecisionRuntime\nfrom sao_mcp.runtime.gm_turn import GMTurnExecutor\n",
)
replace_once(
    bootstrap,
    "gm_turn_executor = GMTurnExecutor(runtime)\n",
    "gm_turn_executor = GMTurnExecutor(runtime)\ngm_decision_runtime = GMDecisionRuntime(GMTurnExecutor.supported_actions())\n",
)
replace_once(
    bootstrap,
    "register_gm_tools(mcp, gm_turn_executor)\n",
    "register_gm_tools(mcp, gm_turn_executor, gm_decision_runtime)\n",
)
replace_once(
    bootstrap,
    '    "gm_turn_executor",\n',
    '    "gm_turn_executor",\n    "gm_decision_runtime",\n',
)

skill = ROOT / "skills/sao-gm/SKILL.md"
text = skill.read_text(encoding="utf-8")
start = text.index("## Structured GM turn executor")
end = text.index("\n## Combat", start)
replacement = r'''## GM observation and decision gate

For ordinary in-world play, start from `get_gm_observation` for the explicit player viewpoint. The observation packet is the narration/decision boundary: it contains that player's current UI state, beliefs, visible entities, encounters, messages and currently usable capability references, but not NPC actor-core plans, guild strategy internals, world-event occurrences, canonical expectation overlays or another entity's private knowledge.

Translate the user's prose into the smallest proposed ordinary action batch, then use `execute_gm_decision`. The GM Decision Runtime receives only the fresh observation packet and rejects action references that are not grounded in that packet. Use `preview_gm_decision` when you need to validate the plan without mutation and `get_gm_decision_contract` for the exact allowed action shapes.

Do not call the internal `GMTurnExecutor` as a narration shortcut. It remains a mechanical dispatcher under the decision gate. NPC/guild administrative goal controls, direct knowledge injection and raw world advancement are deliberately absent from the player-observable decision surface; NPCs, guilds, events, population, economy and ecology continue through their own autonomous runtimes.

A decision batch is bound to the observation digest that justified it. Keep batches small. Once an action changes location, identity, inventory, encounter membership or other visibility, re-observe before deciding the next action. World-only waiting is represented by a positive `world_tick_ms` with no proposed player action.
'''
skill.write_text(text[:start] + replacement + text[end:], encoding="utf-8")

write(TESTS / "test_gm_decision_runtime.py", r'''import pytest

from sao_mcp.runtime.gm_decision import GMDecisionRuntime
from sao_mcp.runtime.gm_observation import GMObservationGate
from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


TOWN = "floor_1_town_of_beginnings"
WEST = "floor_1_west_field"
HORUNKA = "floor_1_horunka"


def make_runtime(seed=1801):
    runtime = SocialCommunicationAincradRuntime(seed=seed)
    executor = GMTurnExecutor(runtime)
    decision = GMDecisionRuntime(executor.supported_actions())
    return runtime, executor, decision


def test_decision_runtime_grounds_direct_travel_in_observation_capability():
    runtime, executor, decision = make_runtime()
    player = runtime.create_character("Walker")
    observation = executor.observe([player.actor_id])
    travel = observation["viewpoints"][player.actor_id]["capabilities"]["travel_options"]
    assert any(row["destination_id"] == WEST for row in travel)
    plan = decision.decide(
        observation,
        [{"op": "travel", "actor_id": player.actor_id, "destination_id": WEST}],
    )
    assert plan.actions[0]["destination_id"] == WEST
    assert plan.observation_digest == decision.observation_digest(observation)


def test_decision_runtime_rejects_hidden_or_nonadjacent_destination_even_if_model_knows_id():
    runtime, executor, decision = make_runtime(1802)
    player = runtime.create_character("Walker")
    observation = executor.observe([player.actor_id])
    with pytest.raises(ValueError, match="observable travel options"):
        decision.decide(
            observation,
            [{"op": "travel", "actor_id": player.actor_id, "destination_id": HORUNKA}],
        )


def test_decision_runtime_rejects_gm_admin_operations_from_player_decision_surface():
    runtime, executor, decision = make_runtime(1803)
    player = runtime.create_character("Observer")
    observation = executor.observe([player.actor_id])
    with pytest.raises(ValueError, match="not player-observable/allowed"):
        decision.decide(
            observation,
            [{"op": "set_npc_goal", "npc_id": "npc_tutorial_instructor", "goal_id": "x", "target_location_id": WEST}],
        )


def test_decision_runtime_cannot_control_remote_player_or_use_remote_private_knowledge():
    runtime, executor, decision = make_runtime(1804)
    observer = runtime.create_character("Observer")
    remote = runtime.create_character("Remote")
    remote.location_id = HORUNKA
    runtime.record_observation(remote.actor_id, "private:route", WEST, observation_location_id=HORUNKA)
    observation = executor.observe([observer.actor_id])
    with pytest.raises(ValueError, match="explicit player viewpoint"):
        decision.decide(
            observation,
            [{"op": "travel", "actor_id": remote.actor_id, "destination_id": WEST}],
        )
    assert "private:route" not in repr(observation)


def test_world_only_wait_is_a_valid_decision_but_zero_work_is_not():
    runtime, executor, decision = make_runtime(1805)
    player = runtime.create_character("Waiter")
    observation = executor.observe([player.actor_id])
    with pytest.raises(ValueError, match="action or advance world time"):
        decision.decide(observation, [], world_tick_ms=0)
    plan = decision.decide(observation, [], world_tick_ms=60_000)
    started = runtime.world.now_ms
    result = executor.execute([], observer_actor_ids=[player.actor_id], world_tick_ms=plan.world_tick_ms)
    assert runtime.world.now_ms == started + 60_000
    assert result["executed_action_count"] == 0


def test_action_batch_is_grounded_in_initial_packet_and_cannot_assume_second_leg_visibility():
    runtime, executor, decision = make_runtime(1806)
    player = runtime.create_character("Walker")
    observation = executor.observe([player.actor_id])
    with pytest.raises(ValueError, match="observable travel options"):
        decision.decide(
            observation,
            [
                {"op": "travel", "actor_id": player.actor_id, "destination_id": WEST},
                {"op": "travel", "actor_id": player.actor_id, "destination_id": HORUNKA},
            ],
        )


def test_visible_npc_interaction_and_known_fact_share_are_grounded():
    runtime, executor, decision = make_runtime(1807)
    player = runtime.create_character("Talker")
    runtime.record_observation(player.actor_id, "fact:test", True, observation_location_id=TOWN)
    observation = executor.observe([player.actor_id])
    caps = observation["viewpoints"][player.actor_id]["capabilities"]
    assert "npc_tutorial_instructor" in caps["interactable_npc_ids"]
    plan = decision.decide(
        observation,
        [{"op": "share_fact", "sender_id": player.actor_id, "recipient_id": "npc_tutorial_instructor", "fact_id": "fact:test"}],
    )
    assert plan.actions[0]["op"] == "share_fact"


def test_decision_id_changes_when_observation_changes():
    runtime, executor, decision = make_runtime(1808)
    player = runtime.create_character("Clock")
    first = executor.observe([player.actor_id])
    plan1 = decision.decide(first, [], world_tick_ms=1)
    runtime.advance_world(1)
    second = executor.observe([player.actor_id])
    plan2 = decision.decide(second, [], world_tick_ms=1)
    assert plan1.observation_digest != plan2.observation_digest
    assert plan1.decision_id != plan2.decision_id
''')

write(TESTS / "test_gm_decision_authority.py", r'''import ast
from pathlib import Path

from sao_mcp.runtime.gm_decision import GMDecisionRuntime, PLAYER_DECISION_OPS
from sao_mcp.runtime.gm_turn import GMTurnExecutor


ROOT = Path(__file__).resolve().parents[1]


def test_decision_runtime_is_pure_and_has_no_raw_runtime_access():
    path = ROOT / "src/sao_mcp/runtime/gm_decision.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    forbidden_attrs = {
        "actors", "world", "world_map", "npcs", "relationships", "encounters",
        "world_events", "npc_actor_cores", "guild_operations", "knowledge_events",
    }
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in forbidden_attrs:
            violations.append((node.lineno, node.attr))
    assert violations == []
    assert "self.runtime" not in source
    assert "GMObservationGate" not in source
    assert "GMTurnExecutor" not in source


def test_decision_surface_excludes_hidden_world_authoring_operations():
    forbidden = {
        "set_npc_goal", "clear_npc_goal", "interrupt_npc_activity", "schedule_npc_travel",
        "assign_guild_goal", "clear_guild_goal", "withdraw_guild_operation", "hold_guild_operation",
        "reorganize_guild_operation", "observe_fact", "infer_fact", "advance_world",
    }
    assert PLAYER_DECISION_OPS.isdisjoint(forbidden)
    runtime = GMDecisionRuntime(GMTurnExecutor.supported_actions())
    assert forbidden.isdisjoint(runtime.contract()["allowed_ops"])


def test_server_gm_has_no_direct_turn_executor_surface_after_decision_gate():
    source = (ROOT / "src/sao_mcp/server_gm.py").read_text(encoding="utf-8")
    assert "def execute_gm_decision" in source
    assert "def preview_gm_decision" in source
    assert "def get_gm_decision_contract" in source
    assert "def execute_gm_turn" not in source
    assert "def get_gm_turn_action_contract" not in source


def test_bootstrap_wires_pure_decision_runtime_above_executor_without_changing_game_runtime_inheritance():
    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")
    assert "GMDecisionRuntime(GMTurnExecutor.supported_actions())" in source
    assert "register_gm_tools(mcp, gm_turn_executor, gm_decision_runtime)" in source
    assert '"gm_decision_runtime"' in source


def test_observation_packet_contains_capabilities_but_not_decision_or_hidden_authority_state():
    source = (ROOT / "src/sao_mcp/runtime/gm_observation.py").read_text(encoding="utf-8")
    assert '"capabilities"' in source
    assert "GMDecisionRuntime" not in source
    assert "gm_decision" not in source
''')

# Add a focused capability test to #17 gate tests.
path = TESTS / "test_gm_observation_gate.py"
with path.open("a", encoding="utf-8") as handle:
    handle.write(r'''


def test_observation_projects_current_decision_capabilities_without_hidden_second_leg():
    runtime = SocialCommunicationAincradRuntime(seed=1708)
    observer = runtime.create_character("Observer")
    packet = GMObservationGate(runtime).observe([observer.actor_id])
    caps = packet["viewpoints"][observer.actor_id]["capabilities"]
    destinations = {row["destination_id"] for row in caps["travel_options"]}
    assert WEST in destinations
    assert HORUNKA not in destinations
    assert "npc_tutorial_instructor" in caps["interactable_npc_ids"]
    assert set(caps["inventory_instance_ids"]) == set(observer.inventory)
''')

# Update #17 server authority expectation from executor surface to decision surface.
path = TESTS / "test_gm_observation_authority.py"
text = path.read_text(encoding="utf-8")
text = text.replace(
    '    assert "def get_gm_observation" in source\n    assert "observer_actor_ids" in source\n',
    '    assert "def get_gm_observation" in source\n    assert "def execute_gm_decision" in source\n    assert "def preview_gm_decision" in source\n    assert "observer_actor_ids" in source\n',
)
path.write_text(text, encoding="utf-8")
