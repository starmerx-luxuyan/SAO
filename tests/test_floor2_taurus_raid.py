from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor2_taurus_raid import install_floor2_taurus_raid_scenario


def test_floor2_taurus_midbosses_transition_into_asterius_and_clear_floor():
    runtime = HousingAincradRuntime(seed=23)
    scenario = install_floor2_taurus_raid_scenario(runtime)
    player = runtime.create_character("TaurusRaid", level=18)
    runtime.world.floors[2].unlocked = True
    player.location_id = "floor_2_boss_room"

    state = scenario.start_raid([player.actor_id])
    encounter = runtime.encounters[state["encounter_id"]]
    assert state["asterius_id"] not in encounter.participants
    assert {state["nato_id"], state["baran_id"]}.issubset(encounter.participants)

    for actor_id in (state["nato_id"], state["baran_id"]):
        actor = runtime.actors[actor_id]
        actor.hp = 0
        actor.alive = False
        runtime._resolve_defeat(encounter, actor, player.actor_id)

    state = scenario.unleash_asterius(state["instance_id"])
    boss = runtime.actors[state["asterius_id"]]
    assert state["stage"] == "asterius"
    assert boss.actor_id in encounter.participants
    assert runtime.boss_bar_state(boss)["hpBars"] == 6

    boss.hp = 0
    boss.alive = False
    runtime._resolve_defeat(encounter, boss, player.actor_id)
    assert runtime.world.floors[2].floor_boss_defeated
