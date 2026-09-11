from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

path = ROOT / "src/sao_mcp/runtime/gm_observation.py"
text = path.read_text(encoding="utf-8")
old = "from sao_mcp.domain.models import EntityKind, QuestObjectiveKind\nfrom sao_mcp.rules.access import require_location_access\n"
new = "from sao_mcp.domain.models import EntityKind\nfrom sao_mcp.rules.access import require_location_access\nfrom sao_mcp.rules.quests import QuestObjectiveKind\n"
if old not in text:
    raise SystemExit("round18 gm observation import anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

path = ROOT / "tests/test_gm_decision_runtime.py"
text = path.read_text(encoding="utf-8")
old = '    assert result["executed_action_count"] == 0\n'
new = '    assert result["actions_executed"] == 0\n    assert result["observation"]["observer_actor_ids"] == [player.actor_id]\n'
if old not in text:
    raise SystemExit("round18 wait assertion anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
