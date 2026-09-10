from pathlib import Path

from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor5_fuscus import (
    FUSCUS_FLAG_DROP_EVENT_RULE_ID,
    Floor5FuscusScenario,
    install_floor5_fuscus_scenario,
)
from sao_mcp.scenarios.floor7_pursuit import (
    LABYRINTH_PURSUIT_EVENT_RULE_ID,
    Floor7PursuitScenario,
    install_floor7_pursuit_scenario,
)
from sao_mcp.scenarios.floor6_buxum import (
    BUXUM_BETRAYAL_EVENT_RULE_ID,
    BUXUM_RETREAT_EVENT_RULE_ID,
    Floor6BuxumScenario,
    install_floor6_buxum_scenario,
)
from sao_mcp.scenarios.floor6_irrational_cube import install_floor6_irrational_cube_scenario
from sao_mcp.scenarios.floor6_stachion import (
    AMBUSHER_RETREAT_EVENT_RULE_ID,
    MORTE_JOE_AMBUSH_EVENT_RULE_ID,
    PARALYSIS_RELEASE_EVENT_RULE_ID,
    Floor6StachionScenario,
    install_floor6_stachion_scenario,
)


ROOT = Path(__file__).resolve().parents[1]


def test_conditional_scene_transitions_are_registered_world_event_rules():
    runtime = HousingAincradRuntime(seed=811)
    cube = install_floor6_irrational_cube_scenario(runtime)
    buxum = install_floor6_buxum_scenario(runtime, cube)
    stachion = install_floor6_stachion_scenario(runtime)
    fuscus = install_floor5_fuscus_scenario(runtime)
    pursuit = install_floor7_pursuit_scenario(runtime)

    assert install_floor6_buxum_scenario(runtime, cube) is buxum
    assert install_floor6_stachion_scenario(runtime) is stachion
    assert install_floor5_fuscus_scenario(runtime) is fuscus
    assert install_floor7_pursuit_scenario(runtime) is pursuit

    assert set(runtime.world_event_rules).issuperset(
        {
            BUXUM_BETRAYAL_EVENT_RULE_ID,
            BUXUM_RETREAT_EVENT_RULE_ID,
            MORTE_JOE_AMBUSH_EVENT_RULE_ID,
            PARALYSIS_RELEASE_EVENT_RULE_ID,
            AMBUSHER_RETREAT_EVENT_RULE_ID,
            FUSCUS_FLAG_DROP_EVENT_RULE_ID,
            LABYRINTH_PURSUIT_EVENT_RULE_ID,
        }
    )


def test_migrated_conditional_events_have_no_public_manual_scenario_trigger_methods():
    assert not hasattr(Floor6BuxumScenario, "trigger_betrayal")
    assert not hasattr(Floor6BuxumScenario, "resolve_buxum_retreat")
    assert not hasattr(Floor6StachionScenario, "trigger_morte_joe_ambush")
    assert not hasattr(Floor6StachionScenario, "advance_to_paralysis_release")
    assert not hasattr(Floor6StachionScenario, "resolve_ambusher_retreat")
    assert hasattr(Floor6StachionScenario, "wait_for_paralysis_release")
    assert not hasattr(Floor5FuscusScenario, "resolve_hidden_flag_drop")
    assert not hasattr(Floor7PursuitScenario, "resolve_labyrinth_pursuit")


def test_migrated_conditional_events_are_not_exposed_as_manual_mcp_tools():
    floor6 = (ROOT / "src/sao_mcp/server_floor6.py").read_text(encoding="utf-8")
    buxum = (ROOT / "src/sao_mcp/server_floor6_buxum.py").read_text(encoding="utf-8")
    forbidden = (
        "trigger_floor6_morte_joe_ambush",
        "advance_floor6_to_paralysis_release",
        "resolve_floor6_ambusher_retreat",
        "trigger_floor6_buxum_betrayal",
        "resolve_floor6_buxum_retreat",
        "resolve_floor5_hidden_flag_drop",
        "resolve_floor7_labyrinth_pursuit",
    )
    joined = floor6 + "\n" + buxum
    assert all(name not in joined for name in forbidden)
    assert "wait_floor6_for_paralysis_release" in floor6
