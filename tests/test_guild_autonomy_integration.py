from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


TOWN = "floor_1_town_of_beginnings"
WEST = "floor_1_west_field"
TOLBANA = "floor_1_tolbana"


def _guild_with_members(runtime: HousingAincradRuntime, count: int = 1):
    leader = runtime.create_character("GuildLeader", level=12)
    guild = runtime.create_guild(leader.actor_id, "RouteGuild")
    members = []
    for index in range(count):
        member = runtime.create_character(f"GuildScout{index + 1}", level=11)
        invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
        runtime.accept_guild_invite(invite.invite_id, member.actor_id)
        members.append(member)
    return guild, leader, members


def test_authoritative_runtime_executes_and_persists_explicit_guild_operation():
    runtime = HousingAincradRuntime(seed=401)
    guild, leader, members = _guild_with_members(runtime, 1)
    member = members[0]
    executor = GMTurnExecutor(runtime)

    assigned = executor.execute([
        {
            "op": "assign_guild_goal",
            "guild_id": guild.guild_id,
            "leader_id": leader.actor_id,
            "goal_id": "scout_tolbana",
            "target_location_id": TOLBANA,
            "assigned_member_ids": [member.actor_id],
        }
    ])
    agenda = assigned["guild_agendas"][guild.guild_id]
    assert agenda["active"] is True
    assert agenda["from_location_id"] == TOWN
    assert agenda["next_location_id"] == WEST
    assert member.location_id is None

    restored = import_runtime(export_runtime(runtime))
    restored_agenda = restored.guild_agenda_state(guild.guild_id)
    assert restored_agenda["active"] is True
    assert restored_agenda["next_location_id"] == WEST
    assert restored.actors[member.actor_id].location_id is None

    restored.advance_world(12 * 60_000)
    second_leg = restored.guild_agenda_state(guild.guild_id)
    assert second_leg["active"] is True
    assert second_leg["from_location_id"] == WEST
    assert second_leg["next_location_id"] == TOLBANA

    restored.advance_world(42 * 60_000)
    reached = restored.guild_agenda_state(guild.guild_id)
    assert reached["active"] is False
    assert reached["goal_reached"] is True
    assert restored.actors[member.actor_id].location_id == TOLBANA

    restored_executor = GMTurnExecutor(restored)
    cleared = restored_executor.execute([
        {
            "op": "clear_guild_goal",
            "guild_id": guild.guild_id,
            "leader_id": leader.actor_id,
            "goal_id": "scout_tolbana",
        }
    ])
    assert cleared["guild_agendas"][guild.guild_id]["goal_id"] is None


def test_strategy_autonomously_splits_two_real_squads_without_member_reuse():
    runtime = HousingAincradRuntime(seed=402)
    guild, leader, members = _guild_with_members(runtime, 4)
    goal = runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "two_squad_scout",
        TOLBANA,
        min_members=2,
        max_members=2,
        desired_squads=2,
        max_concurrent_squads=2,
    )
    assert goal.goal_id == "two_squad_scout"
    state = runtime.guild_agenda_state(guild.guild_id)
    assert len(state["live_operation_ids"]) == 2
    operations = [state["operations"][operation_id] for operation_id in state["live_operation_ids"]]
    assigned = [actor_id for operation in operations for actor_id in operation["assigned_member_ids"]]
    assert set(assigned) == {member.actor_id for member in members}
    assert len(assigned) == len(set(assigned)) == 4
    assert all(operation["next_location_id"] == WEST for operation in operations)
    assert all(runtime.actors[actor_id].location_id is None for actor_id in assigned)


