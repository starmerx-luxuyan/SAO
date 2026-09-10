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
from sao_mcp.scenarios.floor8_standoff import FOREST_ELF_CUSTODY_RESTRICTION


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

    case_id = f"floor8_sluva:{INSTANCE_ID}"
    for actor in players:
        runtime.take_actor_custody(
            actor.actor_id,
            custody_id=f"custody:{case_id}:{actor.actor_id}",
            authority_id=forest[0].actor_id,
            case_id=case_id,
            restriction_code=FOREST_ELF_CUSTODY_RESTRICTION,
            reason="test_sluva_fixture",
        )
    runtime.world.global_flags["floor8_forest_emergency_instances"] = {
        INSTANCE_ID: {
            "instance_id": INSTANCE_ID,
            "stage": "standoff_resolved_custody",
            "floor8_actor_ids": [players[0].actor_id],
            "custody_actor_ids": [actor.actor_id for actor in players],
            "custody_case_id": case_id,
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


def test_sluva_strict_disposition_enforces_imprisonment_without_auto_executing_principal():
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
    assert hearing["sluva_justice"]["principal_finding"] is None
    assert hearing["sluva_justice"]["sentence_enforcement"] is None
    assert hearing["sentences"] == {actor.actor_id: None for actor in players}

    arbiter_id = hearing["sluva_justice"]["arbiter_actor_id"]
    judged = sluva.issue_grave_judgment(INSTANCE_ID, arbiter_id)
    assert judged["stage"] == "sluva_grave_judgment_issued"
    assert runtime.world.now_ms - started == HEARING_TIME_MS + JUDGMENT_TIME_MS
    with pytest.raises(ValueError, match="requires an adjudicated principal"):
        sluva.issue_disposition(INSTANCE_ID, arbiter_id, "strict")

    sluva.adjudicate_principal(INSTANCE_ID, arbiter_id, players[0].actor_id)
    sluva.deposit_restitution_mitigation(INSTANCE_ID, payer.actor_id)
    strict = sluva.issue_disposition(INSTANCE_ID, arbiter_id, "strict")
    assert strict["stage"] == "sluva_disposition_strict"
    assert strict["sentences"][players[0].actor_id] == "execution_ordered"
    assert [strict["sentences"][actor.actor_id] for actor in players[1:]] == [
        "imprisonment_ordered",
        "imprisonment_ordered",
        "imprisonment_ordered",
    ]
    principal_hp = players[0].hp
    term_ms = 60 * 60_000
    enforcement = sluva.begin_imprisonment_enforcement(INSTANCE_ID, arbiter_id, term_ms)
    row = enforcement["sluva_justice"]["sentence_enforcement"]
    assert enforcement["stage"] == "sluva_sentence_enforcement_active"
    assert row["status"] == "imprisonment_active"
    assert row["imprisonment_actor_ids"] == [actor.actor_id for actor in players[1:]]
    assert row["execution_order_actor_ids"] == [players[0].actor_id]
    assert row["execution_status"] == "pending_unexecuted"
    assert row["imprisonment_duration_ms"] == term_ms
    assert enforcement["sentence_enforcement_remaining_ms"] == term_ms
    assert players[0].alive is True and players[0].hp == principal_hp

    with pytest.raises(ValueError, match="has not reached its release time"):
        sluva.complete_imprisonment_enforcement(INSTANCE_ID, arbiter_id)
    runtime.advance_world(term_ms - 1)
    assert sluva.status(INSTANCE_ID)["sentence_enforcement_remaining_ms"] == 1
    with pytest.raises(ValueError, match="has not reached its release time"):
        sluva.complete_imprisonment_enforcement(INSTANCE_ID, arbiter_id)
    runtime.advance_world(1)

    completed = sluva.complete_imprisonment_enforcement(INSTANCE_ID, arbiter_id)
    assert completed["stage"] == "sluva_imprisonment_completed_execution_pending"
    assert completed["sluva_justice"]["sentence_enforcement"]["status"] == "imprisonment_completed"
    assert completed["sentence_enforcement_remaining_ms"] is None
    assert completed["custody_active"][players[0].actor_id] is True
    assert all(completed["custody_active"][actor.actor_id] is False for actor in players[1:])
    assert players[0].alive is True and players[0].hp == principal_hp
    assert runtime.actor_custody_state(players[0].actor_id)["restriction_code"] == FOREST_ELF_CUSTODY_RESTRICTION
    assert all(runtime.actor_custody_state(actor.actor_id) is None for actor in players[1:])
    assert all("autonomous_travel_restriction" not in actor.metadata for actor in players)

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    install_progressive_clearing_guilds(restored)
    restored_sluva = install_floor8_sluva_justice_scenario(restored, _EmergencyStub(restored))
    persisted = restored_sluva.status(INSTANCE_ID)
    assert persisted["stage"] == "sluva_imprisonment_completed_execution_pending"
    assert persisted["sluva_justice"]["sentence_enforcement"]["execution_status"] == "pending_unexecuted"
    assert persisted["custody_active"][players[0].actor_id] is True
    assert all(persisted["custody_active"][actor.actor_id] is False for actor in players[1:])


def test_sluva_mitigation_can_precede_principal_finding_and_pardon_uses_that_finding():
    runtime, emergency, sluva, players, forest = _setup_custody(seed=251)
    hearing = sluva.open_hearing(INSTANCE_ID, players[0].actor_id)
    arbiter_id = hearing["sluva_justice"]["arbiter_actor_id"]
    sluva.issue_grave_judgment(INSTANCE_ID, arbiter_id)

    service_started = runtime.world.now_ms
    mitigated = sluva.perform_restorative_service_mitigation(INSTANCE_ID)
    service = mitigated["sluva_justice"]["mitigation"][0]
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
    assert runtime.world.now_ms - service_started == route_elapsed + RESTORATIVE_SERVICE_MS
    assert mitigated["stage"] == "sluva_grave_judgment_issued"
    assert mitigated["sluva_justice"]["principal_finding"] is None
    assert all(mitigated["custody_active"][actor.actor_id] is True for actor in players)

    sluva.adjudicate_principal(INSTANCE_ID, arbiter_id, players[1].actor_id)
    pardoned = sluva.issue_disposition(INSTANCE_ID, arbiter_id, "pardon")
    assert pardoned["stage"] == "sluva_disposition_pardon"
    assert pardoned["sluva_justice"]["disposition"]["campaign_deviation"] is True
    assert all(pardoned["sentences"][actor.actor_id] == "pardoned" for actor in players)
    assert all(runtime.actor_custody_state(actor.actor_id) is None for actor in players)
    assert all("autonomous_travel_restriction" not in actor.metadata for actor in players)
    assert all(pardoned["custody_active"][actor.actor_id] is False for actor in players)


def test_sluva_commuted_disposition_releases_all_imprisoned_actors_at_term_end():
    runtime, emergency, sluva, players, forest = _setup_custody(seed=263)
    hearing = sluva.open_hearing(INSTANCE_ID, players[0].actor_id)
    arbiter_id = hearing["sluva_justice"]["arbiter_actor_id"]
    sluva.issue_grave_judgment(INSTANCE_ID, arbiter_id)
    players[0].col = RESTITUTION_COL
    sluva.deposit_restitution_mitigation(INSTANCE_ID, players[0].actor_id)
    sluva.adjudicate_principal(INSTANCE_ID, arbiter_id, players[0].actor_id)
    commuted = sluva.issue_disposition(INSTANCE_ID, arbiter_id, "commuted")
    assert commuted["stage"] == "sluva_disposition_commuted"
    assert set(commuted["sentences"].values()) == {"imprisonment_ordered"}

    term_ms = 30 * 60_000
    active = sluva.begin_imprisonment_enforcement(INSTANCE_ID, arbiter_id, term_ms)
    row = active["sluva_justice"]["sentence_enforcement"]
    assert row["imprisonment_actor_ids"] == [actor.actor_id for actor in players]
    assert row["execution_order_actor_ids"] == []
    assert row["execution_status"] is None
    runtime.advance_world(term_ms)
    completed = sluva.complete_imprisonment_enforcement(INSTANCE_ID, arbiter_id)
    assert completed["stage"] == "sluva_sentence_enforcement_completed"
    assert all(completed["custody_active"][actor.actor_id] is False for actor in players)
    assert all(runtime.actor_custody_state(actor.actor_id) is None for actor in players)
    assert all("autonomous_travel_restriction" not in actor.metadata for actor in players)
    assert all(actor.alive for actor in players)
