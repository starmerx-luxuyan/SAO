from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.guild_autonomy import GuildOperationStatus, GuildStrategicGoalState
from sao_mcp.runtime.gm_turn import GMTurnExecutor


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_guild_operation_lifecycle_supports_real_pause_withdrawal_failure_and_completion():
    assert {status.value for status in GuildOperationStatus} == {
        "active", "paused", "withdrawing", "completed", "withdrawn", "failed"
    }


def test_guild_strategy_model_owns_dispatch_constraints_not_actor_or_route_state():
    fields = set(GuildStrategicGoalState.__dataclass_fields__)
    assert {
        "basis_fact_id",
        "required_member_fact_id",
        "member_resource_requirements",
        "guild_resource_requirements",
        "min_members",
        "max_members",
        "desired_squads",
        "max_concurrent_squads",
        "launched_operation_ids",
    } <= fields
    assert "assigned_member_ids" not in fields
    assert "from_location_id" not in fields


def test_gm_contract_can_auto_dispatch_and_manage_real_operations():
    contract = GMTurnExecutor.supported_actions()
    assign = contract["assign_guild_goal"]
    assert set(assign["required"]) == {"guild_id", "leader_id", "goal_id", "target_location_id"}
    assert "assigned_member_ids" in assign["optional"]
    assert {"withdraw_guild_operation", "hold_guild_operation", "reorganize_guild_operation"} <= set(contract)


def test_scenarios_cannot_reach_into_guild_strategy_or_operation_authority():
    forbidden = {
        "guild_strategic_goals",
        "guild_operations",
        "_create_operation",
        "_begin_operation_leg",
        "_finish_operation_leg",
        "_evaluate_guild_strategies",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []
