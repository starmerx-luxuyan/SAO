from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Pursuers and Fallen scouts traverse the same edges during the same elapsed window, but they
# remain separate groups. The pursuer route record must not pretend the hostile scouts are party members.
path = "src/sao_mcp/scenarios/floor7_pursuit.py"
replace_once(
    path,
    'from sao_mcp.rules.group_travel import group_travel_record, travel_together\n',
    'from sao_mcp.rules.group_travel import (\n'
    '    complete_routed_travel_within_window,\n'
    '    group_travel_record,\n'
    '    travel_together,\n'
    ')\n',
)
replace_once(
    path,
    '''        moving = list(pursuit["travelling_actor_ids"]) + list(pursuit["fallen_scout_ids"])
        to_ant = travel_together(self.runtime, moving, ANT_TUNNEL_VALLEY)
        pursuit["tail_to_ant_route"] = [group_travel_record(to_dragon), group_travel_record(to_ant)]
''',
    '''        concurrent_started_at_ms = self.runtime.world.now_ms
        to_ant = travel_together(
            self.runtime,
            pursuit["travelling_actor_ids"],
            ANT_TUNNEL_VALLEY,
        )
        complete_routed_travel_within_window(
            self.runtime,
            pursuit["fallen_scout_ids"],
            ANT_TUNNEL_VALLEY,
            started_at_ms=concurrent_started_at_ms,
            completed_at_ms=self.runtime.world.now_ms,
        )
        pursuit["tail_to_ant_route"] = [group_travel_record(to_dragon), group_travel_record(to_ant)]
''',
)
replace_once(
    path,
    '''        moving = list(pursuit["travelling_actor_ids"]) + list(pursuit["fallen_scout_ids"])
        to_plateau = travel_together(self.runtime, moving, PLATEAU)
        to_labyrinth = travel_together(self.runtime, moving, LABYRINTH)
        for scout_id in pursuit["fallen_scout_ids"]:
''',
    '''        concurrent_started_at_ms = self.runtime.world.now_ms
        to_plateau = travel_together(
            self.runtime,
            pursuit["travelling_actor_ids"],
            PLATEAU,
        )
        to_labyrinth = travel_together(
            self.runtime,
            pursuit["travelling_actor_ids"],
            LABYRINTH,
        )
        complete_routed_travel_within_window(
            self.runtime,
            pursuit["fallen_scout_ids"],
            LABYRINTH,
            started_at_ms=concurrent_started_at_ms,
            completed_at_ms=self.runtime.world.now_ms,
        )
        for scout_id in pursuit["fallen_scout_ids"]:
''',
)

# Raid unit tests previously bypassed world location entirely. Door retreat is a world-graph action,
# so the fixture now materializes test players at the actual boss room and uses normal location enforcement.
path = "tests/test_raids.py"
replace_once(
    path,
    'from sao_mcp.rules.raids import (\n',
    'from sao_mcp.rules.spawn import create_character_at\nfrom sao_mcp.rules.raids import (\n',
)
replace_once(
    path,
    '''    players = [runtime.create_character(f"P{i+1}", level=8) for i in range(player_count)]
    encounter, boss = runtime.start_floor_boss_encounter(
        [player.actor_id for player in players],
        enforce_location=False,
    )
''',
    '''    players = [
        create_character_at(
            runtime,
            f"P{i+1}",
            level=8,
            location_id="floor_1_boss_room",
        )
        for i in range(player_count)
    ]
    encounter, boss = runtime.start_floor_boss_encounter([player.actor_id for player in players])
''',
)

# The Harin integration now deliberately preserves epistemic uncertainty after Lavik leaves:
# the last confirmed location is known, the destination is not. Update the stale assertion accordingly.
path = "tests/test_floor7_elfwar.py"
replace_once(
    path,
    '    assert runtime.npc_location_id(LAVIK_ID) == "floor_7_field"\n',
    '    assert runtime.npc_location_id(LAVIK_ID) == LOOSEROCK_FOREST\n'
    '    assert lavik.metadata["destination_unknown"] is True\n'
    '    assert lavik.metadata["last_confirmed_location_id"] == LOOSEROCK_FOREST\n',
)

# Nocturne cross-floor transport requires a real elapsed window. These fixtures fabricate a validated
# Harin handoff directly, so give the fabricated handoff the same departure-time fact the real scenario writes.
for path in ("tests/test_floor4_nocturne.py", "tests/test_floor8_emergency.py"):
    text = Path(path).read_text(encoding="utf-8")
    marker = '"stage": "boss_room_reached",\n'
    if marker not in text:
        raise RuntimeError(f"{path}: Harin fixture stage marker not found")
    if '"lavik_departed_at_ms":' not in text:
        text = text.replace(marker, marker + '            "lavik_departed_at_ms": 0,\n', 1)
    # The transport minimum is 90 minutes; fixtures start at t=0, so establish enough elapsed world time
    # before the backtrack is opened without inventing an impossible negative timestamp.
    setup_anchor = '    runtime.world.floors[4].main_town_gate_active = True\n'
    if path.endswith("test_floor4_nocturne.py"):
        if setup_anchor not in text:
            raise RuntimeError(f"{path}: setup anchor not found")
        text = text.replace(setup_anchor, setup_anchor + '    runtime.advance_world(2 * 60 * 60_000)\n', 1)
    else:
        floor8_anchor = '    runtime.world.floors[8].main_town_gate_active = True\n'
        if floor8_anchor not in text:
            raise RuntimeError(f"{path}: Floor 8 setup anchor not found")
        text = text.replace(floor8_anchor, floor8_anchor + '    runtime.advance_world(2 * 60 * 60_000)\n', 1)
    Path(path).write_text(text, encoding="utf-8")
