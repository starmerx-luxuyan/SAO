from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def test_world_event_rules_resolve_once_and_chain_in_one_evaluation():
    runtime = HousingAincradRuntime(seed=801)
    flags = {"first": False, "second": False}

    def discover_first():
        return ["test:first"] if flags["first"] else []

    def resolve_first(occurrence_id: str):
        assert occurrence_id == "test:first"
        flags["second"] = True
        return {"kind": "first"}

    def discover_second():
        return ["test:second"] if flags["second"] else []

    runtime.register_world_event_rule("test.first", discover_first, resolve_first)
    runtime.register_world_event_rule(
        "test.second",
        discover_second,
        lambda occurrence_id: {"kind": "second", "occurrence_id": occurrence_id},
    )

    runtime.advance_world(10)
    assert runtime.world_event_history() == []

    flags["first"] = True
    resolved = runtime.evaluate_world_events()
    assert [row.occurrence_id for row in resolved] == ["test:first", "test:second"]
    assert [row.rule_id for row in resolved] == ["test.first", "test.second"]
    assert len(runtime.world_event_history()) == 2

    runtime.advance_world(100)
    assert len(runtime.world_event_history()) == 2


def test_world_event_occurrences_persist_but_executable_rules_do_not():
    runtime = HousingAincradRuntime(seed=802)
    runtime.register_world_event_rule(
        "test.persist",
        lambda: ["test:persist:1"],
        lambda occurrence_id: {"occurrence_id": occurrence_id, "value": 7},
    )
    runtime.evaluate_world_events()

    restored = import_runtime(export_runtime(runtime))
    persisted = restored.world_event_state("test:persist:1")
    assert persisted["rule_id"] == "test.persist"
    assert persisted["status"] == "resolved"
    assert persisted["payload"]["value"] == 7
    assert restored.world_event_state()["registered_rule_ids"] == []

    fired = []
    restored.register_world_event_rule(
        "test.persist",
        lambda: ["test:persist:1"],
        lambda occurrence_id: fired.append(occurrence_id) or {},
    )
    restored.evaluate_world_events()
    assert fired == []
    assert len(restored.world_event_history("test.persist")) == 1
