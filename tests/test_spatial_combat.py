import json

import pytest

from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.spatial_runtime import SpatialAincradRuntime


def test_default_encounter_formation_and_authoritative_range():
    runtime = SpatialAincradRuntime(seed=1)
    player = runtime.create_character("Spatial")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    assert player.actor_id in encounter.positions
    assert monster.actor_id in encounter.positions

    encounter.positions[player.actor_id] = (0.0, 0.0)
    encounter.positions[monster.actor_id] = (4.0, 0.0)
    result, resolved_distance = runtime.attack_authoritative(
        encounter.encounter_id,
        player.actor_id,
        monster.actor_id,
        seed=2,
    )
    assert resolved_distance == pytest.approx(4.0)
    assert not result.legal
    assert "outside attack reach" in (result.reason or "")


def test_encounter_movement_consumes_time_and_changes_distance():
    runtime = SpatialAincradRuntime(seed=1)
    player = runtime.create_character("Mover")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    before_distance = runtime.encounter_distance(encounter.encounter_id, player.actor_id, monster.actor_id)
    start_time = encounter.time_ms
    target_x, target_y = encounter.positions[monster.actor_id]
    result = runtime.move_encounter_actor(
        encounter.encounter_id,
        player.actor_id,
        target_x - 0.8,
        target_y,
    )
    assert result.completed
    assert result.elapsed_ms > 0
    assert encounter.time_ms == start_time + result.elapsed_ms
    after_distance = runtime.encounter_distance(encounter.encounter_id, player.actor_id, monster.actor_id)
    assert after_distance < before_distance
    assert after_distance == pytest.approx(0.8, abs=1e-4)


def _start_spatial_illfang():
    runtime = SpatialAincradRuntime(seed=4)
    player = runtime.create_character("Raider", level=6)
    player.location_id = "floor_1_boss_room"
    encounter, boss = runtime.start_floor_boss_encounter([player.actor_id])
    return runtime, player, encounter, boss


def test_player_can_spatially_escape_boss_telegraph_before_deadline():
    runtime, player, encounter, boss = _start_spatial_illfang()
    assert runtime.encounter_distance(encounter.encounter_id, boss.actor_id, player.actor_id) < 3.0
    runtime.telegraph_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        "illfang_sweeping_axe",
        [player.actor_id],
    )
    runtime.move_encounter_actor(encounter.encounter_id, player.actor_id, -2.0, 0.0)
    assert runtime.encounter_distance(encounter.encounter_id, boss.actor_id, player.actor_id) > 3.0
    result = runtime.resolve_boss_action(encounter.encounter_id, boss.actor_id, seed=1)
    assert result["resolved"]
    assert result["spatialEscapes"] == 1
    escaped = next(row for row in result["targets"] if row.get("spatiallyEscaped"))
    assert escaped["targetId"] == player.actor_id
    assert player.hp == player.max_hp


def test_movement_cannot_finish_after_pending_telegraph_deadline():
    runtime, player, encounter, boss = _start_spatial_illfang()
    runtime.telegraph_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        "illfang_sweeping_axe",
        [player.actor_id],
    )
    with pytest.raises(ValueError, match="after a pending boss telegraph"):
        runtime.move_encounter_actor(encounter.encounter_id, player.actor_id, -10.0, 0.0)


def test_movement_is_blocked_when_telegraph_is_already_due():
    runtime, player, encounter, boss = _start_spatial_illfang()
    runtime.telegraph_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        "illfang_sweeping_axe",
        [player.actor_id],
    )
    encounter.time_ms = int(boss.metadata["pending_boss_action"]["execute_at_ms"])
    with pytest.raises(ValueError, match="must resolve before movement"):
        runtime.move_encounter_actor(encounter.encounter_id, player.actor_id, -1.5, 0.0)


def test_spatial_state_round_trips_through_save():
    runtime = SpatialAincradRuntime(seed=1)
    player = runtime.create_character("Saver")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (-3.25, 1.5)
    encounter.positions[monster.actor_id] = (2.75, -0.5)
    encounter.arena_radius_m = 17.5

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, SpatialAincradRuntime)
    loaded = restored.encounters[encounter.encounter_id]
    assert loaded.positions[player.actor_id] == pytest.approx((-3.25, 1.5))
    assert loaded.positions[monster.actor_id] == pytest.approx((2.75, -0.5))
    assert loaded.arena_radius_m == pytest.approx(17.5)


def test_public_attack_tool_ignores_fake_distance_when_spatial_runtime_is_bootstrapped():
    import sao_mcp.server as core_server
    import sao_mcp.server_bootstrap as bootstrap

    runtime = bootstrap.runtime
    player = runtime.create_character("ToolRange")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
    encounter.positions[monster.actor_id] = (4.0, 0.0)

    payload = json.loads(
        core_server.attack(
            encounter.encounter_id,
            player.actor_id,
            monster.actor_id,
            distance_m=0.01,
            seed=3,
        )
    )
    assert payload["callerDistanceIgnored"] is True
    assert payload["resolvedDistanceM"] == pytest.approx(4.0)
    assert payload["resolution"]["legal"] is False
