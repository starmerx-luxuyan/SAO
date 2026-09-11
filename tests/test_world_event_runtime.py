import pytest

from sao_mcp.rules.world_events import WorldEventResult, WorldEventStatus
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
    assert restored.world_event_state()["registered_rule_ids"] == ["floor22.witch_return"]

    fired = []
    restored.register_world_event_rule(
        "test.persist",
        lambda: ["test:persist:1"],
        lambda occurrence_id: fired.append(occurrence_id) or {},
    )
    restored.evaluate_world_events()
    assert fired == []
    assert len(restored.world_event_history("test.persist")) == 1


def test_planned_event_can_start_early_then_be_interrupted_and_persist():
    runtime = HousingAincradRuntime(seed=803)
    def discover_interruptible():
        occurrence = runtime.world_events.occurrences.get("test:interruptible:1")
        return (
            ["test:interruptible:1"]
            if occurrence is not None and occurrence.status is WorldEventStatus.PENDING
            else []
        )

    runtime.register_world_event_rule(
        "test.interruptible",
        discover_interruptible,
        lambda occurrence_id: WorldEventResult(
            WorldEventStatus.ACTIVE,
            {"occurrence_id": occurrence_id, "phase": "started"},
        ),
    )
    runtime.plan_world_event(
        "test:interruptible:1",
        "test.interruptible",
        expected_at_ms=1_000,
        payload={"seed": "planned"},
    )

    transitioned = runtime.evaluate_world_events()
    assert [row.status for row in transitioned] == [WorldEventStatus.ACTIVE]
    active = runtime.world_event_state("test:interruptible:1")
    assert active["status"] == "active"
    assert active["triggered_at_ms"] == 0
    assert active["expected_at_ms"] == 1_000
    assert active["started_early"] is True
    assert active["payload"] == {
        "seed": "planned",
        "occurrence_id": "test:interruptible:1",
        "phase": "started",
    }

    restored = import_runtime(export_runtime(runtime))
    persisted = restored.world_event_state("test:interruptible:1")
    assert persisted["status"] == "active"
    assert persisted["started_early"] is True
    restored.interrupt_world_event(
        "test:interruptible:1",
        payload={"reason": "player_changed_the_situation"},
    )
    interrupted = restored.world_event_state("test:interruptible:1")
    assert interrupted["status"] == "interrupted"
    assert interrupted["resolved_at_ms"] == restored.world.now_ms
    assert interrupted["payload"]["reason"] == "player_changed_the_situation"
    assert [row["status"] for row in restored.world_event_history("test.interruptible")] == [
        "pending",
        "active",
        "interrupted",
    ]

    with pytest.raises(ValueError, match="illegal world-event transition"):
        restored.resolve_world_event("test:interruptible:1")


def test_planned_event_can_be_skipped_before_it_starts():
    runtime = HousingAincradRuntime(seed=804)
    runtime.register_world_event_rule("test.skip", lambda: [], lambda occurrence_id: {})
    runtime.plan_world_event("test:skip:1", "test.skip")
    runtime.skip_world_event("test:skip:1", payload={"reason": "precondition_removed"})
    skipped = runtime.world_event_state("test:skip:1")
    assert skipped["status"] == "skipped"
    assert skipped["triggered_at_ms"] is None
    assert skipped["resolved_at_ms"] == runtime.world.now_ms
