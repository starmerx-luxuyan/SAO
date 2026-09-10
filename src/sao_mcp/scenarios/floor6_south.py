from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6_finale import GOLDEN_CUBE_ID
from sao_mcp.corpus.floor6_south import BASALT_MORPHA_ID, BASALT_MORPHA_WEAPON_ID
from sao_mcp.corpus.floor6_trials import MYIA_ID, THEANO_ID
from sao_mcp.corpus.floor6_world import GOLDEN_CUBE_LABYRINTH_BREACH_CONNECTION_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.group_travel import (
    complete_routed_travel_within_window,
    group_travel_record,
    routed_travel_window_record,
    travel_route_together,
)
from sao_mcp.rules.world import unlock_dynamic_world_connection


LAKE_TALPHA = "floor_6_lake_talpha"
GOSKAI = "floor_6_goskai"
GOSKAI_CAVES = "floor_6_goskai_caves"
MURUTSUKI = "floor_6_murutsuki"
LABYRINTH = "floor_6_labyrinth"
LABYRINTH_BREACH = "floor_6_labyrinth_golden_cube_breach"
BOSS_ROOM = "floor_6_boss_room"

BASALT_INTACT_ARMOR = 980
BASALT_BROKEN_ARMOR = 75
THEANO_LEVEL = 32


