from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing round18 audit anchor in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"round18 audit anchor not unique in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


path = ROOT / "src/sao_mcp/runtime/gm_decision.py"
replace_once(path, "MAX_DECISION_ACTIONS = 8\n", "MAX_DECISION_ACTIONS = 1\n")
replace_once(
    path,
    '            "requires_fresh_observation": True,\n            "world_progression": "world_tick_ms only; direct advance_world is not a decision action",\n',
    '            "requires_fresh_observation": True,\n            "freshness_boundary": "one ordinary player action per observation; re-observe before the next action",\n            "world_progression": "world_tick_ms only; direct advance_world is not a decision action",\n',
)
replace_once(
    path,
    '''            encounter_id = action.get("encounter_id")\n            if encounter_id is not None:\n                self._encounter_view(observation, encounter_id)\n            return f"viewpoints.{actor_id}.capabilities.teleport_options"\n''',
    '''            encounter_id = action.get("encounter_id")\n            if encounter_id is not None:\n                _, encounter = self._encounter_view(observation, encounter_id)\n                if actor_id not in encounter.get("participants", {}):\n                    raise ValueError("controlled player is not a participant in the referenced encounter")\n            return f"viewpoints.{actor_id}.capabilities.teleport_options"\n''',
)
replace_once(
    path,
    '''                if op == "use_item" and action.get("encounter_id") is not None:\n                    self._encounter_view(observation, action["encounter_id"])\n                return f"viewpoints.{actor_id}.capabilities.inventory_instance_ids"\n''',
    '''                if op == "use_item" and action.get("encounter_id") is not None:\n                    _, encounter = self._encounter_view(observation, action["encounter_id"])\n                    if actor_id not in encounter.get("participants", {}):\n                        raise ValueError("controlled player is not a participant in the referenced encounter")\n                return f"viewpoints.{actor_id}.capabilities.inventory_instance_ids"\n''',
)
replace_once(
    path,
    '''            if action["outgoing_id"] not in observer_ids or action["incoming_id"] not in observer_ids:\n                raise ValueError("Switch may only control player actors explicitly supplied as viewpoints")\n            if action["target_id"] not in encounter.get("participants", {}):\n                raise ValueError("Switch target is not an observable encounter participant")\n''',
    '''            if action["outgoing_id"] not in observer_ids or action["incoming_id"] not in observer_ids:\n                raise ValueError("Switch may only control player actors explicitly supplied as viewpoints")\n            participants = encounter.get("participants", {})\n            if action["outgoing_id"] not in participants or action["incoming_id"] not in participants:\n                raise ValueError("Switch players are not both participants in the referenced encounter")\n            if action["target_id"] not in participants:\n                raise ValueError("Switch target is not an observable encounter participant")\n''',
)

path = ROOT / "tests/test_gm_decision_runtime.py"
replace_once(
    path,
    '''def test_action_batch_is_grounded_in_initial_packet_and_cannot_assume_second_leg_visibility():\n    runtime, executor, decision = make_runtime(1806)\n    player = runtime.create_character("Walker")\n    observation = executor.observe([player.actor_id])\n    with pytest.raises(ValueError, match="observable travel options"):\n        decision.decide(\n            observation,\n            [\n                {"op": "travel", "actor_id": player.actor_id, "destination_id": WEST},\n                {"op": "travel", "actor_id": player.actor_id, "destination_id": HORUNKA},\n            ],\n        )\n\n\n''',
    '''def test_one_observation_can_authorize_at_most_one_player_action():\n    runtime, executor, decision = make_runtime(1806)\n    player = runtime.create_character("Walker")\n    observation = executor.observe([player.actor_id])\n    with pytest.raises(ValueError, match="at most 1 actions"):\n        decision.decide(\n            observation,\n            [\n                {"op": "interact_npc", "actor_id": player.actor_id, "npc_id": "npc_tutorial_instructor"},\n                {"op": "travel", "actor_id": player.actor_id, "destination_id": WEST},\n            ],\n        )\n\n\n''',
)
with path.open("a", encoding="utf-8") as handle:
    handle.write('''\n\ndef test_actor_cannot_borrow_another_viewpoints_encounter_reference_for_item_use():\n    runtime, executor, decision = make_runtime(1809)\n    outsider = runtime.create_character("Outsider")\n    fighter = runtime.create_character("Fighter")\n    fighter.location_id = WEST\n    monster = runtime.create_training_monster(level=1)\n    encounter = runtime.start_encounter([fighter.actor_id, monster.actor_id], zone_id=WEST)\n    potion_id = next(\n        item.instance_id\n        for item in outsider.inventory.values()\n        if item.template_id == "healing_potion_basic"\n    )\n    observation = executor.observe([outsider.actor_id, fighter.actor_id])\n    with pytest.raises(ValueError, match="not a participant"):\n        decision.decide(\n            observation,\n            [{\n                "op": "use_item",\n                "actor_id": outsider.actor_id,\n                "instance_id": potion_id,\n                "encounter_id": encounter.encounter_id,\n            }],\n        )\n''')

path = ROOT / "tests/test_gm_decision_authority.py"
with path.open("a", encoding="utf-8") as handle:
    handle.write('''\n\ndef test_decision_contract_forces_a_fresh_observation_between_player_actions():\n    runtime = GMDecisionRuntime(GMTurnExecutor.supported_actions())\n    contract = runtime.contract()\n    assert contract["max_actions"] == 1\n    assert "one ordinary player action per observation" in contract["freshness_boundary"]\n''')

path = ROOT / "skills/sao-gm/SKILL.md"
replace_once(
    path,
    "Translate the user's prose into the smallest proposed ordinary action batch, then use `execute_gm_decision`.",
    "Translate the user's prose into one ordinary player action, then use `execute_gm_decision`.",
)
replace_once(
    path,
    "A decision batch is bound to the observation digest that justified it. Keep batches small. Once an action changes location, identity, inventory, encounter membership or other visibility, re-observe before deciding the next action.",
    "Each decision is bound to the observation digest that justified it and may authorize at most one ordinary player action. Re-observe before deciding the next action, because location, identity, inventory, encounter membership and other visibility may have changed.",
)
