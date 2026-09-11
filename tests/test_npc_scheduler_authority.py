from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.npc_scheduler import NPCPlanActionKind
from sao_mcp.runtime.gm_turn import GMTurnExecutor


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_scheduler_action_kinds_cover_world_time_npc_work_without_replacing_rule_engines():
    assert {kind.value for kind in NPCPlanActionKind} == {
        "travel", "wait", "investigate", "contact", "trade_vendor", "engage", "attack"
    }


def test_gm_goal_contract_exposes_scheduler_actions_and_explicit_interruption():
    contract = GMTurnExecutor.supported_actions()
    assert "scheduled_actions" in contract["set_npc_goal"]["optional"]
    assert set(contract["interrupt_npc_activity"]["required"]) == {"npc_id", "reason"}


def test_scenarios_cannot_bypass_scheduler_operation_authority():
    forbidden = {
        "npc_scheduler_goals",
        "_begin_scheduler_step",
        "_finish_travel_leg",
        "_interrupt_current_activity",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []
