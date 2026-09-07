import itertools
import math

from sao_mcp.rules.spatial import actor_collision_radius_m, distance_between_points
from sao_mcp.runtime.raid_spatial_runtime import RaidSpatialAincradRuntime


def _assert_no_live_overlap(runtime, encounter):
    live_ids = [
        actor_id
        for actor_id, actor in encounter.participants.items()
        if actor.alive and actor_id in encounter.positions
    ]
    for a_id, b_id in itertools.combinations(live_ids, 2):
        a = encounter.participants[a_id]
        b = encounter.participants[b_id]
        center = distance_between_points(encounter.positions[a_id], encounter.positions[b_id])
        minimum = actor_collision_radius_m(a) + actor_collision_radius_m(b)
        assert center >= minimum - 1e-6, (a_id, b_id, center, minimum)


def test_full_48_player_raid_formation_fits_boss_room_without_overlap():
    runtime = RaidSpatialAincradRuntime(seed=1)
    players = []
    for index in range(48):
        actor = runtime.create_character(f"Raider-{index + 1}", level=6)
        actor.location_id = "floor_1_boss_room"
        players.append(actor)

    encounter, boss = runtime.start_floor_boss_encounter([actor.actor_id for actor in players])
    assert len(players) == 48
    assert encounter.positions[boss.actor_id] == (0.0, 0.0)
    assert encounter.arena_radius_m == 22.0

    for actor in players:
        x, y = encounter.positions[actor.actor_id]
        assert math.hypot(x, y) <= encounter.arena_radius_m
        assert actor.metadata["raid_formation_ring"] in (0, 1, 2)
        assert 0 <= actor.metadata["raid_formation_slot"] < 16

    _assert_no_live_overlap(runtime, encounter)


def test_all_twelve_illfang_sentinel_spawn_slots_remain_distinct_and_valid():
    runtime = RaidSpatialAincradRuntime(seed=2)
    player = runtime.create_character("Lead", level=6)
    player.location_id = "floor_1_boss_room"
    encounter, boss = runtime.start_floor_boss_encounter([player.actor_id])
    definition = runtime.boss_definition(boss)

    for depleted_bars in (1, 2, 3):
        old_hp = boss.hp
        boss.hp = boss.max_hp - depleted_bars * definition.hp_per_bar
        runtime._process_boss_hp_transition(encounter, boss, old_hp)

    minions = [
        actor
        for actor in encounter.participants.values()
        if actor.metadata.get("boss_parent_id") == boss.actor_id
    ]
    assert len(minions) == 12
    assert sorted(int(actor.metadata["boss_spawn_ordinal"]) for actor in minions) == list(range(12))
    positions = [encounter.positions[actor.actor_id] for actor in minions]
    assert len(set(positions)) == 12
    for position in positions:
        assert math.hypot(position[0], position[1]) < encounter.arena_radius_m

    _assert_no_live_overlap(runtime, encounter)
