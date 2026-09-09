from sao_mcp.corpus.floor8_world import FOREST_ELF_SACRED_WOODS, SLUVA
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, PartyState
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor8_emergency import ALS_GUILD_ID, DKB_GUILD_ID
from sao_mcp.scenarios.floor8_sluva import (
    FOREST_ELF_FACTION_ID,
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
    players = []
    for index, guild_id in enumerate((ALS_GUILD_ID, ALS_GUILD_ID, DKB_GUILD_ID, DKB_GUILD_ID), start=1):
        actor = runtime.create_character(f"Sluva Custody {index}", level=26)
        actor.location_id = SLUVA
        actor.guild_id = guild_id
        actor.metadata["forest_elf_custody"] = True
        actor.metadata["forest_elf_custody_location_id"] = SLUVA
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


def test_sluva_restitution_moves_real_col_changes_guild_standing_and_persists():
    runtime, emergency, sluva, players, forest = _setup_custody()
    payer = players[0]
    payer.col = 3_000
    started = runtime.world.now_ms

    hearing = sluva.open_hearing(INSTANCE_ID, payer.actor_id)
    assert hearing["stage"] == "sluva_hearing_open"
    assert runtime.world.now_ms - started == HEARING_TIME_MS
    assert hearing["forest_elf_guild_standing"] == {
        ALS_GUILD_ID: -8,
        DKB_GUILD_ID: -8,
    }

    arbiter_id = hearing["sluva_justice"]["arbiter_actor_id"]
    judged = sluva.issue_restorative_judgment(INSTANCE_ID, arbiter_id)
    assert judged["stage"] == "sluva_judgment_issued"
    assert runtime.world.now_ms - started == HEARING_TIME_MS + JUDGMENT_TIME_MS
    assert judged["sluva_justice"]["judgment"]["restitution_col"] == RESTITUTION_COL

    resolved = sluva.satisfy_with_restitution(INSTANCE_ID, payer.actor_id)
    assert resolved["stage"] == "sluva_justice_resolved_restitution"
    assert payer.col == 3_000 - RESTITUTION_COL
    assert runtime.actors[arbiter_id].col == RESTITUTION_COL
    assert resolved["forest_elf_guild_standing"] == {
        ALS_GUILD_ID: -4,
        DKB_GUILD_ID: -4,
    }
    assert all(resolved["custody_active"][actor.actor_id] is False for actor in players)

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    restored_sluva = install_floor8_sluva_justice_scenario(restored, _EmergencyStub(restored))
    persisted = restored_sluva.status(INSTANCE_ID)
    assert persisted["stage"] == "sluva_justice_resolved_restitution"
    assert persisted["forest_elf_guild_standing"] == {ALS_GUILD_ID: -4, DKB_GUILD_ID: -4}
    assert restored.actors[arbiter_id].col == RESTITUTION_COL


def test_sluva_refusal_keeps_custody_then_service_releases_through_real_world_time():
    runtime, emergency, sluva, players, forest = _setup_custody(seed=251)
    advocate = players[0]
    hearing = sluva.open_hearing(INSTANCE_ID, advocate.actor_id)
    arbiter_id = hearing["sluva_justice"]["arbiter_actor_id"]
    sluva.issue_restorative_judgment(INSTANCE_ID, arbiter_id)

    refused = sluva.refuse_judgment(INSTANCE_ID, players[1].actor_id)
    assert refused["stage"] == "sluva_judgment_refused"
    assert refused["forest_elf_guild_standing"] == {ALS_GUILD_ID: -8, DKB_GUILD_ID: -8}
    assert all(refused["custody_active"][actor.actor_id] is True for actor in players)
    assert all(actor.location_id == SLUVA for actor in players)

    service_started = runtime.world.now_ms
    resolved = sluva.satisfy_with_restorative_service(INSTANCE_ID)
    assert resolved["stage"] == "sluva_justice_resolved_service"
    assert runtime.world.now_ms - service_started == 16 * 60_000 + RESTORATIVE_SERVICE_MS
    assert resolved["forest_elf_guild_standing"] == {ALS_GUILD_ID: -2, DKB_GUILD_ID: -2}
    assert all(actor.location_id == FOREST_ELF_SACRED_WOODS for actor in players + forest)
    assert all(resolved["custody_active"][actor.actor_id] is False for actor in players)
