from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# The authority test must actually install the always-available Floor 22 service before asserting
# that its rule is present. This is not a production fallback: rule installation remains explicit.
replace_once(
    "tests/test_world_event_authority.py",
    '''from sao_mcp.scenarios.floor22_witch import WITCH_RETURN_EVENT_RULE_ID, Floor22WitchScenario\n''',
    '''from sao_mcp.scenarios.floor22_witch import (\n    WITCH_RETURN_EVENT_RULE_ID,\n    Floor22WitchScenario,\n    install_floor22_witch_scenario,\n)\n''',
)
replace_once(
    "tests/test_world_event_authority.py",
    '''    elfwar = install_floor6_elfwar_scenario(runtime)\n    emergency = _EmergencyNoState(runtime)\n''',
    '''    elfwar = install_floor6_elfwar_scenario(runtime)\n    witch = install_floor22_witch_scenario(runtime)\n    emergency = _EmergencyNoState(runtime)\n''',
)
replace_once(
    "tests/test_world_event_authority.py",
    '''    assert install_floor6_elfwar_scenario(runtime) is elfwar\n    assert install_floor8_cave_standoff_scenario(runtime, emergency) is standoff\n''',
    '''    assert install_floor6_elfwar_scenario(runtime) is elfwar\n    assert install_floor22_witch_scenario(runtime) is witch\n    assert install_floor8_cave_standoff_scenario(runtime, emergency) is standoff\n''',
)

# Correct the exact action-driven transition inventory after the AST gate exposed four omissions/
# stale names. Every listed method requires an explicit player choice, target, simulation action or
# time-passage command; pure state conditions are intentionally absent.
start = read_start = Path("tests/test_world_event_authority.py").read_text(encoding="utf-8")
old = '''ACTION_DRIVEN_TRANSITIONS = {\n    ("floor4_nocturne.py", "trigger_kysarah_interception"),\n    ("floor5_karluin.py", "trigger_fallen_elf_robbery"),\n    ("floor6_stachion.py", "trigger_cylon_capture"),\n    ("floor6_stachion.py", "advance_transport_to_ambush_site"),\n    ("floor7_aghyellr.py", "resolve_intimidating_gaze"),\n    ("floor7_elfwar.py", "complete_bouhroum_trial"),\n    ("floor7_pursuit.py", "trigger_nirrnir_poisoning"),\n    ("floor7_pursuit.py", "advance_to_boss_room"),\n    ("floor7_volupta.py", "resolve_arena_match"),\n    ("floor8_emergency.py", "trigger_from_nocturne"),\n}\n'''
new = '''ACTION_DRIVEN_TRANSITIONS = {\n    ("floor4_nocturne.py", "trigger_kysarah_interception"),\n    ("floor4_nocturne.py", "resolve_kysarah_falhari_truce"),\n    ("floor5_karluin.py", "trigger_shrewman_robbery"),\n    ("floor6_elfwar.py", "complete_bouhroum_trial"),\n    ("floor6_stachion.py", "trigger_cylon_capture"),\n    ("floor6_stachion.py", "advance_transport_to_ambush_site"),\n    ("floor7_aghyellr.py", "resolve_intimidating_gaze"),\n    ("floor7_aghyellr.py", "trigger_nirrnir_poisoning"),\n    ("floor7_pursuit.py", "advance_to_boss_room"),\n    ("floor7_volupta.py", "resolve_arena_match"),\n    ("floor8_emergency.py", "trigger_from_nocturne"),\n}\n'''
if start.count(old) != 1:
    raise RuntimeError(f"expected exact action-driven transition set once, found {start.count(old)}")
Path("tests/test_world_event_authority.py").write_text(start.replace(old, new, 1), encoding="utf-8")

# import_runtime deliberately installs the built-in Floor 22 service before loading state, so the
# generic persistence test must expect that built-in executable rule rather than an empty registry.
replace_once(
    "tests/test_world_event_runtime.py",
    '''    assert restored.world_event_state()["registered_rule_ids"] == []\n''',
    '''    assert restored.world_event_state()["registered_rule_ids"] == ["floor22.witch_return"]\n''',
)
