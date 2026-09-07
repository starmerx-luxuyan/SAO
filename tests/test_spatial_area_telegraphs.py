import pytest

from sao_mcp.runtime.spatial_runtime import SpatialAincradRuntime


def _disable_illfang_minions(encounter, boss_id: str) -> None:
    for actor in encounter.participants.values():
        if actor.metadata.get("boss_parent_id") == boss_id:
            actor.alive = False
            actor.hp = 0


def test_area_telegraph_adds_player_who_enters_locked_zone_before_execution():
    runtime = SpatialAincradRuntime(seed=11)
    anchor = runtime.create_character("Anchor", level=6)
    entrant = runtime.create_character("Entrant", level=6)
    anchor.location_id = "floor_1_boss_room"
    entrant.location_id = "floor_1_boss_room"
    encounter, boss = runtime.start_floor_boss_encounter([anchor.actor_id, entrant.actor_id])
    _disable_illfang_minions(encounter, boss.actor_id)

    encounter.positions[boss.actor_id] = (0.0, 0.0)
    encounter.positions[anchor.actor_id] = (-2.0, 0.0)
    encounter.positions[entrant.actor_id] = (-4.0, 3.0)

    assert runtime.encounter_distance(encounter.encounter_id, boss.actor_id, anchor.actor_id) < 3.0
    assert runtime.encounter_distance(encounter.encounter_id, boss.actor_id, entrant.actor_id) > 3.0

    event = runtime.telegraph_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        "illfang_sweeping_axe",
        [anchor.actor_id],
    )
    pending = boss.metadata["pending_boss_action"]
    assert event.payload["spatial_mode"] == "locked_radius"
    assert pending["spatial_mode"] == "locked_radius"
    assert pending["initial_target_ids"] == [anchor.actor_id]
    locked_center = tuple(pending["area_center"])

    movement = runtime.move_encounter_actor(
        encounter.encounter_id,
        entrant.actor_id,
        -2.8,
        1.7,
    )
    assert movement.completed
    assert encounter.time_ms < pending["execute_at_ms"]
    assert tuple(pending["area_center"]) == locked_center
    assert runtime.encounter_distance(encounter.encounter_id, boss.actor_id, entrant.actor_id) < 3.0

    result = runtime.resolve_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        seed=3,
    )
    assert result["resolved"]
    assert result["spatialMode"] == "locked_radius"
    assert result["spatialEntrants"] == 1
    assert result["enteredTargetIds"] == [entrant.actor_id]
    target_ids = {row["targetId"] for row in result["targets"] if row.get("legal") is True}
    assert anchor.actor_id in target_ids
    assert entrant.actor_id in target_ids


def test_single_target_telegraph_does_not_acquire_unannounced_nearby_player():
    runtime = SpatialAincradRuntime(seed=12)
    target = runtime.create_character("Target", level=6)
    nearby = runtime.create_character("Nearby", level=6)
    target.location_id = "floor_1_boss_room"
    nearby.location_id = "floor_1_boss_room"
    encounter, boss = runtime.start_floor_boss_encounter([target.actor_id, nearby.actor_id])
    _disable_illfang_minions(encounter, boss.actor_id)

    encounter.positions[boss.actor_id] = (0.0, 0.0)
    encounter.positions[target.actor_id] = (-2.0, 0.0)
    encounter.positions[nearby.actor_id] = (-2.0, 1.0)

    event = runtime.telegraph_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        "illfang_overhead_cleave",
        [target.actor_id],
    )
    assert event.payload["spatial_mode"] == "locked_targets"
    result = runtime.resolve_boss_action(encounter.encounter_id, boss.actor_id, seed=4)
    resolved_ids = {row["targetId"] for row in result["targets"]}
    assert target.actor_id in resolved_ids
    assert nearby.actor_id not in resolved_ids
    assert result["spatialEntrants"] == 0
