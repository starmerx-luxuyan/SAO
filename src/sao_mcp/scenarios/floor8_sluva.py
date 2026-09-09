from __future__ import annotations

import uuid
from dataclasses import asdict

from sao_mcp.corpus.floor8_world import FOREST_ELF_SACRED_WOODS, SLUVA
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind
from sao_mcp.rules.factions import adjust_faction_standing, faction_standing
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.runtime.canonical_guilds import ALS_GUILD_ID, DKB_GUILD_ID


FOREST_ELF_FACTION_ID = "forest_elves"
FORMAL_CHARGE_STANDING_DELTA = -8
RESTITUTION_STANDING_RECOVERY = 4
SERVICE_STANDING_RECOVERY = 6
HEARING_TIME_MS = 15 * 60_000
JUDGMENT_TIME_MS = 10 * 60_000
RESTITUTION_COL = 1_800
RESTORATIVE_SERVICE_MS = 2 * 60 * 60_000


class Floor8SluvaJusticeScenario:
    """Simulation legal layer for custody outcomes at the canon-backed Forest Elf capital Sluva.

    Progressive 9 establishes the protected-woods conflict and Sluva as the Forest Elf capital.
    The hearing procedure, Col amounts, service duration, and standing numbers below are explicit
    simulation rules so the incident can remain playable without inventing an unpublished canon result.
    """

    def __init__(self, runtime, emergency) -> None:
        if emergency.runtime is not runtime:
            raise RuntimeError("Sluva justice and Floor 8 emergency services must share one runtime")
        self.runtime = runtime
        self.emergency = emergency

    def _state(self, instance_id: str) -> dict:
        return self.emergency._state(instance_id)

    def _incident(self, state: dict) -> dict:
        return state["incident"]

    def _custody_ids(self, state: dict) -> list[str]:
        return list(state["custody_actor_ids"])

    def _forest_ids(self, state: dict) -> list[str]:
        return list(self._incident(state)["forest_elf_actor_ids"])

    def _require_ids_at(self, actor_ids: list[str], location_id: str) -> None:
        wrong = [actor_id for actor_id in actor_ids if self.runtime.actors[actor_id].location_id != location_id]
        if wrong:
            raise ValueError(f"actors are not all at {location_id}: {', '.join(wrong)}")

    def _arbiter(self) -> CombatantState:
        matches = [
            actor
            for actor in self.runtime.actors.values()
            if actor.metadata.get("floor8_sluva_arbiter") is True
        ]
        if len(matches) > 1:
            raise RuntimeError("multiple authoritative Sluva arbiters exist")
        if matches:
            arbiter = matches[0]
            if arbiter.kind is not EntityKind.NPC:
                raise RuntimeError("the authoritative Sluva arbiter is not an NPC actor")
            if not arbiter.alive:
                raise ValueError("the Sluva arbiter is not alive")
            if arbiter.location_id != SLUVA:
                raise ValueError("the Sluva arbiter is not currently at Sluva")
            return arbiter

        actor_id = f"forestelf8_arbiter_{uuid.uuid4().hex[:10]}"
        arbiter = CombatantState(
            actor_id=actor_id,
            name="Sluva Forest Arbiter",
            kind=EntityKind.NPC,
            level=24,
            max_hp=5200,
            hp=5200,
            strength=42,
            agility=48,
            armor=90,
            evasion=10,
            cursor=CursorColor.YELLOW,
            location_id=SLUVA,
            metadata={
                "forest_elf": True,
                "floor8_sluva_arbiter": True,
                "personal_identity_provenance": "simulation",
                "legal_role_provenance": "simulation_from_progressive9_sluva_and_protected_woods_context",
            },
        )
        self.runtime.actors[actor_id] = arbiter
        return arbiter

    def _guild_ids(self, state: dict) -> list[str]:
        custody_ids = self._custody_ids(state)
        guild_ids = sorted({self.runtime.actors[actor_id].guild_id for actor_id in custody_ids})
        if guild_ids != [ALS_GUILD_ID, DKB_GUILD_ID]:
            raise RuntimeError("Sluva custody no longer matches the materialized ALS/DKB incident parties")
        for guild_id in guild_ids:
            if guild_id not in self.runtime.relationships.guilds:
                raise RuntimeError(f"Sluva custody references missing authoritative GuildState {guild_id}")
            guild = self.runtime.relationships.guilds[guild_id]
            if guild.storage_id not in self.runtime.relationships.storages:
                raise RuntimeError(f"authoritative GuildState {guild_id} has no shared storage")
            storage = self.runtime.relationships.storages[guild.storage_id]
            expected_members = {
                actor_id
                for actor_id in custody_ids
                if self.runtime.actors[actor_id].guild_id == guild_id
            }
            if not expected_members.issubset(set(guild.member_ids)):
                raise RuntimeError(f"Sluva custody actors are absent from GuildState {guild_id}")
            if not expected_members.issubset(set(storage.member_ids)):
                raise RuntimeError(f"Sluva custody actors are absent from guild storage membership {guild_id}")
        return guild_ids

    def _release_custody(self, state: dict, *, resolution: str) -> None:
        for actor_id in self._custody_ids(state):
            actor = self.runtime.actors[actor_id]
            actor.metadata["forest_elf_custody"] = False
            actor.metadata["forest_elf_custody_ended_at_ms"] = self.runtime.world.now_ms
            actor.metadata["forest_elf_custody_resolution"] = resolution

    def open_hearing(self, instance_id: str, advocate_actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "standoff_resolved_custody":
            raise ValueError("Sluva hearing requires the real custody branch to have reached Sluva")
        if "sluva_justice" in state:
            raise ValueError("this Floor 8 incident already has a Sluva legal docket")
        custody_ids = self._custody_ids(state)
        forest_ids = self._forest_ids(state)
        self._require_ids_at(custody_ids, SLUVA)
        self._require_ids_at(forest_ids, SLUVA)
        advocate = self.runtime.actors[advocate_actor_id]
        eligible = set(state["floor8_actor_ids"]) | set(custody_ids)
        if advocate_actor_id not in eligible or advocate.kind is not EntityKind.PLAYER:
            raise ValueError("Sluva advocate must be a linked player from the emergency or custody group")
        if not advocate.alive or advocate.location_id != SLUVA:
            raise ValueError("Sluva advocate must be alive and physically present in Sluva")

        arbiter = self._arbiter()
        guild_changes = []
        guild_ids = self._guild_ids(state)
        for guild_id in guild_ids:
            guild_changes.append(
                asdict(
                    adjust_faction_standing(
                        self.runtime.world,
                        guild_id,
                        FOREST_ELF_FACTION_ID,
                        FORMAL_CHARGE_STANDING_DELTA,
                        reason="formal Sluva charge for the Floor 8 protected-woods incident",
                    )
                )
            )
        self.runtime.advance_world(HEARING_TIME_MS)
        state["sluva_justice"] = {
            "status": "hearing_open",
            "arbiter_actor_id": arbiter.actor_id,
            "advocate_actor_id": advocate_actor_id,
            "custody_actor_ids": list(custody_ids),
            "guild_ids": guild_ids,
            "charges": [
                {
                    "code": "protected_woods_damage",
                    "description": "unauthorized felling of protected Forest Elf trees",
                    "provenance": "simulation_legal_code_for_canon_progressive9_incident",
                },
                {
                    "code": "flight_from_warden",
                    "description": "flight from Forest Elf wardens into the escape cave",
                    "provenance": "simulation_legal_code_for_canon_progressive9_incident",
                },
            ],
            "hearing_opened_at_ms": self.runtime.world.now_ms,
            "formal_charge_standing_changes": guild_changes,
            "judgment": None,
            "refused_at_ms": None,
            "resolved_at_ms": None,
            "resolution": None,
        }
        state["stage"] = "sluva_hearing_open"
        return self.status(instance_id)

    def issue_restorative_judgment(self, instance_id: str, arbiter_actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "sluva_hearing_open":
            raise ValueError("Sluva hearing is not open for judgment")
        docket = state["sluva_justice"]
        if arbiter_actor_id != docket["arbiter_actor_id"]:
            raise ValueError("only the authoritative Sluva arbiter can issue this judgment")
        arbiter = self.runtime.actors[arbiter_actor_id]
        if not arbiter.alive or arbiter.location_id != SLUVA:
            raise ValueError("the Sluva arbiter must remain alive and present")
        self._require_ids_at(self._custody_ids(state), SLUVA)

        self.runtime.advance_world(JUDGMENT_TIME_MS)
        docket["judgment"] = {
            "issued_at_ms": self.runtime.world.now_ms,
            "restitution_col": RESTITUTION_COL,
            "restorative_service_ms": RESTORATIVE_SERVICE_MS,
            "choices": ["pay_restitution", "perform_restorative_service", "refuse"],
            "provenance": "simulation_values; Progressive 9 does not publish a Sluva judgment for this incident",
        }
        docket["status"] = "judgment_issued"
        state["stage"] = "sluva_judgment_issued"
        return self.status(instance_id)

    def satisfy_with_restitution(self, instance_id: str, payer_actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] not in {"sluva_judgment_issued", "sluva_judgment_refused"}:
            raise ValueError("there is no unresolved Sluva judgment available for restitution")
        docket = state["sluva_justice"]
        payer = self.runtime.actors[payer_actor_id]
        eligible = set(state["floor8_actor_ids"]) | set(self._custody_ids(state))
        if payer_actor_id not in eligible or payer.kind is not EntityKind.PLAYER:
            raise ValueError("Sluva restitution payer must be a linked player")
        if not payer.alive or payer.location_id != SLUVA:
            raise ValueError("Sluva restitution payer must be alive and present in Sluva")
        amount = int(docket["judgment"]["restitution_col"])
        if payer.col < amount:
            raise ValueError("payer does not hold enough Col to satisfy the Sluva judgment")
        arbiter = self.runtime.actors[docket["arbiter_actor_id"]]
        if arbiter.location_id != SLUVA or not arbiter.alive:
            raise ValueError("the authoritative Sluva arbiter is unavailable to receive restitution")

        payer.col -= amount
        arbiter.col += amount
        standing_changes = []
        for guild_id in docket["guild_ids"]:
            standing_changes.append(
                asdict(
                    adjust_faction_standing(
                        self.runtime.world,
                        guild_id,
                        FOREST_ELF_FACTION_ID,
                        RESTITUTION_STANDING_RECOVERY,
                        reason="Sluva judgment satisfied by restitution",
                    )
                )
            )
        self._release_custody(state, resolution="sluva_restitution")
        docket["status"] = "resolved"
        docket["resolution"] = {
            "kind": "restitution",
            "payer_actor_id": payer_actor_id,
            "col_paid": amount,
            "standing_changes": standing_changes,
        }
        docket["resolved_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "sluva_justice_resolved_restitution"
        return self.status(instance_id)

    def satisfy_with_restorative_service(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] not in {"sluva_judgment_issued", "sluva_judgment_refused"}:
            raise ValueError("there is no unresolved Sluva judgment available for restorative service")
        docket = state["sluva_justice"]
        custody_ids = self._custody_ids(state)
        forest_ids = self._forest_ids(state)
        self._require_ids_at(custody_ids, SLUVA)
        self._require_ids_at(forest_ids, SLUVA)

        travel_together(self.runtime, custody_ids + forest_ids, FOREST_ELF_SACRED_WOODS)
        service_started = self.runtime.world.now_ms
        self.runtime.advance_world(RESTORATIVE_SERVICE_MS)
        standing_changes = []
        for guild_id in docket["guild_ids"]:
            standing_changes.append(
                asdict(
                    adjust_faction_standing(
                        self.runtime.world,
                        guild_id,
                        FOREST_ELF_FACTION_ID,
                        SERVICE_STANDING_RECOVERY,
                        reason="Sluva judgment satisfied by restorative forest service",
                    )
                )
            )
        self._release_custody(state, resolution="sluva_restorative_service")
        docket["status"] = "resolved"
        docket["resolution"] = {
            "kind": "restorative_service",
            "service_started_at_ms": service_started,
            "service_completed_at_ms": self.runtime.world.now_ms,
            "service_ms": RESTORATIVE_SERVICE_MS,
            "release_location_id": FOREST_ELF_SACRED_WOODS,
            "standing_changes": standing_changes,
        }
        docket["resolved_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "sluva_justice_resolved_service"
        return self.status(instance_id)

    def refuse_judgment(self, instance_id: str, actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "sluva_judgment_issued":
            raise ValueError("there is no newly issued Sluva judgment to refuse")
        docket = state["sluva_justice"]
        if actor_id not in docket["custody_actor_ids"]:
            raise ValueError("only a player currently held on this docket can refuse the judgment")
        actor = self.runtime.actors[actor_id]
        if not actor.alive or actor.location_id != SLUVA or actor.metadata.get("forest_elf_custody") is not True:
            raise ValueError("the refusing player must still be alive and in Sluva custody")
        docket["status"] = "judgment_refused"
        docket["refused_at_ms"] = self.runtime.world.now_ms
        docket["refused_by_actor_id"] = actor_id
        state["stage"] = "sluva_judgment_refused"
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        docket = state.get("sluva_justice")
        if docket is None:
            return {
                "instance_id": instance_id,
                "stage": state["stage"],
                "sluva_justice_available": state["stage"] == "standoff_resolved_custody",
                "sluva_justice": None,
            }
        standing = {
            guild_id: faction_standing(self.runtime.world, guild_id, FOREST_ELF_FACTION_ID)
            for guild_id in docket["guild_ids"]
        }
        return {
            "instance_id": instance_id,
            "stage": state["stage"],
            "sluva_justice_available": True,
            "sluva_justice": docket,
            "forest_elf_guild_standing": standing,
            "custody_locations": {
                actor_id: self.runtime.actors[actor_id].location_id
                for actor_id in docket["custody_actor_ids"]
            },
            "custody_active": {
                actor_id: self.runtime.actors[actor_id].metadata.get("forest_elf_custody") is True
                for actor_id in docket["custody_actor_ids"]
            },
            "arbiter_location_id": self.runtime.actors[docket["arbiter_actor_id"]].location_id,
        }


def install_floor8_sluva_justice_scenario(runtime, emergency) -> Floor8SluvaJusticeScenario:
    for location_id in (SLUVA, FOREST_ELF_SACRED_WOODS):
        if location_id not in runtime.world_map.locations:
            raise RuntimeError(f"Floor 8 Sluva justice world corpus is missing {location_id}")
    return Floor8SluvaJusticeScenario(runtime, emergency)
