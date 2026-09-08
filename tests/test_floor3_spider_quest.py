from sao_mcp.corpus.floor3 import FANG_ID, QUEST_ID, SCOUT_EMBLEM_ID
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor3_spiders import install_floor3_spider_scenario


def test_floor3_vanquishing_the_spiders_is_playable_end_to_end():
    runtime = HousingAincradRuntime(seed=17)
    scenario = install_floor3_spider_scenario(runtime)
    player = runtime.create_character("SpiderQuest", level=15)
    runtime.world.floors[3].unlocked = True

    player.location_id = "floor_3_dark_elf_base"
    progress = runtime.accept_quest(player.actor_id, QUEST_ID)
    assert progress.quest_id == QUEST_ID

    player.location_id = "floor_3_queen_spider_nest"
    emblem = scenario.search_dead_scout(player.actor_id)
    assert emblem.template_id == SCOUT_EMBLEM_ID

    encounter, nephila = scenario.create_nephila_encounter(player.actor_id)
    nephila.hp = 0
    nephila.alive = False
    runtime._resolve_defeat(encounter, nephila, player.actor_id)

    assert any(item.template_id == FANG_ID for item in player.inventory.values())
    assert runtime.quests.ready_to_claim(player, QUEST_ID)

    player.location_id = "floor_3_dark_elf_base"
    claim = runtime.claim_quest(player.actor_id, QUEST_ID)
    assert claim.quest_id == QUEST_ID
    assert QUEST_ID in runtime.quests.completed_by_actor[player.actor_id]
    assert not any(
        item.template_id in {SCOUT_EMBLEM_ID, FANG_ID}
        for item in player.inventory.values()
    )
