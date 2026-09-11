import ast
from pathlib import Path

from sao_mcp.rules.npc_autonomy import NPCAgendaState


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_ROOT = ROOT / "src/sao_mcp/scenarios"


def test_npc_agenda_is_execution_state_not_goal_authority():
    fields = set(NPCAgendaState.__dataclass_fields__)
    assert "goal_id" not in fields
    assert "goal_target_location_id" not in fields
    assert "plan_step_id" in fields


def test_scenarios_cannot_bypass_npc_actor_core_or_agenda_authority():
    violations = []
    for path in SCENARIO_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"npc_actor_cores", "npc_agendas"}:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []


def test_gm_exposes_actor_core_inspection_surface():
    server = (ROOT / "src/sao_mcp/server_gm.py").read_text(encoding="utf-8")
    assert "def get_npc_actor_core" in server
    assert "npc_actor_core_state(npc_id)" in server


def test_gm_set_npc_goal_contract_accepts_actor_core_decision_constraints():
    from sao_mcp.runtime.gm_turn import GMTurnExecutor

    optional = set(GMTurnExecutor.supported_actions()["set_npc_goal"]["optional"])
    assert optional == {
        "priority",
        "business_id",
        "required_fact_id",
        "required_fact_value",
        "relationship_actor_id",
        "min_relationship",
        "resource_requirements",
        "scheduled_actions",
    }
