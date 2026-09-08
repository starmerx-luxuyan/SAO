from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario


def test_floor22_witch_quest_completion_unlocks_forest_house_purchase():
    runtime = HousingAincradRuntime(seed=7)
    scenario = install_floor22_witch_scenario(runtime)
    player = runtime.create_character("Floor22", level=30)
    runtime.world.floors[22].unlocked = True
    player.location_id = "floor_22_forest_house_site"
    player.col = 6_000_000

    instance = scenario.start([player.actor_id])
    encounter = scenario.enter_castle(instance["instance_id"])

    for panther_id in list(scenario.instance(instance["instance_id"])["werepanther_ids"]):
        panther = runtime.actors[panther_id]
        panther.hp = 0
        panther.alive = False
        runtime._resolve_defeat(encounter, panther, player.actor_id)

    witch_encounter, witch = scenario.start_confrontation(
        instance["instance_id"],
        accept_soup=True,
    )
    witch.hp = 0
    witch.alive = False
    runtime._resolve_defeat(witch_encounter, witch, player.actor_id)

    result = scenario.finish_return(instance["instance_id"])
    assert player.actor_id in result["completedPlayerIds"]
    assert "witch_of_the_west_and_three_treasures" in runtime.quests.completed_by_actor[player.actor_id]
    assert player.location_id == "floor_22_forest_house_site"

    house = runtime.purchase_residence(player.actor_id, "floor22_forest_house_k4")
    assert house.listing_id == "floor22_forest_house_k4"
    assert house.parent_location_id == "floor_22_forest_house_site"
