import pytest

from sao_mcp.corpus.floor8_progressive import FLOOR8_GUILD_CRISIS_REPORT
from sao_mcp.corpus.floor8_world import ARBOREAL_ROUTE_TAGS, FOREST_ELF_SACRED_WOODS, SLUVA
from sao_mcp.corpus.location_access import FOREST_ELVES
from sao_mcp.corpus.progressive_guilds import ALS_GUILD_ID, DKB_GUILD_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, PartyState
from sao_mcp.runtime.canonical_guilds import install_progressive_clearing_guilds
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor8_emergency import LOCAL_REPRESENTATION_SCOPE, LOCAL_RESOLUTION_SCOPE
from sao_mcp.scenarios.floor8_sluva import (
    HEARING_TIME_MS,
    JUDGMENT_TIME_MS,
    RESTITUTION_COL,
    RESTORATIVE_SERVICE_MS,
    install_floor8_sluva_justice_scenario,
)


INSTANCE_ID = "floor8_sluva_fixture"


class _EmergencyStub:
    def __init__(self, runtime):
        self.runtime = runtime

    def _state(self, instance_id):
        assert instance_id == INSTANCE_ID
        return self.runtime.world.global_flags["floor8_forest_emergency_instances"][instance_id]

    def status(self, instance_id):
        state = self._state(instance_id)
        return {
            "instance_id": instance_id,
            "stage": state["stage"],
            "guild_crisis_report": {
                "affected_guild_ids": list(FLOOR8_GUILD_CRISIS_REPORT.affected_guild_ids),
                "affected_member_scope": FLOOR8_GUILD_CRISIS_REPORT.affected_member_scope,
            },
            "local_materialization": {
                "representation_scope": LOCAL_REPRESENTATION_SCOPE,
                "resolution_scope": LOCAL_RESOLUTION_SCOPE,
            },
        }


def _forest_actor(actor_id, name):
    return CombatantState(
        actor_id=actor_id,
        name=name,
        kind=EntityKind.NPC,
        level=30,
        max_hp=7600,
        hp=7600,
        strength=68,
        agility=74,
        armor=170,
        evasion=16,
        cursor=CursorColor.YELLOW,
        location_id=SLUVA,
        metadata={"faction_ids": (FOREST_ELVES,), "floor8_protected_woods_enforcement": True},
    )


def _setup_custody(seed=241):
    runtime = HousingAincradRuntime(seed=seed)
    runtime.world.floors[8].unlocked = True
    guilds = install_progressive_clearing_guilds(runtime)
    players = []
    for index, guild_id in enumerate((ALS_GUILD_ID, ALS_GUILD_ID, DKB_GUILD_ID, DKB_GUILD_ID), start=1):
        actor = runtime.create_character(f"Sluva Custody {index}", level=26)
        actor.location_id = SLUVA
        actor.metadata["forest_elf_custody"] = True
        actor.metadata["forest_elf_custody_location_id"] = SLUVA
        guild = guilds[guild_id]
        invite = runtime.invite_to_guild(guild_id, guild.leader_id, actor.actor_id)
        runtime.accept_guild_invite(invite.invite_id, actor.actor_id)
        players.append(actor)

    forest = [
        _forest_actor("sluva_warden_fixture", "Forest Elf Warden"),
        _forest_actor("sluva_ranger_fixture", "Forest Elf Ranger"),
    ]
    for actor in forest:
        runtime.actors[actor.actor_id] = actor
    party = PartyState("party8_sluva_forest_fixture", forest[0].actor_id, [actor.actor_id for actor in forest])
    runtime.world.parties[party.party_id] = party
    for actor in forest:
        actor.party_id = party.party_id

    runtime.world.global_flags["floor8_forest_emergency_instances"] = {
        INSTANCE_ID: {
            "instance_id": INSTANCE_ID,
            "stage": "standoff_resolved_custody",
            "floor8_actor_ids": [players[0].actor_id],
            "custody_actor_ids": [actor.actor_id for actor in players],
            "incident": {
                "forest_elf_actor_ids": [actor.actor_id for actor in forest],
                "forest_elf_party_id": party.party_id,
                "frontline_actor_ids": [actor.actor_id for actor in players],
            },
        }
    }
    emergency = _EmergencyStub(runtime)
    sluva = install_floor8_sluva_justice_scenario(runtime, emergency)
    return runtime, emergency, sluva, players, forest


