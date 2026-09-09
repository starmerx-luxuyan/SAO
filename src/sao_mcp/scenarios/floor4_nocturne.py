from __future__ import annotations

import uuid
from dataclasses import asdict

from sao_mcp.corpus.floor4 import YOFILIS_ID
from sao_mcp.corpus.floor4_nocturne import (
    BEAR_FOREST,
    CALDERA_LAKE,
    CETRANN_ID,
    FALLEN_HIDEOUT,
    KELPIE_ID,
    KELPIE_LEVEL,
    KELPIE_WEAPON_ID,
    LAKE_YOFEL,
    LAKE_YOFEL_FOG_BOUNDARY,
    LAKE_YOFEL_NORTH_BEACH,
    LAKE_YOFEL_WEST_SHORE,
    RIVER_ULL,
    YOFEL_CASTLE,
)
from sao_mcp.corpus.floor6_elfwar import SACRED_KEY_BAG_ID
from sao_mcp.corpus.floor7_elfwar import LAVIK_ID
from sao_mcp.corpus.floor7_pursuit import RUBY_KEY_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.rules.nightfolk import CIVIS_NOCTE, night_rank, tame_lower_level_monster


ROVIA = "floor_4_rovia"
USCO = "floor_4_usco"

YOFILIS_TO_NORTH_BEACH_MS = 6 * 60_000
KELPIE_FOG_TO_NORTH_BEACH_MS = 6 * 60_000
KELPIE_NORTH_TO_WEST_SHORE_MS = 8 * 60_000
KELPIE_WEST_SHORE_RETURN_MS = 12 * 60_000


