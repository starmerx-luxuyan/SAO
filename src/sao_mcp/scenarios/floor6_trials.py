from __future__ import annotations

import uuid
from collections import deque

from sao_mcp.corpus.floor6_ambush import IRON_KEY_ID
from sao_mcp.corpus.floor6_stachion import GOLDEN_KEY_ID, QUEST_ID
from sao_mcp.corpus.floor6_trials import BARRO_ID, MYIA_ID, TERRO_ID, THEANO_IRON_KEY_ID
from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import (
    CombatantState,
    CursorColor,
    EntityKind,
    ItemInstance,
    Provenance,
    ProvenanceKind,
    ZoneKind,
)


STACHION = "floor_6_stachion"
PUZZLE_QUARTER = "floor_6_stachion_puzzle_quarter"
CYLON_MANOR = "floor_6_cylon_lord_manor"
MYIA_HOUSE = "floor_6_myia_house"
DUNGEON_ENTRANCE = "floor_6_dungeon_of_trials_entrance"
DUNGEON_OF_TRIALS = "floor_6_dungeon_of_trials"
DUNGEON_SECRET_BACK_DOOR = "floor_6_dungeon_of_trials_secret_back_door"
DUNGEON_FINAL_CHAMBER = "floor_6_dungeon_of_trials_final_chamber"


