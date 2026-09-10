from pathlib import Path

from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
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


def test_floor6_conditional_scene_transitions_are_registered_world_event_rules():
    runtime = HousingAincradRuntime(seed=811)
    cube = install_floor6_irrational_cube_scenario(runtime)
    install_floor6_buxum_scenario(runtime, cube)
    install_floor6_stachion_scenario(runtime)

    assert set(runtime.world_event_rules).issuperset(
        {
            BUXUM_BETRAYAL_EVENT_RULE_ID,
            BUXUM_RETREAT_EVENT_RULE_ID,
            MORTE_JOE_AMBUSH_EVENT_RULE_ID,
            PARALYSIS_RELEASE_EVENT_RULE_ID,
            AMBUSHER_RETREAT_EVENT_RULE_ID,
        }
    )


def test_migrated_conditional_events_have_no_public_manual_scenario_trigger_methods():
    assert not hasattr(Floor6BuxumScenario, "trigger_betrayal")
    assert not hasattr(Floor6BuxumScenario, "resolve_buxum_retreat")
    assert not hasattr(Floor6StachionScenario, "trigger_morte_joe_ambush")
    assert not hasattr(Floor6StachionScenario, "advance_to_paralysis_release")
    assert not hasattr(Floor6StachionScenario, "resolve_ambusher_retreat")
    assert hasattr(Floor6StachionScenario, "wait_for_paralysis_release")


def test_migrated_conditional_events_are_not_exposed_as_manual_mcp_tools():
    floor6 = (ROOT / "src/sao_mcp/server_floor6.py").read_text(encoding="utf-8")
    buxum = (ROOT / "src/sao_mcp/server_floor6_buxum.py").read_text(encoding="utf-8")
    forbidden = (
        "trigger_floor6_morte_joe_ambush",
        "advance_floor6_to_paralysis_release",
        "resolve_floor6_ambusher_retreat",
        "trigger_floor6_buxum_betrayal",
        "resolve_floor6_buxum_retreat",
    )
    joined = floor6 + "\n" + buxum
    assert all(name not in joined for name in forbidden)
    assert "wait_floor6_for_paralysis_release" in floor6
