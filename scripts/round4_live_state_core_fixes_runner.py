from __future__ import annotations

from pathlib import Path

path = Path("scripts/round4_live_state_core_fixes.py")
source = path.read_text(encoding="utf-8")
old = '''    ''' + "'''" + '''        actor.alive
        and actor.actor_id not in member_ids
        and actor.location_id == origin_location_id
''' + "'''" + ''',
    ''' + "'''" + '''        (actor.alive or actor.metadata.get(\"death_state\") == \"end_phase\")
        and actor.actor_id not in member_ids
        and actor.location_id == origin_location_id
''' + "'''" + ''',
'''
new = '''    ''' + "'''" + '''        actor_id not in member_ids
        and participant.alive
        and participant.location_id == origin_location_id
''' + "'''" + ''',
    ''' + "'''" + '''        actor_id not in member_ids
        and (participant.alive or participant.metadata.get(\"death_state\") == \"end_phase\")
        and participant.location_id == origin_location_id
''' + "'''" + ''',
'''
if source.count(old) != 1:
    raise RuntimeError("round4 live-state travel predicate patch source changed")
source = source.replace(old, new, 1)
exec(compile(source, str(path), "exec"), {"__name__": "__main__"})
