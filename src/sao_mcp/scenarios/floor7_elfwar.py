from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6_elfwar import KIZMEL_ID
from sao_mcp.corpus.floor7_elfwar import (
    ELVEN_STOUT_SWORD_ID,
    KIZMEL_SABER_ID,
    LAVIK_ID,
    LAVIK_SABER_ID,
    QUEST_ID,
)
from sao_mcp.corpus.floor7_intrigue import NARSOS_FRUIT_ID, NARSOS_REQUIRED
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.inventory import add_item, recompute_equipment_stats
from sao_mcp.rules.quests import QuestObjectiveKind


PALACE = "floor_7_harin_tree_palace"
B2_CELL = "floor_7_harin_b2_cell"
GUARD_STATION = "floor_7_harin_b2_guard_station"
WEAPON_STORE = "floor_7_harin_weapon_store"
LAVIK_CELL = "floor_7_harin_lavik_cell"
SEVENTH_PRISON = "floor_7_harin_seventh_prison"
ESCAPE_WINDOW = "floor_7_harin_escape_window"
OUTER_TRUNK = "floor_7_harin_outer_trunk"
LOOSEROCK_FOREST = "floor_7_looserock_forest"
VOLUPTA = "floor_7_volupta"

ARREST_PROCESSING_MS = 33 * 60_000
CELL_LOCK_BURN_MS = 2 * 60_000
WEAPON_RECOVERY_MS = 8 * 60_000
LAVIK_SEARCH_MS = 8 * 60_000
ASCENT_AND_GUARD_SUBDUAL_MS = 25 * 60_000
KIZMEL_CONVINCE_MS = 5 * 60_000
BLACKOUT_AND_DESCENT_MS = 35 * 60_000
POST_ESCAPE_NARSOS_GATHER_MS = 90 * 60_000
RETURN_TO_VOLUPTA_MS = 90 * 60_000


