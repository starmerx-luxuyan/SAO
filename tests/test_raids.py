import pytest

from sao_mcp.rules.spawn import create_character_at
from sao_mcp.rules.raids import (
    assign_raid_role,
    boss_raid_status,
    retreat_from_boss_room,
    set_party_rotation,
)
from sao_mcp.runtime.aincrad_runtime import AincradRuntime


def _raid(player_count=1):
    runtime = AincradRuntime(seed=2)
    players = [
        create_character_at(
            runtime,
            f"P{i+1}",
            level=8,
            location_id="floor_1_boss_room",
        )
        for i in range(player_count)
    ]
    encounter, boss = runtime.start_floor_boss_encounter([player.actor_id for player in players])
    return runtime, players, encounter, boss


def test_single_player_door_retreat_resets_boss_when_room_empties():
    runtime, players, encounter, boss = _raid(1)
    player = players[0]
    boss.hp -= 2_000
    result = retreat_from_boss_room(runtime, encounter.encounter_id, player.actor_id, method="door")
    assert result.remaining_players == 0
    assert result.boss_reset
    assert player.actor_id not in encounter.participants
    assert player.location_id == "floor_1_labyrinth"
    assert boss.hp == boss.max_hp
    assert runtime.boss_phase(boss).phase_id == "axe_buckler"
    assert not [actor for actor in encounter.participants.values() if actor.metadata.get("boss_parent_id") == boss.actor_id]
    assert any(event.event_type == "boss_disengaged_reset" for event in encounter.events)


def test_partial_raid_retreat_does_not_reset_boss():
    runtime, players, encounter, boss = _raid(2)
    boss.hp -= 1_500
    hp_before = boss.hp
    result = retreat_from_boss_room(runtime, encounter.encounter_id, players[0].actor_id, method="door")
    assert result.remaining_players == 1
    assert not result.boss_reset
    assert boss.hp == hp_before
    assert players[1].actor_id in encounter.participants


def test_anti_crystal_does_not_block_door_retreat_but_locked_door_does():
    runtime, players, encounter, boss = _raid(1)
    encounter.anti_crystal = True
    status = boss_raid_status(runtime, encounter.encounter_id)
    assert not status["canUseTeleportCrystal"]
    assert status["retreatPossible"]

    boss.metadata["boss_room_door_locked"] = True
    status = boss_raid_status(runtime, encounter.encounter_id)
    assert not status["retreatPossible"]
    with pytest.raises(ValueError, match="locked"):
        retreat_from_boss_room(runtime, encounter.encounter_id, players[0].actor_id, method="door")


def test_wipe_status_is_mechanical_not_inferred_from_narration():
    runtime, players, encounter, boss = _raid(2)
    for player in players:
        player.hp = 0
        player.alive = False
    status = boss_raid_status(runtime, encounter.encounter_id)
    assert status["wipe"]
    assert status["livingPlayers"] == 0
    assert status["deadPlayers"] == 2
    assert status["bossAlive"]


def test_raid_command_roles_and_party_rotation_are_persistent_world_state():
    runtime, players, encounter, boss = _raid(2)
    party_a = runtime.create_party(players[0].actor_id)
    party_b = runtime.create_party(players[1].actor_id)
    assign_raid_role(runtime.world, encounter.encounter_id, players[0].actor_id, "tank")
    assign_raid_role(runtime.world, encounter.encounter_id, players[1].actor_id, "attacker")
    set_party_rotation(runtime.world, encounter.encounter_id, [party_a.party_id, party_b.party_id])
    status = boss_raid_status(runtime, encounter.encounter_id)
    assert status["command"]["roles"][players[0].actor_id] == "tank"
    assert status["command"]["roles"][players[1].actor_id] == "attacker"
    assert status["command"]["party_rotation"] == [party_a.party_id, party_b.party_id]
