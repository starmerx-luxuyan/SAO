import pytest

from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


def test_gm_turn_validates_entire_action_shape_before_any_mechanical_mutation():
    runtime = HousingAincradRuntime(seed=301)
    actor = runtime.create_character("TurnShape", level=8)
    executor = GMTurnExecutor(runtime)
    started = runtime.world.now_ms
    origin = actor.location_id

    with pytest.raises(ValueError, match="unsupported GM turn action"):
        executor.execute(
            [
                {"op": "travel", "actor_id": actor.actor_id, "destination_id": "floor_1_west_field"},
                {"op": "invent_a_result", "actor_id": actor.actor_id},
            ]
        )

    assert runtime.world.now_ms == started
    assert actor.location_id == origin


def test_gm_turn_executes_existing_world_and_timeline_mechanics_and_returns_observables():
    runtime = HousingAincradRuntime(seed=303)
    actor = runtime.create_character("TurnRunner", level=8)
    executor = GMTurnExecutor(runtime)

    exploration = executor.execute(
        [
            {"op": "travel", "actor_id": actor.actor_id, "destination_id": "floor_1_west_field"},
            {"op": "travel", "actor_id": actor.actor_id, "destination_id": "floor_1_tolbana"},
        ],
        world_tick_ms=1_000,
    )
    assert exploration["world_time_after_ms"] - exploration["world_time_before_ms"] == 54 * 60_000 + 1_000
    assert actor.location_id == "floor_1_tolbana"
    assert exploration["actors"][actor.actor_id]["location_id"] == "floor_1_tolbana"
    assert [step["op"] for step in exploration["steps"]] == ["travel", "travel"]

    actor.location_id = "floor_1_west_field"
    actor.skill_proficiencies["one_hand_sword"] = 1000.0
    monster = runtime.create_training_monster(level=4)
    monster.evasion = 0
    encounter = runtime.start_encounter(
        [actor.actor_id, monster.actor_id],
        zone_id="floor_1_west_field",
    )
    encounter.positions[actor.actor_id] = (0.0, 0.0)
    encounter.positions[monster.actor_id] = (1.0, 0.0)
    hp_before = monster.hp

    combat = executor.execute(
        [
            {
                "op": "timeline_attack",
                "encounter_id": encounter.encounter_id,
                "attacker_id": actor.actor_id,
                "target_id": monster.actor_id,
                "defense": "none",
                "seed": 1,
            }
        ]
    )

    step = combat["steps"][0]["result"]
    assert step["queued"] is False
    assert step["resolution"]["legal"] is True
    assert monster.hp <= hp_before
    assert combat["actors"][monster.actor_id]["hp"] == monster.hp
    assert combat["encounters"][encounter.encounter_id]["time_ms"] == encounter.time_ms
    assert combat["new_events"][encounter.encounter_id]
