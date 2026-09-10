from __future__ import annotations

import uuid

from sao_mcp.corpus.floor7_pursuit import ARGO_ID
from sao_mcp.corpus.floor8_progressive import FLOOR8_GUILD_CRISIS_REPORT, KLEIN_ID
from sao_mcp.corpus.floor8_world import (
    ACORN_SHOP,
    FOREST_ELF_ESCAPE_CAVE,
    FOREST_ELF_ESCAPE_CAVE_MOUTH,
    FOREST_ELF_SACRED_WOODS,
    FRIEBEN,
    MANAGED_FOREST_OUTER,
)
from sao_mcp.corpus.location_access import FOREST_ELVES
from sao_mcp.corpus.progressive_guilds import ALS_GUILD_ID, DKB_GUILD_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance, PartyState
from sao_mcp.rules.group_travel import group_travel_record, travel_together
from sao_mcp.rules.spawn import create_character_at
from sao_mcp.rules.state_authority import authoritative_guild_id
from sao_mcp.runtime.canonical_guilds import install_progressive_clearing_guilds


EMERGENCY_TEXT = "Floor 8 emergency: DKB/ALS are trapped in a Forest Elf dispute. Meet me at the Acorn Shop."
LOCAL_REPRESENTATION_SCOPE = "simulation_subset_of_reported_guild_majority"
LOCAL_RESOLUTION_SCOPE = "materialized_local_standoff_only"


