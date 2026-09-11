from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.population import PopulationCohortState, PopulationMovementState


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_population_goal_and_route_state_do_not_duplicate_cohort_headcount_or_segment():
    movement_fields = set(PopulationMovementState.__dataclass_fields__)
    cohort_fields = set(PopulationCohortState.__dataclass_fields__)
    assert "headcount" not in movement_fields
    assert "segment" not in movement_fields
    assert "target_location_id" not in cohort_fields
    assert "due_at_ms" not in cohort_fields


def test_scenarios_cannot_mutate_population_ledgers_directly():
    forbidden = {
        "population",
        "population_movements",
        "_progress_population_movement",
        "_begin_population_leg",
        "_finish_population_leg",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []


def test_population_runtime_exposes_neutral_location_and_floor_interfaces_for_later_systems():
    source = (ROOT / "src/sao_mcp/runtime/population_runtime.py").read_text(encoding="utf-8")
    assert "def population_location_state" in source
    assert "def population_floor_state" in source
    assert "abstract_in_transit_players" in source
    assert "registered_total" in source
