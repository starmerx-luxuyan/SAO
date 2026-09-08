import pytest

from sao_mcp.corpus.floor4 import QUEST_ID
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS
from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor4_biceps import install_floor4_biceps_scenario
from sao_mcp.scenarios.floor4_shipwright import (
    BUILD_TIME_MS,
    HIDEOUT_NAVIGATION_MS,
    install_floor4_shipwright_scenario,
)


def test_floor4_progression_runs_shipwright_biceps_and_yofel_report():
    runtime = HousingAincradRuntime(seed=31)
    shipwright = install_floor4_shipwright_scenario(runtime)
    biceps = install_floor4_biceps_scenario(runtime)
    player = runtime.create_character("Shipwright", level=22)
    runtime.world.floors[4].unlocked = True
    player.location_id = "floor_4_rovia"

    state = shipwright.start_quest(player.actor_id)
    assert state["stage"] == "gather_materials"

    runtime.travel_actor(player.actor_id, "floor_4_bear_forest")
    definition = AINCRAD_MONSTERS["magnatherium"]
    magnatherium = runtime._create_monster(
        name=definition.name,
        level=definition.level,
        location_id=definition.location_id,
        hp_factor=definition.hp_factor,
        loot_table_id=definition.loot_table_id,
        quest_kill_id=definition.quest_kill_id,
    )
    magnatherium.metadata["monster_id"] = definition.monster_id
    encounter = runtime.start_encounter(
        [player.actor_id, magnatherium.actor_id],
        zone_id="floor_4_bear_forest",
    )

    core = shipwright.harvest_noblewood_core(player.actor_id, encounter.encounter_id)
    assert core.template_id == "noblewood_core"

    magnatherium.hp = 0
    magnatherium.alive = False
    runtime._resolve_defeat(encounter, magnatherium, player.actor_id)
    inventory_templates = {item.template_id for item in player.inventory.values()}
    assert {"legendary_bear_fat", "fire_bear_claw", "fire_bear_pelt"}.issubset(inventory_templates)

    # The premium horn is a non-guaranteed drop in runtime tuning; pin one here so this single
    # vertical-slice regression also exercises the canonical Fire-Bear ram finisher later.
    horn = ItemInstance(
        instance_id="test_fire_bear_horn",
        template_id="fire_bear_horn",
        owner_id=player.actor_id,
    )
    add_item(player, horn, runtime.catalog, allow_overweight=True)

    runtime.travel_actor(player.actor_id, "floor_4_rovia")
    before_build = runtime.world.now_ms
    state = shipwright.build_gondola(
        player.actor_id,
        name="The Tilnel",
        passenger_seats=10,
        install_ram=True,
    )
    assert runtime.world.now_ms == before_build + BUILD_TIME_MS
    assert state["gondola"]["name"] == "The Tilnel"
    assert state["gondola"]["passenger_seats"] == 10
    assert state["gondola"]["quality"] == "premium"
    assert state["gondola"]["ram_installed"]
    assert state["quest_progress"]["construct_personal_gondola"] == 1
    assert not runtime.quests.ready_to_claim(player, QUEST_ID)

    sailed = shipwright.sail(player.actor_id, "floor_4_caldera_lake")
    assert sailed["shipwright_state"]["water_carriers_suspicious"]
    assert sailed["shipwright_state"]["stage"] == "return_to_romolo"
    shipwright.sail(player.actor_id, "floor_4_rovia")

    state = shipwright.receive_romolo_followup(player.actor_id)
    assert state["stage"] == "follow_transport_at_nightfall"
    state = shipwright.follow_water_carrier_transport(player.actor_id)
    assert player.location_id == "floor_4_fallen_elf_hideout"
    assert state["stage"] == "hideout_search"

    before_hideout = runtime.world.now_ms
    state = shipwright.investigate_fallen_elf_hideout(player.actor_id)
    assert runtime.world.now_ms == before_hideout + HIDEOUT_NAVIGATION_MS
    assert state["stage"] == "report_to_yofel"
    assert state["quest_progress"]["discover_water_carriers_secret"] == 1
    assert runtime.quests.ready_to_claim(player, QUEST_ID)

    shipwright.sail(player.actor_id, "floor_4_rovia")
    shipwright.sail(player.actor_id, "floor_4_caldera_lake")
    with pytest.raises(ValueError, match="Biceps Archelon blocks passage"):
        shipwright.sail(player.actor_id, "floor_4_usco")

    raid = biceps.start_raid([player.actor_id])
    boss = runtime.actors[raid["boss_id"]]
    assert len(raid["hp_bars"]) == 2
    boss.hp = max(1, int(boss.max_hp * 0.09))
    boss.alive = True
    cleared = biceps.ram_abdomen(raid["instance_id"], player.actor_id)
    assert cleared["stage"] == "cleared"
    assert cleared["last_attack_player_id"] == player.actor_id
    assert cleared["south_route_unlocked"]

    shipwright.sail(player.actor_id, "floor_4_usco")
    shipwright.sail(player.actor_id, "floor_4_yofel_castle")
    result = shipwright.report_to_yofel(player.actor_id)

    assert QUEST_ID in runtime.quests.completed_by_actor[player.actor_id]
    assert result["shipwright_state"]["stage"] == "completed"
    assert result["next_quest_id"] == "laketop_fortress"
    assert player.metadata["floor4_laketop_fortress_unlocked"] is True