def test_strategy_waits_for_leader_knowledge_member_knowledge_and_real_resources():
    runtime = HousingAincradRuntime(seed=403)
    guild, leader, members = _guild_with_members(runtime, 2)
    guild.vault_col = 10
    for member in members:
        member.col = 20

    runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "verified_supply_scout",
        TOLBANA,
        basis_fact_id="route_open",
        required_member_fact_id="route_map_understood",
        member_resource_requirements={"col": 50},
        guild_resource_requirements={"vault_col": 100},
        min_members=1,
        max_members=1,
        desired_squads=1,
    )
    assert runtime.guild_agenda_state(guild.guild_id)["live_operation_ids"] == []

    runtime.record_observation(
        leader.actor_id,
        "route_open",
        True,
        observation_location_id=TOWN,
        source_id="guild_board",
    )
    runtime.record_observation(
        members[0].actor_id,
        "route_map_understood",
        True,
        observation_location_id=TOWN,
        source_id="route_briefing",
    )
    members[0].col = 80
    guild.vault_col = 150
    runtime.advance_world(0)

    state = runtime.guild_agenda_state(guild.guild_id)
    assert len(state["live_operation_ids"]) == 1
    operation = state["operations"][state["live_operation_ids"][0]]
    assert operation["assigned_member_ids"] == [members[0].actor_id]
    assert operation["basis_event_id"] is not None
    assert state["resources"]["vault_col"] == 150


def test_withdrawal_waits_for_next_real_route_node_then_returns_to_regroup():
    runtime = HousingAincradRuntime(seed=404)
    guild, leader, members = _guild_with_members(runtime, 1)
    member = members[0]
    operation = runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "withdrawable_scout",
        TOLBANA,
        [member.actor_id],
    )
    runtime.request_guild_operation_withdrawal(
        guild.guild_id,
        leader.actor_id,
        operation.operation_id,
        regroup_location_id=TOWN,
    )
    assert runtime.guild_operation_state(operation.operation_id)["withdraw_requested"] is True
    assert member.location_id is None

    runtime.advance_world(12 * 60_000)
    returning = runtime.guild_operation_state(operation.operation_id)
    assert returning["status"] == "withdrawing"
    assert returning["from_location_id"] == WEST
    assert returning["next_location_id"] == TOWN
    assert member.location_id is None

    runtime.advance_world(12 * 60_000)
    withdrawn = runtime.guild_operation_state(operation.operation_id)
    assert withdrawn["status"] == "withdrawn"
    assert withdrawn["terminal"] is True
    assert member.location_id == TOWN


def test_hold_and_reorganize_changes_members_only_at_a_settled_node():
    runtime = HousingAincradRuntime(seed=405)
    guild, leader, members = _guild_with_members(runtime, 3)
    a, b, reserve = members
    operation = runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "reorganize_scout",
        TOLBANA,
        [a.actor_id, b.actor_id],
    )
    runtime.hold_guild_operation(guild.guild_id, leader.actor_id, operation.operation_id)
    runtime.advance_world(12 * 60_000)
    paused = runtime.guild_operation_state(operation.operation_id)
    assert paused["status"] == "paused"
    assert a.location_id == b.location_id == WEST

    runtime.travel_actor(reserve.actor_id, WEST)
    resumed = runtime.reorganize_guild_operation(
        guild.guild_id,
        leader.actor_id,
        operation.operation_id,
        [b.actor_id, reserve.actor_id],
    )
    assert resumed.status.value == "active"
    assert set(resumed.assigned_member_ids) == {b.actor_id, reserve.actor_id}
    assert a.location_id == WEST
    assert b.location_id is None and reserve.location_id is None


def test_multi_operation_state_round_trips_without_reusing_members():
    runtime = HousingAincradRuntime(seed=406)
    guild, leader, members = _guild_with_members(runtime, 4)
    runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "persist_two_squads",
        TOLBANA,
        min_members=2,
        max_members=2,
        desired_squads=2,
        max_concurrent_squads=2,
    )
    restored = import_runtime(export_runtime(runtime))
    state = restored.guild_agenda_state(guild.guild_id)
    assert len(state["live_operation_ids"]) == 2
    assigned = [
        actor_id
        for operation_id in state["live_operation_ids"]
        for actor_id in state["operations"][operation_id]["assigned_member_ids"]
    ]
    assert len(assigned) == len(set(assigned)) == 4