class Floor7ElfWarScenario:
    """Release-route Harin Tree Palace arrest, prison break, Kizmel rescue and return to Volupta."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor7_harin_escape_instances", {})

    def _state(self, instance_id: str) -> dict:
        try:
            return self._states()[instance_id]
        except KeyError as exc:
            raise KeyError(f"unknown Harin escape instance: {instance_id}") from exc

    def _active_actor_for_npc(self, npc_definition_id: str) -> CombatantState | None:
        for actor in self.runtime.actors.values():
            if actor.metadata.get("npc_definition_id") == npc_definition_id and actor.alive:
                return actor
        return None

    def _make_storage_cache(self) -> CombatantState:
        cache = CombatantState(
            actor_id=f"harin_store_{uuid.uuid4().hex[:12]}",
            name="Harin Confiscated Weapon Rack",
            kind=EntityKind.NPC,
            level=1,
            max_hp=1,
            hp=1,
            strength=1,
            agility=1,
            cursor=CursorColor.YELLOW,
            location_id=WEAPON_STORE,
            metadata={"noncombatant": True, "harin_confiscated_storage": True},
        )
        for template_id in (ELVEN_STOUT_SWORD_ID, KIZMEL_SABER_ID, LAVIK_SABER_ID):
            template = self.runtime.catalog.weapons[template_id]
            item = ItemInstance(
                instance_id=f"harin_weapon_{uuid.uuid4().hex[:12]}",
                template_id=template_id,
                owner_id=cache.actor_id,
                durability=template.base_durability,
                max_durability=template.base_durability,
                metadata={"confiscated_dark_elf_weapon": True},
            )
            cache.inventory[item.instance_id] = item
        self.runtime.actors[cache.actor_id] = cache
        return cache

    def arrive_and_be_arrested(self, player_ids: list[str]) -> dict:
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("Harin arrest requires at least one player")
        for actor_id in players:
            actor = self.runtime.actors[actor_id]
            if actor.kind is not EntityKind.PLAYER or not actor.alive or actor.location_id != PALACE:
                raise ValueError("all arrested characters must be living players at Harin Tree Palace")

        cache = self._make_storage_cache()
        instance_id = f"harin7_{uuid.uuid4().hex[:12]}"
        confiscated: dict[str, dict[str, str]] = {}
        self.runtime.advance_world(ARREST_PROCESSING_MS)
        for actor_id in players:
            actor = self.runtime.actors[actor_id]
            self.runtime.quests.accept(actor_id, QUEST_ID, now_ms=self.runtime.world.now_ms)
            slots: dict[str, str] = {}
            for slot in ("weapon", "offhand"):
                item_id = actor.equipment.pop(slot, None)
                if item_id is None or item_id not in actor.inventory:
                    continue
                item = actor.inventory.pop(item_id)
                item.owner_id = cache.actor_id
                item.metadata["harin_confiscated_from_actor_id"] = actor_id
                item.metadata["harin_original_slot"] = slot
                cache.inventory[item_id] = item
                slots[slot] = item_id
            recompute_equipment_stats(actor, self.runtime.catalog)
            actor.location_id = B2_CELL
            actor.metadata["harin_prisoner"] = True
            confiscated[actor_id] = slots

        state = {
            "instance_id": instance_id,
            "player_ids": players,
            "stage": "imprisoned_b2",
            "started_at_ms": self.runtime.world.now_ms,
            "storage_actor_id": cache.actor_id,
            "confiscated_slots": confiscated,
            "cell_lock_burns": 0,
            "lavik_actor_id": None,
            "kizmel_actor_id": None,
            "guards_subdued_nonlethally": 0,
            "palace_blackout": False,
            "escaped_at_ms": None,
            "narsos_gathered": 0,
            "lavik_departed": False,
            "returned_to_volupta_at_ms": None,
        }
        self._states()[instance_id] = state
        return self.status(instance_id)

    def burn_cell_lock(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "imprisoned_b2":
            raise ValueError("the party is not locked in the B2 cell")
        self.runtime.advance_world(CELL_LOCK_BURN_MS)
        state["cell_lock_burns"] = 7
        state["stage"] = "cell_escaped_recover_weapons"
        for actor_id in state["player_ids"]:
            actor = self.runtime.actors[actor_id]
            actor.metadata["harin_cell_lock_escaped"] = True
            self.runtime.quests.record_event(
                actor_id,
                kind=QuestObjectiveKind.DISCOVER,
                target_id="harin_b2_cell_escaped",
            )
        return self.status(instance_id)

    def recover_confiscated_weapons(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "cell_escaped_recover_weapons":
            raise ValueError("the B2 cell must be escaped before searching the weapon store")
        cache = self.runtime.actors[state["storage_actor_id"]]
        self.runtime.advance_world(WEAPON_RECOVERY_MS)
        for actor_id in state["player_ids"]:
            actor = self.runtime.actors[actor_id]
            actor.location_id = WEAPON_STORE
            for slot, item_id in state["confiscated_slots"].get(actor_id, {}).items():
                item = cache.inventory.pop(item_id)
                item.owner_id = actor_id
                item.metadata.pop("harin_confiscated_from_actor_id", None)
                item.metadata.pop("harin_original_slot", None)
                actor.inventory[item_id] = item
                actor.equipment[slot] = item_id
            recompute_equipment_stats(actor, self.runtime.catalog)
            self.runtime.quests.record_event(
                actor_id,
                kind=QuestObjectiveKind.DISCOVER,
                target_id="harin_confiscated_weapons_recovered",
            )
        state["stage"] = "search_basement_cells"
        return self.status(instance_id)

    def meet_lavik(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "search_basement_cells":
            raise ValueError("the party is not searching the Harin basement cells")
        self.runtime.advance_world(LAVIK_SEARCH_MS)
        for actor_id in state["player_ids"]:
            self.runtime.actors[actor_id].location_id = LAVIK_CELL
        self.runtime.npcs.states[LAVIK_ID].location_id = LAVIK_CELL
        self.runtime.interact_npc(state["player_ids"][0], LAVIK_ID)
        for actor_id in state["player_ids"][1:]:
            self.runtime.quests.record_event(actor_id, kind=QuestObjectiveKind.TALK, target_id=LAVIK_ID)

        lavik = self._active_actor_for_npc(LAVIK_ID)
        if lavik is None:
            lavik = CombatantState(
                actor_id=f"questnpc_lavik_{uuid.uuid4().hex[:12]}",
                name="Lavik Fen Cortassios",
                kind=EntityKind.NPC,
                level=28,
                max_hp=7800,
                hp=7800,
                strength=72,
                agility=50,
                armor=70,
                evasion=8,
                cursor=CursorColor.YELLOW,
                location_id=LAVIK_CELL,
                skill_proficiencies={"one_hand_curved_sword": 760.0, "parry": 640.0},
                metadata={
                    "npc_definition_id": LAVIK_ID,
                    "harin_prisoner_years": 30,
                    "combat_stats_provenance": "simulation",
                },
            )
            self.runtime.actors[lavik.actor_id] = lavik
        cache = self.runtime.actors[state["storage_actor_id"]]
        lavik_saber = next(
            (item for item in cache.inventory.values() if item.template_id == LAVIK_SABER_ID),
            None,
        )
        if lavik_saber is not None:
            cache.inventory.pop(lavik_saber.instance_id)
            lavik_saber.owner_id = lavik.actor_id
            lavik.inventory[lavik_saber.instance_id] = lavik_saber
            lavik.equipment["weapon"] = lavik_saber.instance_id
        lavik.metadata["harin_status"] = "fugitive"
        state["lavik_actor_id"] = lavik.actor_id
        state["stage"] = "lavik_joined_reach_seventh_prison"
        return self.status(instance_id)

    def lavik_subdues_guard_post(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "lavik_joined_reach_seventh_prison":
            raise ValueError("Lavik has not joined the escape party")
        self.runtime.advance_world(ASCENT_AND_GUARD_SUBDUAL_MS)
        state["guards_subdued_nonlethally"] = 2
        for actor_id in state["player_ids"]:
            self.runtime.actors[actor_id].location_id = SEVENTH_PRISON
        lavik = self.runtime.actors[state["lavik_actor_id"]]
        lavik.location_id = SEVENTH_PRISON
        state["stage"] = "seventh_prison_rejoin_kizmel"
        return self.status(instance_id)

    def rejoin_kizmel(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "seventh_prison_rejoin_kizmel":
            raise ValueError("the party has not reached the seventh-story prison")
        self.runtime.npcs.states[KIZMEL_ID].location_id = SEVENTH_PRISON
        self.runtime.interact_npc(state["player_ids"][0], KIZMEL_ID)
        for actor_id in state["player_ids"][1:]:
            self.runtime.quests.record_event(actor_id, kind=QuestObjectiveKind.TALK, target_id=KIZMEL_ID)

        kizmel = self._active_actor_for_npc(KIZMEL_ID)
        if kizmel is None:
            kizmel = CombatantState(
                actor_id=f"questnpc_kizmel_{uuid.uuid4().hex[:12]}",
                name="Kizmel",
                kind=EntityKind.NPC,
                level=27,
                max_hp=7200,
                hp=7200,
                strength=62,
                agility=58,
                armor=165,
                evasion=10,
                cursor=CursorColor.YELLOW,
                location_id=SEVENTH_PRISON,
                skill_proficiencies={"one_hand_curved_sword": 720.0, "parry": 580.0},
                metadata={
                    "npc_definition_id": KIZMEL_ID,
                    "accused_of_fallen_elf_treachery": True,
                    "combat_stats_provenance": "simulation",
                },
            )
            self.runtime.actors[kizmel.actor_id] = kizmel

        cache = self.runtime.actors[state["storage_actor_id"]]
        saber = next((item for item in cache.inventory.values() if item.template_id == KIZMEL_SABER_ID), None)
        if saber is not None:
            cache.inventory.pop(saber.instance_id)
            saber.owner_id = kizmel.actor_id
            kizmel.inventory[saber.instance_id] = saber
            kizmel.equipment["weapon"] = saber.instance_id
        stout = next((item for item in cache.inventory.values() if item.template_id == ELVEN_STOUT_SWORD_ID), None)
        if stout is not None:
            carrier = self.runtime.actors[state["player_ids"][0]]
            cache.inventory.pop(stout.instance_id)
            add_item(carrier, stout, self.runtime.catalog, allow_overweight=True)
            stout.metadata["recovered_for_kizmel"] = True

        kizmel.metadata["harin_status"] = "prisoner_refusing_escape"
        state["kizmel_actor_id"] = kizmel.actor_id
        state["stage"] = "convince_kizmel_to_escape"
        return self.status(instance_id)

    def convince_kizmel_to_escape(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "convince_kizmel_to_escape":
            raise ValueError("Kizmel is not awaiting the decision to flee Harin")
        self.runtime.advance_world(KIZMEL_CONVINCE_MS)
        kizmel = self.runtime.actors[state["kizmel_actor_id"]]
        kizmel.metadata["harin_status"] = "fugitive_clearing_own_name"
        kizmel.metadata["must_recover_sacred_keys_to_clear_name"] = True
        state["stage"] = "create_palace_blackout"
        return self.status(instance_id)

    def blackout_and_escape(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "create_palace_blackout":
            raise ValueError("the escape party is not ready to leave the seventh story")
        state["palace_blackout"] = True
        for actor_id in state["player_ids"]:
            self.runtime.actors[actor_id].location_id = ESCAPE_WINDOW
        self.runtime.actors[state["lavik_actor_id"]].location_id = ESCAPE_WINDOW
        self.runtime.actors[state["kizmel_actor_id"]].location_id = ESCAPE_WINDOW

        self.runtime.advance_world(BLACKOUT_AND_DESCENT_MS)
        for actor_id in state["player_ids"]:
            actor = self.runtime.actors[actor_id]
            actor.location_id = LOOSEROCK_FOREST
            actor.metadata.pop("harin_prisoner", None)
            self.runtime.quests.record_event(
                actor_id,
                kind=QuestObjectiveKind.DISCOVER,
                target_id="harin_tree_palace_escaped",
            )
        lavik = self.runtime.actors[state["lavik_actor_id"]]
        kizmel = self.runtime.actors[state["kizmel_actor_id"]]
        lavik.location_id = LOOSEROCK_FOREST
        kizmel.location_id = LOOSEROCK_FOREST
        self.runtime.npcs.states[KIZMEL_ID].location_id = LOOSEROCK_FOREST

        for actor_id in state["player_ids"]:
            if self.runtime.quests.ready_to_claim(self.runtime.actors[actor_id], QUEST_ID):
                self.runtime.claim_quest(actor_id, QUEST_ID)
        state["stage"] = "escaped_gather_narsos"
        state["escaped_at_ms"] = self.runtime.world.now_ms
        return self.status(instance_id)

    def gather_narsos_and_part_with_lavik(self, instance_id: str, carrier_actor_id: str | None = None) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "escaped_gather_narsos":
            raise ValueError("the party has not completed the Harin escape")
        carrier_id = carrier_actor_id or state["player_ids"][0]
        if carrier_id not in state["player_ids"]:
            raise ValueError("Narsos carrier must be one of the escaped players")
        if any(self.runtime.actors[actor_id].location_id != LOOSEROCK_FOREST for actor_id in state["player_ids"]):
            raise ValueError("the escape party must still be in Looserock Forest")
        self.runtime.advance_world(POST_ESCAPE_NARSOS_GATHER_MS)
        carrier = self.runtime.actors[carrier_id]
        existing = sum(item.quantity for item in carrier.inventory.values() if item.template_id == NARSOS_FRUIT_ID)
        missing = max(0, NARSOS_REQUIRED - existing)
        if missing:
            add_item(
                carrier,
                ItemInstance(
                    instance_id=f"material_{uuid.uuid4().hex[:12]}",
                    template_id=NARSOS_FRUIT_ID,
                    owner_id=carrier_id,
                    quantity=missing,
                    metadata={"gathered_after_harin_escape": True},
                ),
                self.runtime.catalog,
                allow_overweight=True,
            )
        state["narsos_gathered"] = NARSOS_REQUIRED
        lavik = self.runtime.actors[state["lavik_actor_id"]]
        lavik.metadata["left_escape_party"] = True
        lavik.metadata["destination_unknown"] = True
        lavik.location_id = "floor_7_field"
        state["lavik_departed"] = True
        state["stage"] = "return_to_volupta_with_kizmel"
        return self.status(instance_id)

    def return_to_volupta_with_kizmel(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "return_to_volupta_with_kizmel":
            raise ValueError("the Harin escape party is not ready to return to Volupta")
        if any(self.runtime.actors[actor_id].location_id != LOOSEROCK_FOREST for actor_id in state["player_ids"]):
            raise ValueError("all players must depart from Looserock Forest together")
        self.runtime.advance_world(RETURN_TO_VOLUPTA_MS)
        for actor_id in state["player_ids"]:
            self.runtime.actors[actor_id].location_id = VOLUPTA
        kizmel = self.runtime.actors[state["kizmel_actor_id"]]
        kizmel.location_id = VOLUPTA
        self.runtime.npcs.states[KIZMEL_ID].location_id = VOLUPTA
        state["stage"] = "returned_to_volupta_with_kizmel"
        state["returned_to_volupta_at_ms"] = self.runtime.world.now_ms
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        cache = self.runtime.actors[state["storage_actor_id"]]
        players = {
            actor_id: {
                "location_id": self.runtime.actors[actor_id].location_id,
                "equipped_weapon_id": self.runtime.actors[actor_id].equipment.get("weapon"),
                "quest_completed": QUEST_ID in self.runtime.quests.completed_by_actor.get(actor_id, set()),
            }
            for actor_id in state["player_ids"]
        }
        lavik = self.runtime.actors.get(state.get("lavik_actor_id"))
        kizmel = self.runtime.actors.get(state.get("kizmel_actor_id"))
        return {
            **state,
            "players": players,
            "storage_template_ids": sorted(item.template_id for item in cache.inventory.values()),
            "lavik_status": lavik.metadata.get("harin_status") if lavik else None,
            "lavik_location_id": lavik.location_id if lavik else None,
            "kizmel_status": kizmel.metadata.get("harin_status") if kizmel else None,
            "kizmel_location_id": kizmel.location_id if kizmel else None,
            "next_stage": (
                "burn the wooden cell lock" if state["stage"] == "imprisoned_b2"
                else "recover confiscated weapons beside the guard station" if state["stage"] == "cell_escaped_recover_weapons"
                else "search the basement cells" if state["stage"] == "search_basement_cells"
                else "let Lavik lead the route to the seventh-story prison" if state["stage"] == "lavik_joined_reach_seventh_prison"
                else "rejoin Kizmel" if state["stage"] == "seventh_prison_rejoin_kizmel"
                else "convince Kizmel to clear her name as a fugitive" if state["stage"] == "convince_kizmel_to_escape"
                else "black out Harin and descend the outer trunk" if state["stage"] == "create_palace_blackout"
                else "gather the twenty Narsos fruits and part with Lavik" if state["stage"] == "escaped_gather_narsos"
                else "return to Volupta with Kizmel" if state["stage"] == "return_to_volupta_with_kizmel"
                else None
            ),
        }


def install_floor7_elfwar_scenario(runtime) -> Floor7ElfWarScenario:
    if QUEST_ID not in runtime.quests.definitions:
        raise RuntimeError("Floor 7 Harin Elf War quest corpus was not loaded")
    if LAVIK_ID not in runtime.npcs.definitions or KIZMEL_ID not in runtime.npcs.definitions:
        raise RuntimeError("Floor 7 Harin companion NPC corpus was not loaded")
    return Floor7ElfWarScenario(runtime)
