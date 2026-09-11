from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.corpus.canonical_timeline import DAY_MS
from sao_mcp.rules.world import NEXT_FLOOR_AUTO_GATE_DELAY_MS
from sao_mcp.rules.world_events import WorldEventStatus
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


ROOT = Path(__file__).resolve().parents[1]
PROGRESSIVE = "progressive_novel_early_aincrad_v1"
ANIME = "anime_core_aincrad_v1"


def _milestone(runtime, seed_id: str) -> dict:
    rows = {
        row["seed_id"]: row
        for row in runtime.canonical_timeline_state()["milestones"]
    }
    return rows[seed_id]


def test_default_progressive_profile_uses_date_windows_without_forcing_world_state():
    runtime = HousingAincradRuntime(seed=901)
    state = runtime.canonical_timeline_state()

    assert state["profile_id"] == PROGRESSIVE
    assert state["continuity"] == "Sword Art Online Progressive light-novel continuity"
    assert [row["calendar_date"] for row in state["milestones"]] == [
        "2022-12-04",
        "2022-12-14",
        "2022-12-21",
        "2022-12-27",
        "2022-12-31",
    ]
    assert all(
        row["expected_window_end_ms"] - row["expected_window_start_ms"] + 1 == DAY_MS
        for row in state["milestones"]
    )

    floor1 = _milestone(runtime, "floor1.boss_defeated")
    runtime.advance_world(floor1["expected_window_end_ms"] + 1)
    overdue = _milestone(runtime, "floor1.boss_defeated")

    assert overdue["timing_status"] == "overdue"
    assert runtime.world.floors[1].floor_boss_defeated is False
    assert runtime.world.floors[1].scheduled_gate_activation_at_ms is None
    assert runtime.world.floors[2].unlocked is False
    assert runtime.world.floors[2].main_town_gate_active is False


def test_actual_boss_clear_time_remains_authoritative_and_can_diverge_early():
    runtime = HousingAincradRuntime(seed=902)
    floor1 = _milestone(runtime, "floor1.boss_defeated")
    early_at = floor1["expected_window_start_ms"] - 60 * 60 * 1000
    runtime.advance_world(early_at)

    runtime.floor_boss_defeated(1)
    observed = _milestone(runtime, "floor1.boss_defeated")

    assert observed["timing_status"] == "early"
    assert observed["actual_at_ms"] == early_at
    assert runtime.world.floors[1].floor_boss_defeated_at_ms == early_at
    assert runtime.world.floors[1].scheduled_gate_activation_at_ms == early_at + NEXT_FLOOR_AUTO_GATE_DELAY_MS

    runtime.advance_world(NEXT_FLOOR_AUTO_GATE_DELAY_MS)
    assert runtime.world.floors[2].unlocked is True
    assert runtime.world.floors[2].main_town_gate_active is True
    assert _milestone(runtime, "floor1.boss_defeated")["timing_status"] == "early"


def test_switching_continuity_reinterprets_expectation_without_rewriting_world():
    runtime = HousingAincradRuntime(seed=903)
    progressive_floor1 = _milestone(runtime, "floor1.boss_defeated")
    runtime.advance_world(progressive_floor1["expected_window_start_ms"])
    runtime.floor_boss_defeated(1)

    assert _milestone(runtime, "floor1.boss_defeated")["timing_status"] == "on_window"
    snapshot = (
        runtime.world.now_ms,
        runtime.world.floors[1].floor_boss_defeated,
        runtime.world.floors[1].floor_boss_defeated_at_ms,
        runtime.world.floors[1].scheduled_gate_activation_at_ms,
        runtime.world.floors[2].unlocked,
    )

    anime = runtime.select_canonical_timeline_profile(ANIME)
    assert anime["profile_id"] == ANIME
    assert _milestone(runtime, "floor1.boss_defeated")["timing_status"] == "late"
    assert snapshot == (
        runtime.world.now_ms,
        runtime.world.floors[1].floor_boss_defeated,
        runtime.world.floors[1].floor_boss_defeated_at_ms,
        runtime.world.floors[1].scheduled_gate_activation_at_ms,
        runtime.world.floors[2].unlocked,
    )

    disabled = runtime.select_canonical_timeline_profile(None)
    assert disabled["profile_id"] is None
    assert disabled["milestones"] == []
    assert snapshot == (
        runtime.world.now_ms,
        runtime.world.floors[1].floor_boss_defeated,
        runtime.world.floors[1].floor_boss_defeated_at_ms,
        runtime.world.floors[1].scheduled_gate_activation_at_ms,
        runtime.world.floors[2].unlocked,
    )