class Floor6TrialsScenario:
    """Release-route bridge from Cylon's death through Myia, Terro and the empty final chamber."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self._seed_world()

    def _seed_world(self) -> None:
        source = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
        locations = {
            MYIA_HOUSE: LocationDefinition(
                MYIA_HOUSE,
                6,
                "Myia and Theano's House",
                ZoneKind.SAFE_TOWN,
                safe_zone=True,
                provenance=Provenance(
                    ProvenanceKind.CANON_INFERRED,
                    sources=(source,),
                    notes="Theano's home in Stachion where Myia receives her mother's note and iron key; exact street placement is abstracted.",
                ),
            ),
            DUNGEON_ENTRANCE: LocationDefinition(
                DUNGEON_ENTRANCE,
                6,
                "Dungeon of Trials - Main Entrance",
                ZoneKind.DUNGEON,
                provenance=Provenance(
                    ProvenanceKind.CANON_INFERRED,
                    sources=(source,),
                    notes="Main basement entrance beneath the Stachion lord's mansion. The golden key from Suribus opens this original-route entrance; the release route does not enter here.",
                ),
            ),
            DUNGEON_OF_TRIALS: LocationDefinition(
                DUNGEON_OF_TRIALS,
                6,
                "Dungeon of Trials",
                ZoneKind.DUNGEON,
                provenance=Provenance(
                    ProvenanceKind.CANON,
                    sources=(source,),
                    notes="Puzzle-filled dungeon beneath the Stachion lord's mansion. The release-route party bypasses its ordinary puzzle and monster route through a secret rear entrance.",
                ),
            ),
            DUNGEON_SECRET_BACK_DOOR: LocationDefinition(
                DUNGEON_SECRET_BACK_DOOR,
                6,
                "Dungeon of Trials - Secret Back Door",
                ZoneKind.DUNGEON,
                provenance=Provenance(
                    ProvenanceKind.CANON_INFERRED,
                    sources=(source,),
                    notes="Hidden rear entrance beneath a movable statue base in the manor garden. Terro reveals it in the release route.",
                ),
            ),
            DUNGEON_FINAL_CHAMBER: LocationDefinition(
                DUNGEON_FINAL_CHAMBER,
                6,
                "Dungeon of Trials - Final Chamber",
                ZoneKind.DUNGEON,
                provenance=Provenance(
                    ProvenanceKind.CANON,
                    sources=(source,),
                    notes="Deepest chamber of the Dungeon of Trials. The secret rear route reaches it directly, bypassing the ordinary puzzle, ghost and monster sequence.",
                ),
            ),
        }
        for location_id, location in locations.items():
            self.runtime.world_map.locations.setdefault(location_id, location)

        p = Provenance(
            ProvenanceKind.SIMULATION,
            sources=(source,),
            notes="Short local travel durations are simulation; endpoint relationships are canon-backed.",
        )
        self._add_edges(
            (
                TravelConnection(STACHION, MYIA_HOUSE, 5 * 60_000, provenance=p),
                TravelConnection(CYLON_MANOR, DUNGEON_ENTRANCE, 2 * 60_000, provenance=p),
            )
        )

    def _add_edges(self, edges: tuple[TravelConnection, ...]) -> None:
        existing = {(edge.from_location_id, edge.to_location_id) for edge in self.runtime.world_map.connections}
        for edge in edges:
            if (edge.from_location_id, edge.to_location_id) in existing:
                continue
            self.runtime.world_map.connections = tuple(self.runtime.world_map.connections) + (edge,)
            self.runtime.world_map.adjacency.setdefault(edge.from_location_id, []).append(edge)
            if edge.bidirectional:
                self.runtime.world_map.adjacency.setdefault(edge.to_location_id, []).append(
                    TravelConnection(
                        edge.to_location_id,
                        edge.from_location_id,
                        edge.travel_ms,
                        True,
                        edge.requires_floor_unlocked,
                        edge.provenance,
                    )
                )
            existing.add((edge.from_location_id, edge.to_location_id))

    def _state(self, actor_id: str) -> dict:
        states = self.runtime.world.global_flags.setdefault("floor6_stachion_quest_states", {})
        try:
            return states[actor_id]
        except KeyError as exc:
            raise ValueError("Curse of Stachion has not been started") from exc

    def _require_release_route(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        allowed = {
            "post_ambush_loot_recovered",
            "myia_met_paired_keys",
            "seek_barro_after_theano_note",
            "seek_terro_at_manor",
            "secret_back_door_revealed",
            "theano_golden_cube_missing",
        }
        if state.get("stage") not in allowed:
            raise ValueError("the release-route Myia investigation begins after Cylon's ambush has been resolved")
        return state

    def _find_player_item(self, actor_id: str, template_id: str) -> ItemInstance:
        actor = self.runtime.actors[actor_id]
        item = next((item for item in actor.inventory.values() if item.template_id == template_id), None)
        if item is None:
            raise ValueError(f"actor does not possess required item: {template_id}")
        return item

    def _create_myia_actor(self, location_id: str) -> CombatantState:
        actor_id = f"questnpc_myia_{uuid.uuid4().hex[:12]}"
        myia = CombatantState(
            actor_id=actor_id,
            name="Myia",
            kind=EntityKind.NPC,
            level=42,
            max_hp=6100,
            hp=6100,
            strength=40,
            agility=63,
            armor=120,
            evasion=16,
            cursor=CursorColor.YELLOW,
            location_id=location_id,
            metadata={
                "npc_definition_id": MYIA_ID,
                "quest_id": QUEST_ID,
                "skilled_swordswoman": True,
                "wearing_gas_mask": True,
                "combat_stats_provenance": "simulation",
            },
        )
        key = ItemInstance(
            instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
            template_id=THEANO_IRON_KEY_ID,
            owner_id=actor_id,
            metadata={"paired_with_template_id": IRON_KEY_ID, "inherited_from_theano": True},
        )
        myia.inventory[key.instance_id] = key
        self.runtime.actors[actor_id] = myia
        return myia

    def meet_myia(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._require_release_route(actor_id)
        if state["stage"] != "post_ambush_loot_recovered":
            return self.status(actor_id)
        if actor.location_id not in {STACHION, MYIA_HOUSE}:
            raise ValueError("Myia's release-route meeting occurs in Stachion")
        self._find_player_item(actor_id, IRON_KEY_ID)
        myia = self._create_myia_actor(actor.location_id)
        state["stage"] = "myia_met_paired_keys"
        state["myia_actor_id"] = myia.actor_id
        state["myia_met_at_ms"] = self.runtime.world.now_ms
        state["myia_asks_player_to_keep_cylon_key"] = True
        return self.status(actor_id)

    def _route_to(self, start: str, target: str) -> tuple[str | None, int | None]:
        if start == target:
            return None, 0
        queue = deque([(start, None, 0)])
        visited = {start}
        while queue:
            node, first_hop, distance = queue.popleft()
            for edge in self.runtime.world_map.adjacency.get(node, ()):
                nxt = edge.to_location_id
                if nxt in visited:
                    continue
                next_first = nxt if first_hop is None else first_hop
                if nxt == target:
                    return next_first, distance + 1
                visited.add(nxt)
                queue.append((nxt, next_first, distance + 1))
        return None, None

    def paired_iron_key_signal(self, actor_id: str) -> dict:
        state = self._require_release_route(actor_id)
        player = self.runtime.actors[actor_id]
        player_key = self._find_player_item(actor_id, IRON_KEY_ID)
        myia_id = state.get("myia_actor_id")
        if not myia_id or myia_id not in self.runtime.actors:
            raise ValueError("Myia and Theano's paired iron key have not entered the current quest route")
        myia = self.runtime.actors[myia_id]
        theano_key = next(
            (item for item in myia.inventory.values() if item.template_id == THEANO_IRON_KEY_ID),
            None,
        )
        if theano_key is None:
            raise ValueError("Myia is no longer carrying Theano's iron key")
        next_hop, hops = self._route_to(str(player.location_id), str(myia.location_id))
        if hops is None:
            resonance = "unreachable"
        elif hops == 0:
            resonance = "strong"
        elif hops <= 2:
            resonance = "clear"
        elif hops <= 4:
            resonance = "moderate"
        else:
            resonance = "faint"
        return {
            "player_key_instance_id": player_key.instance_id,
            "theano_key_instance_id": theano_key.instance_id,
            "player_location_id": player.location_id,
            "paired_key_location_id": myia.location_id,
            "direction_next_location_id": next_hop,
            "route_hops": hops,
            "resonance": resonance,
            "canon_mechanic": {
                "vibration_indicates_direction": True,
                "sound_resonance_indicates_distance": True,
            },
            "simulation_mapping": "world-graph hop count is used only to turn the canon qualitative signal into a playable route hint",
        }

    def hear_theano_note(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._require_release_route(actor_id)
        if state["stage"] != "myia_met_paired_keys":
            raise ValueError("Myia must first compare the paired iron keys with the player")
        myia = self.runtime.actors[state["myia_actor_id"]]
        if actor.location_id != myia.location_id:
            raise ValueError("actor must be with Myia to hear Theano's disappearance account")
        state["stage"] = "seek_barro_after_theano_note"
        state["theano_note_learned_at_ms"] = self.runtime.world.now_ms
        state["theano_note_facts"] = [
            "Theano apologised to Myia and revealed the truth of the traveller murder",
            "Theano left her iron key to Myia and then disappeared",
            "the note told Myia to visit Barro if Theano did not return",
        ]
        return self.status(actor_id)

    def consult_barro(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._require_release_route(actor_id)
        if state["stage"] != "seek_barro_after_theano_note":
            raise ValueError("Theano's note must point the investigation toward Barro first")
        if actor.location_id != PUZZLE_QUARTER:
            raise ValueError("Barro is consulted in Stachion after Myia shares Theano's note")
        self.runtime.interact_npc(actor_id, BARRO_ID)
        state["stage"] = "seek_terro_at_manor"
        state["barro_consulted_at_ms"] = self.runtime.world.now_ms
        state["barro_facts"] = [
            "Barro's son Terro is the current gardener at Cylon's manor",
            "Terro knows the manor garden and can reveal the hidden route beneath it",
        ]
        return self.status(actor_id)

    def consult_terro(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._require_release_route(actor_id)
        if state["stage"] != "seek_terro_at_manor":
            raise ValueError("Barro must direct the investigation to Terro first")
        if actor.location_id != CYLON_MANOR:
            raise ValueError("Terro is found at Cylon's manor garden")
        self.runtime.interact_npc(actor_id, TERRO_ID)
        p = Provenance(
            ProvenanceKind.SIMULATION,
            sources=("Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)",),
            notes="Traversal durations are simulation; Terro revealing the movable statue-base secret route is canon.",
        )
        self._add_edges(
            (
                TravelConnection(CYLON_MANOR, DUNGEON_SECRET_BACK_DOOR, 1 * 60_000, provenance=p),
                TravelConnection(DUNGEON_SECRET_BACK_DOOR, DUNGEON_FINAL_CHAMBER, 2 * 60_000, provenance=p),
            )
        )
        state["stage"] = "secret_back_door_revealed"
        state["terro_consulted_at_ms"] = self.runtime.world.now_ms
        state["secret_route_facts"] = [
            "Terro shifts the base of a stone statue in the manor garden",
            "the hidden rear entrance reaches the Dungeon of Trials final chamber directly",
            "the route bypasses the ordinary puzzles, ghosts and monsters",
        ]
        return self.status(actor_id)

    def open_dungeon_of_trials_main_entrance(self, actor_id: str) -> dict:
        """Open the original-route main entrance without advancing the release-route state machine."""
        actor = self.runtime.actors[actor_id]
        if actor.location_id != DUNGEON_ENTRANCE:
            raise ValueError("the golden key is used at the main Dungeon of Trials entrance")
        golden_key = self._find_player_item(actor_id, GOLDEN_KEY_ID)
        p = Provenance(
            ProvenanceKind.SIMULATION,
            sources=("Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)",),
            notes="Door traversal time is simulation; the golden key's main-entrance role is canon-backed.",
        )
        self._add_edges((TravelConnection(DUNGEON_ENTRANCE, DUNGEON_OF_TRIALS, 1 * 60_000, provenance=p),))
        golden_key.metadata["opened_dungeon_of_trials_main_entrance"] = True
        return {
            "actor_id": actor_id,
            "main_entrance_open": True,
            "golden_key_instance_id": golden_key.instance_id,
            "release_route_stage": self._state(actor_id).get("stage"),
        }

    def inspect_release_final_chamber(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._require_release_route(actor_id)
        if state["stage"] != "secret_back_door_revealed":
            raise ValueError("Terro must reveal the secret back door before the final chamber can be checked")
        if actor.location_id != DUNGEON_FINAL_CHAMBER:
            raise ValueError("actor must reach the Dungeon of Trials final chamber through the secret route")
        state["stage"] = "theano_golden_cube_missing"
        state["final_chamber_checked_at_ms"] = self.runtime.world.now_ms
        state["release_final_chamber_facts"] = [
            "the secret route bypassed the ordinary Dungeon of Trials sequence",
            "Theano is no longer in the final chamber",
            "the Golden Cube is gone from its former resting place",
            "Theano reached the chamber first and left with the Golden Cube",
        ]
        state["next_investigation"] = "track Theano and the Golden Cube toward the southern areas of Floor 6"
        return self.status(actor_id)

    def status(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        actor = self.runtime.actors[actor_id]
        progress = self.runtime.quests.progress_by_actor.get(actor_id, {}).get(QUEST_ID)
        myia = self.runtime.actors.get(state.get("myia_actor_id")) if state.get("myia_actor_id") else None
        return {
            "actor_id": actor_id,
            "stage": state.get("stage"),
            "myia_actor_id": state.get("myia_actor_id"),
            "myia_location_id": myia.location_id if myia else None,
            "myia_asks_player_to_keep_cylon_key": bool(state.get("myia_asks_player_to_keep_cylon_key")),
            "secret_back_door_revealed": state.get("stage") in {"secret_back_door_revealed", "theano_golden_cube_missing"},
            "final_chamber_checked": state.get("stage") == "theano_golden_cube_missing",
            "theano_missing_with_golden_cube": state.get("stage") == "theano_golden_cube_missing",
            "quest_progress": dict(progress.counters) if progress else None,
            "ready_to_claim": self.runtime.quests.ready_to_claim(actor, QUEST_ID) if progress else False,
            "next_stage": (
                "compare the two iron keys and hear Theano's note" if state.get("stage") == "myia_met_paired_keys"
                else "consult Barro" if state.get("stage") == "seek_barro_after_theano_note"
                else "consult Terro at Cylon's manor" if state.get("stage") == "seek_terro_at_manor"
                else "enter the secret back door and reach the final chamber" if state.get("stage") == "secret_back_door_revealed"
                else "track Theano and the Golden Cube south" if state.get("stage") == "theano_golden_cube_missing"
                else None
            ),
        }


def install_floor6_trials_scenario(runtime) -> Floor6TrialsScenario:
    required_items = {IRON_KEY_ID, GOLDEN_KEY_ID, THEANO_IRON_KEY_ID}
    if any(template_id not in runtime.catalog.items for template_id in required_items):
        raise RuntimeError("Floor 6 paired-key/Dungeon of Trials item corpus was not loaded")
    required_npcs = {MYIA_ID, BARRO_ID, TERRO_ID}
    if any(npc_id not in runtime.npcs.definitions for npc_id in required_npcs):
        raise RuntimeError("Floor 6 Myia/Barro/Terro NPC corpus was not loaded")
    return Floor6TrialsScenario(runtime)
