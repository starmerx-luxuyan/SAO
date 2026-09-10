from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def _guild_with_member(runtime: HousingAincradRuntime):
    leader = runtime.create_character("GuildLeader", level=12)
    member = runtime.create_character("GuildScout", level=11)
    guild = runtime.create_guild(leader.actor_id, "RouteGuild")
    invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
    runtime.accept_guild_invite(invite.invite_id, member.actor_id)
    return guild, leader, member


def test_authoritative_runtime_executes_and_persists_concurrent_guild_operation():
    runtime = HousingAincradRuntime(seed=401)
    guild, leader, member = _guild_with_member(runtime)
    executor = GMTurnExecutor(runtime)

    assert hasattr(runtime, "assign_guild_goal")
    assert "assign_guild_goal" in executor.supported_actions()

    assigned = executor.execute(
        [
            {
                "op": "assign_guild_goal",
                "guild_id": guild.guild_id,
                "leader_id": leader.actor_id,
                "goal_id": "scout_tolbana",
                "target_location_id": "floor_1_tolbana",
                "assigned_member_ids": [member.actor_id],
            }
        ]
    )

    agenda = assigned["guild_agendas"][guild.guild_id]
    assert agenda["active"] is True
    assert agenda["from_location_id"] == "floor_1_town_of_beginnings"
    assert agenda["next_location_id"] == "floor_1_west_field"
    assert member.location_id is None
    assert assigned["actors"][member.actor_id]["location_id"] is None

    restored = import_runtime(export_runtime(runtime))
    restored_executor = GMTurnExecutor(restored)
    restored_member = restored.actors[member.actor_id]
    restored_agenda = restored.guild_agenda_state(guild.guild_id)

    assert restored_agenda["active"] is True
    assert restored_agenda["next_location_id"] == "floor_1_west_field"
    assert restored_member.location_id is None

    restored.advance_world(12 * 60_000)
    second_leg = restored.guild_agenda_state(guild.guild_id)
    assert second_leg["active"] is True
    assert second_leg["from_location_id"] == "floor_1_west_field"
    assert second_leg["next_location_id"] == "floor_1_tolbana"
    assert restored_member.location_id is None

    restored.advance_world(42 * 60_000)
    reached = restored.guild_agenda_state(guild.guild_id)
    assert reached["active"] is False
    assert reached["goal_reached"] is True
    assert restored_member.location_id == "floor_1_tolbana"
    assert "floor_1_tolbana" in restored.world.floors[1].discovered_locations

    completed_legs = [
        row
        for row in restored.guild_activity_history
        if row["guild_id"] == guild.guild_id and row["event"] == "travel_leg_completed"
    ]
    assert [(row["from_location_id"], row["to_location_id"]) for row in completed_legs] == [
        ("floor_1_town_of_beginnings", "floor_1_west_field"),
        ("floor_1_west_field", "floor_1_tolbana"),
    ]

    cleared = restored_executor.execute(
        [
            {
                "op": "clear_guild_goal",
                "guild_id": guild.guild_id,
                "leader_id": leader.actor_id,
            }
        ]
    )
    assert cleared["guild_agendas"][guild.guild_id]["goal_id"] is None
