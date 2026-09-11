import json

from sao_mcp.rules.population import PlayerPopulationSegment
from sao_mcp.runtime.gm_decision import GMDecisionRuntime
from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


HOUR = 60 * 60 * 1000
MINUTE = 60 * 1000
TOWN = "floor_1_town_of_beginnings"
WEST = "floor_1_west_field"
HORUNKA = "floor_1_horunka"
TOLBANA = "floor_1_tolbana"
URBUS = "floor_2_urbus"


def _campaign_seed(seed: int = 1901) -> tuple[SocialCommunicationAincradRuntime, str]:
    runtime = SocialCommunicationAincradRuntime(seed=seed)
    observer = runtime.create_character("StressObserver", level=4)
    runtime.add_population_cohort(
        "stress_frontline",
        PlayerPopulationSegment.FRONTLINE,
        36,
        WEST,
        3.5,
        "field_hunting",
    )
    runtime.add_population_cohort(
        "stress_production",
        PlayerPopulationSegment.PRODUCTION,
        48,
        TOWN,
        2.5,
        "crafting_and_trade",
    )
    runtime.add_population_cohort(
        "stress_casual",
        PlayerPopulationSegment.CASUAL,
        18,
        WEST,
        1.0,
        "exploration",
    )
    return runtime, observer.actor_id


def _payload(runtime) -> dict:
    return json.loads(export_runtime(runtime))


def test_campaign_long_advance_matches_hourly_scheduler_partitioning():
    runtime, _ = _campaign_seed(1901)
    baseline = export_runtime(runtime)
    long_step = import_runtime(baseline)
    hourly = import_runtime(baseline)

    long_step.advance_world(24 * HOUR)
    for _ in range(24):
        hourly.advance_world(HOUR)

    assert _payload(long_step) == _payload(hourly)


def test_campaign_checkpoint_churn_matches_uninterrupted_world():
    runtime, _ = _campaign_seed(1902)
    baseline = export_runtime(runtime)
    uninterrupted = import_runtime(baseline)
    checkpointed = import_runtime(baseline)

    uninterrupted.advance_world(72 * HOUR)
    for _ in range(12):
        checkpointed.advance_world(6 * HOUR)
        checkpointed = import_runtime(export_runtime(checkpointed))

    assert _payload(uninterrupted) == _payload(checkpointed)


def test_locked_floor_population_migration_resumes_on_exact_gate_activation_boundary():
    runtime = SocialCommunicationAincradRuntime(seed=1903)
    runtime.add_population_cohort(
        "stress_progression",
        PlayerPopulationSegment.MID_TIER,
        40,
        TOWN,
        5.0,
        "floor_progression",
    )
    movement = runtime.schedule_population_movement(
        "stress_progression",
        URBUS,
        reason="stress_cross_floor_progression",
    )
    assert movement is not None
    assert movement.wait_reason == "target_floor_gate_inactive"
    assert runtime.population.cohorts["stress_progression"].location_id == TOWN

    runtime.floor_boss_defeated(1)
    activation = runtime.world.floors[1].scheduled_gate_activation_at_ms
    assert activation == runtime.world.now_ms + 2 * HOUR

    runtime.advance_world(2 * HOUR)

    cohort = runtime.population.cohorts["stress_progression"]
    assert runtime.world.floors[2].unlocked is True
    assert runtime.world.floors[2].main_town_gate_active is True
    assert cohort.location_id == URBUS
    assert cohort.floor_number == 2
    assert runtime.population_movement_state("stress_progression") is None
    assert any(
        row["event"] == "movement_gate_transfer"
        and row["cohort_id"] == "stress_progression"
        and row["at_ms"] == activation
        for row in runtime.population_history
    )
    runtime.population.assert_conservation()
    export_runtime(runtime)


