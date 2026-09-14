from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Callable


_ENGINE_OWNED_OPS = frozenset({"advance_encounter", "process_timeline"})

# Public action contract. The controlling player id is supplied once to turn_execute;
# actor_id/attacker_id/sender_id are injected by the runline rather than delegated to the model.
_PUBLIC_ACTION_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "accept_quest": (frozenset({"quest_id"}), frozenset()),
    "claim_quest": (frozenset({"quest_id"}), frozenset()),
    "engage_monster": (frozenset({"monster_id"}), frozenset()),
    "equip": (frozenset({"instance_id"}), frozenset()),
    "interact_npc": (frozenset({"npc_id"}), frozenset()),
    "move_encounter": (frozenset({"encounter_id", "x", "y"}), frozenset()),
    "share_fact": (frozenset({"fact_id", "recipient_id"}), frozenset()),
    "switch": (frozenset({"encounter_id", "incoming_id", "outgoing_id", "target_id"}), frozenset()),
    "teleport": (frozenset({"crystal_instance_id", "destination_id"}), frozenset({"encounter_id"})),
    "timeline_attack": (
        frozenset({"encounter_id", "target_id"}),
        frozenset({"defense", "sword_skill_id"}),
    ),
    "travel": (frozenset({"destination_id"}), frozenset()),
    "unequip": (frozenset({"slot"}), frozenset()),
    "use_item": (frozenset({"instance_id"}), frozenset({"encounter_id"})),
    # Economy/inventory/progression operations that used to bypass the GM gate.
    "buy_vendor": (frozenset({"vendor_id", "template_id"}), frozenset({"quantity"})),
    "sell_vendor": (frozenset({"vendor_id", "instance_id"}), frozenset({"quantity"})),
    "transfer_item": (frozenset({"destination_id", "instance_id"}), frozenset({"quantity"})),
    "repair_item": (frozenset({"instance_id"}), frozenset()),
    "reinforce_weapon": (
        frozenset({"instance_id", "track"}),
        frozenset({"additional_material_quantity"}),
    ),
    "craft_weapon": (frozenset({"recipe_id"}), frozenset()),
    "reclaim_weapon": (frozenset({"instance_id"}), frozenset()),
    "equip_skill": (frozenset({"skill_id"}), frozenset()),
    "remove_skill": (frozenset({"skill_id"}), frozenset()),
    "create_party": (frozenset(), frozenset()),
    "join_party": (frozenset({"party_id"}), frozenset()),
}

_ACTOR_ID_OPS = frozenset({
    "accept_quest",
    "claim_quest",
    "engage_monster",
    "equip",
    "interact_npc",
    "move_encounter",
    "teleport",
    "travel",
    "unequip",
    "use_item",
})