def test_canonical_profile_and_observations_round_trip_through_save():
    runtime = HousingAincradRuntime(seed=904)
    runtime.select_canonical_timeline_profile(ANIME)
    floor1 = _milestone(runtime, "floor1.boss_defeated")
    runtime.advance_world(floor1["expected_window_end_ms"] + 5 * 60 * 60 * 1000)
    runtime.floor_boss_defeated(1)

    before = runtime.canonical_timeline_state()
    restored = import_runtime(export_runtime(runtime))
    after = restored.canonical_timeline_state()

    assert after == before
    assert after["profile_id"] == ANIME
    assert _milestone(restored, "floor1.boss_defeated")["timing_status"] == "late"
    assert restored.world.floors[1].floor_boss_defeated_at_ms == runtime.world.floors[1].floor_boss_defeated_at_ms


def test_canonical_seed_supplies_default_timing_but_not_trigger_truth():
    runtime = HousingAincradRuntime(seed=905)
    occurrence_id = "test:canonical:floor1"
    ready = {"value": False}

    def discover():
        occurrence = runtime.world_events.occurrences.get(occurrence_id)
        return [occurrence_id] if ready["value"] and occurrence is not None and occurrence.status is WorldEventStatus.PENDING else []

    runtime.register_world_event_rule(
        "test.canonical",
        discover,
        lambda current_id: {"resolved_occurrence_id": current_id},
    )
    occurrence = runtime.plan_canonical_world_event(
        occurrence_id,
        "test.canonical",
        "floor1.boss_defeated",
        payload={"kind": "test_only"},
    )
    floor1 = _milestone(runtime, "floor1.boss_defeated")

    assert occurrence.status is WorldEventStatus.PENDING
    assert occurrence.expected_at_ms == floor1["expected_window_start_ms"]
    assert runtime.evaluate_world_events() == []
    runtime.advance_world(1)
    assert runtime.world_event_state(occurrence_id)["status"] == "pending"

    ready["value"] = True
    runtime.evaluate_world_events()
    resolved = runtime.world_event_state(occurrence_id)
    assert resolved["status"] == "resolved"
    assert resolved["started_early"] is True
    assert resolved["payload"]["canonical_profile_id"] == PROGRESSIVE
    assert resolved["payload"]["canonical_seed_id"] == "floor1.boss_defeated"
    assert resolved["payload"]["canonical_expected_window_end_ms"] == floor1["expected_window_end_ms"]
    assert runtime.world.floors[1].floor_boss_defeated is False


def test_scenarios_cannot_read_canonical_profile_windows_directly():
    scenario_root = ROOT / "src/sao_mcp/scenarios"
    forbidden_modules = {
        "sao_mcp.corpus.canonical_timeline",
        "sao_mcp.rules.canonical_timeline",
    }
    forbidden_attributes = {
        "canonical_timeline",
        "expected_window_start_ms",
        "expected_window_end_ms",
        "window_start_offset_ms",
        "window_end_offset_ms",
    }

    violations = []
    for path in scenario_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden_modules:
                violations.append(f"{path.name}:{node.lineno}: direct canonical profile import")
            if isinstance(node, ast.Attribute) and node.attr in forbidden_attributes:
                violations.append(f"{path.name}:{node.lineno}: direct canonical profile state read")
    assert violations == []
