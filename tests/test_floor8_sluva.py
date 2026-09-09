from sao_mcp.corpus.floor8_world import SLUVA
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, PartyState
from sao_mcp.runtime.canonical_guilds import (
    ALS_GUILD_ID,
    DKB_GUILD_ID,
    install_progressive_clearing_guilds,
)
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
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
        metadata={"forest_elf": True, "floor8_protected_woods_enforcement": True},
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


def test_sluva_restitution_is_mitigation_not_release_and_strict_disposition_preserves_real_sentences():
    runtime, emergency, sluva, players, forest = _setup_custody()
    payer = players[0]
    payer.col = 3_000
    started = runtime.world.now_ms

    hearing = sluva.open_hearing(INSTANCE_ID, payer.actor_id)
    assert hearing["stage"] == "sluva_hearing_open"
    assert runtime.world.now_ms - started == HEARING_TIME_MS
    assert hearing["forest_elf_guild_standing"] == {ALS_GUILD_ID: -15, DKB_GUILD_ID: -15}
    assert hearing["sluva_justice"]["known_penalty_risk"] == {
        "principal_or_commander": "execution_risk",
        "other_participants": "imprisonment_risk",
        "provenance": "Progressive 9 Dark Elf assessment; actual Sluva disposition remains unresolved here",
    }

    arbiter_id = hearing["sluva_justice"]["arbiter_actor_id"]
    judged = sluva.issue_grave_judgment(INSTANCE_ID, arbiter_id)
    assert judged["stage"] == "sluva_grave_judgment_issued"
    assert runtime.world.now_ms - started == HEARING_TIME_MS + JUDGMENT_TIME_MS

    mitigated = sluva.deposit_restitution_mitigation(INSTANCE_ID, payer.actor_id)
    assert payer.col == 3_000 - RESTITUTION_COL
    assert runtime.actors[arbiter_id].col == RESTITUTION_COL
    assert mitigated["forest_elf_guild_standing"] == {ALS_GUILD_ID: -12, DKB_GUILD_ID: -12}
    assert all(mitigated["custody_active"][actor.actor_id] is True for actor in players)

    strict = sluva.issue_disposition(INSTANCE_ID, arbiter_id, players[0].actor_id, "strict")
    assert strict["stage"] == "sluva_disposition_strict"
    assert strict["sentences"][players[0].actor_id] == "execution_ordered"
    for actor in players[1:]:
        assert strict["sentences"][actor.actor_id] == "imprisonment_ordered"
    assert all(strict["custody_active"][actor.actor_id] is True for actor in players)
    assert strict["sluva_justice"]["disposition"]["execution_not_auto_resolved"] is True

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    install_progressive_clearing_guilds(restored)
    restored_sluva = install_floor8_sluva_justice_scenario(restored, _EmergencyStub(restored))
    persisted = restored_sluva.status(INSTANCE_ID)
    assert persisted["stage"] == "sluva_disposition_strict"
    assert persisted["sentences"][players[0].actor_id] == "execution_ordered"
    assert restored.actors[arbiter_id].col == RESTITUTION_COL


def test_sluva_service_mitigation_returns_detainees_to_custody_and_pardon_requires_explicit_deviation():
    runtime, emergency, sluva, players, forest = _setup_custody(seed=251)
    hearing = sluva.open_hearing(INSTANCE_ID, players[0].actor_id)
    arbiter_id = hearing["sluva_justice"]["arbiter_actor_id"]
    sluva.issue_grave_judgment(INSTANCE_ID, arbiter_id)

    service_started = runtime.world.now_ms
    mitigated = sluva.perform_restorative_service_mitigation(INSTANCE_ID)
    assert runtime.world.now_ms - service_started == 32 * 60_000 + RESTORATIVE_SERVICE_MS
    assert mitigated["forest_elf_guild_standing"] == {ALS_GUILD_ID: -10, DKB_GUILD_ID: -10}
    assert all(actor.location_id == SLUVA for actor in players + forest)
    assert all(mitigated["custody_active"][actor.actor_id] is True for actor in players)

    pardoned = sluva.issue_disposition(INSTANCE_ID, arbiter_id, players[0].actor_id, "pardon")
    assert pardoned["stage"] == "sluva_disposition_pardon"
    assert pardoned["sluva_justice"]["disposition"]["campaign_deviation"] is True
    assert all(pardoned["sentences"][actor.actor_id] == "pardoned" for actor in players)
    assert all(pardoned["custody_active"][actor.actor_id] is False for actor in players)