class Floor8ForestEmergencyScenario:
    """Progressive 9 Floor 8 emergency linked to the optional Nocturne branch split."""

    def __init__(self, runtime, nocturne) -> None:
        if nocturne.runtime is not runtime:
            raise RuntimeError("Floor 8 emergency and Nocturne services must share one runtime")
        self.runtime = runtime
        self.nocturne = nocturne
        self.clearing_guilds = install_progressive_clearing_guilds(runtime)

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
            if argo.location_id != ACORN_SHOP:
                raise RuntimeError("materialized Argo is not at the authoritative Acorn Shop rendezvous")
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
                location_id=ACORN_SHOP,
                skill_proficiencies={"claw": 760.0, "searching": 920.0},
                metadata={
                    "npc_definition_id": ARGO_ID,
                    "named_player": True,
                    "information_broker": True,
                    "combat_stats_provenance": "simulation",
                },
            )
            self.runtime.actors[actor_id] = argo
        return argo

    def _klein_actor(self) -> CombatantState:
        matches = [
            actor
            for actor in self.runtime.actors.values()
            if actor.metadata.get("npc_definition_id") == KLEIN_ID
        ]
        if len(matches) > 1:
            raise RuntimeError("multiple authoritative Klein player actors exist")
        if matches:
            klein = matches[0]
            if klein.kind is not EntityKind.PLAYER:
                raise RuntimeError("the materialized Klein actor is not a player character")
            if not klein.alive:
                raise ValueError("Klein is not alive for the Floor 8 rendezvous")
            if klein.location_id != ACORN_SHOP:
                raise RuntimeError("materialized Klein is not at the authoritative Acorn Shop rendezvous")
        else:
            actor_id = f"pc_klein_{uuid.uuid4().hex[:12]}"
            klein = CombatantState(
                actor_id=actor_id,
                name="Klein",
                kind=EntityKind.PLAYER,
                level=28,
                max_hp=7000,
                hp=7000,
                strength=66,
                agility=62,
                armor=120,
                evasion=12,
                cursor=CursorColor.GREEN,
                location_id=ACORN_SHOP,
                skill_proficiencies={"katana": 760.0, "one_hand_curved_sword": 720.0},
                metadata={
                    "npc_definition_id": KLEIN_ID,
                    "named_player": True,
                    "combat_stats_provenance": "simulation",
                    "progressive9_acorn_shop_rendezvous": True,
                    "combat_equipment_unmodelled_for_floor8_period": True,
                },
            )
            self.runtime.actors[actor_id] = klein
        klein.metadata["progressive9_acorn_shop_rendezvous"] = True
        return klein

    def _ensure_friend_contact(self, argo_id: str, recipient_id: str) -> None:
        if self.runtime.relationships.are_friends(argo_id, recipient_id):
            return
        request = self.runtime.request_friend(argo_id, recipient_id)
        self.runtime.accept_friend(request.request_id, recipient_id)
        if not self.runtime.relationships.are_friends(argo_id, recipient_id):
            raise RuntimeError("Argo friend contact did not become authoritative")

    def _make_incident_player(self, name: str, guild_id: str, level: int) -> CombatantState:
        guild = self.clearing_guilds[guild_id]
        actor = create_character_at(
            self.runtime,
            name,
            level=level,
            location_id=FOREST_ELF_ESCAPE_CAVE,
        )
        actor.metadata.update(
            {
                "floor8_protected_tree_incident": True,
                "frontline_incident_group_member": True,
                "incident_representation_scope": LOCAL_REPRESENTATION_SCOPE,
                "personal_identity_provenance": "simulation",
                "guild_affiliation_provenance": "canon",
                "sheltering_in_escape_cave": True,
            }
        )
        invite = self.runtime.invite_to_guild(guild_id, guild.leader_id, actor.actor_id)
        joined = self.runtime.accept_guild_invite(invite.invite_id, actor.actor_id)
        if authoritative_guild_id(self.runtime, actor.actor_id) != guild_id:
            raise RuntimeError("Floor 8 incident player did not join the authoritative clearing GuildState")
        if actor.actor_id not in joined.member_ids:
            raise RuntimeError("Floor 8 incident player is absent from authoritative guild membership")
        if actor.actor_id not in self.runtime.relationships.storages[joined.storage_id].member_ids:
            raise RuntimeError("Floor 8 incident player is absent from authoritative guild storage membership")
        return actor

    def _make_forest_elf_pursuer(self, role: str, index: int) -> CombatantState:
        actor_id = f"forestelf8_{role}_{uuid.uuid4().hex[:10]}"
        actor = CombatantState(
            actor_id=actor_id,
            name=f"Forest Elf {role.title()} {index}",
            kind=EntityKind.NPC,
            level=30,
            max_hp=7600,
            hp=7600,
            strength=68,
            agility=74,
            armor=170,
            evasion=16,
            cursor=CursorColor.YELLOW,
            location_id=FOREST_ELF_SACRED_WOODS,
            skill_proficiencies={"one_hand_sword": 760.0},
            metadata={
                "faction_ids": (FOREST_ELVES,),
                "floor8_protected_woods_enforcement": True,
                "pursuing_frontline_incident_group": True,
                "personal_identity_provenance": "simulation",
                "combat_stats_provenance": "simulation",
            },
        )
        template = self.runtime.catalog.weapons["starter_one_hand_sword"]
        weapon = ItemInstance(
            instance_id=f"forestelf_weapon_{uuid.uuid4().hex[:10]}",
            template_id=template.template_id,
            owner_id=actor_id,
            durability=template.base_durability,
            max_durability=template.base_durability,
            metadata={"simulation_equipment_for_anonymous_canon_role": True},
        )
        actor.inventory[weapon.instance_id] = weapon
        actor.equipment["weapon"] = weapon.instance_id
        self.runtime.actors[actor_id] = actor
        return actor

    def _create_party(self, prefix: str, members: list[CombatantState]) -> PartyState:
        if not members:
            raise ValueError("incident party requires at least one actor")
        party_id = f"{prefix}_{uuid.uuid4().hex[:12]}"
        party = PartyState(party_id, members[0].actor_id, [member.actor_id for member in members])
        self.runtime.world.parties[party_id] = party
        for member in members:
            member.party_id = party_id
        return party

    def _materialize_incident_actors(self, state: dict) -> None:
        if state["incident"]["frontline_actor_ids"] or state["incident"]["forest_elf_actor_ids"]:
            raise RuntimeError("Floor 8 incident actors were already materialized")

        als = [
            self._make_incident_player("ALS Incident Representative A", ALS_GUILD_ID, 26),
            self._make_incident_player("ALS Incident Representative B", ALS_GUILD_ID, 25),
        ]
        dkb = [
            self._make_incident_player("DKB Incident Representative A", DKB_GUILD_ID, 27),
            self._make_incident_player("DKB Incident Representative B", DKB_GUILD_ID, 26),
        ]
        als_party = self._create_party("party8_als_incident", als)
        dkb_party = self._create_party("party8_dkb_incident", dkb)

        forest_elves = [
            self._make_forest_elf_pursuer("warden", 1),
            self._make_forest_elf_pursuer("ranger", 1),
        ]
        forest_party = self._create_party("party8_forest_elf_pursuit", forest_elves)

        incident = state["incident"]
        incident["frontline_party_ids"] = [als_party.party_id, dkb_party.party_id]
        incident["frontline_actor_ids"] = [actor.actor_id for actor in als + dkb]
        incident["forest_elf_party_id"] = forest_party.party_id
        incident["forest_elf_actor_ids"] = [actor.actor_id for actor in forest_elves]
        incident["actors_materialized_at_ms"] = self.runtime.world.now_ms

    def _guild_decision_authority(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for guild_id in FLOOR8_GUILD_CRISIS_REPORT.affected_guild_ids:
            guild = self.runtime.relationships.guilds[guild_id]
            leader = self.runtime.actors[guild.leader_id]
            result[guild_id] = {
                "actor_id": leader.actor_id,
                "name": leader.name,
                "alive": leader.alive,
                "location_id": leader.location_id,
            }
        return result

    @staticmethod
    def _guild_crisis_report() -> dict:
        report = FLOOR8_GUILD_CRISIS_REPORT
        return {
            "affected_guild_ids": list(report.affected_guild_ids),
            "affected_member_scope": report.affected_member_scope,
            "trigger": {
                "kind": report.trigger_kind,
                "location_scope": report.trigger_location_scope,
            },
            "escalation_depends_on_guild_leaders": report.escalation_depends_on_guild_leaders,
            "provenance": {
                "kind": report.provenance.kind.value,
                "sources": list(report.provenance.sources),
                "notes": report.provenance.notes,
            },
        }

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
        klein = self._klein_actor()
        self._ensure_friend_contact(argo.actor_id, recipient_actor_id)
        message = self.runtime.send_short_message(argo.actor_id, recipient_actor_id, EMERGENCY_TEXT)
        instance_id = f"floor8_emergency_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "nocturne_instance_id": nocturne_instance_id,
            "argo_actor_id": argo.actor_id,
            "klein_actor_id": klein.actor_id,
            "recipient_actor_id": recipient_actor_id,
            "message_id": message.message_id,
            "message_channel": message.channel.value,
            "rendezvous_location_id": ACORN_SHOP,
            "incident": {
                "location_id": FOREST_ELF_ESCAPE_CAVE,
                "protected_trees_cut": True,
                "forest_elf_pursuit_triggered": True,
                "frontline_group_sheltering_in_cave": True,
                "reported_by_actor_id": argo.actor_id,
                "frontline_party_ids": [],
                "frontline_actor_ids": [],
                "forest_elf_party_id": None,
                "forest_elf_actor_ids": [],
                "actors_materialized_at_ms": None,
                "argo_briefing_confirmed_at_ms": None,
                "sacred_woods_inspected_at_ms": None,
                "sacred_woods_to_cave_mouth_route": [],
                "cave_mouth_reached_at_ms": None,
                "cave_mouth_to_cave_route": [],
                "responders_entered_cave_at_ms": None,
            },
            "floor8_actor_ids": [],
            "hideout_actor_ids": [],
            "response_split_assigned_at_ms": None,
            "responders_arrived_frieben_at_ms": None,
            "acorn_shop_rendezvous_at_ms": None,
            "frieben_to_acorn_shop_route": [],
            "acorn_shop_to_sacred_woods_route": [],
            "stage": "argo_message_sent",
            "triggered_at_ms": self.runtime.world.now_ms,
        }
        self._states()[instance_id] = state
        self._materialize_incident_actors(state)
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

    def meet_argo_and_klein(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "responders_at_frieben":
            raise ValueError("Floor 8 responders have not assembled at Frieben")
        self._require_responders_at(state, FRIEBEN)
        argo = self.runtime.actors[state["argo_actor_id"]]
        klein = self.runtime.actors[state["klein_actor_id"]]
        if argo.location_id != ACORN_SHOP or klein.location_id != ACORN_SHOP:
            raise RuntimeError("Argo and Klein are not both waiting at the Acorn Shop rendezvous")
        resolution = travel_together(self.runtime, state["floor8_actor_ids"], ACORN_SHOP)
        state["frieben_to_acorn_shop_route"] = [group_travel_record(resolution)]
        state["acorn_shop_rendezvous_at_ms"] = self.runtime.world.now_ms
        state["incident"]["argo_briefing_confirmed_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "responders_briefed_at_acorn_shop"
        return self.status(instance_id)

    def depart_acorn_shop_to_sacred_woods(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "responders_briefed_at_acorn_shop":
            raise ValueError("responders have not completed the Acorn Shop rendezvous")
        responders = state["floor8_actor_ids"]
        self._require_responders_at(state, ACORN_SHOP)
        segments = [
            travel_together(self.runtime, responders, FRIEBEN),
            travel_together(self.runtime, responders, MANAGED_FOREST_OUTER),
            travel_together(self.runtime, responders, FOREST_ELF_SACRED_WOODS),
        ]
        state["acorn_shop_to_sacred_woods_route"] = [group_travel_record(resolution) for resolution in segments]
        state["stage"] = "responders_at_sacred_woods"
        return self.status(instance_id)

    def inspect_sacred_woods_incident(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "responders_at_sacred_woods":
            raise ValueError("responders have not reached the protected Forest Elf woods")
        self._require_responders_at(state, FOREST_ELF_SACRED_WOODS)
        incident = state["incident"]
        forest_elves = [self.runtime.actors[actor_id] for actor_id in incident["forest_elf_actor_ids"]]
        if any(actor.location_id != FOREST_ELF_SACRED_WOODS for actor in forest_elves):
            raise RuntimeError("Forest Elf pursuit actors left the protected woods before inspection")
        frontline = [self.runtime.actors[actor_id] for actor_id in incident["frontline_actor_ids"]]
        if any(actor.location_id != FOREST_ELF_ESCAPE_CAVE for actor in frontline):
            raise RuntimeError("materialized incident representatives are not sheltering inside the cave")
        incident["sacred_woods_inspected_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "sacred_woods_incident_confirmed"
        return self.status(instance_id)

    def follow_to_escape_cave_mouth(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "sacred_woods_incident_confirmed":
            raise ValueError("the sacred-woods incident has not been confirmed")
        self._require_responders_at(state, FOREST_ELF_SACRED_WOODS)
        forest_ids = list(state["incident"]["forest_elf_actor_ids"])
        self._require_actor_ids_at(forest_ids, FOREST_ELF_SACRED_WOODS)
        moving = list(state["floor8_actor_ids"]) + forest_ids
        resolution = travel_together(self.runtime, moving, FOREST_ELF_ESCAPE_CAVE_MOUTH)
        state["incident"]["sacred_woods_to_cave_mouth_route"] = [group_travel_record(resolution)]
        state["incident"]["cave_mouth_reached_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "cave_mouth_standoff"
        return self.status(instance_id)

    def enter_escape_cave(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "cave_mouth_standoff":
            raise ValueError("responders have not reached the cave mouth standoff")
        self._require_responders_at(state, FOREST_ELF_ESCAPE_CAVE_MOUTH)
        forest_ids = list(state["incident"]["forest_elf_actor_ids"])
        self._require_actor_ids_at(forest_ids, FOREST_ELF_ESCAPE_CAVE_MOUTH)
        resolution = travel_together(self.runtime, state["floor8_actor_ids"], FOREST_ELF_ESCAPE_CAVE)
        state["incident"]["cave_mouth_to_cave_route"] = [group_travel_record(resolution)]
        frontline_ids = list(state["incident"]["frontline_actor_ids"])
        self._require_actor_ids_at(frontline_ids, FOREST_ELF_ESCAPE_CAVE)
        state["incident"]["responders_entered_cave_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "responders_inside_cave_standoff"
        return self.status(instance_id)

    def _require_actor_ids_at(self, actor_ids: list[str], location_id: str) -> None:
        wrong = [actor_id for actor_id in actor_ids if self.runtime.actors[actor_id].location_id != location_id]
        if wrong:
            raise ValueError(f"actors are not all at {location_id}: {', '.join(wrong)}")

    def _require_responders_at(self, state: dict, location_id: str) -> None:
        self._require_actor_ids_at(state["floor8_actor_ids"], location_id)

    def status(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        message = self.runtime.communications.messages[state["message_id"]]
        if message.sender_id != state["argo_actor_id"] or message.recipient_id != state["recipient_actor_id"]:
            raise RuntimeError("Floor 8 emergency points to the wrong authoritative short message")
        incident = state["incident"]
        frontline_actors = {
            actor_id: {
                "name": self.runtime.actors[actor_id].name,
                "guild_id": authoritative_guild_id(self.runtime, actor_id),
                "party_id": self.runtime.actors[actor_id].party_id,
                "location_id": self.runtime.actors[actor_id].location_id,
                "alive": self.runtime.actors[actor_id].alive,
                "representation_scope": self.runtime.actors[actor_id].metadata["incident_representation_scope"],
            }
            for actor_id in incident["frontline_actor_ids"]
        }
        forest_elf_actors = {
            actor_id: {
                "name": self.runtime.actors[actor_id].name,
                "party_id": self.runtime.actors[actor_id].party_id,
                "location_id": self.runtime.actors[actor_id].location_id,
                "alive": self.runtime.actors[actor_id].alive,
                "cursor": self.runtime.actors[actor_id].cursor.value,
            }
            for actor_id in incident["forest_elf_actor_ids"]
        }
        report = FLOOR8_GUILD_CRISIS_REPORT
        guilds = {
            guild_id: {
                "name": self.runtime.relationships.guilds[guild_id].name,
                "leader_id": self.runtime.relationships.guilds[guild_id].leader_id,
                "runtime_materialized_member_ids": list(self.runtime.relationships.guilds[guild_id].member_ids),
                "reported_affected_member_scope": report.affected_member_scope,
            }
            for guild_id in report.affected_guild_ids
        }
        return {
            **state,
            "frieben_to_acorn_shop_ms": sum(segment["elapsed_ms"] for segment in state["frieben_to_acorn_shop_route"]),
            "acorn_shop_to_sacred_woods_ms": sum(segment["elapsed_ms"] for segment in state["acorn_shop_to_sacred_woods_route"]),
            "guild_crisis_report": self._guild_crisis_report(),
            "local_materialization": {
                "representation_scope": LOCAL_REPRESENTATION_SCOPE,
                "resolution_scope": LOCAL_RESOLUTION_SCOPE,
            },
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
            "klein_location_id": self.runtime.actors[state["klein_actor_id"]].location_id,
            "floor8_responder_locations": {
                actor_id: self.runtime.actors[actor_id].location_id for actor_id in state["floor8_actor_ids"]
            },
            "hideout_responder_locations": {
                actor_id: self.runtime.actors[actor_id].location_id for actor_id in state["hideout_actor_ids"]
            },
            "frontline_actors": frontline_actors,
            "forest_elf_actors": forest_elf_actors,
            "clearing_guilds": guilds,
            "guild_decision_authority": self._guild_decision_authority(),
            "frontline_parties": {
                party_id: {
                    "leader_id": self.runtime.world.parties[party_id].leader_id,
                    "member_ids": list(self.runtime.world.parties[party_id].member_ids),
                }
                for party_id in incident["frontline_party_ids"]
            },
            "forest_elf_party": (
                {
                    "party_id": incident["forest_elf_party_id"],
                    "leader_id": self.runtime.world.parties[incident["forest_elf_party_id"]].leader_id,
                    "member_ids": list(self.runtime.world.parties[incident["forest_elf_party_id"]].member_ids),
                }
                if incident["forest_elf_party_id"] is not None
                else None
            ),
            "next_stage": (
                "choose which Nocturne players respond to Floor 8 and which continue the sacred-key hideout route"
                if state["stage"] == "argo_message_sent"
                else "Floor 8 responders must reach the already-active Frieben Teleport Gate through ordinary teleport/travel rules"
                if state["stage"] == "response_split_assigned" and state["floor8_actor_ids"]
                else "the Floor 8 incident remains unresolved because this split assigned no responder"
                if state["stage"] == "response_split_assigned"
                else "walk from the Frieben gate to Argo and Klein at the Acorn Shop rendezvous"
                if state["stage"] == "responders_at_frieben"
                else "leave the Acorn Shop through Frieben and enter the outer managed forest toward the protected woods"
                if state["stage"] == "responders_briefed_at_acorn_shop"
                else "inspect the protected-woods damage and the materialized local representatives without treating them as the full reported guild majorities"
                if state["stage"] == "responders_at_sacred_woods"
                else "follow the Forest Elf pursuit party to the escape-cave mouth"
                if state["stage"] == "sacred_woods_incident_confirmed"
                else "decide whether the responders enter the cave while Forest Elf pursuers remain outside"
                if state["stage"] == "cave_mouth_standoff"
                else "local standoff reached: materialized representatives are inside the cave and Forest Elf pursuers remain outside; the wider guild-scale crisis remains unresolved"
                if state["stage"] == "responders_inside_cave_standoff"
                else None
            ),
        }


def install_floor8_forest_emergency_scenario(runtime, nocturne) -> Floor8ForestEmergencyScenario:
    for location_id in (
        FRIEBEN,
        ACORN_SHOP,
        MANAGED_FOREST_OUTER,
        FOREST_ELF_SACRED_WOODS,
        FOREST_ELF_ESCAPE_CAVE_MOUTH,
        FOREST_ELF_ESCAPE_CAVE,
    ):
        if location_id not in runtime.world_map.locations:
            raise RuntimeError(f"Floor 8 world corpus is missing {location_id}")
    for npc_id in (ARGO_ID, KLEIN_ID):
        if npc_id not in runtime.npcs.definitions:
            raise RuntimeError(f"Floor 8 Progressive corpus was not loaded: {npc_id}")
    if not hasattr(runtime, "communications") or not hasattr(runtime, "relationships"):
        raise RuntimeError("Floor 8 emergency requires the communicating relationship runtime")
    return Floor8ForestEmergencyScenario(runtime, nocturne)
