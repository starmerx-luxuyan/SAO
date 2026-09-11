from pathlib import Path

path = Path(__file__).resolve().parents[1] / "src/sao_mcp/runtime/gm_observation.py"
text = path.read_text(encoding="utf-8")
old = "from sao_mcp.domain.models import EntityKind, QuestObjectiveKind\nfrom sao_mcp.rules.access import require_location_access\n"
new = "from sao_mcp.domain.models import EntityKind\nfrom sao_mcp.rules.access import require_location_access\nfrom sao_mcp.rules.quests import QuestObjectiveKind\n"
if old not in text:
    raise SystemExit("round18 gm observation import anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
