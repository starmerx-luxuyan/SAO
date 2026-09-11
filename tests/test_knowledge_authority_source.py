import ast
from pathlib import Path

from sao_mcp.rules.knowledge import KnowledgeEvent
from sao_mcp.rules.npc_actor_core import NPCActorCoreState
from sao_mcp.runtime.gm_turn import GMTurnExecutor


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src/sao_mcp"


def test_knowledge_events_have_causal_and_temporal_provenance_fields():
    fields = set(KnowledgeEvent.__dataclass_fields__)
    assert {
        "event_id",
        "confidence",
        "expires_at_ms",
        "learned_location_id",
        "evidence_event_ids",
        "supersedes_event_id",
        "transmission_depth",
    } <= fields


def test_actor_core_persists_exact_knowledge_event_used_for_decision():
    fields = set(NPCActorCoreState.__dataclass_fields__)
    assert "decision_basis_event_ids" in fields


def test_gm_observation_and_inference_contracts_require_epistemic_evidence():
    contract = GMTurnExecutor.supported_actions()
    assert set(contract["observe_fact"]["required"]) == {
        "entity_id",
        "fact_id",
        "value",
        "observation_location_id",
    }
    assert set(contract["infer_fact"]["required"]) == {
        "entity_id",
        "fact_id",
        "value",
        "evidence_fact_ids",
    }


def test_no_source_module_outside_knowledge_runtime_reads_or_mutates_raw_knowledge_event_ledger():
    violations = []
    authority = SOURCE_ROOT / "runtime/knowledge_runtime.py"
    for path in SOURCE_ROOT.rglob("*.py"):
        if path == authority:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"knowledge_events", "_knowledge_event_index"}:
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.attr}")
    assert violations == []
