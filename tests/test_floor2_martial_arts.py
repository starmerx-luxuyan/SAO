from sao_mcp.corpus.floor2 import QUEST_ID
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor2_martial_arts import install_floor2_martial_arts_scenario


def test_floor2_martial_arts_trial_unlocks_extra_skill_after_rock_breaks():
    runtime = HousingAincradRuntime(seed=29)
    scenario = install_floor2_martial_arts_scenario(runtime)
    player = runtime.create_character("RockBreaker", level=10)
    runtime.world.floors[2].unlocked = True
    player.location_id = "floor_2_martial_arts_hut"

    state = scenario.start_trial(player.actor_id)
    assert state["whisker_paint"]
    assert not state["martial_arts_unlocked"]

    state = scenario.practice_palm_strikes(player.actor_id, hours=71)
    assert state["completed_at_ms"] is None
    assert state["whisker_paint"]

    state = scenario.practice_palm_strikes(player.actor_id, hours=1)
    assert state["completed_at_ms"] is not None
    assert state["martial_arts_unlocked"]
    assert not state["whisker_paint"]
    assert QUEST_ID in runtime.quests.completed_by_actor[player.actor_id]
    assert "martial_arts" not in player.equipped_skills
    assert "martial_arts" in player.metadata["unlocked_special_skills"]