def test_sluva_principal_finding_is_explicit_before_strict_disposition():
    runtime, emergency, sluva, players, forest = _setup_custody()
    payer = players[0]
    payer.col = 3_000
    started = runtime.world.now_ms

    hearing = sluva.open_hearing(INSTANCE_ID, payer.actor_id)
    assert hearing["stage"] == "sluva_hearing_open"
    assert runtime.world.now_ms - started == HEARING_TIME_MS
    assert hearing["guild_crisis_report"]["affected_member_scope"] == "majority_of_each_guild"
    assert hearing["local_materialization"]["resolution_scope"] == "materialized_local_standoff_only"
    assert hearing["sluva_case_scope"] == {
        "resolution_scope": "materialized_local_standoff_only",
        "custody_actor_ids": [actor.actor_id for actor in players],
    }
    assert hearing["forest_elf_guild_standing"] == {ALS_GUILD_ID: -15, DKB_GUILD_ID: -15}
    assert hearing["sluva_justice"]["charges"][0] == {
        "code": "protected_tree_incident_participation",
        "severity": "grave",
        "description": (
            "custody case arising from the felling of a large protected living tree; "
            "the individual principal has not yet been established"
        ),
        "provenance": "canon_incident_cause_and_penalty_risk_plus_simulation_legal_framing",
    }
    assert hearing["sluva_justice"]["principal_finding"] is None
    assert hearing["sentences"] == {actor.actor_id: None for actor in players}
    assert hearing["sluva_justice"]["known_penalty_risk"] == {
        "principal_or_commander": "execution_risk",
        "other_participants": "imprisonment_risk",
        "provenance": "Progressive 9 Dark Elf assessment; actual Sluva disposition remains unresolved here",
    }

    arbiter_id = hearing["sluva_justice"]["arbiter_actor_id"]
    judged = sluva.issue_grave_judgment(INSTANCE_ID, arbiter_id)
    assert judged["stage"] == "sluva_grave_judgment_issued"
    assert runtime.world.now_ms - started == HEARING_TIME_MS + JUDGMENT_TIME_MS
    with pytest.raises(ValueError, match="requires an adjudicated principal"):
        sluva.issue_disposition(INSTANCE_ID, arbiter_id, "strict")

    finding = sluva.adjudicate_principal(INSTANCE_ID, arbiter_id, players[0].actor_id)
    assert finding["stage"] == "sluva_principal_adjudicated"
    assert finding["sluva_justice"]["principal_finding"] == {
        "actor_id": players[0].actor_id,
        "finding": "principal_or_commander_for_materialized_local_case",
        "adjudicated_by_actor_id": arbiter_id,
        "adjudicated_at_ms": runtime.world.now_ms,
        "provenance": (
            "simulation Sluva judicial finding; Progressive 9 establishes differential penalty risk "
            "but does not identify this campaign's principal"
        ),
    }
    assert "forest_elf_principal" not in runtime.actors[players[0].actor_id].metadata

    mitigated = sluva.deposit_restitution_mitigation(INSTANCE_ID, payer.actor_id)
    assert payer.col == 3_000 - RESTITUTION_COL
    assert runtime.actors[arbiter_id].col == RESTITUTION_COL
    assert mitigated["forest_elf_guild_standing"] == {ALS_GUILD_ID: -12, DKB_GUILD_ID: -12}
    assert all(mitigated["custody_active"][actor.actor_id] is True for actor in players)
    assert mitigated["stage"] == "sluva_principal_adjudicated"

    strict = sluva.issue_disposition(INSTANCE_ID, arbiter_id, "strict")
    assert strict["stage"] == "sluva_disposition_strict"
    assert strict["sentences"][players[0].actor_id] == "execution_ordered"
    for actor in players[1:]:
        assert strict["sentences"][actor.actor_id] == "imprisonment_ordered"
    assert all("forest_elf_sentence" not in actor.metadata for actor in players)
    assert all(strict["custody_active"][actor.actor_id] is True for actor in players)
    assert strict["sluva_justice"]["disposition"]["execution_not_auto_resolved"] is True
    assert strict["sentences"] == strict["sluva_justice"]["disposition"]["sentences"]
    assert "principal_actor_id" not in strict["sluva_justice"]["disposition"]
    assert strict["sluva_case_scope"]["resolution_scope"] == "materialized_local_standoff_only"

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    install_progressive_clearing_guilds(restored)
    restored_sluva = install_floor8_sluva_justice_scenario(restored, _EmergencyStub(restored))
    persisted = restored_sluva.status(INSTANCE_ID)
    assert persisted["stage"] == "sluva_disposition_strict"
    assert persisted["sentences"][players[0].actor_id] == "execution_ordered"
    assert persisted["sentences"] == persisted["sluva_justice"]["disposition"]["sentences"]
    assert persisted["sluva_justice"]["principal_finding"]["actor_id"] == players[0].actor_id
    assert persisted["guild_crisis_report"]["affected_member_scope"] == "majority_of_each_guild"
    assert persisted["sluva_case_scope"]["resolution_scope"] == "materialized_local_standoff_only"
    assert all("forest_elf_sentence" not in restored.actors[actor.actor_id].metadata for actor in players)
    assert restored.actors[arbiter_id].col == RESTITUTION_COL


