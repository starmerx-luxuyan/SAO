from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# -------------------- Floor 22 Witch automatic return --------------------
replace_once(
    "src/sao_mcp/scenarios/floor22_witch.py",
    '''LOG_HOUSE_FLIGHT_MS = 15 * 60_000\n''',
    '''LOG_HOUSE_FLIGHT_MS = 15 * 60_000\nWITCH_RETURN_EVENT_RULE_ID = "floor22.witch_return"\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor22_witch.py",
    '''        runtime.quests.definitions.setdefault(QUEST_ID, floor22_quest_definition())\n        install_floor22_npc(runtime)\n''',
    '''        runtime.quests.definitions.setdefault(QUEST_ID, floor22_quest_definition())\n        install_floor22_npc(runtime)\n        runtime.register_world_event_rule(\n            WITCH_RETURN_EVENT_RULE_ID,\n            self._discover_witch_return_events,\n            self._resolve_witch_return_event,\n        )\n        runtime.evaluate_world_events()\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor22_witch.py",
    '''    def finish_return(self, instance_id: str) -> dict:\n        runtime = self.runtime\n        state = self.instance(instance_id)\n        self._sync_witch_defeat(state)\n        if state["stage"] != "witch_defeated":\n            raise ValueError("the Witch must be defeated before the Log House can return")\n''',
    '''    @staticmethod\n    def _witch_return_instance_id(occurrence_id: str) -> str:\n        prefix = f"{WITCH_RETURN_EVENT_RULE_ID}:"\n        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):\n            raise RuntimeError(f"invalid Witch return occurrence id: {occurrence_id}")\n        return occurrence_id[len(prefix):]\n\n    def _discover_witch_return_events(self) -> list[str]:\n        states = self.runtime.world.global_flags.get("floor22_witch_instances", {})\n        ready: list[str] = []\n        for instance_id, state in states.items():\n            if state["stage"] not in {"witch_battle", "witch_defeated"}:\n                continue\n            witch_id = state.get("witch_id")\n            witch = self.runtime.actors.get(witch_id) if witch_id else None\n            if (\n                witch is None\n                or witch.alive\n                or witch.metadata.get("defeat_resolved") is not True\n            ):\n                continue\n            returning_ids = [\n                actor_id for actor_id in state["player_ids"]\n                if actor_id in self.runtime.actors and self.runtime.actors[actor_id].alive\n            ]\n            if not returning_ids:\n                continue\n            if any(self.runtime.actors[actor_id].location_id != WITCH_CASTLE for actor_id in returning_ids):\n                raise RuntimeError("Witch return candidates are no longer colocated at the Witch Castle")\n            ready.append(f"{WITCH_RETURN_EVENT_RULE_ID}:{instance_id}")\n        return ready\n\n    def _resolve_witch_return_event(self, occurrence_id: str) -> dict:\n        instance_id = self._witch_return_instance_id(occurrence_id)\n        state = self.instance(instance_id)\n        self._sync_witch_defeat(state)\n        result = self._finish_return(instance_id)\n        return {\n            "instance_id": instance_id,\n            "completed_player_ids": list(result["completedPlayerIds"]),\n            "stage": result["stage"],\n        }\n\n    def _finish_return(self, instance_id: str) -> dict:\n        runtime = self.runtime\n        state = self.instance(instance_id)\n        if state["stage"] != "witch_defeated":\n            raise ValueError("the Witch must be defeated before the Log House can return")\n''',
)
replace_once(
    "src/sao_mcp/server_floor22.py",
    '''    @mcp.tool()\n    def finish_floor22_witch_quest_return(instance_id: str) -> str:\n        """Return the Log House to its Floor 22 site after the Witch is defeated and unlock property eligibility."""\n        return _json(scenario.finish_return(instance_id))\n\n''',
    "",
)
replace_once(
    "tests/test_floor22_witch_quest.py",
    '''    runtime._resolve_defeat(witch_encounter, witch, player.actor_id)\n\n    result = scenario.finish_return(instance["instance_id"])\n    assert player.actor_id in result["completedPlayerIds"]\n''',
    '''    runtime._resolve_defeat(witch_encounter, witch, player.actor_id)\n\n    state = scenario.instance(instance["instance_id"])\n    occurrence = runtime.world_event_state(\n        f"floor22.witch_return:{instance['instance_id']}"\n    )\n    assert occurrence["status"] == "resolved"\n    assert player.actor_id in occurrence["payload"]["completed_player_ids"]\n    assert state["stage"] == "completed"\n''',
)

# Floor22 is installed by import_runtime before save data is restored. This regression verifies the
# executable rule remains installed and a resolved occurrence is not replayed after load.
replace_once(
    "tests/test_floor22_witch_quest.py",
    '''from sao_mcp.runtime.housing_runtime import HousingAincradRuntime\n''',
    '''from sao_mcp.runtime.housing_runtime import HousingAincradRuntime\nfrom sao_mcp.runtime.persistence import export_runtime, import_runtime\n''',
)
replace_once(
    "tests/test_floor22_witch_quest.py",
    '''    assert house.parent_location_id == "floor_22_forest_house_site"\n''',
    '''    assert house.parent_location_id == "floor_22_forest_house_site"\n\n    restored = import_runtime(export_runtime(runtime))\n    assert "floor22.witch_return" in restored.world_event_rules\n    restored.evaluate_world_events()\n    assert len(restored.world_event_history("floor22.witch_return")) == 1\n    assert restored.scenarios["floor22_witch"].instance(instance["instance_id"])["stage"] == "completed"\n''',
)