class Floor6SouthScenario:
    """Release-route pursuit of Theano from the empty Dungeon of Trials chamber to the Floor 6 boss room."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def _state(self, actor_id: str) -> dict:
        states = self.runtime.world.global_flags.setdefault("floor6_stachion_quest_states", {})
        try:
            return states[actor_id]
        except KeyError as exc:
            raise ValueError("Curse of Stachion has not been started") from exc

    def _find_or_create_theano(self) -> CombatantState:
        existing = next(
            (
                actor
                for actor in self.runtime.actors.values()
                if actor.metadata.get("npc_definition_id") == THEANO_ID
                and actor.metadata.get("floor6_release_theano")
            ),
            None,
        )
        if existing is not None:
            return existing
        actor_id = f"questnpc_theano_{uuid.uuid4().hex[:12]}"
        theano = CombatantState(
            actor_id=actor_id,
            name="Theano",
            kind=EntityKind.NPC,
            level=THEANO_LEVEL,
            max_hp=5600,
            hp=5600,
            strength=44,
            agility=58,
            armor=125,
            evasion=14,
            cursor=CursorColor.YELLOW,
            location_id=GOSKAI_CAVES,
            skill_proficiencies={"rapier": 690.0, "parry": 460.0},
            metadata={
                "npc_definition_id": THEANO_ID,
                "floor6_release_theano": True,
                "combat_stats_provenance": "simulation",
                "golden_cube_user": True,
            },
        )
        rapier_template = self.runtime.catalog.weapons["starter_rapier"]
        rapier = ItemInstance(
            instance_id=f"weapon_{uuid.uuid4().hex[:12]}",
            template_id=rapier_template.template_id,
            owner_id=actor_id,
            durability=rapier_template.base_durability,
            max_durability=rapier_template.base_durability,
            metadata={"descriptive_weapon": True, "not_claimed_named_canon_weapon": True},
        )
        golden_cube = ItemInstance(
            instance_id=f"golden_cube_{uuid.uuid4().hex[:12]}",
            template_id=GOLDEN_CUBE_ID,
            owner_id=actor_id,
            metadata={
                "taken_from_dungeon_of_trials": True,
                "holder_route": "theano_release_route",
            },
        )
        theano.inventory[rapier.instance_id] = rapier
        theano.inventory[golden_cube.instance_id] = golden_cube
        theano.equipment["weapon"] = rapier.instance_id
        self.runtime.actors[actor_id] = theano
        return theano

    def receive_south_sighting(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state.get("stage") != "theano_golden_cube_missing":
            raise ValueError("the empty Dungeon of Trials final chamber must be confirmed first")
        theano = self._find_or_create_theano()
        state["stage"] = "theano_sighted_goskai_caves"
        state["theano_actor_id"] = theano.actor_id
        state["south_sighting_at_ms"] = self.runtime.world.now_ms
        state["theano_murutsuki_route"] = []
        state["theano_boss_route"] = None
        state["south_sighting_facts"] = [
            "Theano was seen heading through the southern fourth area",
            "she is carrying the missing Golden Cube",
            "her trail leads toward the caves around Goskai",
        ]
        return self.status(actor_id)

    def _create_basalt_morpha(self) -> CombatantState:
        actor_id = f"midboss_basalt_morpha_{uuid.uuid4().hex[:12]}"
        weapon_template = self.runtime.catalog.weapons[BASALT_MORPHA_WEAPON_ID]
        boss = CombatantState(
            actor_id=actor_id,
            name="Basalt Morpha",
            kind=EntityKind.MONSTER,
            level=35,
            max_hp=18_500,
            hp=18_500,
            strength=82,
            agility=30,
            armor=BASALT_INTACT_ARMOR,
            evasion=3,
            cursor=CursorColor.RED,
            location_id=GOSKAI_CAVES,
            skill_proficiencies={"other": 650.0},
            metadata={
                "monster_id": BASALT_MORPHA_ID,
                "floor6_midboss": True,
                "rock_armor_intact": True,
                "combat_stats_provenance": "simulation",
                "no_standard_loot": True,
            },
        )
        weapon = ItemInstance(
            instance_id=f"natural_{uuid.uuid4().hex[:12]}",
            template_id=BASALT_MORPHA_WEAPON_ID,
            owner_id=actor_id,
            durability=weapon_template.base_durability,
            max_durability=weapon_template.base_durability,
            metadata={"natural_attack": True},
        )
        boss.inventory[weapon.instance_id] = weapon
        boss.equipment["weapon"] = weapon.instance_id
        self.runtime.actors[actor_id] = boss
        return boss

    def start_basalt_morpha_event(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state.get("stage") != "theano_sighted_goskai_caves":
            raise ValueError("Theano's Goskai trail has not been established")
        if actor.location_id != GOSKAI_CAVES:
            raise ValueError("Basalt Morpha is encountered in the caves around Goskai")
        theano = self.runtime.actors[state["theano_actor_id"]]
        if theano.location_id != GOSKAI_CAVES:
            raise RuntimeError("Theano is no longer at the authoritative Goskai-caves sighting location")
        basalt = self._create_basalt_morpha()
        encounter = self.runtime.start_encounter(
            [actor_id, theano.actor_id, basalt.actor_id],
            zone_id=GOSKAI_CAVES,
            safe_zone=False,
        )
        state["stage"] = "basalt_morpha_battle"
        state["basalt_actor_id"] = basalt.actor_id
        state["basalt_encounter_id"] = encounter.encounter_id
        state["basalt_started_at_ms"] = self.runtime.world.now_ms
        return self.status(actor_id)

    def theano_break_basalt_armor(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state.get("stage") != "basalt_morpha_battle":
            raise ValueError("Basalt Morpha battle is not active")
        theano = self.runtime.actors[state["theano_actor_id"]]
        basalt = self.runtime.actors[state["basalt_actor_id"]]
        if not basalt.alive:
            raise ValueError("Basalt Morpha is already defeated")
        cube = next((item for item in theano.inventory.values() if item.template_id == GOLDEN_CUBE_ID), None)
        if cube is None:
            raise ValueError("Theano is no longer carrying the Golden Cube")
        basalt.armor = BASALT_BROKEN_ARMOR
        basalt.metadata["rock_armor_intact"] = False
        basalt.metadata["rock_armor_broken_by_golden_cube"] = True
        cube.metadata["break_used_on_basalt_morpha"] = True
        cube.metadata["last_break_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "basalt_morpha_armor_broken"
        self.runtime._append(
            self.runtime.encounters[state["basalt_encounter_id"]],
            "golden_cube_break_basalt_armor",
            theano.actor_id,
            basalt.actor_id,
            armor_before=BASALT_INTACT_ARMOR,
            armor_after=BASALT_BROKEN_ARMOR,
            golden_cube_instance_id=cube.instance_id,
        )
        return self.status(actor_id)

    def continue_trail_to_murutsuki(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state.get("stage") != "basalt_morpha_armor_broken":
            raise ValueError("Basalt Morpha's rock armor must be broken before the pursuit can continue")
        basalt = self.runtime.actors[state["basalt_actor_id"]]
        if basalt.alive:
            raise ValueError("Basalt Morpha must be defeated by ordinary combat before the route advances")
        theano = self.runtime.actors[state["theano_actor_id"]]
        encounter = self.runtime.encounters[state["basalt_encounter_id"]]
        encounter.participants = {actor_id: self.runtime.actors[actor_id]}
        encounter.positions = {actor_id: encounter.positions.get(actor_id, (-1.15, 0.0))}
        route = travel_route_together(self.runtime, [theano.actor_id], MURUTSUKI)
        state["theano_murutsuki_route"] = [group_travel_record(segment) for segment in route]
        state["stage"] = "theano_passed_murutsuki"
        state["murutsuki_trail_at_ms"] = self.runtime.world.now_ms
        state["murutsuki_facts"] = [
            "Theano passed through Murutsuki ahead of the pursuit",
            "the trail continues toward the Floor 6 Labyrinth",
        ]
        return self.status(actor_id)

    def breach_labyrinth_with_golden_cube(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state.get("stage") != "theano_passed_murutsuki":
            raise ValueError("the Murutsuki trail must be established first")
        if actor.location_id != LABYRINTH:
            raise ValueError("the pursuit must reach the Floor 6 Labyrinth")
        theano = self.runtime.actors[state["theano_actor_id"]]
        cube = next((item for item in theano.inventory.values() if item.template_id == GOLDEN_CUBE_ID), None)
        if cube is None:
            raise ValueError("Theano is no longer carrying the Golden Cube")
        cube.metadata["break_used_on_labyrinth_walls"] = True
        cube.metadata["last_break_at_ms"] = self.runtime.world.now_ms
        unlock_dynamic_world_connection(
            self.runtime.world,
            self.runtime.world_map,
            GOLDEN_CUBE_LABYRINTH_BREACH_CONNECTION_ID,
        )
        route = complete_routed_travel_within_window(
            self.runtime,
            [theano.actor_id],
            BOSS_ROOM,
            started_at_ms=int(state["murutsuki_trail_at_ms"]),
        )
        state["theano_boss_route"] = routed_travel_window_record(route)
        state["stage"] = "theano_reached_floor6_boss_room"
        state["labyrinth_breached_at_ms"] = self.runtime.world.now_ms
        state["labyrinth_breach_facts"] = [
            "Golden Cube Break dismantled labyrinth walls into blocks",
            "Theano created an abnormal direct route toward the boss chamber",
            "ordinary labyrinth puzzles and walls no longer force the pursuit onto the intended path",
        ]
        return self.status(actor_id)

    def status(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        theano = self.runtime.actors.get(state.get("theano_actor_id")) if state.get("theano_actor_id") else None
        basalt = self.runtime.actors.get(state.get("basalt_actor_id")) if state.get("basalt_actor_id") else None
        cube = None
        if theano is not None:
            cube = next((item for item in theano.inventory.values() if item.template_id == GOLDEN_CUBE_ID), None)
        return {
            "actor_id": actor_id,
            "stage": state.get("stage"),
            "theano_actor_id": state.get("theano_actor_id"),
            "theano_location_id": theano.location_id if theano else None,
            "theano_murutsuki_route": state.get("theano_murutsuki_route", []),
            "theano_boss_route": state.get("theano_boss_route"),
            "golden_cube_instance_id": cube.instance_id if cube else None,
            "basalt_actor_id": state.get("basalt_actor_id"),
            "basalt_encounter_id": state.get("basalt_encounter_id"),
            "basalt_alive": basalt.alive if basalt else None,
            "basalt_hp": basalt.hp if basalt else None,
            "basalt_armor": basalt.armor if basalt else None,
            "basalt_rock_armor_intact": basalt.metadata.get("rock_armor_intact") if basalt else None,
            "next_stage": (
                "travel to the Goskai caves" if state.get("stage") == "theano_sighted_goskai_caves"
                else "let Theano use Golden Cube Break on Basalt Morpha's stone armor" if state.get("stage") == "basalt_morpha_battle"
                else "defeat Basalt Morpha through ordinary combat" if state.get("stage") == "basalt_morpha_armor_broken" and basalt and basalt.alive
                else "follow Theano toward Murutsuki" if state.get("stage") == "basalt_morpha_armor_broken"
                else "reach the Floor 6 Labyrinth" if state.get("stage") == "theano_passed_murutsuki"
                else "follow the Golden Cube breach to the boss room" if state.get("stage") == "theano_reached_floor6_boss_room"
                else None
            ),
        }


def install_floor6_south_scenario(runtime) -> Floor6SouthScenario:
    if GOLDEN_CUBE_ID not in runtime.catalog.items:
        raise RuntimeError("Floor 6 Golden Cube corpus was not loaded")
    if BASALT_MORPHA_WEAPON_ID not in runtime.catalog.weapons:
        raise RuntimeError("Floor 6 Basalt Morpha corpus was not loaded")
    if any(npc_id not in runtime.npcs.definitions for npc_id in (THEANO_ID, MYIA_ID)):
        raise RuntimeError("Floor 6 Theano/Myia NPC corpus was not loaded")
    return Floor6SouthScenario(runtime)
