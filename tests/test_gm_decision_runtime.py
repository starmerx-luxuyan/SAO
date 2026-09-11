import pytest

from sao_mcp.runtime.gm_decision import GMDecisionRuntime
from sao_mcp.runtime.gm_observation import GMObservationGate
from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


TOWN = "floor_1_town_of_beginnings"
WEST = "floor_1_west_field"
HORUNKA = "floor_1_horunka"


def make_runtime(seed=1801):
    runtime = SocialCommunicationAincradRuntime(seed=seed)
    executor = GMTurnExecutor(runtime)
    decision = GMDecisionRuntime(executor.supported_actions())
    return runtime, executor, decision


def test_decision_runtime_grounds_direct_travel_in_observation_capability():
    runtime, executor, decision = make_runtime()
    player = runtime.create_character("Walker")
    observation = executor.observe([player.actor_id])
    travel = observation["viewpoints"][player.actor_id]["capabilities"]["travel_options"]
    assert any(row["destination_id"] == WEST for row in travel)
    plan = decision.decide(
        observation,
        [{"op": "travel", "actor_id": player.actor_id, "destination_id": WEST}],
    )
    assert plan.actions[0]["destination_id"] == WEST
    assert plan.observation_digest == decision.observation_digest(observation)


def test_decision_runtime_rejects_hidden_or_nonadjacent_destination_even_if_model_knows_id():
    runtime, executor, decision = make_runtime(1802)
    player = runtime.create_character("Walker")
    observation = executor.observe([player.actor_id])
    with pytest.raises(ValueError, match="observable travel options"):
        decision.decide(
            observation,
            [{"op": "travel", "actor_id": player.actor_id, "destination_id": HORUNKA}],
        )


def test_decision_runtime_rejects_gm_admin_operations_from_player_decision_surface():
    runtime, executor, decision = make_runtime(1803)
    player = runtime.create_character("Observer")
    observation = executor.observe([player.actor_id])
    with pytest.raises(ValueError, match="not player-observable/allowed"):
        decision.decide(
            observation,
            [{"op": "set_npc_goal", "npc_id": "npc_tutorial_instructor", "goal_id": "x", "target_location_id": WEST}],
        )


def test_decision_runtime_cannot_control_remote_player_or_use_remote_private_knowledge():
    runtime, executor, decision = make_runtime(1804)
    observer = runtime.create_character("Observer")
    remote = runtime.create_character("Remote")
    remote.location_id = HORUNKA
    runtime.record_observation(remote.actor_id, "private:route", WEST, observation_location_id=HORUNKA)
    observation = executor.observe([observer.actor_id])
    with pytest.raises(ValueError, match="explicit player viewpoint"):
        decision.decide(
            observation,
            [{"op": "travel", "actor_id": remote.actor_id, "destination_id": WEST}],
        )
    assert "private:route" not in repr(observation)


def test_world_only_wait_is_a_valid_decision_but_zero_work_is_not():
    runtime, executor, decision = make_runtime(1805)
    player = runtime.create_character("Waiter")
    observation = executor.observe([player.actor_id])
    with pytest.raises(ValueError, match="action or advance world time"):
        decision.decide(observation, [], world_tick_ms=0)
    plan = decision.decide(observation, [], world_tick_ms=60_000)
    started = runtime.world.now_ms
    result = executor.execute([], observer_actor_ids=[player.actor_id], world_tick_ms=plan.world_tick_ms)
    assert runtime.world.now_ms == started + 60_000
    assert result["actions_executed"] == 0
    assert result["observation"]["observer_actor_ids"] == [player.actor_id]


def test_one_observation_can_authorize_at_most_one_player_action():
    runtime, executor, decision = make_runtime(1806)
    player = runtime.create_character("Walker")
    observation = executor.observe([player.actor_id])
    with pytest.raises(ValueError, match="at most 1 actions"):
        decision.decide(
            observation,
            [
                {"op": "interact_npc", "actor_id": player.actor_id, "npc_id": "npc_tutorial_instructor"},
                {"op": "travel", "actor_id": player.actor_id, "destination_id": WEST},
            ],
        )


def test_visible_npc_interaction_and_known_fact_share_are_grounded():
    runtime, executor, decision = make_runtime(1807)
    player = runtime.create_character("Talker")
    runtime.record_observation(player.actor_id, "fact:test", True, observation_location_id=TOWN)
    observation = executor.observe([player.actor_id])
    caps = observation["viewpoints"][player.actor_id]["capabilities"]
    assert "npc_tutorial_instructor" in caps["interactable_npc_ids"]
    plan = decision.decide(
        observation,
        [{"op": "share_fact", "sender_id": player.actor_id, "recipient_id": "npc_tutorial_instructor", "fact_id": "fact:test"}],
    )
    assert plan.actions[0]["op"] == "share_fact"


def test_decision_id_changes_when_observation_changes():
    runtime, executor, decision = make_runtime(1808)
    player = runtime.create_character("Clock")
    first = executor.observe([player.actor_id])
    plan1 = decision.decide(first, [], world_tick_ms=1)
    runtime.advance_world(1)
    second = executor.observe([player.actor_id])
    plan2 = decision.decide(second, [], world_tick_ms=1)
    assert plan1.observation_digest != plan2.observation_digest
    assert plan1.decision_id != plan2.decision_id


def test_actor_cannot_borrow_another_viewpoints_encounter_reference_for_item_use():
    runtime, executor, decision = make_runtime(1809)
    outsider = runtime.create_character("Outsider")
    fighter = runtime.create_character("Fighter")
    fighter.location_id = WEST
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([fighter.actor_id, monster.actor_id], zone_id=WEST)
    potion_id = next(
        item.instance_id
        for item in outsider.inventory.values()
        if item.template_id == "healing_potion_basic"
    )
    observation = executor.observe([outsider.actor_id, fighter.actor_id])
    with pytest.raises(ValueError, match="not a participant"):
        decision.decide(
            observation,
            [{
                "op": "use_item",
                "actor_id": outsider.actor_id,
                "instance_id": potion_id,
                "encounter_id": encounter.encounter_id,
            }],
        )
