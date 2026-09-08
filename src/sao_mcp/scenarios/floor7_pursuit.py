from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6_elfwar import KIZMEL_ID
from sao_mcp.corpus.floor7 import NIRRNIR_ID
from sao_mcp.corpus.floor7_pursuit import GREENLEAF_CAPE_ID, MAP_OF_SCYIA_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.duels import DuelMode
from sao_mcp.rules.inventory import add_item


CASINO = "floor_7_volupta_grand_casino"
VOLUPTA = "floor_7_volupta"
WATCH_HILL = "floor_7_field_of_bones_watch_hill"
DRAGON_BONE = "floor_7_dragon_bone"
ANT_VALLEY = "floor_7_ant_tunnel_valley"
PLATEAU = "floor_7_ant_tunnel_plateau"
LABYRINTH = "floor_7_labyrinth"
SAFEROOM = "floor_7_labyrinth_saferoom"

MAP_RESPONSE_MS = 3 * 60_000
MAP_ACCEPT_DELAY_MS = 2 * 60_000
MAP_CONFIRM_WAIT_MS = 5 * 60_000
REST_AND_APPROACH_MS = 5 * 60 * 60_000 + 20 * 60_000
WAIT_FOR_FALLEN_DEPARTURE_MS = 35 * 60_000
DRAGON_BONE_TO_VALLEY_MS = 90 * 60_000
VALLEY_TO_LABYRINTH_MS = 60 * 60_000
LABYRINTH_PURSUIT_TO_0400_MS = 18 * 60 * 60_000 + 25 * 60_000


