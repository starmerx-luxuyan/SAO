import pytest

from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


def test_gm_turn_validates_entire_action_shape_before_any_mechanical_mutation():
    runtime = SocialCommunicationAincradRuntime(seed=301)
    actor = runtime.create_character("TurnShape", level=8)
    executor = GMTurnExecutor(runtime)
    started = runtime.world.now_ms
    origin = actor.location_id

    with pytest.raises(ValueError, match="unsupported GM turn action"):
        executor.execute(
            [
                {"op": "travel", "actor_id": actor.actor_id, "destination_id": "floor_1_west_field"},
                {"op": "invent_a_result", "actor_id": actor.actor_id},
            ],
            observer_actor_ids=[actor.actor_id],
        )

    assert runtime.world.now_ms == started
    assert actor.location_id == origin


def test_gm_turn_returns_only_gated_observation_not_raw_resolution_or_hidden_agendas():
    runtime = SocialCommunicationAincradRuntime(seed=303)
    actor = runtime.create_character("TurnRunner", level=8)
    executor = GMTurnExecutor(runtime)

    exploration = executor.execute(
        [
            {"op": "travel", "actor_id": actor.actor_id, "destination_id": "floor_1_west_field"},
            {"op": "travel", "actor_id": actor.actor_id, "destination_id": "floor_1_tolbana"},
        ],
        observer_actor_ids=[actor.actor_id],
        world_tick_ms=1_000,
    )
    assert exploration["world_time_after_ms"] - exploration["world_time_before_ms"] == 54 * 60_000 + 1_000
    assert exploration["actions_executed"] == 2
    assert "steps" not in exploration
    assert "actors" not in exploration
    assert "npc_agendas" not in exploration
    assert "guild_agendas" not in exploration
    viewpoint = exploration["observation"]["viewpoints"][actor.actor_id]
    assert viewpoint["observer"]["location_id"] == "floor_1_tolbana"

    actor.location_id = "floor_1_west_field"
    actor.skill_proficiencies["one_hand_sword"] = 1000.0
    monster = runtime.create_training_monster(level=4)
    monster.evasion = 0
    encounter = runtime.start_encounter([actor.actor_id, monster.actor_id], zone_id="floor_1_west_field")
    encounter.positions[actor.actor_id] = (0.0, 0.0)
    encounter.positions[monster.actor_id] = (1.0, 0.0)

    combat = executor.execute(
        [{
            "op": "timeline_attack",
            "encounter_id": encounter.encounter_id,
            "attacker_id": actor.actor_id,
            "target_id": monster.actor_id,
            "defense": "none",
            "seed": 1,
        }],
        observer_actor_ids=[actor.actor_id],
    )
    encounter_row = combat["observation"]["viewpoints"][actor.actor_id]["encounters"][encounter.encounter_id]
    assert encounter_row["recent_events"]
    attack = next(row for row in encounter_row["recent_events"] if row["event_type"] == "attack")
    assert "damage" in attack["payload"]
    assert "hit_chance" not in attack["payload"]
    assert "threat_generated" not in attack["payload"]
    assert "weapon_durability" not in attack["payload"]
