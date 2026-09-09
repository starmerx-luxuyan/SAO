from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6_elfwar import KYSARAH_ID, SACRED_KEY_BAG_ID
from sao_mcp.corpus.floor7_monsters import AINCRAD_MONSTERS
from sao_mcp.corpus.floor7_pursuit import (
    ANT_TUNNEL_VALLEY,
    FIELD_OF_BONES,
    LABYRINTH,
    MAP_OF_SCYIA_ID,
    RUBY_KEY_ID,
)
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.duels import DuelMode
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.rules.inventory import add_item, transfer_item


CASINO = "floor_7_volupta_grand_casino"
VOLUPTA = "floor_7_volupta"
WATCH_HILL = "floor_7_field_of_bones_watch_hill"
DRAGON_BONE = "floor_7_dragon_bone"
PLATEAU = "floor_7_ant_tunnel_plateau"
BOSS_ROOM = "floor_7_boss_room"

MAP_RESPONSE_MS = 3 * 60_000
MAP_CONFIRM_WAIT_MS = 5 * 60_000
RENDEZVOUS_PREPARATION_MS = 30 * 60_000
FALLEN_RENDEZVOUS_OBSERVE_MS = 5 * 60_000
TRAIL_MARGIN_MS = 3 * 60_000


class Floor7PursuitScenario:
    """Continue the Harin Elf War state through the Scyia-map Fallen Elf pursuit."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def _harin_states(self) -> dict:
        try:
            return self.runtime.world.global_flags["floor7_harin_escape_instances"]
        except KeyError as exc:
            raise RuntimeError("Floor 7 Harin escape state has not been created") from exc

    def _state(self, instance_id: str) -> dict:
        return self._harin_states()[instance_id]

    def _eligible_harin_state(self, lead_actor_id: str, duel_partner_id: str) -> dict:
        participant_ids = {lead_actor_id, duel_partner_id}
        matches = [
            state
            for state in self._harin_states().values()
            if state["stage"] == "returned_to_volupta_with_kizmel"
            and participant_ids.issubset(set(state["player_ids"]))
        ]
        if len(matches) != 1:
            raise ValueError(
                "Scyia negotiation requires exactly one returned Harin escape instance containing both duel players"
            )
        return matches[0]

    def _kizmel(self, state: dict) -> CombatantState:
        kizmel = self.runtime.actors[state["kizmel_actor_id"]]
        if not kizmel.alive:
            raise ValueError("Kizmel must be alive to continue the sacred-key pursuit")
        if not kizmel.metadata.get("must_recover_sacred_keys_to_clear_name"):
            raise ValueError("Kizmel has not reached the fugitive sacred-key recovery stage")
        return kizmel

    def _target_key_bag(self) -> tuple[CombatantState, ItemInstance]:
        matches: list[tuple[CombatantState, ItemInstance]] = []
        for actor in self.runtime.actors.values():
            if actor.metadata.get("npc_definition_id") != KYSARAH_ID:
                continue
            for item in actor.inventory.values():
                if item.template_id == SACRED_KEY_BAG_ID and item.metadata.get("stolen_by_kysarah") is True:
                    matches.append((actor, item))
        if not matches:
            raise ValueError(
                "the actual Floor 6 four-sacred-key bag stolen by Kysarah is absent; "
                "the Floor 7 sacred-key pursuit cannot proceed"
            )
        if len(matches) != 1:
            raise RuntimeError("multiple authoritative Kysarah four-sacred-key bags exist")
        return matches[0]

    def _map_owner(self, map_instance_id: str) -> CombatantState:
        owners = [actor for actor in self.runtime.actors.values() if map_instance_id in actor.inventory]
        if len(owners) != 1:
            raise RuntimeError("the Map of Scyia must have exactly one inventory owner")
        return owners[0]

    def _ruby_key_owner(self, instance_id: str) -> CombatantState:
        owners = [actor for actor in self.runtime.actors.values() if instance_id in actor.inventory]
        if len(owners) != 1:
            raise RuntimeError("the Ruby Key must have exactly one inventory owner")
        return owners[0]

    def _seed_ruby_key_retrieval_team(self) -> tuple[CombatantState, ItemInstance]:
        existing = [
            item
            for actor in self.runtime.actors.values()
            for item in actor.inventory.values()
            if item.template_id == RUBY_KEY_ID
        ]
        if existing:
            raise RuntimeError("a Ruby Key instance already exists in the campaign")
        courier = CombatantState(
            actor_id=f"darkelf7_ruby_courier_{uuid.uuid4().hex[:10]}",
            name="Dark Elf Ruby Key Retrieval Team",
            kind=EntityKind.NPC,
            level=24,
            max_hp=6400,
            hp=6400,
            strength=58,
            agility=60,
            armor=150,
            evasion=12,
            cursor=CursorColor.YELLOW,
            location_id="floor_7_field",
            metadata={
                "dark_elf": True,
                "ruby_key_retrieval_team": True,
                "combat_stats_provenance": "simulation",
            },
        )
        ruby = ItemInstance(
            instance_id=f"rubykey_{uuid.uuid4().hex[:12]}",
            template_id=RUBY_KEY_ID,
            owner_id=courier.actor_id,
            metadata={
                "retrieved_by_dark_elves": True,
                "fallen_control": False,
            },
        )
        add_item(courier, ruby, self.runtime.catalog, allow_overweight=True)
        self.runtime.actors[courier.actor_id] = courier
        return courier, ruby

    def _resolve_ruby_key_loss(self, state: dict) -> None:
        pursuit = state["pursuit"]
        if pursuit["ruby_key_status"] != "dark_elf_retrieval_team":
            raise RuntimeError("Ruby Key loss can only resolve from the Dark Elf retrieval-team state")
        courier = self.runtime.actors[pursuit["ruby_key_courier_actor_id"]]
        ruby = courier.inventory[pursuit["ruby_key_instance_id"]]
        if ruby.template_id != RUBY_KEY_ID:
            raise RuntimeError("the recorded Ruby Key instance has the wrong template")

        raider = CombatantState(
            actor_id=f"fallen7_ruby_raider_{uuid.uuid4().hex[:10]}",
            name="Fallen Elf Ruby Key Raider",
            kind=EntityKind.NPC,
            level=25,
            max_hp=6800,
            hp=6800,
            strength=62,
            agility=70,
            armor=145,
            evasion=16,
            cursor=CursorColor.YELLOW,
            location_id="floor_7_field",
            metadata={
                "fallen_elf": True,
                "ruby_key_ambush_participant": True,
                "combat_stats_provenance": "simulation",
            },
        )
        self.runtime.actors[raider.actor_id] = raider
        moved = transfer_item(
            courier,
            raider,
            ruby.instance_id,
            self.runtime.catalog,
            allow_destination_overweight=True,
        )
        moved.metadata.update(
            {
                "fallen_control": True,
                "stolen_from_dark_elf_retrieval_team": True,
                "stolen_at_ms": self.runtime.world.now_ms,
            }
        )
        courier.metadata["ambushed_during_ruby_key_retrieval"] = True
        courier.metadata["ruby_key_lost"] = True
        pursuit["ruby_key_status"] = "fallen_control"
        pursuit["ruby_key_fallen_holder_id"] = raider.actor_id
        pursuit["ruby_key_stolen_at_ms"] = self.runtime.world.now_ms
        pursuit["fallen_sacred_key_count"] = 5

    def _spawn_fallen_scouts(self) -> list[str]:
        scout_ids: list[str] = []
        for role in ("messenger", "escort"):
            actor_id = f"fallen7_{role}_{uuid.uuid4().hex[:10]}"
            scout = CombatantState(
                actor_id=actor_id,
                name=f"Fallen Elf {role.title()}",
                kind=EntityKind.NPC,
                level=22,
                max_hp=5200,
                hp=5200,
                strength=58,
                agility=68,
                armor=118,
                evasion=15,
                cursor=CursorColor.YELLOW,
                location_id=DRAGON_BONE,
                metadata={
                    "fallen_elf": True,
                    "unnamed_canon_scout": True,
                    "pursuit_role": role,
                    "combat_stats_provenance": "simulation",
                    "paired_scyia_map_carrier": role == "messenger",
                },
            )
            self.runtime.actors[actor_id] = scout
            scout_ids.append(actor_id)
        return scout_ids

    def _spawn_labyrinth_blockers(self, travelling_actor_ids: list[str]):
        blockers = []
        for monster_id in ("tiny_lurking_spider", "armor_plated_monitor"):
            definition = AINCRAD_MONSTERS[monster_id]
            monster = self.runtime._create_monster(
                name=definition.name,
                level=definition.level,
                location_id=LABYRINTH,
                hp_factor=definition.hp_factor,
                loot_table_id=definition.loot_table_id,
                quest_kill_id=definition.quest_kill_id,
            )
            monster.metadata["monster_id"] = monster_id
            monster.metadata["floor7_fallen_pursuit_blocker"] = True
            blockers.append(monster)
        encounter = self.runtime.start_encounter(
            travelling_actor_ids + [monster.actor_id for monster in blockers],
            zone_id=LABYRINTH,
            safe_zone=False,
        )
        return encounter, blockers

    def negotiate_scyia_counteroffer(self, lead_actor_id: str, duel_partner_id: str) -> dict:
        if lead_actor_id == duel_partner_id:
            raise ValueError("the safe-zone blood-marking method requires two different players")
        state = self._eligible_harin_state(lead_actor_id, duel_partner_id)
        if "pursuit" in state:
            raise ValueError("this Harin instance already has a sacred-key pursuit state")

        lead = self.runtime.actors[lead_actor_id]
        partner = self.runtime.actors[duel_partner_id]
        if lead.location_id != CASINO or partner.location_id != CASINO:
            raise ValueError("both Scyia duel players must search Bardun's room in the Volupta Grand Casino")

        kizmel = self._kizmel(state)
        if kizmel.location_id != VOLUPTA:
            raise ValueError("Kizmel must already be waiting in Volupta after the Harin escape")
        for actor_id in state["player_ids"]:
            if actor_id not in {lead_actor_id, duel_partner_id} and self.runtime.actors[actor_id].location_id != VOLUPTA:
                raise ValueError("other Harin party players must already be assembled in Volupta")

        intrigue_states = self.runtime.world.global_flags.get("floor7_casino_intrigue_states")
        if intrigue_states is None or lead_actor_id not in intrigue_states:
            raise ValueError("the Bardun-room search requires the existing Volupta cheating investigation")
        if intrigue_states[lead_actor_id]["true_species_revealed"] is not True:
            raise ValueError("the disguised Storm Lykaon must be exposed before Bardun's room is searched")

        kysarah, key_bag = self._target_key_bag()
        existing_maps = [
            item
            for actor in self.runtime.actors.values()
            for item in actor.inventory.values()
            if item.template_id == MAP_OF_SCYIA_ID
        ]
        if existing_maps:
            raise RuntimeError("a Map of Scyia instance already exists in the campaign")

        map_item = ItemInstance(
            instance_id=f"scyia_{uuid.uuid4().hex[:12]}",
            template_id=MAP_OF_SCYIA_ID,
            owner_id=lead_actor_id,
            metadata={
                "recovered_from": "bardun_room",
                "paired_counterpart_held_by_fallen_elves": True,
                "blood_marks": [],
            },
        )
        add_item(lead, map_item, self.runtime.catalog, allow_overweight=True)
        ruby_courier, ruby_key = self._seed_ruby_key_retrieval_team()

        travel_together(self.runtime, [lead_actor_id, duel_partner_id], VOLUPTA)
        duel = self.runtime.challenge_duel(lead_actor_id, duel_partner_id, DuelMode.FIRST_STRIKE)
        accepted, encounter = self.runtime.accept_duel(duel.duel_id, duel_partner_id)

        map_item.metadata["blood_authorisation_duel_id"] = accepted.duel_id
        map_item.metadata["blood_marks"].append(
            {
                "kind": "proposal",
                "location": "aspen_pair_on_volupta_looserock_route",
                "time": "03:00",
                "marked_at_ms": self.runtime.world.now_ms,
            }
        )
        self.runtime.advance_world(MAP_RESPONSE_MS)
        map_item.metadata["paired_map_counteroffer"] = {
            "location": "dragon_bone_in_field_of_bones",
            "time": "07:00",
        }
        map_item.metadata["counteroffer_received_at_ms"] = self.runtime.world.now_ms
        map_item.metadata["blood_marks"].append(
            {
                "kind": "acceptance",
                "mark": "Y",
                "marked_at_ms": self.runtime.world.now_ms,
            }
        )
        self.runtime.advance_world(MAP_CONFIRM_WAIT_MS)
        map_item.metadata["counteroffer_accepted_at_ms"] = self.runtime.world.now_ms
        self.runtime.draw_duel(duel.duel_id)

        state["pursuit"] = {
            "lead_actor_id": lead_actor_id,
            "duel_partner_id": duel_partner_id,
            "duel_id": duel.duel_id,
            "duel_encounter_id": encounter.encounter_id,
            "map_instance_id": map_item.instance_id,
            "target_key_bag_instance_id": key_bag.instance_id,
            "target_key_bag_holder_id": kysarah.actor_id,
            "ruby_key_instance_id": ruby_key.instance_id,
            "ruby_key_courier_actor_id": ruby_courier.actor_id,
            "ruby_key_status": "dark_elf_retrieval_team",
            "ruby_key_fallen_holder_id": None,
            "ruby_key_stolen_at_ms": None,
            "fallen_sacred_key_count": 4,
            "travelling_actor_ids": [],
            "fallen_scout_ids": [],
            "blocker_actor_ids": [],
            "blocker_encounter_id": None,
            "blocker_encounter_started_at_ms": None,
            "blocker_world_synced_ms": None,
            "trail_outcome": None,
            "boss_room_reached_at_ms": None,
        }
        state["stage"] = "scyia_counteroffer_accepted"
        return self.status(state["instance_id"])

    def rest_and_reach_dragon_bone_watch(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "scyia_counteroffer_accepted":
            raise ValueError("the Scyia counteroffer has not been accepted")
        self._target_key_bag()
        kizmel = self._kizmel(state)
        travelling_actor_ids = list(state["player_ids"]) + [kizmel.actor_id]
        if any(self.runtime.actors[actor_id].location_id != VOLUPTA for actor_id in travelling_actor_ids):
            raise ValueError("every Harin player and Kizmel must be assembled in Volupta before departure")

        self.runtime.advance_world(RENDEZVOUS_PREPARATION_MS)
        to_field = travel_together(self.runtime, travelling_actor_ids, FIELD_OF_BONES)
        to_watch = travel_together(self.runtime, travelling_actor_ids, WATCH_HILL)
        pursuit = state["pursuit"]
        pursuit["travelling_actor_ids"] = travelling_actor_ids
        pursuit["volupta_to_field_ms"] = to_field.elapsed_ms
        pursuit["field_to_watch_ms"] = to_watch.elapsed_ms
        pursuit["watch_hill_arrived_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "waiting_at_field_of_bones_rendezvous"
        return self.status(instance_id)

    def observe_fallen_departure(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "waiting_at_field_of_bones_rendezvous":
            raise ValueError("the party is not waiting at the Field of Bones rendezvous")
        pursuit = state["pursuit"]
        if any(
            self.runtime.actors[actor_id].location_id != WATCH_HILL
            for actor_id in pursuit["travelling_actor_ids"]
        ):
            raise ValueError("the entire pursuit group must remain on the Field of Bones watch hill")

        self.runtime.advance_world(FALLEN_RENDEZVOUS_OBSERVE_MS)
        pursuit["fallen_scout_ids"] = self._spawn_fallen_scouts()
        pursuit["fallen_first_seen_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "fallen_departed_begin_tail"
        return self.status(instance_id)

    def pursue_to_ant_tunnel_valley(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "fallen_departed_begin_tail":
            raise ValueError("the two Fallen Elves have not begun leaving the rendezvous")
        pursuit = state["pursuit"]
        to_dragon = travel_together(
            self.runtime,
            pursuit["travelling_actor_ids"],
            DRAGON_BONE,
        )
        to_ant = travel_together(
            self.runtime,
            pursuit["travelling_actor_ids"],
            ANT_TUNNEL_VALLEY,
        )
        for scout_id in pursuit["fallen_scout_ids"]:
            self.runtime.actors[scout_id].location_id = ANT_TUNNEL_VALLEY
        pursuit["watch_to_dragon_ms"] = to_dragon.elapsed_ms
        pursuit["dragon_to_ant_ms"] = to_ant.elapsed_ms
        state["stage"] = "tracking_through_ant_tunnel_valley"
        return self.status(instance_id)

    def follow_through_valley_into_labyrinth(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "tracking_through_ant_tunnel_valley":
            raise ValueError("the Fallen Elf trail has not reached Ant Tunnel Valley")
        pursuit = state["pursuit"]
        to_plateau = travel_together(
            self.runtime,
            pursuit["travelling_actor_ids"],
            PLATEAU,
        )
        for scout_id in pursuit["fallen_scout_ids"]:
            self.runtime.actors[scout_id].location_id = PLATEAU
        to_labyrinth = travel_together(
            self.runtime,
            pursuit["travelling_actor_ids"],
            LABYRINTH,
        )
        for scout_id in pursuit["fallen_scout_ids"]:
            scout = self.runtime.actors[scout_id]
            scout.location_id = LABYRINTH
            scout.metadata["ahead_of_pursuers"] = True

        self._resolve_ruby_key_loss(state)
        encounter, blockers = self._spawn_labyrinth_blockers(pursuit["travelling_actor_ids"])
        pursuit["ant_to_plateau_ms"] = to_plateau.elapsed_ms
        pursuit["plateau_to_labyrinth_ms"] = to_labyrinth.elapsed_ms
        pursuit["blocker_actor_ids"] = [monster.actor_id for monster in blockers]
        pursuit["blocker_encounter_id"] = encounter.encounter_id
        pursuit["blocker_encounter_started_at_ms"] = encounter.time_ms
        state["stage"] = "labyrinth_blocker_battle"
        return self.status(instance_id)

    def resolve_labyrinth_pursuit(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "labyrinth_blocker_battle":
            raise ValueError("the pursuit is not waiting on the Labyrinth blocker encounter")
        pursuit = state["pursuit"]
        encounter = self.runtime.encounters[pursuit["blocker_encounter_id"]]

        if any(
            encounter.participants[actor_id].alive or encounter.participants[actor_id].hp > 0
            for actor_id in pursuit["blocker_actor_ids"]
        ):
            raise ValueError("the Labyrinth blockers are still alive")
        if any(
            not self.runtime.actors[actor_id].alive
            for actor_id in pursuit["travelling_actor_ids"]
        ):
            raise ValueError("the pursuit group cannot continue with a defeated traveller")
        if pursuit["blocker_world_synced_ms"] is not None:
            raise RuntimeError("the Labyrinth blocker encounter has already been synchronized to world time")

        combat_elapsed_ms = encounter.time_ms - pursuit["blocker_encounter_started_at_ms"]
        if combat_elapsed_ms < 0:
            raise RuntimeError("Labyrinth encounter time moved backwards")
        if combat_elapsed_ms:
            self.runtime.advance_world(combat_elapsed_ms)
        pursuit["blocker_world_synced_ms"] = combat_elapsed_ms
        pursuit["trail_margin_ms"] = TRAIL_MARGIN_MS
        pursuit["trail_outcome"] = "maintained" if combat_elapsed_ms <= TRAIL_MARGIN_MS else "lost"

        for scout_id in pursuit["fallen_scout_ids"]:
            self.runtime.actors[scout_id].metadata["pursuit_trail_outcome"] = pursuit["trail_outcome"]
        state["stage"] = (
            "trail_maintained_in_labyrinth"
            if pursuit["trail_outcome"] == "maintained"
            else "trail_lost_in_labyrinth"
        )
        return self.status(instance_id)

    def advance_to_boss_room(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] not in {"trail_maintained_in_labyrinth", "trail_lost_in_labyrinth"}:
            raise ValueError("the Labyrinth pursuit must be resolved before advancing to the Floor Boss")
        pursuit = state["pursuit"]
        resolution = travel_together(
            self.runtime,
            pursuit["travelling_actor_ids"],
            BOSS_ROOM,
        )
        for scout_id in pursuit["fallen_scout_ids"]:
            self.runtime.actors[scout_id].metadata["pursuit_deferred_for_floor_boss"] = True
        pursuit["boss_room_travel_ms"] = resolution.elapsed_ms
        pursuit["boss_room_reached_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "boss_room_reached"
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        pursuit = state.get("pursuit")
        if pursuit is None:
            return {
                "instance_id": instance_id,
                "stage": state["stage"],
                "pursuit_started": False,
            }

        map_owner = self._map_owner(pursuit["map_instance_id"])
        map_item = map_owner.inventory[pursuit["map_instance_id"]]
        key_bag_matches = []
        for actor in self.runtime.actors.values():
            for item in actor.inventory.values():
                if item.instance_id == pursuit["target_key_bag_instance_id"]:
                    key_bag_matches.append(
                        {
                            "owner_id": actor.actor_id,
                            "owner_npc_definition_id": actor.metadata.get("npc_definition_id"),
                            "stolen_by_kysarah": item.metadata.get("stolen_by_kysarah"),
                        }
                    )
        if len(key_bag_matches) != 1:
            raise RuntimeError("the four-key bag no longer has exactly one authoritative owner")

        ruby_owner = self._ruby_key_owner(pursuit["ruby_key_instance_id"])
        ruby_item = ruby_owner.inventory[pursuit["ruby_key_instance_id"]]
        if pursuit["ruby_key_status"] == "fallen_control" and not ruby_owner.metadata.get("fallen_elf"):
            raise RuntimeError("Ruby Key is marked Fallen-controlled but its real holder is not a Fallen Elf")

        blocker_state = {}
        encounter_id = pursuit["blocker_encounter_id"]
        if encounter_id is not None:
            encounter = self.runtime.encounters[encounter_id]
            blocker_state = {
                actor_id: {
                    "hp": encounter.participants[actor_id].hp,
                    "alive": encounter.participants[actor_id].alive,
                }
                for actor_id in pursuit["blocker_actor_ids"]
            }

        return {
            "instance_id": instance_id,
            "stage": state["stage"],
            "pursuit_started": True,
            "world_now_ms": self.runtime.world.now_ms,
            "map_instance_id": pursuit["map_instance_id"],
            "map_owner_id": map_owner.actor_id,
            "map_metadata": dict(map_item.metadata),
            "target_key_bag_instance_id": pursuit["target_key_bag_instance_id"],
            "target_key_bag_matches": key_bag_matches,
            "ruby_key_instance_id": ruby_item.instance_id,
            "ruby_key_owner_id": ruby_owner.actor_id,
            "ruby_key_owner_is_fallen": bool(ruby_owner.metadata.get("fallen_elf")),
            "ruby_key_status": pursuit["ruby_key_status"],
            "fallen_sacred_key_count": pursuit["fallen_sacred_key_count"],
            "travelling_actor_locations": {
                actor_id: self.runtime.actors[actor_id].location_id
                for actor_id in pursuit["travelling_actor_ids"]
            },
            "fallen_scout_locations": {
                scout_id: self.runtime.actors[scout_id].location_id
                for scout_id in pursuit["fallen_scout_ids"]
            },
            "blocker_encounter_id": encounter_id,
            "blockers": blocker_state,
            "trail_outcome": pursuit["trail_outcome"],
            "ready_for_aghyellr": state["stage"] == "boss_room_reached",
            "pursuit": dict(pursuit),
            "next_stage": (
                "assemble the Harin party with Kizmel in Volupta and reach the Field of Bones watch hill"
                if state["stage"] == "scyia_counteroffer_accepted"
                else "observe the Fallen Elf pair at Dragon Bone from the watch hill"
                if state["stage"] == "waiting_at_field_of_bones_rendezvous"
                else "tail the Fallen Elves through Dragon Bone into Ant Tunnel Valley"
                if state["stage"] == "fallen_departed_begin_tail"
                else "follow the Fallen Elves over the plateau into the Floor 7 Labyrinth"
                if state["stage"] == "tracking_through_ant_tunnel_valley"
                else "defeat the Labyrinth blockers through ordinary encounter combat"
                if state["stage"] == "labyrinth_blocker_battle"
                else "advance to the Floor 7 Boss Room"
                if state["stage"] in {"trail_maintained_in_labyrinth", "trail_lost_in_labyrinth"}
                else None
            ),
        }


def install_floor7_pursuit_scenario(runtime) -> Floor7PursuitScenario:
    if MAP_OF_SCYIA_ID not in runtime.catalog.items or RUBY_KEY_ID not in runtime.catalog.items:
        raise RuntimeError("Floor 7 pursuit item corpus was not loaded")
    if SACRED_KEY_BAG_ID not in runtime.catalog.items:
        raise RuntimeError("Floor 6 sacred-key bag corpus was not loaded")
    return Floor7PursuitScenario(runtime)
