import ast
from pathlib import Path

from sao_mcp.runtime.gm_decision import GMDecisionRuntime, PLAYER_DECISION_OPS
from sao_mcp.runtime.gm_turn import GMTurnExecutor


ROOT = Path(__file__).resolve().parents[1]


def test_decision_runtime_is_pure_and_has_no_raw_runtime_access():
    path = ROOT / "src/sao_mcp/runtime/gm_decision.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    forbidden_attrs = {
        "actors", "world", "world_map", "npcs", "relationships", "encounters",
        "world_events", "npc_actor_cores", "guild_operations", "knowledge_events",
    }
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in forbidden_attrs:
            violations.append((node.lineno, node.attr))
    assert violations == []
    assert "self.runtime" not in source
    assert "GMObservationGate" not in source
    assert "GMTurnExecutor" not in source


def test_decision_surface_excludes_hidden_world_authoring_operations():
    forbidden = {
        "set_npc_goal", "clear_npc_goal", "interrupt_npc_activity", "schedule_npc_travel",
        "assign_guild_goal", "clear_guild_goal", "withdraw_guild_operation", "hold_guild_operation",
        "reorganize_guild_operation", "observe_fact", "infer_fact", "advance_world",
    }
    assert PLAYER_DECISION_OPS.isdisjoint(forbidden)
    runtime = GMDecisionRuntime(GMTurnExecutor.supported_actions())
    assert forbidden.isdisjoint(runtime.contract()["allowed_ops"])


def test_server_gm_has_no_direct_turn_executor_surface_after_decision_gate():
    source = (ROOT / "src/sao_mcp/server_gm.py").read_text(encoding="utf-8")
    assert "def execute_gm_decision" in source
    assert "def preview_gm_decision" in source
    assert "def get_gm_decision_contract" in source
    assert "def execute_gm_turn" not in source
    assert "def get_gm_turn_action_contract" not in source


def test_bootstrap_wires_pure_decision_runtime_above_executor_without_changing_game_runtime_inheritance():
    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")
    assert "GMDecisionRuntime(GMTurnExecutor.supported_actions())" in source
    assert "register_gm_tools(mcp, gm_turn_executor, gm_decision_runtime)" in source
    assert '"gm_decision_runtime"' in source


def test_observation_packet_contains_capabilities_but_not_decision_or_hidden_authority_state():
    source = (ROOT / "src/sao_mcp/runtime/gm_observation.py").read_text(encoding="utf-8")
    assert '"capabilities"' in source
    assert "GMDecisionRuntime" not in source
    assert "gm_decision" not in source
