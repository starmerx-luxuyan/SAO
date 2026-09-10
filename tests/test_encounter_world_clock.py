import json

import pytest

from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.engine import GameRuntime
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import SAVE_SCHEMA, SAVE_SCHEMA_V1, SAVE_SCHEMA_V2, export_runtime, import_runtime


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
    assert first.world_started_at_ms == 0
    assert second.world_started_at_ms == 0
    assert first.events[0].event_type == "encounter_started"
    assert "world_started_at_ms" not in first.events[0].payload

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


def test_ended_encounter_history_no_longer_participates_in_live_travel_or_combat():
    runtime = GameRuntime(seed=312)
    player = runtime.create_character("Traveller", level=8)
    monster = runtime.create_training_monster(level=4)
    player.location_id = "floor_1_west_field"
    monster.location_id = "floor_1_west_field"
    encounter = runtime.start_encounter(
        [player.actor_id, monster.actor_id],
        zone_id="floor_1_west_field",
    )

    with pytest.raises(ValueError, match="ordinary travel is unavailable during a live encounter"):
        runtime.travel_actor(player.actor_id, "floor_1_horunka")

    ended = runtime.end_encounter(encounter.encounter_id, reason="combat_disengaged")
    assert ended.active is False
    assert ended.ended_at_world_ms == runtime.world.now_ms
    assert ended.end_reason == "combat_disengaged"

    moved = runtime.travel_actor(player.actor_id, "floor_1_horunka")
    assert moved.to_location_id == "floor_1_horunka"
    with pytest.raises(ValueError, match="has ended"):
        runtime.advance_encounter(encounter.encounter_id, 1)
    with pytest.raises(ValueError, match="has ended"):
        runtime.attack(encounter.encounter_id, player.actor_id, monster.actor_id)


def test_dead_actor_cannot_walk_or_consume_teleport_crystal():
    runtime = GameRuntime(seed=314)
    player = runtime.create_character("DeadTraveller", level=8)
    player.location_id = "floor_1_west_field"
    crystal = ItemInstance(
        instance_id="dead_travel_teleport_crystal",
        template_id="teleport_crystal",
        owner_id=player.actor_id,
        quantity=1,
    )
    add_item(player, crystal, runtime.catalog, allow_overweight=True)
    player.hp = 0
    player.alive = False
    world_before = runtime.world.now_ms

    with pytest.raises(ValueError, match="dead actor cannot use world travel"):
        runtime.travel_actor(player.actor_id, "floor_1_horunka")
    assert runtime.world.now_ms == world_before

    with pytest.raises(ValueError, match="dead actor cannot use world travel"):
        runtime.teleport_actor(
            player.actor_id,
            crystal.instance_id,
            "floor_1_town_of_beginnings",
        )
    assert crystal.instance_id in player.inventory
    assert player.inventory[crystal.instance_id].quantity == 1
    assert runtime.world.now_ms == world_before


def test_legacy_saves_migrate_only_when_no_unrepresentable_encounter_state_exists():
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

    v2 = json.loads(export_runtime(HousingAincradRuntime(seed=316)))
    v2["schema"] = SAVE_SCHEMA_V2
    assert import_runtime(json.dumps(v2)).encounters == {}

    v2_with_encounter = json.loads(export_runtime(runtime_with_encounter))
    v2_with_encounter["schema"] = SAVE_SCHEMA_V2
    with pytest.raises(ValueError, match="explicit encounter lifecycle"):
        import_runtime(json.dumps(v2_with_encounter))