def test_sluva_mitigation_can_precede_principal_finding_and_pardon_uses_that_finding():
    runtime, emergency, sluva, players, forest = _setup_custody(seed=251)
    hearing = sluva.open_hearing(INSTANCE_ID, players[0].actor_id)
    arbiter_id = hearing["sluva_justice"]["arbiter_actor_id"]
    sluva.issue_grave_judgment(INSTANCE_ID, arbiter_id)

    service_started = runtime.world.now_ms
    mitigated = sluva.perform_restorative_service_mitigation(INSTANCE_ID)
    service = mitigated["sluva_justice"]["mitigation"][0]
    assert "outward_travel_ms" not in service
    assert "return_travel_ms" not in service
    assert len(service["outward_route"]) == 1
    assert len(service["return_route"]) == 1
    outward = service["outward_route"][0]
    returning = service["return_route"][0]
    assert (outward["from_location_id"], outward["to_location_id"], outward["elapsed_ms"]) == (
        SLUVA,
        FOREST_ELF_SACRED_WOODS,
        16 * 60_000,
    )
    assert (returning["from_location_id"], returning["to_location_id"], returning["elapsed_ms"]) == (
        FOREST_ELF_SACRED_WOODS,
        SLUVA,
        16 * 60_000,
    )
    expected_tags = list(ARBOREAL_ROUTE_TAGS + ("managed_inner_forest",))
    assert outward["traversal_tags"] == expected_tags
    assert returning["traversal_tags"] == expected_tags
    route_elapsed = outward["elapsed_ms"] + returning["elapsed_ms"]
    assert route_elapsed == 32 * 60_000
    assert runtime.world.now_ms - service_started == route_elapsed + RESTORATIVE_SERVICE_MS
    assert mitigated["stage"] == "sluva_grave_judgment_issued"
    assert mitigated["sluva_justice"]["principal_finding"] is None
    assert mitigated["forest_elf_guild_standing"] == {ALS_GUILD_ID: -10, DKB_GUILD_ID: -10}
    assert all(actor.location_id == SLUVA for actor in players + forest)
    assert all(mitigated["custody_active"][actor.actor_id] is True for actor in players)
    assert mitigated["sluva_case_scope"]["custody_actor_ids"] == [actor.actor_id for actor in players]

    finding = sluva.adjudicate_principal(INSTANCE_ID, arbiter_id, players[1].actor_id)
    assert finding["sluva_justice"]["principal_finding"]["actor_id"] == players[1].actor_id
    pardoned = sluva.issue_disposition(INSTANCE_ID, arbiter_id, "pardon")
    assert pardoned["stage"] == "sluva_disposition_pardon"
    assert pardoned["sluva_justice"]["disposition"]["campaign_deviation"] is True
    assert pardoned["sluva_justice"]["principal_finding"]["actor_id"] == players[1].actor_id
    assert all(pardoned["sentences"][actor.actor_id] == "pardoned" for actor in players)
    assert pardoned["sentences"] == pardoned["sluva_justice"]["disposition"]["sentences"]
    assert all("forest_elf_sentence" not in actor.metadata for actor in players)
    assert all(pardoned["custody_active"][actor.actor_id] is False for actor in players)
    assert pardoned["guild_crisis_report"]["affected_member_scope"] == "majority_of_each_guild"
