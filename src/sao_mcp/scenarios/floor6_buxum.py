from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6_buxum import BUXUM_ID, BUXUM_LONGSWORD_ID
from sao_mcp.corpus.floor6_elfwar import KYSARAH_ID, MEDITATION_SKILL_ID
from sao_mcp.corpus.floor6_finale import COMBINED_IRON_KEY_ID, GOLDEN_CUBE_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance, StatusType
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.state_authority import locate_runtime_item


BOSS_ROOM = "floor_6_boss_room"
BUXUM_RETREAT_HP_RATIO = 0.35  # Simulation trigger; canon retreat follows loss of his sword and both forearms.
AWAKENING_BURST_MS = 12_000  # Simulation marker window; canon only establishes a short superhuman burst.
BUXUM_BETRAYAL_EVENT_RULE_ID = "floor6.buxum_betrayal"
BUXUM_RETREAT_EVENT_RULE_ID = "floor6.buxum_retreat"


class Floor6BuxumScenario:
    """Buxum's betrayal at The Irrational Cube's final HP pixel, handing combat back to normal PvP after Bind breaks."""

    def __init__(self, runtime, cube) -> None:
        self.runtime = runtime
        self.cube = cube
        runtime.register_defeat_hook(self._on_defeat)
        runtime.register_world_event_rule(
            BUXUM_BETRAYAL_EVENT_RULE_ID,
            self._discover_betrayal_events,
            self._resolve_betrayal_event,
        )
        runtime.register_world_event_rule(
            BUXUM_RETREAT_EVENT_RULE_ID,
            self._discover_retreat_events,
            self._resolve_retreat_event,
        )
        runtime.evaluate_world_events()

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor6_buxum_states", {})

    def _state(self, cube_instance_id: str) -> dict:
        try:
            return self._states()[cube_instance_id]
        except KeyError as exc:
            raise ValueError("Buxum's Floor 6 betrayal has not been triggered for this boss instance") from exc

    def _on_defeat(self, encounter, target, killer_id: str | None) -> None:
        for cube_instance_id, state in self._states().items():
            if state["stage"] != "golden_cube_recovered":
                continue
            cube_state = self.cube._instance(cube_instance_id)
            if cube_state["boss_id"] != target.actor_id or cube_state["stage"] != "cleared":
                continue
            state["stage"] = "floor_cleared"

    def _combined_key_location(self) -> tuple[CombatantState, ItemInstance] | None:
        key_id = self.runtime.world.global_flags.get("floor6_combined_iron_key_instance_id")
        if not key_id:
            return None
        located = locate_runtime_item(self.runtime, key_id)
        if located is None:
            return None
        if located.item.template_id != COMBINED_IRON_KEY_ID:
            raise RuntimeError("Floor 6 combined-key instance ID points to the wrong item template")
        return located

    def _take_kysarah_combined_key(self) -> tuple[CombatantState, ItemInstance]:
        located = self._combined_key_location()
        if located is None:
            raise ValueError("Kysarah's stolen combined iron key has not reached the Floor 6 finale route")
        holder_id = located.sole_actor_id
        if holder_id is None:
            raise ValueError("the canonical Buxum betrayal requires Kysarah to be the combined key's current actor holder")
        holder = self.runtime.actors[holder_id]
        key = located.item
        if holder.metadata.get("npc_definition_id") != KYSARAH_ID:
            raise ValueError("the canonical Buxum betrayal requires the combined key previously stolen by Kysarah")
        holder.inventory.pop(key.instance_id)
        return holder, key

    def _create_buxum(self, key: ItemInstance) -> CombatantState:
        actor_id = f"namedplayer_buxum_{uuid.uuid4().hex[:10]}"
        weapon_template = self.runtime.catalog.weapons[BUXUM_LONGSWORD_ID]
        buxum = CombatantState(
            actor_id=actor_id,
            name="Buxum",
            kind=EntityKind.PLAYER,
            level=31,
            max_hp=8_700,
            hp=8_700,
            strength=66,
            agility=74,
            armor=220,
            evasion=15,
            cursor=CursorColor.GREEN,
            location_id=BOSS_ROOM,
            skill_proficiencies={"one_hand_sword": 760.0, "parry": 610.0},
            metadata={
                "npc_definition_id": BUXUM_ID,
                "named_player_npc": True,
                "dkb_infiltrator": True,
                "black_poncho_group": True,
                "combat_stats_provenance": "simulation",
            },
        )
        weapon = ItemInstance(
            instance_id=f"weapon_{uuid.uuid4().hex[:12]}",
            template_id=BUXUM_LONGSWORD_ID,
            owner_id=actor_id,
            durability=weapon_template.base_durability,
            max_durability=weapon_template.base_durability,
        )
        buxum.inventory[weapon.instance_id] = weapon
        buxum.equipment["weapon"] = weapon.instance_id

        key.owner_id = actor_id
        key.metadata["received_by_buxum_after_kysarah_theft"] = True
        key.metadata["handoff_mechanism"] = "canonically_unexplained"
        buxum.inventory[key.instance_id] = key
        self.runtime.actors[actor_id] = buxum
        return buxum

    @staticmethod
    def _event_instance_id(occurrence_id: str, rule_id: str) -> str:
        prefix = f"{rule_id}:"
        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):
            raise RuntimeError(f"invalid {rule_id} occurrence id: {occurrence_id}")
        return occurrence_id[len(prefix):]

    def _discover_betrayal_events(self) -> list[str]:
        located = self._combined_key_location()
        if located is None or located.sole_actor_id is None:
            return []
        holder = self.runtime.actors[located.sole_actor_id]
        if holder.metadata.get("npc_definition_id") != KYSARAH_ID:
            return []

        ready: list[str] = []
        for cube_instance_id, cube_state in self.cube._instances().items():
            if cube_instance_id in self._states() or cube_state["stage"] != "black_core_battle":
                continue
            boss = self.runtime.actors[cube_state["boss_id"]]
            encounter = self.runtime.encounters[cube_state["encounter_id"]]
            if boss.alive and boss.hp == 1 and encounter.active and boss.actor_id in encounter.participants:
                ready.append(f"{BUXUM_BETRAYAL_EVENT_RULE_ID}:{cube_instance_id}")
        return ready

    def _resolve_betrayal_event(self, occurrence_id: str) -> dict:
        cube_instance_id = self._event_instance_id(occurrence_id, BUXUM_BETRAYAL_EVENT_RULE_ID)
        state = self._trigger_betrayal(cube_instance_id)
        return {
            "cube_instance_id": cube_instance_id,
            "encounter_id": state["encounter_id"],
            "buxum_actor_id": state["buxum_actor_id"],
            "golden_cube_instance_id": state["golden_cube_instance_id"],
        }

    def _trigger_betrayal(self, cube_instance_id: str) -> dict:
        cube_state = self.cube._instance(cube_instance_id)
        if cube_state["stage"] != "black_core_battle":
            raise ValueError("Buxum acts only after the numbered armor is broken and the black core is exposed")
        boss = self.runtime.actors[cube_state["boss_id"]]
        if boss.hp != 1:
            raise ValueError("Buxum waits until The Irrational Cube is at its final HP pixel")
        if cube_instance_id in self._states():
            raise RuntimeError("Buxum betrayal occurrence attempted to resolve twice")

        kysarah, combined_key = self._take_kysarah_combined_key()
        buxum = self._create_buxum(combined_key)
        encounter = self.runtime.encounters[cube_state["encounter_id"]]
        boss_position = encounter.positions.get(boss.actor_id, (1.15, 0.0))
        self.runtime.add_encounter_participant(
            encounter.encounter_id,
            buxum.actor_id,
            position=(boss_position[0] + 1.65, boss_position[1] + 0.75),
        )
        self.runtime._append(
            encounter,
            "buxum_revealed",
            buxum.actor_id,
            boss.actor_id,
            former_combined_key_holder_id=kysarah.actor_id,
            combined_key_instance_id=combined_key.instance_id,
            key_handoff_mechanism="canonically_unexplained",
        )

        # The existing guardian scenario owns the keyhole, cube-ejection and crime-aware Bind mechanics.
        self.cube.eject_golden_cube(cube_instance_id, buxum.actor_id, combined_key.instance_id)
        bind_result = self.cube.use_golden_cube_bind(cube_instance_id, buxum.actor_id)

        state = {
            "cube_instance_id": cube_instance_id,
            "stage": "bind_active",
            "buxum_actor_id": buxum.actor_id,
            "encounter_id": encounter.encounter_id,
            "combined_key_instance_id": combined_key.instance_id,
            "golden_cube_instance_id": cube_state["golden_cube_instance_id"],
            "former_combined_key_holder_id": kysarah.actor_id,
            "awakening_actor_ids": [],
            "cube_ground_cache_actor_id": None,
            "cube_recovered_by_actor_id": None,
            "triggered_at_ms": self.runtime.world.now_ms,
            "bind_affected_actor_ids": list(bind_result["affected_actor_ids"]),
        }
        self._states()[cube_instance_id] = state
        return self.status(cube_instance_id)

    def break_bind_with_awakening(self, cube_instance_id: str, actor_id: str) -> dict:
        state = self._state(cube_instance_id)
        if state["stage"] not in {"bind_active", "awakening_counterattack"}:
            raise ValueError("Golden Cube Bind is not the active Buxum threat")
        encounter = self.runtime.encounters[state["encounter_id"]]
        if actor_id not in encounter.participants:
            raise ValueError("Awakening user must be a participant in the Floor 6 boss encounter")
        actor = encounter.participants[actor_id]
        if actor.skill_proficiencies.get(MEDITATION_SKILL_ID, 0.0) < 500:
            raise ValueError("Awakening requires Meditation proficiency 500")
        if "awakening" not in actor.metadata.get("skill_mods", {}).get(MEDITATION_SKILL_ID, []):
            raise ValueError("the actor has not unlocked the Awakening Meditation mod")
        if not any(status.stack_key == "golden_cube_bind" for status in actor.statuses):
            raise ValueError("the actor is not currently held by Golden Cube Bind")

        actor.statuses = [status for status in actor.statuses if status.stack_key != "golden_cube_bind"]
        actor.metadata["floor6_awakening_active_until_ms"] = encounter.time_ms + AWAKENING_BURST_MS
        actor.metadata["floor6_awakening_broke_bind"] = True
        if actor_id not in state["awakening_actor_ids"]:
            state["awakening_actor_ids"].append(actor_id)
        state["stage"] = "awakening_counterattack"
        self.runtime._append(
            encounter,
            "awakening_breaks_golden_cube_bind",
            actor_id,
            state["buxum_actor_id"],
            meditation_proficiency=actor.skill_proficiencies[MEDITATION_SKILL_ID],
            burst_marker_until_ms=actor.metadata["floor6_awakening_active_until_ms"],
        )
        return self.status(cube_instance_id)

    def _drop_buxum_cube(self, state: dict, buxum: CombatantState) -> CombatantState:
        cube_id = state["golden_cube_instance_id"]
        cube_item = buxum.inventory.pop(cube_id, None)
        if cube_item is None or cube_item.template_id != GOLDEN_CUBE_ID:
            raise ValueError("Buxum no longer possesses the ejected Golden Cube")
        cube_item.owner_id = None
        cube_item.metadata["dropped_by_buxum"] = True
        cache_id = f"groundloot_buxum_cube_{uuid.uuid4().hex[:10]}"
        cache = CombatantState(
            actor_id=cache_id,
            name="Dropped Golden Cube",
            kind=EntityKind.NPC,
            level=1,
            max_hp=1,
            hp=1,
            strength=1,
            agility=1,
            cursor=CursorColor.YELLOW,
            location_id=BOSS_ROOM,
            metadata={"ground_loot_cache": True, "noncombatant": True, "source_actor_id": buxum.actor_id},
        )
        cache.inventory[cube_item.instance_id] = cube_item
        self.runtime.actors[cache_id] = cache
        return cache

    def _discover_retreat_events(self) -> list[str]:
        ready: list[str] = []
        for cube_instance_id, state in self._states().items():
            if state["stage"] not in {"bind_active", "awakening_counterattack"}:
                continue
            buxum = self.runtime.actors[state["buxum_actor_id"]]
            weapon_id = buxum.equipment.get("weapon")
            weapon_broken = bool(
                not weapon_id
                or weapon_id not in buxum.inventory
                or buxum.inventory[weapon_id].broken
            )
            low_hp = buxum.hp <= max(1, int(round(buxum.max_hp * BUXUM_RETREAT_HP_RATIO)))
            if not buxum.alive or low_hp or weapon_broken:
                ready.append(f"{BUXUM_RETREAT_EVENT_RULE_ID}:{cube_instance_id}")
        return ready

    def _resolve_retreat_event(self, occurrence_id: str) -> dict:
        cube_instance_id = self._event_instance_id(occurrence_id, BUXUM_RETREAT_EVENT_RULE_ID)
        state = self._resolve_buxum_retreat(cube_instance_id)
        return {
            "cube_instance_id": cube_instance_id,
            "buxum_actor_id": state["buxum_actor_id"],
            "golden_cube_instance_id": state["golden_cube_instance_id"],
            "stage": state["stage"],
        }

    def _resolve_buxum_retreat(self, cube_instance_id: str) -> dict:
        state = self._state(cube_instance_id)
        if state["stage"] not in {"bind_active", "awakening_counterattack"}:
            raise ValueError("Buxum is not in the active betrayal phase")
        buxum = self.runtime.actors[state["buxum_actor_id"]]
        weapon_id = buxum.equipment.get("weapon")
        weapon_broken = bool(
            not weapon_id
            or weapon_id not in buxum.inventory
            or buxum.inventory[weapon_id].broken
        )
        low_hp = buxum.hp <= max(1, int(round(buxum.max_hp * BUXUM_RETREAT_HP_RATIO)))
        if buxum.alive and not low_hp and not weapon_broken:
            raise ValueError("Buxum has not yet been overpowered enough to abandon the Golden Cube and retreat")

        cache = self._drop_buxum_cube(state, buxum)
        encounter = self.runtime.encounters[state["encounter_id"]]
        if buxum.alive:
            buxum.metadata["retreated"] = True
            buxum.metadata["retreat_reason"] = "overpowered_after_golden_cube_bind"
        self.runtime.remove_encounter_participants(
            encounter.encounter_id, [buxum.actor_id], reason="buxum_retreat"
        )
        state["stage"] = "golden_cube_dropped"
        state["cube_ground_cache_actor_id"] = cache.actor_id
        state["buxum_retreat_at_ms"] = self.runtime.world.now_ms
        self.runtime._append(
            encounter,
            "buxum_drops_cube_and_retreats",
            buxum.actor_id,
            None,
            golden_cube_instance_id=state["golden_cube_instance_id"],
            buxum_alive=buxum.alive,
            weapon_broken=weapon_broken,
            hp=buxum.hp,
            max_hp=buxum.max_hp,
        )
        return self.status(cube_instance_id)

    def recover_golden_cube(self, cube_instance_id: str, actor_id: str) -> dict:
        state = self._state(cube_instance_id)
        if state["stage"] != "golden_cube_dropped":
            raise ValueError("Buxum has not dropped the Golden Cube")
        encounter = self.runtime.encounters[state["encounter_id"]]
        if actor_id not in encounter.participants or not encounter.participants[actor_id].alive:
            raise ValueError("only a living boss-room participant can recover the dropped Golden Cube")
        actor = self.runtime.actors[actor_id]
        cache = self.runtime.actors[state["cube_ground_cache_actor_id"]]
        cube_item = cache.inventory.pop(state["golden_cube_instance_id"], None)
        if cube_item is None:
            raise ValueError("the Golden Cube has already been recovered")
        add_item(actor, cube_item, self.runtime.catalog, allow_overweight=True)
        state["stage"] = "golden_cube_recovered"
        state["cube_recovered_by_actor_id"] = actor_id
        self.runtime._append(
            encounter,
            "golden_cube_recovered_after_buxum",
            actor_id,
            None,
            golden_cube_instance_id=cube_item.instance_id,
        )
        return self.status(cube_instance_id)

    def status(self, cube_instance_id: str) -> dict:
        state = self._state(cube_instance_id)
        buxum = self.runtime.actors[state["buxum_actor_id"]]
        encounter = self.runtime.encounters[state["encounter_id"]]
        cube_state = self.cube.status(cube_instance_id)
        bound_actor_ids = [
            actor_id
            for actor_id, actor in encounter.participants.items()
            if any(status.stack_key == "golden_cube_bind" for status in actor.statuses)
        ]
        located = self._combined_key_location()
        combined_key_holder_id = located.sole_actor_id if located is not None else None
        return {
            **state,
            "buxum_alive": buxum.alive,
            "buxum_hp": buxum.hp,
            "buxum_max_hp": buxum.max_hp,
            "buxum_cursor": buxum.cursor.value,
            "buxum_in_encounter": buxum.actor_id in encounter.participants,
            "bound_actor_ids": bound_actor_ids,
            "cube_state": cube_state,
            "combined_key_holder_id": combined_key_holder_id,
            "next_stage": (
                "an Awakening-capable player must break Bind or Buxum remains in control" if state["stage"] == "bind_active"
                else "ordinary PvP can now overpower Buxum" if state["stage"] == "awakening_counterattack"
                else "recover the dropped Golden Cube" if state["stage"] == "golden_cube_dropped"
                else "reinsert the Golden Cube and destroy the one-HP core" if state["stage"] == "golden_cube_recovered"
                else "recover the surviving combined steel key from the boss-room floor" if state["stage"] == "floor_cleared" and cube_state.get("combined_key_grounded")
                else None
            ),
        }


def install_floor6_buxum_scenario(runtime, cube) -> Floor6BuxumScenario:
    if BUXUM_LONGSWORD_ID not in runtime.catalog.weapons or BUXUM_ID not in runtime.npcs.definitions:
        raise RuntimeError("Floor 6 Buxum corpus was not loaded")
    if COMBINED_IRON_KEY_ID not in runtime.catalog.items or GOLDEN_CUBE_ID not in runtime.catalog.items:
        raise RuntimeError("Floor 6 finale item corpus was not loaded")
    return Floor6BuxumScenario(runtime, cube)
