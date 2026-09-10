from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:150]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Canon-backed encounter location: Magnatherium is the Bear Forest rare monster, not a generic Floor 4 field spawn.
path = "src/sao_mcp/corpus/monsters.py"
replace_once(
    path,
    '''        "magnatherium", "Magnatherium", 4, level=10, hp_factor=3.2,
        tags=("rare_named_monster", "beast", "shipwright_of_yore"),
''',
    '''        "magnatherium", "Magnatherium", 4, level=10, location="floor_4_bear_forest", hp_factor=3.2,
        tags=("rare_named_monster", "beast", "shipwright_of_yore"),
''',
)

# Boss tests must put the player in the boss room; the scenario may no longer remote-place them.
path = "tests/test_boss_runtime.py"
replace_once(
    path,
    '''    player = runtime.create_character("Raider", level=8)
    player.skill_proficiencies["one_hand_sword"] = 700
    encounter, boss = runtime.start_floor_boss_encounter(
        [player.actor_id],
        enforce_location=False,
    )
''',
    '''    player = runtime.create_character("Raider", level=8)
    player.skill_proficiencies["one_hand_sword"] = 700
    player.location_id = "floor_1_boss_room"
    encounter, boss = runtime.start_floor_boss_encounter([player.actor_id])
''',
)

path = "tests/test_family_divorce.py"
replace_once(
    path,
    '''    a, b, marriage = _married(runtime, strong=True)
    original_ids = set(a.inventory)
    encounter = runtime.start_encounter([a.actor_id, b.actor_id], zone_id="floor_1_west_field")
''',
    '''    a, b, marriage = _married(runtime, strong=True)
    original_ids = set(a.inventory)
    a.location_id = "floor_1_west_field"
    b.location_id = "floor_1_west_field"
    encounter = runtime.start_encounter([a.actor_id, b.actor_id], zone_id="floor_1_west_field")
''',
)

path = "tests/test_inventory_loot.py"
replace_once(
    path,
    '''    monster.hp = 1
    monster.max_hp = 1
    monster.agility = -100
    enc = rt.start_encounter([a.actor_id, b.actor_id, monster.actor_id])
''',
    '''    monster.hp = 1
    monster.max_hp = 1
    monster.agility = -100
    a.location_id = monster.location_id
    b.location_id = monster.location_id
    enc = rt.start_encounter([a.actor_id, b.actor_id, monster.actor_id])
''',
)

path = "tests/test_relationships_community.py"
replace_once(
    path,
    '''    party = runtime.create_party(a.actor_id)
    runtime.join_party(party.party_id, b.actor_id)
    runtime.start_encounter([a.actor_id, b.actor_id, monster.actor_id])
''',
    '''    party = runtime.create_party(a.actor_id)
    runtime.join_party(party.party_id, b.actor_id)
    a.location_id = monster.location_id
    b.location_id = monster.location_id
    runtime.start_encounter([a.actor_id, b.actor_id, monster.actor_id])
''',
)

path = "tests/test_runtime.py"
replace_once(
    path,
    '''    rt.join_party(party.party_id, b.actor_id)
    monster = rt.create_training_monster(level=4)
    enc = rt.start_encounter([a.actor_id, b.actor_id, monster.actor_id])
''',
    '''    rt.join_party(party.party_id, b.actor_id)
    monster = rt.create_training_monster(level=4)
    a.location_id = monster.location_id
    b.location_id = monster.location_id
    enc = rt.start_encounter([a.actor_id, b.actor_id, monster.actor_id])
''',
)
replace_once(
    path,
    '''    a = rt.create_character("A")
    b = rt.create_character("B")
    enc = rt.start_encounter([a.actor_id, b.actor_id], safe_zone=True, zone_id="town")
''',
    '''    a = rt.create_character("A")
    b = rt.create_character("B")
    enc = rt.start_encounter(
        [a.actor_id, b.actor_id], safe_zone=True, zone_id="floor_1_town_of_beginnings"
    )
''',
)

path = "tests/test_spatial_combat.py"
for old, new in (
    (
        '''def test_default_encounter_formation_and_authoritative_range():
    runtime = SpatialAincradRuntime(seed=1)
    player = runtime.create_character("Spatial")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
''',
        '''def test_default_encounter_formation_and_authoritative_range():
    runtime = SpatialAincradRuntime(seed=1)
    player = runtime.create_character("Spatial")
    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
''',
    ),
    (
        '''def test_encounter_movement_consumes_time_and_changes_distance():
    runtime = SpatialAincradRuntime(seed=1)
    player = runtime.create_character("Mover")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
''',
        '''def test_encounter_movement_consumes_time_and_changes_distance():
    runtime = SpatialAincradRuntime(seed=1)
    player = runtime.create_character("Mover")
    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
''',
    ),
    (
        '''    mover = runtime.create_character("Mover")
    tank = runtime.create_character("Tank")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([mover.actor_id, tank.actor_id, monster.actor_id])
''',
        '''    mover = runtime.create_character("Mover")
    tank = runtime.create_character("Tank")
    monster = runtime.create_training_monster(level=1)
    mover.location_id = monster.location_id
    tank.location_id = monster.location_id
    encounter = runtime.start_encounter([mover.actor_id, tank.actor_id, monster.actor_id])
''',
    ),
    (
        '''    monster = runtime.create_training_monster(level=1)
    party = runtime.create_party(outgoing.actor_id)
    runtime.join_party(party.party_id, incoming.actor_id)
    encounter = runtime.start_encounter([outgoing.actor_id, incoming.actor_id, monster.actor_id])
''',
        '''    monster = runtime.create_training_monster(level=1)
    party = runtime.create_party(outgoing.actor_id)
    runtime.join_party(party.party_id, incoming.actor_id)
    outgoing.location_id = monster.location_id
    incoming.location_id = monster.location_id
    encounter = runtime.start_encounter([outgoing.actor_id, incoming.actor_id, monster.actor_id])
''',
    ),
    (
        '''    runtime = bootstrap.runtime
    player = runtime.create_character("ToolRange")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
''',
        '''    runtime = bootstrap.runtime
    player = runtime.create_character("ToolRange")
    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
''',
    ),
):
    replace_once(path, old, new)

path = "tests/test_timeline_combat.py"
replace_once(
    path,
    '''def test_queued_attack_resolves_when_no_boss_event_precedes_it():
    runtime = TimelineRaidAincradRuntime(seed=1)
    player = runtime.create_character("Timeline")
    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
''',
    '''def test_queued_attack_resolves_when_no_boss_event_precedes_it():
    runtime = TimelineRaidAincradRuntime(seed=1)
    player = runtime.create_character("Timeline")
    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
''',
)
replace_once(
    path,
    '''def test_target_moving_out_during_windup_causes_queued_whiff():
    runtime = TimelineRaidAincradRuntime(seed=1)
    player = runtime.create_character("Attacker")
    target = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, target.actor_id])
''',
    '''def test_target_moving_out_during_windup_causes_queued_whiff():
    runtime = TimelineRaidAincradRuntime(seed=1)
    player = runtime.create_character("Attacker")
    target = runtime.create_training_monster(level=1)
    player.location_id = target.location_id
    encounter = runtime.start_encounter([player.actor_id, target.actor_id])
''',
)
