from __future__ import annotations

import uuid

from sao_mcp.corpus.floor4_nocturne import (
    BEAR_FOREST,
    CALDERA_LAKE,
    FALLEN_HIDEOUT,
    LAKE_YOFEL,
    RIVER_ULL,
    YOFEL_CASTLE,
    YOFILIS_ID,
)
from sao_mcp.corpus.floor6_elfwar import SACRED_KEY_BAG_ID
from sao_mcp.corpus.floor7_elfwar import LAVIK_ID
from sao_mcp.corpus.floor7_pursuit import RUBY_KEY_ID
from sao_mcp.rules.group_travel import travel_together


ROVIA = "floor_4_rovia"
USCO = "floor_4_usco"


class Floor4NocturneScenario:
    """Progressive 9 entry: five-key trail backtracks to Floor 4, Lavik, Yofilis and Lake Yofel."""

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

    def _require_group_at(self, state: dict, location_id: str) -> None:
        actor_ids = self._group_actor_ids(state)
        wrong = [
            actor_id
            for actor_id in actor_ids
            if self.runtime.actors[actor_id].location_id != location_id
        ]
        if wrong:
            raise ValueError(
                f"Nocturne group actors are not all at {location_id}: {', '.join(wrong)}"
            )

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

    def open_five_key_backtrack(self, harin_instance_id: str, aghyellr_instance_id: str) -> dict:
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
        lavik.location_id = YOFEL_CASTLE
        lavik.metadata.update(
            {
                "progressive9_nocturne": True,
                "returned_to_floor4_for_yofilis": True,
                "nocturne_arrived_yofel_at_ms": self.runtime.world.now_ms,
            }
        )
        self.runtime.npcs.states[LAVIK_ID].location_id = YOFEL_CASTLE
        self.runtime.npcs.states[YOFILIS_ID].location_id = YOFEL_CASTLE

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
            "target_location_id": YOFEL_CASTLE,
            "five_key_count": 5,
            "four_key_bag_instance_id": pursuit["target_key_bag_instance_id"],
            "four_key_bag_owner_id": pursuit["target_key_bag_holder_id"],
            "ruby_key_instance_id": pursuit["ruby_key_instance_id"],
            "ruby_key_owner_id": pursuit["ruby_key_fallen_holder_id"],
            "floor7_civis_actor_id": handoff["civisActorId"],
            "doleful_nocturne_instance_id": handoff["dolefulNocturneInstanceId"],
            "lavik_request_accepted_by_actor_id": None,
            "lavik_request_accepted_at_ms": None,
            "yofilis_met_by_actor_id": None,
            "yofilis_met_at_ms": None,
            "ancient_elven_dispute_opened": False,
            "castle_to_lake_ms": None,
            "lake_to_hideout_ms": None,
            "river_route_segments_ms": {},
            "fallen_hideout_reached_at_ms": None,
        }
        self._states()[instance_id] = state
        self._validate_inherited_keys(state)
        return self.status(instance_id)

    def arrive_yofel_castle(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "five_key_trail_points_to_floor4":
            raise ValueError("the Nocturne backtrack is not waiting for the party at Yofel Castle")
        self._validate_inherited_keys(state)
        self._require_group_at(state, YOFEL_CASTLE)
        lavik = self.runtime.actors[state["lavik_actor_id"]]
        if lavik.location_id != YOFEL_CASTLE:
            raise RuntimeError("Lavik is not at Yofel Castle for his Progressive 9 request")
        lead_id = state["player_ids"][0]
        self.runtime.interact_npc(lead_id, LAVIK_ID)
        state["stage"] = "lavik_request_offered"
        state["party_arrived_yofel_at_ms"] = self.runtime.world.now_ms
        return self.status(instance_id)

    def accept_lavik_request(self, instance_id: str, actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "lavik_request_offered":
            raise ValueError("Lavik has not offered the Nocturne request")
        if actor_id not in state["player_ids"]:
            raise ValueError("Lavik's request must be accepted by a player in this pursuit group")
        if self.runtime.actors[actor_id].location_id != YOFEL_CASTLE:
            raise ValueError("Lavik's request is accepted at Yofel Castle")
        state["lavik_request_accepted_by_actor_id"] = actor_id
        state["lavik_request_accepted_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "meet_viscount_yofilis"
        return self.status(instance_id)

    def meet_yofilis(self, instance_id: str, actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "meet_viscount_yofilis":
            raise ValueError("Lavik's request must be accepted before meeting Viscount Yofilis")
        if actor_id not in state["player_ids"]:
            raise ValueError("Yofilis must be met by a player from this Nocturne group")
        if self.runtime.actors[actor_id].location_id != YOFEL_CASTLE:
            raise ValueError("Viscount Yofilis is met at Yofel Castle")
        interaction = self.runtime.interact_npc(actor_id, YOFILIS_ID)
        state["yofilis_met_by_actor_id"] = actor_id
        state["yofilis_met_at_ms"] = self.runtime.world.now_ms
        state["ancient_elven_dispute_opened"] = True
        state["yofilis_knowledge_tags"] = list(interaction.knowledge_tags)
        state["stage"] = "lake_yofel_recon_ready"
        return self.status(instance_id)

    def embark_lake_yofel(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "lake_yofel_recon_ready":
            raise ValueError("the Yofilis meeting must occur before entering Lake Yofel")
        self._require_group_at(state, YOFEL_CASTLE)
        resolution = travel_together(self.runtime, self._group_actor_ids(state), LAKE_YOFEL)
        state["castle_to_lake_ms"] = resolution.elapsed_ms
        state["stage"] = "lake_yofel_recon"
        return self.status(instance_id)

    def follow_river_ull_to_fallen_hideout(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "lake_yofel_recon":
            raise ValueError("the Nocturne group must begin from Lake Yofel")
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
        return {
            **state,
            "group_locations": group_locations,
            "lavik_location_id": lavik.location_id,
            "yofilis_location_id": yofilis_state.location_id,
            "five_key_assets_intact": True,
            "next_stage": (
                "use the active Floor 4 Teleport Gate and existing roads to reach Yofel Castle"
                if state["stage"] == "five_key_trail_points_to_floor4"
                else "hear Lavik's request at Yofel Castle"
                if state["stage"] == "lavik_request_offered"
                else "meet Viscount Yofilis"
                if state["stage"] == "meet_viscount_yofilis"
                else "embark from Yofel Castle onto Lake Yofel"
                if state["stage"] == "lake_yofel_recon_ready"
                else "follow River Ull and the old Floor 4 waterways toward the submerged Fallen Elf hideout"
                if state["stage"] == "lake_yofel_recon"
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
    }
    missing = sorted(required_locations - set(runtime.world_map.locations))
    if missing:
        raise RuntimeError(f"Floor 4 Nocturne world corpus is incomplete: {missing}")
    if YOFILIS_ID not in runtime.npcs.definitions:
        raise RuntimeError("Viscount Yofilis NPC corpus was not loaded")
    if LAVIK_ID not in runtime.npcs.definitions:
        raise RuntimeError("Lavik NPC corpus was not loaded")
    return Floor4NocturneScenario(runtime, floor7_campaign)
