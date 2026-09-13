from __future__ import annotations

import json
import sys
from pathlib import Path

from sao_mcp.runtime.campaign_amendment import apply_campaign_amendment
from sao_mcp.runtime.campaign_blueprint import apply_campaign_blueprint
from sao_mcp.runtime.character_setup import begin_campaign_setup, finalize_campaign_setup
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_save() -> str:
    runtime = SocialCommunicationAincradRuntime(seed=0xA1C0)
    begin_campaign_setup(runtime)
    blueprint = load_json(ROOT / "presets" / "kageaki_day3.json")
    result = apply_campaign_blueprint(runtime, blueprint)
    if result["world_now_ms"] != 172_800_000:
        raise RuntimeError("Day 3 blueprint did not reach its authoritative world time")
    finalize_campaign_setup(runtime)
    amendment = load_json(ROOT / "presets" / "kageaki_super_luck_amendment.json")
    applied = apply_campaign_amendment(runtime, amendment)
    if not applied["committed"]:
        raise RuntimeError("Super Luck amendment was not committed")

    save_json = export_runtime(runtime)
    restored = SocialCommunicationAincradRuntime(seed=1)
    import_runtime(save_json, into=restored)
    if export_runtime(restored) != save_json:
        raise RuntimeError("native Day 3 save failed exact export/import round-trip")
    from sao_mcp.corpus.progressive_guilds import ALS_GUILD_ID, DKB_GUILD_ID
    if DKB_GUILD_ID in restored.relationships.guilds or ALS_GUILD_ID in restored.relationships.guilds:
        raise RuntimeError("future Progressive clearing guilds leaked into Day 3")
    kageaki = restored.actors["pc_419ba4144d33"]
    if kageaki.col != 88_888:
        raise RuntimeError("Kageaki amendment Col did not persist")
    if len(restored.relationships.friends.get(kageaki.actor_id, set())) != 7:
        raise RuntimeError("Kageaki Day 3 friendship graph is incomplete")
    represented = restored.player_population_state()["total_living_players_represented"]
    if represented <= 9_000:
        raise RuntimeError("Day 3 population bootstrap is missing")
    return save_json


def main() -> None:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "SAO_Kageaki_Day3_v1.3.1.save.json")
    save_json = build_save()
    output.write_text(save_json + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