# -------------------- Floor8 End Phase timing contract --------------------
replace_once(
    "tests/test_floor8_standoff.py",
    '''from sao_mcp.runtime.persistence import export_runtime, import_runtime\n''',
    '''from sao_mcp.runtime.persistence import export_runtime, import_runtime\nfrom sao_mcp.runtime.social_runtime import REVIVAL_WINDOW_MS\n''',
)
append = '''\n\ndef test_cave_mouth_player_defeat_waits_for_revival_end_phase_before_world_event_resolution():\n    runtime, nocturne, emergency, standoff, instance_id, responder = _make_live_standoff(seed=229)\n    state = emergency._state(instance_id)\n    forest_ids = list(state["incident"]["forest_elf_actor_ids"])\n    combat = standoff.start_cave_mouth_combat(instance_id, [responder.actor_id])\n    encounter_id = combat["cave_combat_encounter_id"]\n    encounter = runtime.encounters[encounter_id]\n    occurrence_id = f"floor8.cave_mouth_combat_resolution:{instance_id}"\n\n    responder.hp = 0\n    responder.alive = False\n    runtime._resolve_defeat(encounter, responder, forest_ids[0])\n    assert responder.metadata["death_state"] == "end_phase"\n    assert occurrence_id not in runtime.world_events.occurrences\n    assert standoff.status(instance_id)["stage"] == "cave_mouth_combat"\n\n    runtime.advance_encounter(encounter_id, REVIVAL_WINDOW_MS - 1)\n    assert responder.metadata["death_state"] == "end_phase"\n    assert occurrence_id not in runtime.world_events.occurrences\n\n    runtime.advance_encounter(encounter_id, 1)\n    assert responder.metadata["death_state"] == "permanent"\n    assert runtime.world_event_state(occurrence_id)["status"] == "resolved"\n    resolved = standoff.status(instance_id)\n    assert resolved["stage"] == "cave_mouth_combat_player_side_defeated"\n    assert resolved["cave_combat_outcome"] == "selected_player_combatants_defeated"\n    assert encounter.active is False\n'''
path = Path("tests/test_floor8_standoff.py")
text = path.read_text(encoding="utf-8")
if "test_cave_mouth_player_defeat_waits_for_revival_end_phase" in text:
    raise RuntimeError("Floor8 End Phase regression already exists")
path.write_text(text.rstrip() + append + "\n", encoding="utf-8")

# -------------------- Permanent transition classification gate --------------------
path = Path("tests/test_world_event_authority.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    '''from pathlib import Path\n''',
    '''import ast\nfrom pathlib import Path\n''',
    1,
)
text = text.replace(
    '''from sao_mcp.runtime.housing_runtime import HousingAincradRuntime\n''',
    '''from sao_mcp.runtime.housing_runtime import HousingAincradRuntime\nfrom sao_mcp.scenarios.floor22_witch import WITCH_RETURN_EVENT_RULE_ID, Floor22WitchScenario\n''',
    1,
)
text = text.replace(
    '''            SLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID,\n        }\n''',
    '''            SLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID,\n            WITCH_RETURN_EVENT_RULE_ID,\n        }\n''',
    1,
)
text = text.replace(
    '''    assert not hasattr(Floor8SluvaJusticeScenario, "complete_imprisonment_enforcement")\n''',
    '''    assert not hasattr(Floor8SluvaJusticeScenario, "complete_imprisonment_enforcement")\n    assert not hasattr(Floor22WitchScenario, "finish_return")\n''',
    1,
)
text = text.replace(
    '''        "src/sao_mcp/server_floor8.py",\n    )\n''',
    '''        "src/sao_mcp/server_floor8.py",\n        "src/sao_mcp/server_floor22.py",\n    )\n''',
    1,
)
text = text.replace(
    '''        "complete_progressive9_sluva_imprisonment_enforcement",\n    )\n''',
    '''        "complete_progressive9_sluva_imprisonment_enforcement",\n        "finish_floor22_witch_quest_return",\n    )\n''',
    1,
)
text += '''\n\nACTION_DRIVEN_TRANSITIONS = {\n    ("floor4_nocturne.py", "trigger_kysarah_interception"),\n    ("floor5_karluin.py", "trigger_fallen_elf_robbery"),\n    ("floor6_stachion.py", "trigger_cylon_capture"),\n    ("floor6_stachion.py", "advance_transport_to_ambush_site"),\n    ("floor7_aghyellr.py", "resolve_intimidating_gaze"),\n    ("floor7_elfwar.py", "complete_bouhroum_trial"),\n    ("floor7_pursuit.py", "trigger_nirrnir_poisoning"),\n    ("floor7_pursuit.py", "advance_to_boss_room"),\n    ("floor7_volupta.py", "resolve_arena_match"),\n    ("floor8_emergency.py", "trigger_from_nocturne"),\n}\n\n\ndef test_remaining_public_transition_methods_are_explicitly_action_driven():\n    scenario_root = ROOT / "src/sao_mcp/scenarios"\n    prefixes = ("trigger_", "advance_", "resolve_", "finish_", "complete_")\n    found = set()\n    for path in scenario_root.glob("*.py"):\n        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))\n        for node in ast.walk(tree):\n            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(prefixes):\n                found.add((path.name, node.name))\n    assert found == ACTION_DRIVEN_TRANSITIONS\n'''
path.write_text(text, encoding="utf-8")
