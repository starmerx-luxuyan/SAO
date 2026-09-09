from __future__ import annotations

import uuid
from dataclasses import asdict

from sao_mcp.corpus.floor8_world import FOREST_ELF_SACRED_WOODS, SLUVA
from sao_mcp.corpus.location_access import FOREST_ELVES
from sao_mcp.corpus.progressive_guilds import ALS_GUILD_ID, DKB_GUILD_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind
from sao_mcp.rules.factions import adjust_faction_standing, faction_standing
from sao_mcp.rules.group_travel import group_travel_record, travel_together


FORMAL_CHARGE_STANDING_DELTA = -15
RESTITUTION_STANDING_RECOVERY = 3
SERVICE_STANDING_RECOVERY = 5
HEARING_TIME_MS = 15 * 60_000
JUDGMENT_TIME_MS = 10 * 60_000
RESTITUTION_COL = 1_800
RESTORATIVE_SERVICE_MS = 2 * 60 * 60_000


class Floor8SluvaJusticeScenario:
    """Sluva custody/hearing layer for the materialized local Floor 8 representatives.

    Progressive 9 establishes the wider protected-tree crisis, Sluva, and a Dark Elf assessment
    that capture exposes the responsible commander to execution and the remaining offenders to
    imprisonment. The runtime docket applies only to the actors actually transferred into Sluva
    custody. Exact court procedure, money, service duration and any commutation/pardon are
    simulation so the campaign can diverge without pretending an unpublished resolution is canon.
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
        matches = [actor for actor in self.runtime.actors.values() if actor.metadata.get("floor8_sluva_arbiter") is True]
        if len(matches) > 1:
            raise RuntimeError("multiple authoritative Sluva arbiters exist")
        if matches:
            arbiter = matches[0]
            if arbiter.kind is not EntityKind.NPC:
                raise RuntimeError("the authoritative Sluva arbiter is not an NPC actor")
            if not arbiter.alive or arbiter.location_id != SLUVA:
                raise ValueError("the Sluva arbiter must be alive and present in Sluva")
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
                "faction_ids": (FOREST_ELVES,),
                "floor8_sluva_arbiter": True,
                "personal_identity_provenance": "simulation",
                "legal_role_provenance": "simulation_from_progressive9_sluva_context",
            },
        )
        self.runtime.actors[actor_id] = arbiter
        return arbiter

    def _guild_ids(self, state: dict) -> list[str]:
        custody_ids = self._custody_ids(state)
        guild_ids = sorted({self.runtime.actors[actor_id].guild_id for actor_id in custody_ids})
        if guild_ids != [ALS_GUILD_ID, DKB_GUILD_ID]:
            raise RuntimeError("Sluva custody no longer matches the materialized ALS/DKB representatives")
        for guild_id in guild_ids:
            if guild_id not in self.runtime.relationships.guilds:
                raise RuntimeError(f"Sluva custody references missing authoritative GuildState {guild_id}")
            guild = self.runtime.relationships.guilds[guild_id]
            if guild.storage_id not in self.runtime.relationships.storages:
                raise RuntimeError(f"authoritative GuildState {guild_id} has no shared storage")
            storage = self.runtime.relationships.storages[guild.storage_id]
            expected_members = {
                actor_id for actor_id in custody_ids if self.runtime.actors[actor_id].guild_id == guild_id
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
            raise ValueError("Sluva hearing requires the materialized local custody branch to have reached Sluva")
        if "sluva_justice" in state:
            raise ValueError("this materialized custody case already has a Sluva legal docket")
        custody_ids = self._custody_ids(state)
        forest_ids = self._forest_ids(state)
        self._require_ids_at(custody_ids, SLUVA)
        self._require_ids_at(forest_ids, SLUVA)
        advocate = self.runtime.actors[advocate_actor_id]
        eligible = set(state["floor8_actor_ids"]) | set(custody_ids)
        if advocate_actor_id not in eligible or advocate.kind is not EntityKind.PLAYER:
            raise ValueError("Sluva advocate must be a linked player from the response or custody group")
        if not advocate.alive or advocate.location_id != SLUVA:
            raise ValueError("Sluva advocate must be alive and physically present in Sluva")

        arbiter = self._arbiter()
        guild_ids = self._guild_ids(state)
        guild_changes = [
            asdict(
                adjust_faction_standing(
                    self.runtime.world,
                    guild_id,
                    FOREST_ELVES,
                    FORMAL_CHARGE_STANDING_DELTA,
                    reason="formal Sluva grave charge against materialized Floor 8 representatives",
                )
            )
            for guild_id in guild_ids
        ]
        self.runtime.advance_world(HEARING_TIME_MS)
        state["sluva_justice"] = {
            "status": "hearing_open",
            "arbiter_actor_id": arbiter.actor_id,
            "advocate_actor_id": advocate_actor_id,
            "custody_actor_ids": list(custody_ids),
            "guild_ids": guild_ids,
            "charges": [
                {
                    "code": "protected_tree_incident_participation",
                    "severity": "grave",
                    "description": (
                        "custody case arising from the felling of a large protected living tree; "
                        "the individual principal has not yet been established"
                    ),
                    "provenance": "canon_incident_cause_and_penalty_risk_plus_simulation_legal_framing",
                },
                {
                    "code": "flight_from_wardens",
                    "severity": "aggravating",
                    "description": "the materialized representatives fled from Forest Elf wardens into the escape cave",
                    "provenance": "runtime_materialized_incident_plus_simulation_legal_code",
                },
            ],
            "known_penalty_risk": {
                "principal_or_commander": "execution_risk",
                "other_participants": "imprisonment_risk",
                "provenance": "Progressive 9 Dark Elf assessment; actual Sluva disposition remains unresolved here",
            },
            "hearing_opened_at_ms": self.runtime.world.now_ms,
            "formal_charge_standing_changes": guild_changes,
            "judgment": None,
            "principal_finding": None,
            "mitigation": [],
            "disposition": None,
            "resolved_at_ms": None,
        }
        state["stage"] = "sluva_hearing_open"
        return self.status(instance_id)

    def issue_grave_judgment(self, instance_id: str, arbiter_actor_id: str) -> dict:
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
            "baseline": "grave_penalties_pending_principal_finding",
            "principal_risk": "execution_order",
            "other_participant_risk": "imprisonment",
            "mitigation_options": ["restitution_deposit", "restorative_service"],
            "provenance": "canon severity basis plus simulation procedure; no unpublished final outcome is asserted",
        }
        docket["status"] = "grave_judgment_issued"
        state["stage"] = "sluva_grave_judgment_issued"
        return self.status(instance_id)

    def adjudicate_principal(
        self,
        instance_id: str,
        arbiter_actor_id: str,
        principal_actor_id: str,
    ) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "sluva_grave_judgment_issued":
            raise ValueError("principal adjudication requires an unresolved grave Sluva judgment")
        docket = state["sluva_justice"]
        if arbiter_actor_id != docket["arbiter_actor_id"]:
            raise ValueError("only the authoritative Sluva arbiter can adjudicate the principal")
        arbiter = self.runtime.actors[arbiter_actor_id]
        if not arbiter.alive or arbiter.location_id != SLUVA:
            raise ValueError("the Sluva arbiter must remain alive and present")
        custody_ids = self._custody_ids(state)
        if principal_actor_id not in custody_ids:
            raise ValueError("the adjudicated principal must be one of the materialized detainees")
        self._require_ids_at(custody_ids, SLUVA)

        docket["principal_finding"] = {
            "actor_id": principal_actor_id,
            "finding": "principal_or_commander_for_materialized_local_case",
            "adjudicated_by_actor_id": arbiter_actor_id,
            "adjudicated_at_ms": self.runtime.world.now_ms,
            "provenance": (
                "simulation Sluva judicial finding; Progressive 9 establishes differential penalty risk "
                "but does not identify this campaign's principal"
            ),
        }
        docket["status"] = "principal_adjudicated"
        state["stage"] = "sluva_principal_adjudicated"
        return self.status(instance_id)

    def deposit_restitution_mitigation(self, instance_id: str, payer_actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] not in {"sluva_grave_judgment_issued", "sluva_principal_adjudicated"}:
            raise ValueError("restitution mitigation requires an unresolved grave Sluva judgment")
        docket = state["sluva_justice"]
        if any(row["kind"] == "restitution_deposit" for row in docket["mitigation"]):
            raise ValueError("this Sluva docket already has a restitution deposit")
        payer = self.runtime.actors[payer_actor_id]
        eligible = set(state["floor8_actor_ids"]) | set(self._custody_ids(state))
        if payer_actor_id not in eligible or payer.kind is not EntityKind.PLAYER:
            raise ValueError("Sluva restitution payer must be a linked player")
        if not payer.alive or payer.location_id != SLUVA:
            raise ValueError("Sluva restitution payer must be alive and present in Sluva")
        if payer.col < RESTITUTION_COL:
            raise ValueError("payer does not hold enough Col for the Sluva restitution deposit")
        arbiter = self.runtime.actors[docket["arbiter_actor_id"]]
        if not arbiter.alive or arbiter.location_id != SLUVA:
            raise ValueError("the authoritative Sluva arbiter is unavailable to receive restitution")

        payer.col -= RESTITUTION_COL
        arbiter.col += RESTITUTION_COL
        standing_changes = [
            asdict(
                adjust_faction_standing(
                    self.runtime.world,
                    guild_id,
                    FOREST_ELVES,
                    RESTITUTION_STANDING_RECOVERY,
                    reason="restitution deposited as mitigation for the materialized Sluva case",
                )
            )
            for guild_id in docket["guild_ids"]
        ]
        docket["mitigation"].append(
            {
                "kind": "restitution_deposit",
                "payer_actor_id": payer_actor_id,
                "col": RESTITUTION_COL,
                "at_ms": self.runtime.world.now_ms,
                "standing_changes": standing_changes,
            }
        )
        return self.status(instance_id)

    def perform_restorative_service_mitigation(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] not in {"sluva_grave_judgment_issued", "sluva_principal_adjudicated"}:
            raise ValueError("restorative-service mitigation requires an unresolved grave Sluva judgment")
        docket = state["sluva_justice"]
        if any(row["kind"] == "restorative_service" for row in docket["mitigation"]):
            raise ValueError("this Sluva docket already completed restorative service")
        custody_ids = self._custody_ids(state)
        forest_ids = self._forest_ids(state)
        self._require_ids_at(custody_ids, SLUVA)
        self._require_ids_at(forest_ids, SLUVA)

        outward = travel_together(self.runtime, custody_ids + forest_ids, FOREST_ELF_SACRED_WOODS)
        service_started = self.runtime.world.now_ms
        self.runtime.advance_world(RESTORATIVE_SERVICE_MS)
        returning = travel_together(self.runtime, custody_ids + forest_ids, SLUVA)
        standing_changes = [
            asdict(
                adjust_faction_standing(
                    self.runtime.world,
                    guild_id,
                    FOREST_ELVES,
                    SERVICE_STANDING_RECOVERY,
                    reason="restorative forest service completed for the materialized Sluva case",
                )
            )
            for guild_id in docket["guild_ids"]
        ]
        docket["mitigation"].append(
            {
                "kind": "restorative_service",
                "service_started_at_ms": service_started,
                "service_completed_at_ms": self.runtime.world.now_ms - returning.elapsed_ms,
                "service_ms": RESTORATIVE_SERVICE_MS,
                "outward_route": [group_travel_record(outward)],
                "return_route": [group_travel_record(returning)],
                "standing_changes": standing_changes,
            }
        )
        return self.status(instance_id)

    def issue_disposition(
        self,
        instance_id: str,
        arbiter_actor_id: str,
        disposition: str,
    ) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "sluva_principal_adjudicated":
            raise ValueError("Sluva disposition requires an adjudicated principal")
        docket = state["sluva_justice"]
        if arbiter_actor_id != docket["arbiter_actor_id"]:
            raise ValueError("only the authoritative Sluva arbiter can issue the disposition")
        arbiter = self.runtime.actors[arbiter_actor_id]
        if not arbiter.alive or arbiter.location_id != SLUVA:
            raise ValueError("the Sluva arbiter must remain alive and present")
        custody_ids = self._custody_ids(state)
        self._require_ids_at(custody_ids, SLUVA)
        principal_actor_id = docket["principal_finding"]["actor_id"]
        if disposition not in {"strict", "commuted", "pardon"}:
            raise ValueError("disposition must be strict, commuted, or pardon")
        if disposition in {"commuted", "pardon"} and not docket["mitigation"]:
            raise ValueError("commutation or pardon requires an actual mitigation action on this docket")

        if disposition == "strict":
            sentences = {
                actor_id: "execution_ordered" if actor_id == principal_actor_id else "imprisonment_ordered"
                for actor_id in custody_ids
            }
            state["stage"] = "sluva_disposition_strict"
        elif disposition == "commuted":
            sentences = {actor_id: "imprisonment_ordered" for actor_id in custody_ids}
            state["stage"] = "sluva_disposition_commuted"
        else:
            self._release_custody(state, resolution="sluva_explicit_pardon")
            sentences = {actor_id: "pardoned" for actor_id in custody_ids}
            state["stage"] = "sluva_disposition_pardon"

        docket["status"] = "disposed"
        docket["disposition"] = {
            "kind": disposition,
            "sentences": sentences,
            "issued_at_ms": self.runtime.world.now_ms,
            "campaign_deviation": disposition == "pardon",
            "execution_not_auto_resolved": disposition == "strict",
        }
        docket["resolved_at_ms"] = self.runtime.world.now_ms
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        payload = self.emergency.status(instance_id)
        docket = state.get("sluva_justice")
        if docket is None:
            payload["sluva_justice_available"] = state["stage"] == "standoff_resolved_custody"
            payload["sluva_justice"] = None
            payload["sluva_case_scope"] = None
            return payload
        standing = {
            guild_id: faction_standing(self.runtime.world, guild_id, FOREST_ELVES)
            for guild_id in docket["guild_ids"]
        }
        disposition = docket["disposition"]
        sentences = (
            dict(disposition["sentences"])
            if disposition is not None
            else {actor_id: None for actor_id in docket["custody_actor_ids"]}
        )
        payload.update(
            {
                "sluva_justice_available": True,
                "sluva_justice": docket,
                "sluva_case_scope": {
                    "resolution_scope": payload["local_materialization"]["resolution_scope"],
                    "custody_actor_ids": list(docket["custody_actor_ids"]),
                },
                "forest_elf_guild_standing": standing,
                "custody_locations": {
                    actor_id: self.runtime.actors[actor_id].location_id
                    for actor_id in docket["custody_actor_ids"]
                },
                "custody_active": {
                    actor_id: self.runtime.actors[actor_id].metadata.get("forest_elf_custody") is True
                    for actor_id in docket["custody_actor_ids"]
                },
                "sentences": sentences,
                "arbiter_location_id": self.runtime.actors[docket["arbiter_actor_id"]].location_id,
            }
        )
        return payload


def install_floor8_sluva_justice_scenario(runtime, emergency) -> Floor8SluvaJusticeScenario:
    for location_id in (SLUVA, FOREST_ELF_SACRED_WOODS):
        if location_id not in runtime.world_map.locations:
            raise RuntimeError(f"Floor 8 Sluva justice world corpus is missing {location_id}")
    return Floor8SluvaJusticeScenario(runtime, emergency)
