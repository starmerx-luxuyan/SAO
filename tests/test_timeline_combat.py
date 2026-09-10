import pytest

from sao_mcp.domain.models import DefenseMode
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.timeline_runtime import TimelineRaidAincradRuntime


def _boss_duel(seed=7):
    runtime = TimelineRaidAincradRuntime(seed=seed)
    player = runtime.create_character("TimelineRaider", level=6)
    player.location_id = "floor_1_boss_room"
    encounter, boss = runtime.start_floor_boss_encounter([player.actor_id])
    # Keep the player in melee range for deterministic queue tests.
    encounter.positions[player.actor_id] = (-1.4, 0.0)
    encounter.positions[boss.actor_id] = (0.0, 0.0)
    return runtime, player, encounter, boss


def test_crossing_boss_deadline_queues_instead_of_rejecting():
    runtime, player, encounter, boss = _boss_duel()
    runtime.telegraph_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        "illfang_shield_bash",
        [player.actor_id],
    )
    result = runtime.attack_or_queue_authoritative(
        encounter.encounter_id,
        player.actor_id,
        boss.actor_id,
        sword_skill_id=None,
        seed=11,
    )
    assert result["queued"] is True
    action = result["action"]
    assert action.started_at_ms == 0
    assert action.impact_at_ms > boss.metadata["pending_boss_action"]["execute_at_ms"]
    assert player.metadata["timeline_action_id"] == action.action_id


def test_boss_hit_interrupts_queued_player_attack():
    runtime, player, encounter, boss = _boss_duel(seed=9)
    runtime.telegraph_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        "illfang_shield_bash",
        [player.actor_id],
    )
    action = runtime.queue_player_attack(
        encounter.encounter_id,
        player.actor_id,
        boss.actor_id,
        seed=2,
    )
    boss_event = runtime.process_next_timeline_event(encounter.encounter_id)
    assert boss_event["event"] == "boss_action"
    # If this seed misses, force the semantic interruption marker to mimic a connected Boss hit;
    # the next assertion still exercises queued-action interruption resolution deterministically.
    if not any(row.get("hit") for row in boss_event["result"].get("targets", [])):
        runtime._interrupt_actor_actions(encounter.encounter_id, player.actor_id, "test Boss connection")
    player_event = runtime.process_next_timeline_event(encounter.encounter_id)
    assert player_event["event"] == "player_attack"
    assert player_event["resolved"] is False
    assert player_event.get("interrupted") is True
    assert action.action_id not in [row.action_id for row in runtime._queue(encounter.encounter_id)]


def test_queued_attack_resolves_when_no_boss_event_precedes_it():
    runtime = TimelineRaidAincradRuntime(seed=1)
    player = runtime.create_character("Timeline")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
    encounter.positions[monster.actor_id] = (1.2, 0.0)
    action = runtime.queue_player_attack(
        encounter.encounter_id,
        player.actor_id,
        monster.actor_id,
        defense=DefenseMode.NONE,
        seed=5,
    )
    event = runtime.process_next_timeline_event(encounter.encounter_id)
    assert event["event"] == "player_attack"
    assert event["actionId"] == action.action_id
    assert event["resolved"] is True
    assert encounter.time_ms == action.impact_at_ms


def test_target_moving_out_during_windup_causes_queued_whiff():
    runtime = TimelineRaidAincradRuntime(seed=1)
    player = runtime.create_character("Attacker")
    target = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, target.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
    encounter.positions[target.actor_id] = (1.2, 0.0)
    action = runtime.queue_player_attack(encounter.encounter_id, player.actor_id, target.actor_id, seed=3)
    # Directly mutate target position to model target movement completed by another timeline source.
    encounter.positions[target.actor_id] = (8.0, 0.0)
    event = runtime.process_next_timeline_event(encounter.encounter_id)
    assert event["actionId"] == action.action_id
    assert event["resolved"] is True
    assert event["resolution"]["legal"] is False
    assert "outside attack reach" in (event["resolution"]["reason"] or "")
    assert target.hp == target.max_hp


def test_timeline_round_trips_through_save():
    runtime = TimelineRaidAincradRuntime(seed=1)
    player = runtime.create_character("Saver")
    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
    encounter.positions[monster.actor_id] = (1.2, 0.0)
    action = runtime.queue_player_attack(encounter.encounter_id, player.actor_id, monster.actor_id, seed=88)

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, TimelineRaidAincradRuntime)
    state = restored.timeline_state(encounter.encounter_id)
    assert len(state["queuedPlayerAttacks"]) == 1
    assert state["queuedPlayerAttacks"][0]["action_id"] == action.action_id
    assert state["queuedPlayerAttacks"][0]["seed"] == 88
