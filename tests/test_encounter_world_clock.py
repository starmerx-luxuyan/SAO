import json

import pytest

from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import SAVE_SCHEMA, SAVE_SCHEMA_V1, export_runtime, import_runtime


def _encounter(runtime, player_name):
    player = runtime.create_character(player_name, level=8)
    monster = runtime.create_training_monster(level=4)
    player.location_id = "floor_1_west_field"
    encounter = runtime.start_encounter(
        [player.actor_id, monster.actor_id],
        zone_id="floor_1_west_field",
    )
    return encounter


def test_parallel_encounters_share_one_absolute_world_clock_and_persist_their_anchors():
    runtime = HousingAincradRuntime(seed=311)
    first = _encounter(runtime, "ClockA")
    second = _encounter(runtime, "ClockB")

    assert runtime.world.now_ms == 0
    assert first.events[0].event_type == "encounter_started"
    assert first.events[0].payload["world_started_at_ms"] == 0
    assert second.events[0].payload["world_started_at_ms"] == 0

    runtime.advance_encounter(first.encounter_id, 10_000)
    assert runtime.world.now_ms == 10_000
    assert runtime.encounter_world_time_ms(first.encounter_id) == 10_000

    runtime.advance_encounter(second.encounter_id, 10_000)
    assert runtime.world.now_ms == 10_000
    assert runtime.encounter_world_time_ms(second.encounter_id) == 10_000

    runtime.advance_encounter(second.encounter_id, 10_000)
    assert runtime.world.now_ms == 20_000
    assert runtime.encounter_world_time_ms(second.encounter_id) == 20_000
    assert runtime.encounter_world_time_ms(first.encounter_id) == 10_000

    saved = export_runtime(runtime)
    assert json.loads(saved)["schema"] == SAVE_SCHEMA
    restored = import_runtime(saved)
    assert restored.world.now_ms == 20_000
    assert restored.encounter_world_time_ms(first.encounter_id) == 10_000
    assert restored.encounter_world_time_ms(second.encounter_id) == 20_000


def test_v1_save_migrates_only_when_no_unanchored_encounter_state_exists():
    runtime = HousingAincradRuntime(seed=313)
    runtime.create_character("LegacyNoEncounter", level=8)
    no_encounters = json.loads(export_runtime(runtime))
    no_encounters["schema"] = SAVE_SCHEMA_V1
    restored = import_runtime(json.dumps(no_encounters))
    assert restored.encounters == {}

    runtime_with_encounter = HousingAincradRuntime(seed=315)
    _encounter(runtime_with_encounter, "LegacyEncounter")
    legacy = json.loads(export_runtime(runtime_with_encounter))
    legacy["schema"] = SAVE_SCHEMA_V1
    with pytest.raises(ValueError, match="cannot be migrated exactly"):
        import_runtime(json.dumps(legacy))
