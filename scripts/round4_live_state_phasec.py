from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:150]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "src/sao_mcp/runtime/engine.py"
replace_once(
    path,
    '        zone_id: str = "floor_1_west_field",\n',
    '        zone_id: str | None = None,\n',
)
replace_once(
    path,
    '''        for actor_id in actor_ids:
            conflicts = [
                encounter_id
                for encounter_id, existing in self.encounters.items()
                if existing.active and actor_id in existing.participants
            ]
            if conflicts:
                raise ValueError(f"actor {actor_id} is already in active encounter {conflicts[0]}")
        location = self.world_map.locations.get(zone_id)
''',
    '''        for actor_id in actor_ids:
            conflicts = [
                encounter_id
                for encounter_id, existing in self.encounters.items()
                if existing.active and actor_id in existing.participants
            ]
            if conflicts:
                raise ValueError(f"actor {actor_id} is already in active encounter {conflicts[0]}")
        participant_locations = {self.actors[actor_id].location_id for actor_id in actor_ids}
        if None in participant_locations or len(participant_locations) != 1:
            raise ValueError("encounter participants must already share one settled world location")
        shared_location_id = next(iter(participant_locations))
        if zone_id is None:
            zone_id = shared_location_id
        elif zone_id != shared_location_id:
            raise ValueError("encounter zone must match the participants' current world location")
        if zone_id not in self.world_map.locations:
            raise KeyError(zone_id)
        location = self.world_map.locations[zone_id]
''',
)

path = "src/sao_mcp/runtime/spatial_runtime.py"
replace_once(
    path,
    '    def start_encounter(self, actor_ids, *, zone_id="floor_1_west_field", safe_zone=None, anti_crystal=None):\n',
    '    def start_encounter(self, actor_ids, *, zone_id=None, safe_zone=None, anti_crystal=None):\n',
)
replace_once(
    path,
    '        encounter.arena_radius_m = 22.0 if zone_id.endswith("boss_room") else 30.0\n',
    '        encounter.arena_radius_m = 22.0 if encounter.zone_id.endswith("boss_room") else 30.0\n',
)

path = "src/sao_mcp/runtime/raid_spatial_runtime.py"
replace_once(
    path,
    '    def start_encounter(self, actor_ids, *, zone_id="floor_1_west_field", safe_zone=None, anti_crystal=None):\n',
    '    def start_encounter(self, actor_ids, *, zone_id=None, safe_zone=None, anti_crystal=None):\n',
)

# This test intentionally verifies illegal field PvP, so place both players in that field first.
path = "tests/test_duels_death.py"
replace_once(
    path,
    '''    a = runtime.create_character("A")
    b = runtime.create_character("B")
    encounter = runtime.start_encounter([a.actor_id, b.actor_id], zone_id="floor_1_west_field")
    result, _ = runtime.attack_authoritative(
''',
    '''    a = runtime.create_character("A")
    b = runtime.create_character("B")
    a.location_id = "floor_1_west_field"
    b.location_id = "floor_1_west_field"
    encounter = runtime.start_encounter([a.actor_id, b.actor_id], zone_id="floor_1_west_field")
    result, _ = runtime.attack_authoritative(
''',
)