class Floor7PursuitScenario:
    """Sacred-key pursuit from the Map of Scyia exchange to the January-8 Labyrinth saferoom."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor7_fallen_pursuit_instances", {})

    def _state(self, instance_id: str) -> dict:
        try:
            return self._states()[instance_id]
        except KeyError as exc:
            raise KeyError(f"unknown Floor 7 Fallen Elf pursuit instance: {instance_id}") from exc

    def _actor_for_npc(self, npc_definition_id: str) -> CombatantState | None:
        for actor in self.runtime.actors.values():
            if actor.alive and actor.metadata.get("npc_definition_id") == npc_definition_id:
                return actor
        return None

    def _kizmel(self) -> CombatantState:
        kizmel = self._actor_for_npc(KIZMEL_ID)
        if kizmel is None:
            raise ValueError("Kizmel must already be present from the continuing Elf War route")
        if not kizmel.metadata.get("must_recover_sacred_keys_to_clear_name"):
            raise ValueError("Kizmel has not yet reached the fugitive sacred-key recovery stage")
        return kizmel

    def _ensure_greenleaf_cape(self, kizmel: CombatantState) -> ItemInstance:
        existing = next(
            (item for item in kizmel.inventory.values() if item.template_id == GREENLEAF_CAPE_ID),
            None,
        )
        if existing is None:
            existing = ItemInstance(
                instance_id=f"greenleaf_{uuid.uuid4().hex[:12]}",
                template_id=GREENLEAF_CAPE_ID,
                owner_id=kizmel.actor_id,
                metadata={"borrowed_from_castle_galey_treasury": True, "authorised_by_bouhroum": True},
            )
            add_item(kizmel, existing, self.runtime.catalog, allow_overweight=True)
        kizmel.metadata["arid_weakness_suppressed_by"] = existing.instance_id
        return existing

    def _map_item(self, actor_id: str) -> ItemInstance:
        actor = self.runtime.actors[actor_id]
        item = next((item for item in actor.inventory.values() if item.template_id == MAP_OF_SCYIA_ID), None)
        if item is None:
            item = ItemInstance(
                instance_id=f"scyia_{uuid.uuid4().hex[:12]}",
                template_id=MAP_OF_SCYIA_ID,
                owner_id=actor_id,
                metadata={"contact_party": "fallen_elves"},
            )
            add_item(actor, item, self.runtime.catalog, allow_overweight=True)
        return item

    def negotiate_scyia_counteroffer(self, lead_actor_id: str, duel_partner_id: str) -> dict:
        lead = self.runtime.actors[lead_actor_id]
        partner = self.runtime.actors[duel_partner_id]
        if lead.location_id != CASINO or partner.location_id != CASINO:
            raise ValueError("the Scyia blood-map negotiation is prepared in the Volupta casino hotel safe zone")
        if lead_actor_id == duel_partner_id:
            raise ValueError("the safe-zone blood workaround requires a second player for a duel")
        kizmel = self._kizmel()
        if kizmel.location_id not in (VOLUPTA, CASINO):
            raise ValueError("Kizmel must be with the group in Volupta before contacting the Fallen Elves")

        map_item = self._map_item(lead_actor_id)
        duel = self.runtime.challenge_duel(lead_actor_id, duel_partner_id, DuelMode.FIRST_STRIKE)
        accepted, encounter = self.runtime.accept_duel(duel.duel_id, duel_partner_id)
        map_item.metadata.update(
            {
                "blood_authorisation_duel_id": accepted.duel_id,
                "proposed_location": "pair of aspen trees on the Volupta-Looserock route",
                "proposed_time": "03:00",
                "proposal_blood_marked": True,
            }
        )

        self.runtime.advance_world(MAP_RESPONSE_MS)
        map_item.metadata.update(
            {
                "fallen_counteroffer_location_id": DRAGON_BONE,
                "fallen_counteroffer_time": "07:00",
                "counteroffer_received": True,
            }
        )
        self.runtime.advance_world(MAP_ACCEPT_DELAY_MS)
        map_item.metadata["response_mark"] = "Y"
        map_item.metadata["counteroffer_accepted"] = True
        self.runtime.advance_world(MAP_CONFIRM_WAIT_MS)
        self.runtime.draw_duel(duel.duel_id)

        instance_id = f"pursuit7_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "player_ids": [lead_actor_id, duel_partner_id],
            "lead_actor_id": lead_actor_id,
            "duel_partner_id": duel_partner_id,
            "duel_id": duel.duel_id,
            "duel_encounter_id": encounter.encounter_id,
            "map_instance_id": map_item.instance_id,
            "stage": "counteroffer_accepted_rest_and_depart",
            "started_at_ms": self.runtime.world.now_ms,
            "meeting_location_id": DRAGON_BONE,
            "meeting_time_clock": "07:00",
            "fallen_scout_ids": [],
            "sacred_keys_recovered": 0,
            "fallen_hideout_found": False,
            "fallen_lost_in_labyrinth": False,
            "suspected_fallen_base_in_labyrinth": False,
            "reached_saferoom_at_ms": None,
        }
        self._states()[instance_id] = state
        return self.status(instance_id)

    def _spawn_fallen_scouts(self) -> list[str]:
        ids: list[str] = []
        for index in range(2):
            actor_id = f"fallen_scout7_{uuid.uuid4().hex[:10]}"
            scout = CombatantState(
                actor_id=actor_id,
                name=f"Fallen Elf Scout {index + 1}",
                kind=EntityKind.NPC,
                level=28,
                max_hp=7600,
                hp=7600,
                strength=65,
                agility=72,
                armor=180,
                evasion=17,
                cursor=CursorColor.YELLOW,
                location_id=DRAGON_BONE,
                metadata={
                    "fallen_elf": True,
                    "unnamed_canon_scout": True,
                    "taboo_branch_arid_protection": True,
                    "combat_stats_provenance": "simulation",
                },
            )
            template = self.runtime.catalog.weapons["starter_one_hand_sword"]
            weapon = ItemInstance(
                instance_id=f"fallen_weapon_{uuid.uuid4().hex[:12]}",
                template_id=template.template_id,
                owner_id=actor_id,
                durability=template.base_durability,
                max_durability=template.base_durability,
                metadata={"descriptive_weapon": True},
            )
            scout.inventory[weapon.instance_id] = weapon
            scout.equipment["weapon"] = weapon.instance_id
            self.runtime.actors[actor_id] = scout
            ids.append(actor_id)
        return ids

    def rest_and_reach_dragon_bone_watch(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "counteroffer_accepted_rest_and_depart":
            raise ValueError("the Fallen Elf counteroffer has not been accepted")
        players = [self.runtime.actors[actor_id] for actor_id in state["player_ids"]]
        if any(actor.location_id != CASINO for actor in players):
            raise ValueError("the map-negotiation players must depart from the Volupta casino hotel")
        kizmel = self._kizmel()
        cape = self._ensure_greenleaf_cape(kizmel)

        self.runtime.advance_world(REST_AND_APPROACH_MS)
        for actor in players:
            actor.location_id = WATCH_HILL
        kizmel.location_id = WATCH_HILL
        nirrnir_story = self.runtime.world.global_flags.get("floor7_nirrnir_poison_story", {})
        nirrnir_id = nirrnir_story.get("nirrnir_actor_id")
        if nirrnir_id in self.runtime.actors:
            nirrnir = self.runtime.actors[nirrnir_id]
            nirrnir.location_id = WATCH_HILL
            nirrnir.metadata["carried_during_fallen_pursuit"] = True

        scout_ids = self._spawn_fallen_scouts()
        state["fallen_scout_ids"] = scout_ids
        state["stage"] = "watching_dragon_bone_rendezvous"
        state["watch_hill_distance_yards"] = 300
        state["greenleaf_cape_instance_id"] = cape.instance_id
        state["nirrnir_actor_id"] = nirrnir_id if nirrnir_id in self.runtime.actors else None
        state["arrival_clock"] = "06:30"
        return self.status(instance_id)

    def observe_fallen_departure(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "watching_dragon_bone_rendezvous":
            raise ValueError("the party is not watching the Dragon Bone rendezvous")
        self.runtime.advance_world(WAIT_FOR_FALLEN_DEPARTURE_MS)
        state["stage"] = "fallen_departed_begin_tail"
        state["fallen_departure_clock"] = "07:05"
        return self.status(instance_id)

    def pursue_to_ant_tunnel_valley(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "fallen_departed_begin_tail":
            raise ValueError("the two Fallen Elves have not begun returning from Dragon Bone")
        self.runtime.advance_world(DRAGON_BONE_TO_VALLEY_MS)
        for actor_id in state["player_ids"]:
            self.runtime.actors[actor_id].location_id = ANT_VALLEY
        kizmel = self._kizmel()
        kizmel.location_id = ANT_VALLEY
        for scout_id in state["fallen_scout_ids"]:
            self.runtime.actors[scout_id].location_id = ANT_VALLEY
        nirrnir_id = state.get("nirrnir_actor_id")
        if nirrnir_id in self.runtime.actors:
            self.runtime.actors[nirrnir_id].location_id = ANT_VALLEY
        state["stage"] = "tracking_through_ant_tunnel_valley"
        state["tracks_visible_in_soft_ground"] = True
        state["hideout_found_in_valley"] = False
        return self.status(instance_id)

    def follow_through_valley_into_labyrinth(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "tracking_through_ant_tunnel_valley":
            raise ValueError("the Fallen Elf trail has not reached Ant Tunnel Valley")
        self.runtime.advance_world(VALLEY_TO_LABYRINTH_MS)
        for actor_id in state["player_ids"]:
            self.runtime.actors[actor_id].location_id = LABYRINTH
        kizmel = self._kizmel()
        kizmel.location_id = LABYRINTH
        for scout_id in state["fallen_scout_ids"]:
            self.runtime.actors[scout_id].location_id = LABYRINTH
        nirrnir_id = state.get("nirrnir_actor_id")
        if nirrnir_id in self.runtime.actors:
            self.runtime.actors[nirrnir_id].location_id = LABYRINTH
        state["stage"] = "pursuing_inside_floor7_labyrinth"
        state["fallen_passed_valley_without_hideout"] = True
        state["fallen_passed_plateau"] = True
        return self.status(instance_id)

    def pursue_until_saferoom(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "pursuing_inside_floor7_labyrinth":
            raise ValueError("the two Fallen Elves have not entered the Floor 7 Labyrinth")
        self.runtime.advance_world(LABYRINTH_PURSUIT_TO_0400_MS)
        for actor_id in state["player_ids"]:
            self.runtime.actors[actor_id].location_id = SAFEROOM
        kizmel = self._kizmel()
        kizmel.location_id = SAFEROOM
        for scout_id in state["fallen_scout_ids"]:
            scout = self.runtime.actors[scout_id]
            scout.location_id = LABYRINTH
            scout.metadata["lost_from_pursuers_after_monster_battles"] = True
        nirrnir_id = state.get("nirrnir_actor_id")
        if nirrnir_id in self.runtime.actors:
            self.runtime.actors[nirrnir_id].location_id = SAFEROOM
        state["stage"] = "labyrinth_saferoom_no_keys"
        state["fallen_lost_in_labyrinth"] = True
        state["suspected_fallen_base_in_labyrinth"] = True
        state["sacred_keys_recovered"] = 0
        state["reached_saferoom_at_ms"] = self.runtime.world.now_ms
        state["reference_clock"] = "January 8 04:00"
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        lead = self.runtime.actors[state["lead_actor_id"]]
        map_item = lead.inventory.get(state["map_instance_id"])
        kizmel = self._actor_for_npc(KIZMEL_ID)
        nirrnir_id = state.get("nirrnir_actor_id")
        nirrnir = self.runtime.actors.get(nirrnir_id) if nirrnir_id else None
        poison_story = self.runtime.world.global_flags.get("floor7_nirrnir_poison_story", {})
        deadline = poison_story.get("deadline_ms")
        nirrnir_remaining = (
            max(0, int(deadline) - self.runtime.world.now_ms)
            if deadline is not None and nirrnir is not None and poison_story.get("stage") != "cured"
            else None
        )
        return {
            **state,
            "map_metadata": dict(map_item.metadata) if map_item else None,
            "kizmel_actor_id": kizmel.actor_id if kizmel else None,
            "kizmel_location_id": kizmel.location_id if kizmel else None,
            "nirrnir_remaining_ms": nirrnir_remaining,
            "fallen_scout_locations": {
                scout_id: self.runtime.actors[scout_id].location_id
                for scout_id in state.get("fallen_scout_ids", ())
                if scout_id in self.runtime.actors
            },
            "next_stage": (
                "rest, leave Volupta at 04:30 and reach the Dragon Bone watch hill" if state["stage"] == "counteroffer_accepted_rest_and_depart"
                else "wait for the seven-o'clock Fallen Elf rendezvous" if state["stage"] == "watching_dragon_bone_rendezvous"
                else "tail the two Fallen Elves toward Ant Tunnel Valley" if state["stage"] == "fallen_departed_begin_tail"
                else "follow the tracks through Ant Tunnel Valley" if state["stage"] == "tracking_through_ant_tunnel_valley"
                else "continue the pursuit inside the Floor 7 Labyrinth" if state["stage"] == "pursuing_inside_floor7_labyrinth"
                else "the sacred keys are still missing; the Fallen base is now suspected to be somewhere in the Labyrinth" if state["stage"] == "labyrinth_saferoom_no_keys"
                else None
            ),
        }


def install_floor7_pursuit_scenario(runtime) -> Floor7PursuitScenario:
    if MAP_OF_SCYIA_ID not in runtime.catalog.items or GREENLEAF_CAPE_ID not in runtime.catalog.items:
        raise RuntimeError("Floor 7 sacred-key pursuit item corpus was not loaded")
    return Floor7PursuitScenario(runtime)
