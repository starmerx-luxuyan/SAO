from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected fix anchor missing in {path}: {old[:160]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "src/sao_mcp/runtime/knowledge_runtime.py"
replace_once(
    path,
    "    def knowledge_event(self, event_id: str) -> KnowledgeEvent:\n        return self._knowledge_event_index[event_id]\n\n",
    "    def knowledge_event(self, event_id: str) -> KnowledgeEvent:\n"
    "        return self._knowledge_event_index[event_id]\n\n"
    "    def knowledge_event_count(self) -> int:\n"
    "        return len(self.knowledge_events)\n\n"
    "    def knowledge_events_since(self, offset: int) -> tuple[KnowledgeEvent, ...]:\n"
    "        if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= len(self.knowledge_events):\n"
    "            raise ValueError(\"knowledge event offset is outside the authoritative event log\")\n"
    "        return tuple(self.knowledge_events[offset:])\n\n",
)

path = "src/sao_mcp/runtime/social_communication_runtime.py"
text = (ROOT / path).read_text(encoding="utf-8")
text = text.replace("len(self.knowledge_events)", "self.knowledge_event_count()")
text = text.replace(
    "rows = self.knowledge_events[self.social_knowledge_cursor :]",
    "rows = self.knowledge_events_since(self.social_knowledge_cursor)",
)
(ROOT / path).write_text(text, encoding="utf-8")
