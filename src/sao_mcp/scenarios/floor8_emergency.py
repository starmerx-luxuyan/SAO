from __future__ import annotations

import uuid

from sao_mcp.corpus.floor7_pursuit import ARGO_ID
from sao_mcp.corpus.floor8_world import FOREST_ELF_ESCAPE_CAVE, FRIEBEN
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind


EMERGENCY_TEXT = "Floor 8 emergency: sacred Forest Elf trees were cut; frontline players fled into a cave."


class Floor8ForestEmergencyScenario:
    """Progressive 9 Floor 8 emergency linked to the optional Nocturne branch split."""

    def __init__(self, runtime, nocturne) -> None:
        if nocturne.runtime is not runtime:
            raise RuntimeError("Floor 8 emergency and Nocturne services must share one runtime")
        self.runtime = runtime
        self.nocturne = nocturne

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor8_forest_emergency_instances", {})

    def _state(self, instance_id: str) -> dict:
        return self._states()[instance_id]

    def _argo_actor(self) -> CombatantState:
        matches = [
            actor
            for actor in self.runtime.actors.values()
            if actor.metadata.get("npc_definition_id") == ARGO_ID
        ]
        if len(matches) > 1:
            raise RuntimeError("multiple authoritative Argo player actors exist")
        if matches:
            argo = matches[0]
            if argo.kind is not EntityKind.PLAYER:
                raise RuntimeError("the materialized Argo actor is not a player character")
            if not argo.alive:
                raise ValueError("Argo is not alive to send the Floor 8 emergency message")
        else:
            actor_id = f"pc_argo_{uuid.uuid4().hex[:12]}"
            argo = CombatantState(
                actor_id=actor_id,
                name="Argo",
                kind=EntityKind.PLAYER,
                level=28,
                max_hp=6200,
                hp=6200,
                strength=58,
                agility=76,
                armor=105,
                evasion=18,
                cursor=CursorColor.GREEN,
                location_id=FRIEBEN,
                skill_proficiencies={"claw": 760.0, "searching": 920.0},
                metadata={
                    "npc_definition_id": ARGO_ID,
                    "named_player": True,
                    "information_broker": True,
                    "combat_stats_provenance": "simulation",
                },
            )
            self.runtime.actors[actor_id] = argo
        argo.location_id = FRIEBEN
        self.runtime.npcs.states[ARGO_ID].location_id = FRIEBEN
        return argo

    def _ensure_friend_contact(self, argo_id: str, recipient_id: str) -> None:
        if self.runtime.relationships.are_friends(argo_id, recipient_id):
            return
        request = self.runtime.request_friend(argo_id, recipient_id)
        self.runtime.accept_friend(request.request_id, recipient_id)
        if not self.runtime.relationships.are_friends(argo_id, recipient_id):
            raise RuntimeError("Argo friend contact did not become authoritative")

    def trigger_from_nocturne(self, nocturne_instance_id: str, recipient_actor_id: str) -> dict:
        if any(state["nocturne_instance_id"] == nocturne_instance_id for state in self._states().values()):
            raise ValueError("this Nocturne instance already has a Floor 8 forest emergency")
        floor8 = self.runtime.world.floors[8]
        if not floor8.unlocked or not floor8.main_town_gate_active:
            raise ValueError("Floor 8 Frieben Teleport Gate must be active before Argo can report the incident")
        nocturne_state = self.nocturne.status(nocturne_instance_id)
        if nocturne_state["stage"] != "five_key_hideout_recon_on_lake":
            raise ValueError("the Floor 8 emergency is linked after the Nocturne group resumes the five-key route on Lake Yofel")
        if recipient_actor_id not in nocturne_state["player_ids"]:
            raise ValueError("Argo's recipient must be a player in the linked Nocturne pursuit")

        argo = self._argo_actor()
        self._ensure_friend_contact(argo.actor_id, recipient_actor_id)
        message = self.runtime.send_short_message(argo.actor_id, recipient_actor_id, EMERGENCY_TEXT)
        instance_id = f"floor8_emergency_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "nocturne_instance_id": nocturne_instance_id,
            "argo_actor_id": argo.actor_id,
            "recipient_actor_id": recipient_actor_id,
            "message_id": message.message_id,
            "message_channel": message.channel.value,
            "incident": {
                "location_id": FOREST_ELF_ESCAPE_CAVE,
                "protected_trees_cut": True,
                "forest_elf_pursuit_triggered": True,
                "frontline_group_sheltering_in_cave": True,
                "reported_by_actor_id": argo.actor_id,
            },
            "floor8_actor_ids": [],
            "hideout_actor_ids": [],
            "response_split_assigned_at_ms": None,
            "responders_arrived_frieben_at_ms": None,
            "stage": "argo_message_sent",
            "triggered_at_ms": self.runtime.world.now_ms,
        }
        self._states()[instance_id] = state
        self.nocturne.link_floor8_emergency(nocturne_instance_id, instance_id, message.message_id)
        return self.status(instance_id)

    def assign_response_split(
        self,
        instance_id: str,
        floor8_actor_ids: list[str],
        hideout_actor_ids: list[str],
    ) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "argo_message_sent":
            raise ValueError("the emergency response split has already been assigned or the message is not active")
        split = self.nocturne.assign_floor8_emergency_split(
            state["nocturne_instance_id"],
            floor8_actor_ids,
            hideout_actor_ids,
        )
        state["floor8_actor_ids"] = list(split["floor8_actor_ids"])
        state["hideout_actor_ids"] = list(split["hideout_actor_ids"])
        state["response_split_assigned_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "response_split_assigned"
        return self.status(instance_id)

    def arrive_frieben(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "response_split_assigned":
            raise ValueError("the emergency response split has not been assigned")
        responders = state["floor8_actor_ids"]
        if not responders:
            raise ValueError("this emergency split assigned no player to Floor 8")
        wrong = [actor_id for actor_id in responders if self.runtime.actors[actor_id].location_id != FRIEBEN]
        if wrong:
            raise ValueError(f"Floor 8 responders have not all reached Frieben: {', '.join(wrong)}")
        state["responders_arrived_frieben_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "responders_at_frieben"
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        message = self.runtime.communications.messages[state["message_id"]]
        if message.sender_id != state["argo_actor_id"] or message.recipient_id != state["recipient_actor_id"]:
            raise RuntimeError("Floor 8 emergency points to the wrong authoritative short message")
        return {
            **state,
            "message": {
                "message_id": message.message_id,
                "sender_id": message.sender_id,
                "recipient_id": message.recipient_id,
                "channel": message.channel.value,
                "text": message.text,
                "sent_at_ms": message.sent_at_ms,
                "read_at_ms": message.read_at_ms,
            },
            "argo_location_id": self.runtime.actors[state["argo_actor_id"]].location_id,
            "floor8_responder_locations": {
                actor_id: self.runtime.actors[actor_id].location_id
                for actor_id in state["floor8_actor_ids"]
            },
            "hideout_responder_locations": {
                actor_id: self.runtime.actors[actor_id].location_id
                for actor_id in state["hideout_actor_ids"]
            },
            "next_stage": (
                "choose which Nocturne players respond to Floor 8 and which continue the sacred-key hideout route"
                if state["stage"] == "argo_message_sent"
                else "Floor 8 responders must reach the already-active Frieben Teleport Gate through ordinary teleport/travel rules"
                if state["stage"] == "response_split_assigned" and state["floor8_actor_ids"]
                else "the Floor 8 incident remains unresolved because this split assigned no responder"
                if state["stage"] == "response_split_assigned"
                else "meet Argo in Frieben; the sacred-woods cave incident remains live for the next Floor 8 scenario slice"
                if state["stage"] == "responders_at_frieben"
                else None
            ),
        }


def install_floor8_forest_emergency_scenario(runtime, nocturne) -> Floor8ForestEmergencyScenario:
    for location_id in (FRIEBEN, FOREST_ELF_ESCAPE_CAVE):
        if location_id not in runtime.world_map.locations:
            raise RuntimeError(f"Floor 8 world corpus is missing {location_id}")
    if ARGO_ID not in runtime.npcs.definitions:
        raise RuntimeError("Argo corpus was not loaded")
    if not hasattr(runtime, "communications") or not hasattr(runtime, "relationships"):
        raise RuntimeError("Floor 8 emergency requires the communicating relationship runtime")
    return Floor8ForestEmergencyScenario(runtime, nocturne)