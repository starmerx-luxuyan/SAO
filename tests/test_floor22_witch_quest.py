from sao_mcp.runtime.floor22_runtime import Floor22QuestAincradRuntime


def test_floor22_witch_quest_completion_unlocks_forest_house_purchase():
    runtime = Floor22QuestAincradRuntime(seed=7)
    player = runtime.create_character("Floor22", level=30)
    runtime.world.floors[22].unlocked = True
    player.location_id = "floor_22_forest_house_site"
    player.col = 6_000_000

    instance = runtime.start_witch_quest([player.actor_id])
    encounter = runtime.enter_witch_castle(instance["instance_id"])

    for panther_id in list(runtime._instance(instance["instance_id"])["werepanther_ids"]):
        panther = runtime.actors[panther_id]
        panther.hp = 0
        panther.alive = False
        runtime._resolve_defeat(encounter, panther, player.actor_id)

    witch_encounter, witch = runtime.start_witch_confrontation(
        instance["instance_id"],
        accept_soup=True,
    )
    witch.hp = 0
    witch.alive = False
    runtime._resolve_defeat(witch_encounter, witch, player.actor_id)

    result = runtime.return_from_witch_quest(instance["instance_id"])
    assert player.actor_id in result["completedPlayerIds"]
    assert "witch_of_the_west_and_three_treasures" in runtime.quests.completed_by_actor[player.actor_id]
    assert player.location_id == "floor_22_forest_house_site"

    house = runtime.purchase_residence(player.actor_id, "floor22_forest_house_k4")
    assert house.listing_id == "floor22_forest_house_k4"
    assert house.parent_location_id == "floor_22_forest_house_site"
