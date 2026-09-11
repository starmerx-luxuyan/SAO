import ast
from pathlib import Path

from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor22_witch import (
    WITCH_RETURN_EVENT_RULE_ID,
    Floor22WitchScenario,
    install_floor22_witch_scenario,
)
from sao_mcp.scenarios.floor5_fuscus import (
    FUSCUS_FLAG_DROP_EVENT_RULE_ID,
    Floor5FuscusScenario,
    install_floor5_fuscus_scenario,
)
from sao_mcp.scenarios.floor6_buxum import (
    BUXUM_BETRAYAL_EVENT_RULE_ID,
    BUXUM_RETREAT_EVENT_RULE_ID,
    Floor6BuxumScenario,
    install_floor6_buxum_scenario,
)
from sao_mcp.scenarios.floor6_elfwar import (
    CASTLE_GALEY_ATTACK_EVENT_RULE_ID,
    KYSARAH_KEY_THEFT_EVENT_RULE_ID,
    Floor6ElfWarScenario,
    install_floor6_elfwar_scenario,
)
from sao_mcp.scenarios.floor6_irrational_cube import install_floor6_irrational_cube_scenario
from sao_mcp.scenarios.floor6_stachion import (
    AMBUSHER_RETREAT_EVENT_RULE_ID,
    MORTE_JOE_AMBUSH_EVENT_RULE_ID,
    PARALYSIS_RELEASE_EVENT_RULE_ID,
    Floor6StachionScenario,
    install_floor6_stachion_scenario,
)
from sao_mcp.scenarios.floor7_pursuit import (
    LABYRINTH_PURSUIT_EVENT_RULE_ID,
    Floor7PursuitScenario,
    install_floor7_pursuit_scenario,
)
from sao_mcp.scenarios.floor8_sluva import (
    SLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID,
    Floor8SluvaJusticeScenario,
    install_floor8_sluva_justice_scenario,
)
from sao_mcp.scenarios.floor8_standoff import (
    CAVE_MOUTH_COMBAT_EVENT_RULE_ID,
    Floor8CaveStandoffScenario,
    install_floor8_cave_standoff_scenario,
)


ROOT = Path(__file__).resolve().parents[1]


class _EmergencyNoState:
    def __init__(self, runtime):
        self.runtime = runtime


def test_conditional_scene_transitions_are_registered_world_event_rules():
    runtime = HousingAincradRuntime(seed=811)
    cube = install_floor6_irrational_cube_scenario(runtime)
    buxum = install_floor6_buxum_scenario(runtime, cube)
    stachion = install_floor6_stachion_scenario(runtime)
    fuscus = install_floor5_fuscus_scenario(runtime)
    pursuit = install_floor7_pursuit_scenario(runtime)
    elfwar = install_floor6_elfwar_scenario(runtime)
    witch = install_floor22_witch_scenario(runtime)
    emergency = _EmergencyNoState(runtime)
    standoff = install_floor8_cave_standoff_scenario(runtime, emergency)
    sluva = install_floor8_sluva_justice_scenario(runtime, emergency)

    assert install_floor6_buxum_scenario(runtime, cube) is buxum
    assert install_floor6_stachion_scenario(runtime) is stachion
    assert install_floor5_fuscus_scenario(runtime) is fuscus
    assert install_floor7_pursuit_scenario(runtime) is pursuit
    assert install_floor6_elfwar_scenario(runtime) is elfwar
    assert install_floor22_witch_scenario(runtime) is witch
    assert install_floor8_cave_standoff_scenario(runtime, emergency) is standoff
    assert install_floor8_sluva_justice_scenario(runtime, emergency) is sluva

    assert set(runtime.world_event_rules).issuperset(
        {
            BUXUM_BETRAYAL_EVENT_RULE_ID,
            BUXUM_RETREAT_EVENT_RULE_ID,
            MORTE_JOE_AMBUSH_EVENT_RULE_ID,
            PARALYSIS_RELEASE_EVENT_RULE_ID,
            AMBUSHER_RETREAT_EVENT_RULE_ID,
            FUSCUS_FLAG_DROP_EVENT_RULE_ID,
            LABYRINTH_PURSUIT_EVENT_RULE_ID,
            CASTLE_GALEY_ATTACK_EVENT_RULE_ID,
            KYSARAH_KEY_THEFT_EVENT_RULE_ID,
            CAVE_MOUTH_COMBAT_EVENT_RULE_ID,
            SLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID,
            WITCH_RETURN_EVENT_RULE_ID,
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
    assert not hasattr(Floor6ElfWarScenario, "trigger_castle_galey_attack")
    assert not hasattr(Floor6ElfWarScenario, "trigger_kysarah_key_theft")
    assert not hasattr(Floor8CaveStandoffScenario, "resolve_cave_mouth_combat")
    assert not hasattr(Floor8SluvaJusticeScenario, "complete_imprisonment_enforcement")
    assert not hasattr(Floor22WitchScenario, "finish_return")


def test_migrated_conditional_events_are_not_exposed_as_manual_mcp_tools():
    server_paths = (
        "src/sao_mcp/server_floor5.py",
        "src/sao_mcp/server_floor6.py",
        "src/sao_mcp/server_floor6_buxum.py",
        "src/sao_mcp/server_floor6_elfwar.py",
        "src/sao_mcp/server_floor7.py",
        "src/sao_mcp/server_floor8.py",
        "src/sao_mcp/server_floor22.py",
    )
    joined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in server_paths)
    forbidden = (
        "trigger_floor6_morte_joe_ambush",
        "advance_floor6_to_paralysis_release",
        "resolve_floor6_ambusher_retreat",
        "trigger_floor6_buxum_betrayal",
        "resolve_floor6_buxum_retreat",
        "resolve_floor5_hidden_flag_drop",
        "resolve_floor7_labyrinth_pursuit",
        "trigger_floor6_castle_galey_attack",
        "trigger_floor6_kysarah_key_theft",
        "resolve_progressive9_cave_mouth_combat",
        "complete_progressive9_sluva_imprisonment_enforcement",
        "finish_floor22_witch_quest_return",
        "trigger_progressive9_kysarah_interception",
    )
    assert all(name not in joined for name in forbidden)
    assert "wait_floor6_for_paralysis_release" in joined


ACTION_DRIVEN_TRANSITIONS = {
    ("floor4_nocturne.py", "resolve_kysarah_falhari_truce"),
    ("floor5_karluin.py", "trigger_shrewman_robbery"),
    ("floor6_elfwar.py", "complete_bouhroum_trial"),
    ("floor6_stachion.py", "trigger_cylon_capture"),
    ("floor6_stachion.py", "advance_transport_to_ambush_site"),
    ("floor7_aghyellr.py", "resolve_intimidating_gaze"),
    ("floor7_aghyellr.py", "trigger_nirrnir_poisoning"),
    ("floor7_pursuit.py", "advance_to_boss_room"),
    ("floor7_volupta.py", "resolve_arena_match"),
    ("floor8_emergency.py", "trigger_from_nocturne"),
}


def test_remaining_public_transition_methods_are_explicitly_action_driven():
    scenario_root = ROOT / "src/sao_mcp/scenarios"
    prefixes = ("trigger_", "advance_", "resolve_", "finish_", "complete_")
    found = set()
    for path in scenario_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(prefixes):
                found.add((path.name, node.name))
    assert found == ACTION_DRIVEN_TRANSITIONS
