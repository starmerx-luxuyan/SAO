from __future__ import annotations

from pathlib import Path

path = Path("scripts/round4_live_state_core_fixes.py")
source = path.read_text(encoding="utf-8")

travel_old = '''    ''' + "'''" + '''        actor.alive
        and actor.actor_id not in member_ids
        and actor.location_id == origin_location_id
''' + "'''" + ''',
    ''' + "'''" + '''        (actor.alive or actor.metadata.get(\"death_state\") == \"end_phase\")
        and actor.actor_id not in member_ids
        and actor.location_id == origin_location_id
''' + "'''" + ''',
'''
travel_new = '''    ''' + "'''" + '''        actor_id not in member_ids
        and participant.alive
        and participant.location_id == origin_location_id
''' + "'''" + ''',
    ''' + "'''" + '''        actor_id not in member_ids
        and (participant.alive or participant.metadata.get(\"death_state\") == \"end_phase\")
        and participant.location_id == origin_location_id
''' + "'''" + ''',
'''
if source.count(travel_old) != 1:
    raise RuntimeError("round4 live-state travel predicate patch source changed")
source = source.replace(travel_old, travel_new, 1)

timeline_old = '''path = "tests/test_timeline_combat.py"
replace_once(
    path,
    ''' + "'''" + '''    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
''' + "'''" + ''',
    ''' + "'''" + '''    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
''' + "'''" + ''',
)
'''
timeline_new = '''path = "tests/test_timeline_combat.py"
replace_once(
    path,
    ''' + "'''" + '''def test_timeline_round_trips_through_save():
    runtime = TimelineRaidAincradRuntime(seed=1)
    player = runtime.create_character("Saver")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
''' + "'''" + ''',
    ''' + "'''" + '''def test_timeline_round_trips_through_save():
    runtime = TimelineRaidAincradRuntime(seed=1)
    player = runtime.create_character("Saver")
    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
''' + "'''" + ''',
)
'''
if source.count(timeline_old) != 1:
    raise RuntimeError("round4 timeline fixture patch source changed")
source = source.replace(timeline_old, timeline_new, 1)

exec(compile(source, str(path), "exec"), {"__name__": "__main__"})