class PlayerRunline:
    """Single ordinary-play mutation boundary.

    Every public action, including each action in a compound request, follows the same
    server-owned pipeline:

        fresh observation -> player projection -> gate -> execute -> settle
        -> fresh observation -> System Menu projection

    The model never supplies world_tick_ms, never calls process_timeline/advance_encounter,
    and never decides whether a refresh is necessary.
    """

    schema = "sao.player-runline.v1"
    max_actions = 16

    def __init__(
        self,
        runtime: Any,
        gm_turn_executor: Any,
        gm_decision_runtime: Any,
        system_menu_view: Callable[[Any, str, str | None], dict[str, Any]],
    ) -> None:
        self.runtime = runtime
        self.executor = gm_turn_executor
        self.decision = gm_decision_runtime
        self.system_menu_view = system_menu_view

    @classmethod
    def contract(cls) -> dict[str, Any]:
        return {
            "schema": cls.schema,
            "max_actions": cls.max_actions,
            "pipeline": [
                "observe",
                "project_player_state",
                "gate",
                "execute",
                "settle_to_decision_boundary",
                "reobserve",
                "project_system_menu",
            ],
            "engine_owned_ops": sorted(_ENGINE_OWNED_OPS),
            "world_tick_input": False,
            "actions": {
                op: {"required": sorted(required), "optional": sorted(optional)}
                for op, (required, optional) in _PUBLIC_ACTION_FIELDS.items()
            },
        }

    def execute(self, actor_id: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
        if not actions:
            raise ValueError("turn_execute requires at least one action")
        if len(actions) > self.max_actions:
            raise ValueError(f"turn_execute accepts at most {self.max_actions} actions")

        steps: list[dict[str, Any]] = []
        final_observation: dict[str, Any] | None = None
        final_menu: dict[str, Any] | None = None

        for index, requested in enumerate(actions):
            action = self._normalize_action(actor_id, requested)

            # GATE phase 1: always acquire a fresh snapshot. No prior step may donate
            # its observation to the next decision.
            before = self.executor.observe([actor_id])
            before_menu = self.system_menu_view(self.runtime, actor_id, self._active_encounter_id(before, actor_id))

            grounded = self._ground(actor_id, action, before, before_menu)
            result = self._execute_one(actor_id, grounded)

            # Engine-owned stabilization. The caller cannot request or skip this phase.
            settle = self._settle(actor_id, grounded)

            # GATE phase 2: every mutation is followed by a fresh authoritative read and
            # the one public visual projection.
            final_observation = self.executor.observe([actor_id])
            encounter_id = self._active_encounter_id(final_observation, actor_id)
            final_menu = self.system_menu_view(self.runtime, actor_id, encounter_id)

            steps.append(
                {
                    "index": index,
                    "op": grounded["op"],
                    "grounded_action": grounded,
                    "result": self._plain(result),
                    "settle": settle,
                    "world_now_ms": final_observation.get("world_now_ms"),
                }
            )

        return {
            "schema": self.schema,
            "actor_id": actor_id,
            "steps": steps,
            "observation": final_observation,
            "system_menu": final_menu,
        }

    def _normalize_action(self, actor_id: str, requested: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(requested, dict):
            raise TypeError("each action must be an object")
        op = requested.get("op")
        if op not in _PUBLIC_ACTION_FIELDS:
            if op in _ENGINE_OWNED_OPS:
                raise ValueError(f"{op} is engine-owned and cannot be requested by the model")
            raise ValueError(f"unsupported public action: {op!r}")

        required, optional = _PUBLIC_ACTION_FIELDS[op]
        supplied = set(requested) - {"op"}
        missing = required - supplied
        extra = supplied - required - optional
        if missing:
            raise ValueError(f"{op} missing fields: {sorted(missing)}")
        if extra:
            raise ValueError(f"{op} has unsupported fields: {sorted(extra)}")

        action = dict(requested)
        if op in _ACTOR_ID_OPS:
            action["actor_id"] = actor_id
        elif op == "timeline_attack":
            action["attacker_id"] = actor_id
        elif op == "share_fact":
            action["sender_id"] = actor_id
        return action

    def _ground(
        self,
        actor_id: str,
        action: dict[str, Any],
        observation: dict[str, Any],
        menu: dict[str, Any],
    ) -> dict[str, Any]:
        op = action["op"]
        legacy = set(self.executor.supported_actions()) - _ENGINE_OWNED_OPS
        if op in legacy:
            plan = self.decision.decide(observation, [action])
            if len(plan.actions) != 1:
                raise RuntimeError("GM decision gate must return exactly one grounded action")
            return dict(plan.actions[0])

        self._ground_extension(actor_id, action, observation, menu)
        return action

    def _ground_extension(
        self,
        actor_id: str,
        action: dict[str, Any],
        observation: dict[str, Any],
        menu: dict[str, Any],
    ) -> None:
        op = action["op"]
        actor = self.runtime.actors[actor_id]

        inventory = {row["instanceId"]: row for row in menu["character"]["inventory"]}
        vendors = {row["vendor_id"]: row for row in menu.get("vendors", [])}
        forge = menu.get("forge", {})

        if op == "buy_vendor":
            vendor = vendors.get(action["vendor_id"])
            if vendor is None:
                raise ValueError("vendor is not visible at the player's current location")
            listing = next(
                (row for row in vendor.get("listings", []) if row["template_id"] == action["template_id"]),
                None,
            )
            quantity = int(action.get("quantity", 1))
            if listing is None or quantity < 1 or listing["stock"] < quantity:
                raise ValueError("requested vendor stock is not currently visible/available")
            return

        if op == "sell_vendor":
            if action["vendor_id"] not in vendors:
                raise ValueError("vendor is not visible at the player's current location")
            item = inventory.get(action["instance_id"])
            if item is None or item["equipped"]:
                raise ValueError("only a visible unequipped carried item can be sold")
            quantity = int(action.get("quantity", item["quantity"]))
            if quantity < 1 or quantity > item["quantity"]:
                raise ValueError("sale quantity exceeds the visible carried stack")
            return

        if op in {"repair_item", "reinforce_weapon", "craft_weapon", "reclaim_weapon"}:
            if not forge.get("available"):
                raise ValueError("a forge/workshop is not currently available")
            if not forge.get("blacksmithSkillEquipped"):
                raise ValueError("Blacksmithing must occupy a visible equipped skill slot")
            if op in {"repair_item", "reinforce_weapon", "reclaim_weapon"}:
                item = inventory.get(action["instance_id"])
                if item is None:
                    raise ValueError("item is not in the player's visible inventory")
                if item["equipped"] and op in {"repair_item", "reclaim_weapon"}:
                    raise ValueError("item must be unequipped for this forge operation")
            if op == "craft_weapon":
                recipe_ids = {row["recipe_id"] for row in forge.get("recipes", [])}
                if action["recipe_id"] not in recipe_ids:
                    raise ValueError("recipe is not currently visible at this forge")
            return

        if op == "equip_skill":
            skill_state = menu["skillManagement"]
            rows = {row["id"]: row for row in skill_state["skills"]}
            row = rows.get(action["skill_id"])
            if row is None:
                raise ValueError("skill is not present in the player's System Menu")
            if row["equipped"]:
                raise ValueError("skill is already equipped")
            if skill_state["slotsUsed"] >= skill_state["slotsTotal"]:
                raise ValueError("no free skill slot")
            special = set(actor.metadata.get("unlocked_special_skills", ()))
            if row["kind"] in {"extra", "unique"} and action["skill_id"] not in special:
                raise ValueError("Extra/Unique Skill has not been acquired by this character")
            return

        if op == "remove_skill":
            rows = {row["id"]: row for row in menu["skillManagement"]["skills"]}
            row = rows.get(action["skill_id"])
            if row is None or not row["equipped"]:
                raise ValueError("skill is not currently equipped")
            return

        if op == "transfer_item":
            item = inventory.get(action["instance_id"])
            if item is None or item["equipped"]:
                raise ValueError("only a visible unequipped carried item can be transferred")
            view = observation["viewpoints"][actor_id]
            visible_ids = {
                row.get("actor_id")
                for row in view.get("visible_entities", [])
                if isinstance(row, dict) and isinstance(row.get("actor_id"), str)
            }
            if action["destination_id"] not in visible_ids:
                raise ValueError("transfer recipient is not currently visible")
            return

        if op == "create_party":
            if menu.get("party") is not None:
                raise ValueError("player already belongs to a party")
            return

        if op == "join_party":
            if menu.get("party") is not None:
                raise ValueError("player already belongs to a party")
            # party_id is an explicit player-supplied social reference. Runtime membership
            # authority still validates it during commit.
            return

        raise ValueError(f"no extension gate for {op!r}")

    def _execute_one(self, actor_id: str, action: dict[str, Any]) -> Any:
        op = action["op"]
        if op in set(self.executor.supported_actions()) - _ENGINE_OWNED_OPS:
            return self.executor.execute([action], observer_actor_ids=[actor_id], world_tick_ms=0)

        actor = self.runtime.actors[actor_id]

        if op == "buy_vendor":
            return self.runtime.economy.buy_from_vendor(
                actor,
                action["vendor_id"],
                action["template_id"],
                int(action.get("quantity", 1)),
                self.runtime.catalog,
                actor_location_id=actor.location_id,
            )
        if op == "sell_vendor":
            return self.runtime.economy.sell_to_vendor(
                actor,
                action["vendor_id"],
                action["instance_id"],
                self.runtime.catalog,
                quantity=action.get("quantity"),
                actor_location_id=actor.location_id,
            )
        if op == "transfer_item":
            return self.runtime.transfer_inventory_item(
                actor_id,
                action["destination_id"],
                action["instance_id"],
                quantity=action.get("quantity"),
            )
        if op == "create_party":
            return self.runtime.create_party(actor_id)
        if op == "join_party":
            return self.runtime.join_party(action["party_id"], actor_id)

        if op == "equip_skill":
            from sao_mcp.rules.progression import equip_skill

            equip_skill(actor, action["skill_id"])
            return {"equipped_skills": list(actor.equipped_skills)}
        if op == "remove_skill":
            from sao_mcp.rules.progression import remove_skill

            remove_skill(actor, action["skill_id"], preserve_proficiency=False)
            return {"removed_skill_id": action["skill_id"], "proficiency_lost": True}

        if op == "repair_item":
            proficiency = actor.skill_proficiencies.get("blacksmithing", 0.0)
            return self.runtime.repair_inventory_item(
                actor_id,
                action["instance_id"],
                smith_proficiency=proficiency,
                pay_from_actor=True,
            )

        if op == "reinforce_weapon":
            from sao_mcp.domain.models import EnhancementTrack
            from sao_mcp.rules.progression import gain_skill_proficiency
            from sao_mcp.rules.quests import QuestObjectiveKind
            from sao_mcp.rules.reinforcement import reinforce_item

            item = actor.inventory[action["instance_id"]]
            proficiency = actor.skill_proficiencies.get("blacksmithing", 0.0)
            result = reinforce_item(
                actor,
                item,
                EnhancementTrack(action["track"]),
                self.runtime.catalog,
                smith_proficiency=proficiency,
                additional_material_quantity=int(action.get("additional_material_quantity", 1)),
                hammer_hits=10,
                elapsed_since_first_hit_ms=60_000,
                rng=self.runtime.rng,
                force_end_product=False,
            )
            if result.attempted:
                gain_skill_proficiency(actor, "blacksmithing", 2.0 if result.success else 1.0, catalog=self.runtime.catalog)
            if result.success:
                self.runtime.quests.record_event(
                    actor_id,
                    kind=QuestObjectiveKind.ENHANCE,
                    target_id=item.template_id,
                )
            return result

        if op == "craft_weapon":
            from sao_mcp.corpus.recipes import WEAPON_RECIPES
            from sao_mcp.rules.production import craft_weapon
            from sao_mcp.rules.progression import gain_skill_proficiency
            from sao_mcp.rules.quests import QuestObjectiveKind

            recipe = WEAPON_RECIPES[action["recipe_id"]]
            proficiency = actor.skill_proficiencies.get("blacksmithing", 0.0)
            result = craft_weapon(
                actor,
                recipe,
                self.runtime.catalog,
                smith_proficiency=proficiency,
                material_quality=1.0,
                rng=self.runtime.rng,
            )
            gain_skill_proficiency(actor, "blacksmithing", 6.0 + recipe.difficulty * 3.0, catalog=self.runtime.catalog)
            self.runtime.quests.record_event(actor_id, kind=QuestObjectiveKind.CRAFT, target_id=recipe.product_template_id)
            return result

        if op == "reclaim_weapon":
            from sao_mcp.rules.production import reclaim_weapon_to_ingot
            from sao_mcp.rules.progression import gain_skill_proficiency

            result = reclaim_weapon_to_ingot(actor, action["instance_id"], self.runtime.catalog)
            gain_skill_proficiency(actor, "blacksmithing", 1.5, catalog=self.runtime.catalog)
            return result

        raise ValueError(f"no execution handler for {op!r}")

    def _next_timeline_event_ms(self, encounter_id: str) -> int | None:
        """Return the next authoritative combat event timestamp without advancing time."""
        times: list[int] = []
        queued = getattr(self.runtime, "queued_player_attacks", {})
        if isinstance(queued, dict):
            for row in queued.get(encounter_id, ()):
                impact_at_ms = getattr(row, "impact_at_ms", None)
                if impact_at_ms is not None:
                    times.append(int(impact_at_ms))

        encounters = getattr(self.runtime, "encounters", {})
        encounter = encounters.get(encounter_id) if isinstance(encounters, dict) else None
        if encounter is not None:
            for participant in encounter.participants.values():
                pending = participant.metadata.get("pending_boss_action")
                if isinstance(pending, dict) and pending.get("execute_at_ms") is not None:
                    times.append(int(pending["execute_at_ms"]))

        return min(times) if times else None

    def _settle(self, actor_id: str, action: dict[str, Any]) -> dict[str, Any]:
        """Run engine-owned combat time until the player reaches a real decision boundary."""
        if action["op"] not in {"timeline_attack", "switch"}:
            return {"kind": "stable", "engine_actions": []}

        engine_actions: list[dict[str, Any]] = []
        encounter_id: str | None = None
        started_at_ms: int | None = None

        for _ in range(64):
            observation = self.executor.observe([actor_id])
            active_encounter_id = self._active_encounter_id(observation, actor_id)
            if active_encounter_id is None:
                elapsed_ms = 0
                if encounter_id is not None and started_at_ms is not None:
                    encounters = getattr(self.runtime, "encounters", {})
                    ended = encounters.get(encounter_id) if isinstance(encounters, dict) else None
                    if ended is not None:
                        elapsed_ms = max(0, int(ended.time_ms) - started_at_ms)
                return {
                    "kind": "encounter_complete",
                    "encounter_id": encounter_id,
                    "elapsed_ms": elapsed_ms,
                    "engine_actions": engine_actions,
                }

            if encounter_id is None:
                encounter_id = active_encounter_id
            elif active_encounter_id != encounter_id:
                raise RuntimeError("player runline changed encounters while settling one action")

            view = observation["viewpoints"][actor_id]
            encounter = view["encounters"][encounter_id]
            now_ms = int(encounter["time_ms"])
            if started_at_ms is None:
                started_at_ms = now_ms

            observer = view["observer"]
            boundary_ms = max(
                int(observer.get("committed_until_ms", now_ms)),
                int(observer.get("recovery_until_ms", now_ms)),
            )
            next_event_ms = self._next_timeline_event_ms(encounter_id)

            # A timeline event that occurs before (or exactly at) the player's next
            # decision boundary must resolve first. process_timeline may advance time,
            # so call it only when its next event is known to be inside that boundary.
            if next_event_ms is not None and next_event_ms <= max(now_ms, boundary_ms):
                process = {"op": "process_timeline", "encounter_id": encounter_id}
                self.executor.execute([process], observer_actor_ids=[actor_id], world_tick_ms=0)
                engine_actions.append(process)
                continue

            if boundary_ms > now_ms:
                advance = {
                    "op": "advance_encounter",
                    "encounter_id": encounter_id,
                    "elapsed_ms": boundary_ms - now_ms,
                }
                self.executor.execute([advance], observer_actor_ids=[actor_id], world_tick_ms=0)
                engine_actions.append(advance)
                continue

            return {
                "kind": "decision_boundary",
                "encounter_id": encounter_id,
                "elapsed_ms": max(0, now_ms - (started_at_ms or now_ms)),
                "engine_actions": engine_actions,
            }

        raise RuntimeError("player runline did not stabilize within 64 engine steps")

    @staticmethod
    def _active_encounter_id(observation: dict[str, Any], actor_id: str) -> str | None:
        view = observation["viewpoints"][actor_id]
        for encounter_id, encounter in view.get("encounters", {}).items():
            if encounter.get("active") and actor_id in encounter.get("participants", {}):
                return encounter_id
        return None

    @classmethod
    def _plain(cls, value: Any) -> Any:
        if is_dataclass(value):
            return cls._plain(asdict(value))
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(key): cls._plain(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._plain(item) for item in value]
        return value
