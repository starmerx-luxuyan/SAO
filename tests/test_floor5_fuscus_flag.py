from sao_mcp.rules.combat import _guild_party_bonus
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor5_fuscus import install_floor5_fuscus_scenario


def test_fuscus_flag_drop_is_personal_and_deployed_aura_buffs_nearby_guildmates():
    runtime = HousingAincradRuntime(seed=41)
    fuscus = install_floor5_fuscus_scenario(runtime)
    players = [runtime.create_character(name, level=35) for name in ("A", "B", "C")]
    runtime.world.floors[5].unlocked = True
    for player in players:
        player.location_id = "floor_5_boss_room"

    state = fuscus.start_raid([player.actor_id for player in players])
    boss = runtime.actors[state["boss_id"]]
    encounter = runtime.encounters[state["encounter_id"]]
    boss.hp = 0
    boss.alive = False
    runtime._resolve_defeat(encounter, boss, players[0].actor_id)

    public = fuscus.resolve_hidden_flag_drop(state["instance_id"])
    assert public == {"instance_id": state["instance_id"], "resolved": True, "drop_created": True}
    personal = [
        fuscus.check_personal_flag_drop(player.actor_id, state["instance_id"])
        for player in players
    ]
    winners = [row for row in personal if row["received"]]
    assert len(winners) == 1
    recipient = runtime.actors[winners[0]["actor_id"]]
    mate = next(player for player in players if player.actor_id != recipient.actor_id)
    outsider = next(
        player for player in players
        if player.actor_id not in {recipient.actor_id, mate.actor_id}
    )

    for player in players:
        player.location_id = "floor_5_field"
    guild = runtime.create_guild(recipient.actor_id, "FlagGuild")
    invite = runtime.invite_to_guild(guild.guild_id, recipient.actor_id, mate.actor_id)
    runtime.accept_guild_invite(invite.invite_id, mate.actor_id)

    monster = runtime.create_training_monster("Aura Target", level=5)
    monster.location_id = "floor_5_field"
    aura_encounter = runtime.start_encounter(
        [recipient.actor_id, mate.actor_id, outsider.actor_id, monster.actor_id],
        zone_id="floor_5_field",
    )
    aura_encounter.positions[recipient.actor_id] = (0.0, 0.0)
    aura_encounter.positions[mate.actor_id] = (5.0, 0.0)
    aura_encounter.positions[outsider.actor_id] = (5.0, 5.0)
    aura_encounter.positions[monster.actor_id] = (10.0, 0.0)

    deployment = fuscus.refresh_flag_aura(recipient.actor_id, aura_encounter.encounter_id)
    assert mate.actor_id in deployment["affected_actor_ids"]
    assert outsider.actor_id not in deployment["affected_actor_ids"]
    assert _guild_party_bonus(mate) == deployment["stat_bonus"]
    assert _guild_party_bonus(outsider) == 0.0

    fuscus.withdraw_flag(recipient.actor_id, aura_encounter.encounter_id)
    assert _guild_party_bonus(mate) == 0.0
