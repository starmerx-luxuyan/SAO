from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected audit anchor missing in {path}: {old[:180]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "src/sao_mcp/runtime/social_communication_runtime.py"
replace_once(
    path,
    '''        for event_id in self.argo_publishable_event_ids:\n            event = self._knowledge_event_index.get(event_id)\n            if event is None or event.knower_id != ARGO_NPC_ID:\n                raise RuntimeError("Argo publishable event lacks authoritative Argo knowledge")\n''',
    '''        for event_id in self.argo_publishable_event_ids:\n            event = self.knowledge_event(event_id)\n            if event.knower_id != ARGO_NPC_ID:\n                raise RuntimeError("Argo publishable event lacks authoritative Argo knowledge")\n''',
)
replace_once(
    path,
    '''            source = self._knowledge_event_index.get(delivery.source_event_id)\n            if source is None or source.fact_id != delivery.fact_id:\n                raise RuntimeError("social delivery source fact disagrees with Knowledge authority")\n''',
    '''            source = self.knowledge_event(delivery.source_event_id)\n            if source.fact_id != delivery.fact_id:\n                raise RuntimeError("social delivery source fact disagrees with Knowledge authority")\n''',
)
replace_once(
    path,
    '''                received = self._knowledge_event_index.get(str(delivery.received_event_id))\n                if received is None or delivery.source_event_id not in received.evidence_event_ids:\n                    raise RuntimeError("delivered social fact lacks exact Knowledge evidence chain")\n''',
    '''                received = self.knowledge_event(str(delivery.received_event_id))\n                if delivery.source_event_id not in received.evidence_event_ids:\n                    raise RuntimeError("delivered social fact lacks exact Knowledge evidence chain")\n''',
)

path = "tests/test_knowledge_authority_source.py"
replace_once(
    path,
    '''        for node in ast.walk(tree):\n            if isinstance(node, ast.Attribute) and node.attr == "knowledge_events":\n                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")\n''',
    '''        for node in ast.walk(tree):\n            if isinstance(node, ast.Attribute) and node.attr in {"knowledge_events", "_knowledge_event_index"}:\n                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.attr}")\n''',
)