def test_long_campaign_keeps_cross_system_authorities_bounded_and_gm_decision_usable():
    runtime, observer_id = _campaign_seed(1904)
    runtime.advance_world(48 * HOUR)

    population = runtime.player_population_state()
    assert population["conservation_balance"] == 0
    assert population["abstract_living_players"] + population["abstract_cumulative_deaths"] == population["abstract_registered_players"]

    for monster_id, state in runtime.monster_ecology.items():
        reserved = runtime._reserved_units(monster_id)
        assert 0 <= state.available_units <= state.carrying_capacity
        assert state.available_units + reserved <= state.carrying_capacity
        assert state.next_recovery_at_ms > runtime.world.now_ms

    for contract in runtime.quest_contracts.values():
        occurrence = runtime.world_events.occurrences[contract.occurrence_id]
        if occurrence.status.value == "active":
            assert contract.expires_at_ms > runtime.world.now_ms
        assert 0 <= contract.world_progress <= contract.required

    for delivery in runtime.social_deliveries.values():
        if delivery.pending:
            assert delivery.due_at_ms > runtime.world.now_ms

    executor = GMTurnExecutor(runtime)
    decision = GMDecisionRuntime(executor.supported_actions())
    observation = executor.observe([observer_id])
    travel_options = observation["viewpoints"][observer_id]["capabilities"]["travel_options"]
    assert travel_options
    target = travel_options[0]["destination_id"]
    plan = decision.decide(
        observation,
        [{"op": "travel", "actor_id": observer_id, "destination_id": target}],
    )
    assert plan.observation_digest == decision.observation_digest(observation)
    result = executor.execute(
        list(plan.actions),
        observer_actor_ids=list(plan.observer_actor_ids),
        world_tick_ms=plan.world_tick_ms,
    )
    assert result["actions_executed"] == 1
    assert result["observation"]["viewpoints"][observer_id]["observer"]["location_id"] == target
    export_runtime(runtime)


def test_checkpoint_churn_preserves_simultaneous_npc_guild_social_and_live_encounter_state():
    runtime = SocialCommunicationAincradRuntime(seed=1905)

    fighter = runtime.create_character("StressFighter", level=4)
    runtime.travel_actor(fighter.actor_id, WEST)
    ecological_ids = runtime._ecology_actor_ids(location_id=WEST)
    assert ecological_ids
    monster_actor_id = ecological_ids[0]
    encounter = runtime.start_encounter([fighter.actor_id, monster_actor_id], zone_id=WEST)

    leader = runtime.create_character("StressLeader", level=8)
    member = runtime.create_character("StressScout", level=7)
    guild = runtime.create_guild(leader.actor_id, "Stress Guild")
    invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
    runtime.accept_guild_invite(invite.invite_id, member.actor_id)

    fact = runtime.record_observation(
        leader.actor_id,
        "stress:guild_route_open",
        True,
        observation_location_id=TOWN,
    )
    deliveries = runtime.post_guild_fact_notice(
        leader.actor_id,
        guild.guild_id,
        fact.fact_id,
    )
    assert len(deliveries) == 1
    delivery_id = deliveries[0].delivery_id

    operation = runtime.assign_guild_goal(
        guild.guild_id,
        leader.actor_id,
        "stress_scout_tolbana",
        TOLBANA,
        [member.actor_id],
    )
    assert operation.active is True
    assert runtime.actors[member.actor_id].location_id is None

    runtime.set_npc_goal(
        "npc_tutorial_instructor",
        "stress_visit_horunka",
        HORUNKA,
        priority=500,
    )
    npc_agenda = runtime.npc_agenda_state("npc_tutorial_instructor")
    assert npc_agenda["active"] is True
    assert runtime.social_deliveries[delivery_id].pending is True
    assert runtime.encounters[encounter.encounter_id].active is True

    baseline = export_runtime(runtime)
    uninterrupted = import_runtime(baseline)
    checkpointed = import_runtime(baseline)

    uninterrupted.advance_world(HOUR)
    for elapsed in (30_000, 90_000, 13 * MINUTE, 17 * MINUTE, 28 * MINUTE):
        checkpointed.advance_world(elapsed)
        checkpointed = import_runtime(export_runtime(checkpointed))

    assert checkpointed.world.now_ms == uninterrupted.world.now_ms
    assert _payload(uninterrupted) == _payload(checkpointed)

    restored_operation = checkpointed.guild_operations[operation.operation_id]
    assert restored_operation.status.value == "completed"
    assert checkpointed.actors[member.actor_id].location_id == TOLBANA
    assert checkpointed.npc_location_id("npc_tutorial_instructor") == HORUNKA
    assert checkpointed.social_deliveries[delivery_id].status.value == "delivered"
    assert checkpointed.encounters[encounter.encounter_id].active is True
    assert fighter.actor_id in checkpointed.encounters[encounter.encounter_id].participants
    export_runtime(checkpointed)