class Floor4NocturneScenario:
    """Progressive 9: the five-key trail returns to Floor 4 and opens Lavik/Yofilis/Kelpie state."""

    def __init__(self, runtime, floor7_campaign) -> None:
        if floor7_campaign.runtime is not runtime:
            raise RuntimeError("Progressive 9 and Floor 7 campaign services must share one runtime")
        self.runtime = runtime
        self.floor7_campaign = floor7_campaign

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("progressive9_nocturne_instances", {})

    def _state(self, instance_id: str) -> dict:
        return self._states()[instance_id]

    def _harin_state(self, harin_instance_id: str) -> dict:
        states = self.runtime.world.global_flags["floor7_harin_escape_instances"]
        return states[harin_instance_id]

    def _single_alive_actor_for_npc(self, npc_definition_id: str):
        matches = [
            actor
            for actor in self.runtime.actors.values()
            if actor.alive and actor.metadata.get("npc_definition_id") == npc_definition_id
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected exactly one living actor for NPC {npc_definition_id}, found {len(matches)}"
            )
        return matches[0]

    def _group_actor_ids(self, state: dict) -> list[str]:
        return list(state["player_ids"]) + [state["kizmel_actor_id"]]

    def _require_actor_ids_at(self, actor_ids: list[str], location_id: str) -> None:
        wrong = [
            actor_id
            for actor_id in actor_ids
            if self.runtime.actors[actor_id].location_id != location_id
        ]
        if wrong:
            raise ValueError(f"actors are not all at {location_id}: {', '.join(wrong)}")

    def _require_group_at(self, state: dict, location_id: str) -> None:
        self._require_actor_ids_at(self._group_actor_ids(state), location_id)

    def _validate_inherited_keys(self, state: dict) -> None:
        bag_id = state["four_key_bag_instance_id"]
        ruby_id = state["ruby_key_instance_id"]
        bag_owners = [actor for actor in self.runtime.actors.values() if bag_id in actor.inventory]
        ruby_owners = [actor for actor in self.runtime.actors.values() if ruby_id in actor.inventory]
        if len(bag_owners) != 1 or len(ruby_owners) != 1:
            raise RuntimeError("inherited sacred-key assets do not each have exactly one owner")
        bag = bag_owners[0].inventory[bag_id]
        ruby = ruby_owners[0].inventory[ruby_id]
        if bag.template_id != SACRED_KEY_BAG_ID or bag.metadata.get("stolen_by_kysarah") is not True:
            raise RuntimeError("the inherited four-key bag is not the Kysarah theft asset")
        if ruby.template_id != RUBY_KEY_ID:
            raise RuntimeError("the inherited Ruby Key has the wrong template")
        if not ruby_owners[0].metadata.get("fallen_elf") or ruby.metadata.get("fallen_control") is not True:
            raise RuntimeError("the inherited Ruby Key is no longer under real Fallen Elf control")
        state["four_key_bag_owner_id"] = bag_owners[0].actor_id
        state["ruby_key_owner_id"] = ruby_owners[0].actor_id

    def _kelpie(self, state: dict) -> CombatantState:
        actor_id = state["kelpie_actor_id"]
        if actor_id is None:
            raise ValueError("Morvarc'h has not appeared")
        kelpie = self.runtime.actors[actor_id]
        if kelpie.metadata.get("monster_id") != KELPIE_ID:
            raise RuntimeError("Nocturne Kelpie state points to the wrong monster")
        return kelpie

    def _spawn_kelpie(self) -> CombatantState:
        if any(actor.metadata.get("monster_id") == KELPIE_ID for actor in self.runtime.actors.values()):
            raise RuntimeError("a Morvarc'h the Lake Kelpie actor already exists in the campaign")
        actor_id = f"fieldboss_kelpie_{uuid.uuid4().hex[:12]}"
        kelpie = CombatantState(
            actor_id=actor_id,
            name="Morvarc'h the Lake Kelpie",
            kind=EntityKind.BOSS,
            level=KELPIE_LEVEL,
            max_hp=12_800,
            hp=12_800,
            strength=72,
            agility=78,
            armor=130,
            evasion=18,
            cursor=CursorColor.RED,
            location_id=LAKE_YOFEL_FOG_BOUNDARY,
            skill_proficiencies={"other": 720.0},
            metadata={
                "monster_id": KELPIE_ID,
                "field_boss": True,
                "night_tameable": True,
                "water_walking": True,
                "lake_yofel_native": True,
                "combat_stats_provenance": "simulation",
            },
        )
        template = self.runtime.catalog.weapons[KELPIE_WEAPON_ID]
        natural = ItemInstance(
            instance_id=f"natural_{uuid.uuid4().hex[:12]}",
            template_id=KELPIE_WEAPON_ID,
            owner_id=actor_id,
            durability=template.base_durability,
            max_durability=template.base_durability,
            metadata={"natural_attack": True},
        )
        kelpie.inventory[natural.instance_id] = natural
        kelpie.equipment["weapon"] = natural.instance_id
        self.runtime.actors[actor_id] = kelpie
        return kelpie

    def open_five_key_backtrack(self, harin_instance_id: str, aghyellr_instance_id: str) -> dict:
        if any(
            row["harin_instance_id"] == harin_instance_id
            and row["aghyellr_instance_id"] == aghyellr_instance_id
            for row in self._states().values()
        ):
            raise ValueError("this Floor 7 handoff already has a Progressive 9 Nocturne instance")
        handoff = self.floor7_campaign.handoff(harin_instance_id, aghyellr_instance_id)
        if handoff["fallenSacredKeyCount"] != 5 or handoff["fiveKeyPursuitContinues"] is not True:
            raise RuntimeError("Floor 7 handoff is not the five-key continuing Elf War state")
        floor4 = self.runtime.world.floors[4]
        if not floor4.unlocked or not floor4.main_town_gate_active:
            raise ValueError("Floor 4 Rovia Teleport Gate must already be active for the backtrack")

        harin = self._harin_state(harin_instance_id)
        if harin["stage"] != "boss_room_reached":
            raise RuntimeError("Floor 7 Harin state no longer matches the validated campaign handoff")
        pursuit = harin["pursuit"]
        player_ids = list(harin["player_ids"])
        kizmel_id = harin["kizmel_actor_id"]
        if not self.runtime.actors[kizmel_id].alive:
            raise ValueError("Kizmel must be alive to continue the Elf War campaign")

        lavik = self._single_alive_actor_for_npc(LAVIK_ID)
        lavik.location_id = LAKE_YOFEL_WEST_SHORE
        lavik.metadata.update(
            {
                "progressive9_nocturne": True,
                "refuses_yofel_castle_entry": True,
                "waiting_for_yofilis_at_lake_yofel": True,
                "nocturne_arrived_yofel_at_ms": self.runtime.world.now_ms,
            }
        )
        self.runtime.npcs.states[LAVIK_ID].location_id = LAKE_YOFEL_WEST_SHORE
        if self.runtime.npcs.states[YOFILIS_ID].location_id != YOFEL_CASTLE:
            raise RuntimeError("the authoritative Yofilis NPC is not at Yofel Castle")
        if self.runtime.npcs.states[CETRANN_ID].location_id != YOFEL_CASTLE:
            raise RuntimeError("Cetrann is not at Yofel Castle")

        instance_id = f"nocturne9_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "harin_instance_id": harin_instance_id,
            "aghyellr_instance_id": aghyellr_instance_id,
            "player_ids": player_ids,
            "kizmel_actor_id": kizmel_id,
            "lavik_actor_id": lavik.actor_id,
            "stage": "five_key_trail_points_to_floor4",
            "opened_at_ms": self.runtime.world.now_ms,
            "floor4_entry_gate_id": ROVIA,
            "target_location_id": LAKE_YOFEL_WEST_SHORE,
            "five_key_count": 5,
            "four_key_bag_instance_id": pursuit["target_key_bag_instance_id"],
            "four_key_bag_owner_id": pursuit["target_key_bag_holder_id"],
            "ruby_key_instance_id": pursuit["ruby_key_instance_id"],
            "ruby_key_owner_id": pursuit["ruby_key_fallen_holder_id"],
            "floor7_civis_actor_id": handoff["civisActorId"],
            "doleful_nocturne_instance_id": handoff["dolefulNocturneInstanceId"],
            "lavik_request_accepted_by_actor_id": None,
            "lavik_request_accepted_at_ms": None,
            "party_arrived_yofel_at_ms": None,
            "cetrann_met_by_actor_id": None,
            "yofilis_meeting_requested_by_actor_id": None,
            "yofilis_meeting_agreed_at_ms": None,
            "search_actor_ids": [],
            "search_equipment_by_actor": {},
            "kelpie_actor_id": None,
            "kelpie_tamed_by_actor_id": None,
            "kelpie_nickname": None,
            "kelpie_search_equipment_restored": False,
            "yofilis_north_beach_at_ms": None,
            "lavik_yofilis_reunited_at_ms": None,
            "lavik_yofilis_duel_promised": False,
            "yofilis_past_opened": False,
            "yofilis_past_facts": [],
            "castle_to_lake_ms": None,
            "lake_to_hideout_ms": None,
            "river_route_segments_ms": {},
            "fallen_hideout_reached_at_ms": None,
        }
        self._states()[instance_id] = state
        self._validate_inherited_keys(state)
        return self.status(instance_id)

    def arrive_lavik_west_shore(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "five_key_trail_points_to_floor4":
            raise ValueError("the Nocturne backtrack is not waiting for the party to reach Lavik")
        self._validate_inherited_keys(state)
        self._require_group_at(state, LAKE_YOFEL_WEST_SHORE)
        lavik = self.runtime.actors[state["lavik_actor_id"]]
        if lavik.location_id != LAKE_YOFEL_WEST_SHORE:
            raise RuntimeError("Lavik is not waiting outside Yofel Castle")
        lead_id = state["player_ids"][0]
        self.runtime.interact_npc(lead_id, LAVIK_ID)
        state["stage"] = "lavik_request_offered"
        state["party_met_lavik_at_ms"] = self.runtime.world.now_ms
        return self.status(instance_id)

    def accept_lavik_request(self, instance_id: str, actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "lavik_request_offered":
            raise ValueError("Lavik has not offered the Nocturne request")
        if actor_id not in state["player_ids"]:
            raise ValueError("Lavik's request must be accepted by a player in this pursuit group")
        if self.runtime.actors[actor_id].location_id != LAKE_YOFEL_WEST_SHORE:
            raise ValueError("Lavik's request is accepted at his Lake Yofel shore camp")
        state["lavik_request_accepted_by_actor_id"] = actor_id
        state["lavik_request_accepted_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "reach_yofel_castle_without_lavik"
        return self.status(instance_id)

    def arrive_yofel_castle(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "reach_yofel_castle_without_lavik":
            raise ValueError("Lavik's request must be accepted before the party enters Yofel Castle")
        self._require_group_at(state, YOFEL_CASTLE)
        lavik = self.runtime.actors[state["lavik_actor_id"]]
        if lavik.location_id != LAKE_YOFEL_WEST_SHORE:
            raise RuntimeError("Lavik entered Yofel Castle despite refusing to do so")
        lead_id = state["player_ids"][0]
        interaction = self.runtime.interact_npc(lead_id, CETRANN_ID)
        state["cetrann_met_by_actor_id"] = lead_id
        state["cetrann_knowledge_tags"] = list(interaction.knowledge_tags)
        state["party_arrived_yofel_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "request_secret_yofilis_meeting"
        return self.status(instance_id)

    def request_yofilis_secret_meeting(self, instance_id: str, actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "request_secret_yofilis_meeting":
            raise ValueError("the party has not reached the private Yofilis request stage")
        if actor_id not in state["player_ids"]:
            raise ValueError("Yofilis must be approached by a player from this Nocturne group")
        if self.runtime.actors[actor_id].location_id != YOFEL_CASTLE:
            raise ValueError("Viscount Yofilis is approached at Yofel Castle")
        interaction = self.runtime.interact_npc(actor_id, YOFILIS_ID)
        state["yofilis_meeting_requested_by_actor_id"] = actor_id
        state["yofilis_meeting_agreed_at_ms"] = self.runtime.world.now_ms
        state["yofilis_knowledge_tags"] = list(interaction.knowledge_tags)
        state["stage"] = "kelpie_search_ready"
        return self.status(instance_id)

    def prepare_kelpie_search(self, instance_id: str, search_actor_ids: list[str]) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "kelpie_search_ready":
            raise ValueError("Yofilis must agree to the secret meeting before the Kelpie search")
        searchers = list(dict.fromkeys(search_actor_ids))
        if not searchers or len(searchers) > 2:
            raise ValueError("the Kelpie search supports one or two player searchers")
        if any(actor_id not in state["player_ids"] for actor_id in searchers):
            raise ValueError("Kelpie searchers must be players from this Nocturne group")
        if state["floor7_civis_actor_id"] not in searchers:
            raise ValueError("the Floor 7 Civis Nocte must join the Kelpie search")
        self._require_actor_ids_at(searchers, YOFEL_CASTLE)

        equipment_by_actor: dict[str, dict[str, str]] = {}
        for actor_id in searchers:
            actor = self.runtime.actors[actor_id]
            equipment_by_actor[actor_id] = dict(actor.equipment)
            for slot in list(actor.equipment):
                self.runtime.unequip_item(actor_id, slot)
            if actor.equipment:
                raise RuntimeError("Kelpie searcher still has visible equipment after stowing all gear")

        travel_together(self.runtime, searchers, LAKE_YOFEL)
        travel_together(self.runtime, searchers, LAKE_YOFEL_FOG_BOUNDARY)
        state["search_actor_ids"] = searchers
        state["search_equipment_by_actor"] = equipment_by_actor
        state["kelpie_search_prepared_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "kelpie_search_prepared"
        return self.status(instance_id)

    def call_kelpie_from_fog(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "kelpie_search_prepared":
            raise ValueError("the Kelpie search has not been prepared")
        self._require_actor_ids_at(state["search_actor_ids"], LAKE_YOFEL_FOG_BOUNDARY)
        if any(self.runtime.actors[actor_id].equipment for actor_id in state["search_actor_ids"]):
            raise ValueError("Morvarc'h will not appear while a searcher has equipment exposed")
        kelpie = self._spawn_kelpie()
        state["kelpie_actor_id"] = kelpie.actor_id
        state["kelpie_appeared_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "kelpie_present"
        return self.status(instance_id)

    def tame_kelpie(self, instance_id: str, actor_id: str, nickname: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "kelpie_present":
            raise ValueError("Morvarc'h is not waiting for a Night-control attempt")
        if actor_id != state["floor7_civis_actor_id"]:
            raise ValueError("this Nocturne tame attempt belongs to the Civis Nocte created on Floor 7")
        if actor_id not in state["search_actor_ids"]:
            raise ValueError("the Civis Nocte is not part of the current Kelpie search")
        actor = self.runtime.actors[actor_id]
        if night_rank(actor) != CIVIS_NOCTE:
            raise ValueError("the recorded Floor 7 Civis actor no longer has Civis Nocte rank")
        clean_name = nickname.strip()
        if not clean_name:
            raise ValueError("a nickname is required when Morvarc'h is tamed")
        kelpie = self._kelpie(state)
        resolution = tame_lower_level_monster(actor, kelpie, now_ms=self.runtime.world.now_ms)
        kelpie.metadata["nickname"] = clean_name
        state["kelpie_tamed_by_actor_id"] = actor_id
        state["kelpie_nickname"] = clean_name
        state["kelpie_tamed_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "kelpie_tamed"
        return {"taming": asdict(resolution), "state": self.status(instance_id)}

    def restore_kelpie_search_equipment(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "kelpie_tamed":
            raise ValueError("Morvarc'h must be tamed before the search equipment is restored")
        self._require_actor_ids_at(state["search_actor_ids"], LAKE_YOFEL_FOG_BOUNDARY)
        for actor_id in state["search_actor_ids"]:
            actor = self.runtime.actors[actor_id]
            expected = state["search_equipment_by_actor"][actor_id]
            if actor.equipment:
                raise RuntimeError("search equipment was changed before the recorded restoration step")
            for expected_slot, instance_id_value in expected.items():
                if instance_id_value not in actor.inventory:
                    raise RuntimeError("recorded pre-search equipment is no longer in the actor inventory")
                self.runtime.equip_item(actor_id, instance_id_value)
                if actor.equipment.get(expected_slot) != instance_id_value:
                    raise RuntimeError("equipment restoration did not return an item to its original slot")
        state["kelpie_search_equipment_restored"] = True
        state["stage"] = "escort_yofilis_to_north_beach"
        return self.status(instance_id)

    def escort_yofilis_to_north_beach(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "escort_yofilis_to_north_beach":
            raise ValueError("the Kelpie must be tamed and search equipment restored first")
        kizmel = self.runtime.actors[state["kizmel_actor_id"]]
        if kizmel.location_id != YOFEL_CASTLE:
            raise ValueError("Kizmel must still be at Yofel Castle to escort Yofilis")
        if self.runtime.npcs.states[YOFILIS_ID].location_id != YOFEL_CASTLE:
            raise RuntimeError("Yofilis is no longer at Yofel Castle before the secret departure")
        self.runtime.advance_world(YOFILIS_TO_NORTH_BEACH_MS)
        kizmel.location_id = LAKE_YOFEL_NORTH_BEACH
        self.runtime.npcs.states[YOFILIS_ID].location_id = LAKE_YOFEL_NORTH_BEACH
        state["yofilis_north_beach_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "ride_kelpie_to_yofilis"
        return self.status(instance_id)

    def ride_kelpie_to_yofilis(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "ride_kelpie_to_yofilis":
            raise ValueError("Yofilis is not waiting at the secluded north beach")
        kelpie = self._kelpie(state)
        if kelpie.metadata.get("night_tamed_by_actor_id") != state["floor7_civis_actor_id"]:
            raise RuntimeError("Morvarc'h is no longer controlled by the Floor 7 Civis")
        self._require_actor_ids_at(state["search_actor_ids"], LAKE_YOFEL_FOG_BOUNDARY)
        if kelpie.location_id != LAKE_YOFEL_FOG_BOUNDARY:
            raise RuntimeError("Morvarc'h is not at the fog boundary with its riders")
        self.runtime.advance_world(KELPIE_FOG_TO_NORTH_BEACH_MS)
        for actor_id in state["search_actor_ids"]:
            self.runtime.actors[actor_id].location_id = LAKE_YOFEL_NORTH_BEACH
        kelpie.location_id = LAKE_YOFEL_NORTH_BEACH
        state["stage"] = "kelpie_at_yofilis_rendezvous"
        return self.status(instance_id)

    def carry_yofilis_to_lavik(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "kelpie_at_yofilis_rendezvous":
            raise ValueError("the Kelpie party has not reached Yofilis")
        actor_ids = list(state["search_actor_ids"]) + [state["kizmel_actor_id"]]
        self._require_actor_ids_at(actor_ids, LAKE_YOFEL_NORTH_BEACH)
        if self.runtime.npcs.states[YOFILIS_ID].location_id != LAKE_YOFEL_NORTH_BEACH:
            raise RuntimeError("Yofilis is not at the north-beach rendezvous")
        kelpie = self._kelpie(state)
        if kelpie.location_id != LAKE_YOFEL_NORTH_BEACH:
            raise RuntimeError("Morvarc'h is not at the north-beach rendezvous")
        lavik = self.runtime.actors[state["lavik_actor_id"]]
        if lavik.location_id != LAKE_YOFEL_WEST_SHORE:
            raise RuntimeError("Lavik left his Lake Yofel meeting point")

        self.runtime.advance_world(KELPIE_NORTH_TO_WEST_SHORE_MS)
        for actor_id in actor_ids:
            self.runtime.actors[actor_id].location_id = LAKE_YOFEL_WEST_SHORE
        kelpie.location_id = LAKE_YOFEL_WEST_SHORE
        self.runtime.npcs.states[YOFILIS_ID].location_id = LAKE_YOFEL_WEST_SHORE
        state["lavik_yofilis_reunited_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "lavik_yofilis_reunited"
        return self.status(instance_id)

    def record_lavik_yofilis_duel_promise(self, instance_id: str, actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "lavik_yofilis_reunited":
            raise ValueError("Lavik and Yofilis have not yet been reunited")
        if actor_id not in state["search_actor_ids"]:
            raise ValueError("a player present at the reunion must witness the duel promise")
        if self.runtime.actors[actor_id].location_id != LAKE_YOFEL_WEST_SHORE:
            raise ValueError("the duel promise is made at Lavik's shore camp")
        self.runtime.interact_npc(actor_id, LAVIK_ID)
        self.runtime.interact_npc(actor_id, YOFILIS_ID)
        state["lavik_yofilis_duel_promised"] = True
        state["duel_promise_recorded_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "return_yofilis_to_castle"
        return self.status(instance_id)

    def return_yofilis_and_open_past(self, instance_id: str, actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "return_yofilis_to_castle":
            raise ValueError("the Lavik/Yofilis reunion must conclude before returning to Yofel Castle")
        if actor_id not in state["search_actor_ids"]:
            raise ValueError("a returning search player must receive Yofilis's history")
        kelpie = self._kelpie(state)
        returning = list(state["search_actor_ids"]) + [state["kizmel_actor_id"]]
        self._require_actor_ids_at(returning, LAKE_YOFEL_WEST_SHORE)
        if kelpie.location_id != LAKE_YOFEL_WEST_SHORE:
            raise RuntimeError("Morvarc'h is not with the returning party")
        if self.runtime.npcs.states[YOFILIS_ID].location_id != LAKE_YOFEL_WEST_SHORE:
            raise RuntimeError("Yofilis is not with the returning party")

        self.runtime.advance_world(KELPIE_WEST_SHORE_RETURN_MS)
        for actor_id_value in returning:
            self.runtime.actors[actor_id_value].location_id = YOFEL_CASTLE
        kelpie.location_id = LAKE_YOFEL
        self.runtime.npcs.states[YOFILIS_ID].location_id = YOFEL_CASTLE
        self.runtime.interact_npc(actor_id, YOFILIS_ID)
        state["yofilis_past_opened"] = True
        state["yofilis_past_facts"] = [
            "Yofilis and Almarc were close in youth before their conflict became entangled with the older elven dispute.",
            "A water spirit and a lethal water-related curse shaped the deaths in Yofilis's family.",
            "The history explains why the apparent age and passage of time among these elven NPCs cannot be treated as ordinary static quest scripting.",
        ]
        state["yofilis_past_opened_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "five_key_hideout_recon_ready"
        return self.status(instance_id)

    def embark_five_key_hideout_recon(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "five_key_hideout_recon_ready":
            raise ValueError("the Lavik/Yofilis chapter must reach its return-to-castle point before key pursuit resumes")
        self._validate_inherited_keys(state)
        self._require_group_at(state, YOFEL_CASTLE)
        resolution = travel_together(self.runtime, self._group_actor_ids(state), LAKE_YOFEL)
        state["castle_to_lake_ms"] = resolution.elapsed_ms
        state["stage"] = "five_key_hideout_recon_on_lake"
        return self.status(instance_id)

    def follow_river_ull_to_fallen_hideout(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "five_key_hideout_recon_on_lake":
            raise ValueError("the Nocturne group must begin the hideout route from Lake Yofel")
        self._validate_inherited_keys(state)
        group = self._group_actor_ids(state)
        self._require_group_at(state, LAKE_YOFEL)

        river = travel_together(self.runtime, group, RIVER_ULL)
        caldera = travel_together(self.runtime, group, CALDERA_LAKE)
        forest = travel_together(self.runtime, group, BEAR_FOREST)
        hideout = travel_together(self.runtime, group, FALLEN_HIDEOUT)
        segments = {
            "lake_yofel_to_river_ull": river.elapsed_ms,
            "river_ull_to_caldera_lake": caldera.elapsed_ms,
            "caldera_lake_to_bear_forest": forest.elapsed_ms,
            "bear_forest_to_fallen_hideout": hideout.elapsed_ms,
        }
        total = sum(segments.values())
        if total != 60 * 60_000:
            raise RuntimeError("Floor 4 Nocturne water-route corpus no longer preserves the one-hour route")
        state["river_route_segments_ms"] = segments
        state["lake_to_hideout_ms"] = total
        state["fallen_hideout_reached_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "floor4_fallen_hideout_reached"
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        self._validate_inherited_keys(state)
        group_locations = {
            actor_id: self.runtime.actors[actor_id].location_id
            for actor_id in self._group_actor_ids(state)
        }
        lavik = self.runtime.actors[state["lavik_actor_id"]]
        yofilis_state = self.runtime.npcs.states[YOFILIS_ID]
        cetrann_state = self.runtime.npcs.states[CETRANN_ID]
        kelpie_state = None
        if state["kelpie_actor_id"] is not None:
            kelpie = self._kelpie(state)
            kelpie_state = {
                "actor_id": kelpie.actor_id,
                "level": kelpie.level,
                "hp": kelpie.hp,
                "max_hp": kelpie.max_hp,
                "alive": kelpie.alive,
                "cursor": kelpie.cursor.value,
                "location_id": kelpie.location_id,
                "night_tamed_by_actor_id": kelpie.metadata.get("night_tamed_by_actor_id"),
                "nickname": kelpie.metadata.get("nickname"),
                "water_walking": kelpie.metadata.get("water_walking"),
            }
        return {
            **state,
            "group_locations": group_locations,
            "lavik_location_id": lavik.location_id,
            "yofilis_location_id": yofilis_state.location_id,
            "cetrann_location_id": cetrann_state.location_id,
            "kelpie": kelpie_state,
            "five_key_assets_intact": True,
            "next_stage": (
                "use the active Floor 4 gate and existing roads to reach Lavik on Lake Yofel's west shore"
                if state["stage"] == "five_key_trail_points_to_floor4"
                else "hear Lavik's request to bring Yofilis without guards or attendants"
                if state["stage"] == "lavik_request_offered"
                else "continue into Yofel Castle while Lavik remains outside"
                if state["stage"] == "reach_yofel_castle_without_lavik"
                else "ask Viscount Yofilis to leave the castle for a secret meeting"
                if state["stage"] == "request_secret_yofilis_meeting"
                else "choose one or two players including the Civis Nocte and stow equipment for the fog-bound Kelpie search"
                if state["stage"] == "kelpie_search_ready"
                else "wait in the deep fog with all search equipment stowed until Morvarc'h appears"
                if state["stage"] == "kelpie_search_prepared"
                else "tame Morvarc'h through Night monster control or engage it through ordinary combat"
                if state["stage"] == "kelpie_present"
                else "restore the exact equipment stowed before the Kelpie search"
                if state["stage"] == "kelpie_tamed"
                else "have Kizmel escort Yofilis to the secluded north beach"
                if state["stage"] == "escort_yofilis_to_north_beach"
                else "ride the tamed Kelpie from the fog boundary to Yofilis"
                if state["stage"] == "ride_kelpie_to_yofilis"
                else "carry Yofilis and Kizmel across Lake Yofel to Lavik"
                if state["stage"] == "kelpie_at_yofilis_rendezvous"
                else "witness Lavik and Yofilis agree to settle their dispute by a future duel"
                if state["stage"] == "lavik_yofilis_reunited"
                else "return Yofilis to Yofel Castle and hear the history behind the dispute"
                if state["stage"] == "return_yofilis_to_castle"
                else "reassemble the full pursuit group and embark from Yofel Castle to resume the five-key investigation"
                if state["stage"] == "five_key_hideout_recon_ready"
                else "follow River Ull and the old Floor 4 waterways toward the submerged Fallen Elf hideout"
                if state["stage"] == "five_key_hideout_recon_on_lake"
                else None
            ),
        }


def install_floor4_nocturne_scenario(runtime, floor7_campaign) -> Floor4NocturneScenario:
    required_locations = {
        YOFEL_CASTLE,
        LAKE_YOFEL,
        RIVER_ULL,
        CALDERA_LAKE,
        BEAR_FOREST,
        FALLEN_HIDEOUT,
        LAKE_YOFEL_WEST_SHORE,
        LAKE_YOFEL_NORTH_BEACH,
        LAKE_YOFEL_FOG_BOUNDARY,
    }
    missing = sorted(required_locations - set(runtime.world_map.locations))
    if missing:
        raise RuntimeError(f"Floor 4 Nocturne world corpus is incomplete: {missing}")
    for npc_id in (YOFILIS_ID, CETRANN_ID, LAVIK_ID):
        if npc_id not in runtime.npcs.definitions:
            raise RuntimeError(f"Progressive 9 NPC corpus was not loaded: {npc_id}")
    if KELPIE_WEAPON_ID not in runtime.catalog.weapons:
        raise RuntimeError("Morvarc'h natural weapon corpus was not loaded")
    return Floor4NocturneScenario(runtime, floor7_campaign)