from sao_mcp.runtime.canonical_guilds import (
    ALS_GUILD_ID,
    DKB_GUILD_ID,
    KIBAOU_ACTOR_ID,
    LIND_ACTOR_ID,
)
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor8_emergency import install_floor8_forest_emergency_scenario


class _NocturneStub:
    def __init__(self, runtime, player_id):
        self.runtime = runtime
        self.player_id = player_id
        self.stage = "five_key_hideout_recon_on_lake"

    def status(self, instance_id):
        assert instance_id == "nocturne_guild_fixture"
        return {"stage": self.stage, "player_ids": [self.player_id]}

    def link_floor8_emergency(self, instance_id, emergency_instance_id, message_id):
        assert instance_id == "nocturne_guild_fixture"
        self.stage = "floor8_emergency_received"
        return {"stage": self.stage}


def test_floor8_incident_uses_real_canonical_guild_states_and_persists_membership():
    runtime = HousingAincradRuntime(seed=271)
    runtime.world.floors[8].unlocked = True
    runtime.world.floors[8].main_town_gate_active = True
    player = runtime.create_character("GuildStateWitness", level=28)
    nocturne = _NocturneStub(runtime, player.actor_id)
    emergency = install_floor8_forest_emergency_scenario(runtime, nocturne)

    notice = emergency.trigger_from_nocturne("nocturne_guild_fixture", player.actor_id)
    state = emergency._state(notice["instance_id"])
    guilds = runtime.relationships.guilds
    assert set(guilds).issuperset({ALS_GUILD_ID, DKB_GUILD_ID})
    assert guilds[ALS_GUILD_ID].leader_id == KIBAOU_ACTOR_ID
    assert guilds[DKB_GUILD_ID].leader_id == LIND_ACTOR_ID
    assert runtime.actors[KIBAOU_ACTOR_ID].location_id is None
    assert runtime.actors[LIND_ACTOR_ID].location_id is None

    for actor_id in state["incident"]["frontline_actor_ids"]:
        actor = runtime.actors[actor_id]
        guild = guilds[actor.guild_id]
        storage = runtime.relationships.storages[guild.storage_id]
        assert actor_id in guild.member_ids
        assert actor_id in storage.member_ids
        assert actor.metadata["guild_affiliation_provenance"] == "canon"

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    restored_nocturne = _NocturneStub(restored, player.actor_id)
    restored_nocturne.stage = "floor8_emergency_received"
    restored_emergency = install_floor8_forest_emergency_scenario(restored, restored_nocturne)
    restored_state = restored_emergency.status(notice["instance_id"])
    assert restored_state["clearing_guilds"][ALS_GUILD_ID]["leader_id"] == KIBAOU_ACTOR_ID
    assert restored_state["clearing_guilds"][DKB_GUILD_ID]["leader_id"] == LIND_ACTOR_ID
    for actor_id in state["incident"]["frontline_actor_ids"]:
        guild_id = restored.actors[actor_id].guild_id
        assert actor_id in restored.relationships.guilds[guild_id].member_ids
        assert actor_id in restored.relationships.storages[
            restored.relationships.guilds[guild_id].storage_id
        ].member_ids
