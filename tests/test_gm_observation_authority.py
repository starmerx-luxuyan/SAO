import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_server_gm_exposes_only_gated_observation_and_action_execution_surfaces():
    source = (ROOT / "src/sao_mcp/server_gm.py").read_text(encoding="utf-8")
    assert "def get_gm_observation" in source
    assert "observer_actor_ids" in source
    for forbidden in (
        "get_npc_agenda",
        "get_npc_actor_core",
        "get_npc_scheduler",
        "get_guild_agenda",
        "get_guild_operation",
        "get_entity_knowledge",
        "get_entity_knowledge_history",
        "get_knowledge_event_chain",
        "get_world_event_state",
        "get_world_event_history",
        "get_canonical_timeline_profile",
        "set_canonical_timeline_profile",
    ):
        assert f"def {forbidden}" not in source


def test_gm_turn_has_no_direct_hidden_projection_calls_after_execution():
    source = (ROOT / "src/sao_mcp/runtime/gm_turn.py").read_text(encoding="utf-8")
    for forbidden in (
        "npc_agenda_state(",
        "npc_actor_core_state(",
        "npc_scheduler_state(",
        "guild_agenda_state(",
        "guild_operation_state(",
        "knowledge_state(",
        "world_event_state(",
        "canonical_timeline_state(",
    ):
        assert forbidden not in source
    assert "GMObservationGate" in source


def test_observation_gate_does_not_read_hidden_autonomy_event_or_canon_authorities():
    path = ROOT / "src/sao_mcp/runtime/gm_observation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden = {
        "npc_actor_cores",
        "npc_agendas",
        "npc_schedulers",
        "guild_strategic_goals",
        "guild_operations",
        "world_events",
        "canonical_timeline",
        "monster_ecology",
        "regional_markets",
        "social_deliveries",
    }
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            violations.append((node.lineno, node.attr))
    assert violations == []


def test_observation_gate_is_stateless_projection_not_persistence_authority():
    source = (ROOT / "src/sao_mcp/runtime/gm_observation.py").read_text(encoding="utf-8")
    assert "dump_state" not in source
    assert "load_state" not in source
    assert "save" not in source.lower()
    persistence = (ROOT / "src/sao_mcp/runtime/persistence.py").read_text(encoding="utf-8")
    assert "gm_observation_state" not in persistence
