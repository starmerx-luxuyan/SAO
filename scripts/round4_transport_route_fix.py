from __future__ import annotations

from pathlib import Path

path = Path("src/sao_mcp/rules/transport.py")
text = path.read_text(encoding="utf-8")
old = '''def _npc_location(runtime, npc_id: str) -> str | None:\n    materialized = _materialized_npc(runtime, npc_id)\n    if materialized is not None:\n        return materialized.location_id\n    return runtime.npcs.states[npc_id].location_id\n'''
new = '''def _npc_location(runtime, npc_id: str) -> str | None:\n    resolver = getattr(runtime, "npc_location_id", None)\n    if resolver is not None:\n        return resolver(npc_id)\n    materialized = _materialized_npc(runtime, npc_id)\n    if materialized is not None:\n        return materialized.location_id\n    return runtime.npcs.states[npc_id].location_id\n'''
if text.count(old) != 1:
    raise RuntimeError("transport NPC location authority source changed")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
