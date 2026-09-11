from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''        if previous_id != selected_id or core.current_plan_step is None:\n            self._replace_goal_plan(npc_id, selected)\n        self._plan_goal_step(npc_id, decision_at_ms)\n''',
    '''        needs_plan = previous_id != selected_id or (\n            core.current_plan_step is None\n            and selected.target_location_id is not None\n            and self._stationary_npc_location_id(npc_id) != selected.target_location_id\n        )\n        if needs_plan:\n            self._replace_goal_plan(npc_id, selected)\n        self._plan_goal_step(npc_id, decision_at_ms)\n''',
)

replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''    "set_npc_goal": (\n        frozenset({"npc_id", "goal_id", "target_location_id"}),\n        frozenset(),\n    ),\n''',
    '''    "set_npc_goal": (\n        frozenset({"npc_id", "goal_id", "target_location_id"}),\n        frozenset({\n            "priority",\n            "business_id",\n            "required_fact_id",\n            "required_fact_value",\n            "relationship_actor_id",\n            "min_relationship",\n            "resource_requirements",\n        }),\n    ),\n''',
)

replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''        if op == "set_npc_goal":\n            return runtime.set_npc_goal(\n                action["npc_id"],\n                action["goal_id"],\n                action["target_location_id"],\n            )\n''',
    '''        if op == "set_npc_goal":\n            return runtime.set_npc_goal(\n                action["npc_id"],\n                action["goal_id"],\n                action["target_location_id"],\n                priority=int(action.get("priority", 100)),\n                business_id=action.get("business_id"),\n                required_fact_id=action.get("required_fact_id"),\n                required_fact_value=action.get("required_fact_value", True),\n                relationship_actor_id=action.get("relationship_actor_id"),\n                min_relationship=(\n                    int(action["min_relationship"])\n                    if action.get("min_relationship") is not None\n                    else None\n                ),\n                resource_requirements=action.get("resource_requirements"),\n            )\n''',
)

path = Path("tests/test_npc_actor_core_authority.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_gm_set_npc_goal_contract_accepts_actor_core_decision_constraints():\n    from sao_mcp.runtime.gm_turn import GMTurnExecutor\n\n    optional = set(GMTurnExecutor.supported_actions()["set_npc_goal"]["optional"])\n    assert optional == {\n        "priority",\n        "business_id",\n        "required_fact_id",\n        "required_fact_value",\n        "relationship_actor_id",\n        "min_relationship",\n        "resource_requirements",\n    }\n'''
path.write_text(text, encoding="utf-8")

path = Path("tests/test_npc_autonomy.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_reached_goal_does_not_rebuild_identical_plan_every_world_tick():\n    runtime = HousingAincradRuntime(seed=113)\n    runtime.world.floors[50].unlocked = True\n    runtime.set_npc_goal(AGIL, "visit_algade_once", ALGADE)\n    runtime.advance_world(SHOP_TO_ALGADE_MS)\n    core = runtime.npc_actor_cores[AGIL]\n    assert runtime.npc_actor_core_state(AGIL)["goal_reached"] is True\n    revision = core.revision\n    runtime.advance_world(60_000)\n    assert core.revision == revision\n'''
path.write_text(text, encoding="utf-8")
