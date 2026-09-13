from __future__ import annotations

import json
import sys
from pathlib import Path

from sao_mcp.runtime.campaign_amendment import apply_campaign_amendment
from sao_mcp.runtime.campaign_blueprint import apply_campaign_blueprint
from sao_mcp.runtime.character_setup import begin_campaign_setup, finalize_campaign_setup
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime
from sao_mcp.rules.travel import discover_location

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_recovery() -> str:
    runtime = SocialCommunicationAincradRuntime(seed=0xA1C0)
    begin_campaign_setup(runtime)
    apply_campaign_blueprint(runtime, load_json(ROOT / "presets/kageaki_day3.json"))
    finalize_campaign_setup(runtime)
    apply_campaign_amendment(runtime, load_json(ROOT / "presets/kageaki_super_luck_amendment.json"))

    kageaki = runtime.actors["pc_419ba4144d33"]
    reina = runtime.actors["pc_friend_reina"]
    kageaki.col = 88_918
    kageaki.metadata["experience"] = 2_831
    kageaki.skill_proficiencies["star_sword"] = 248.60
    weapon = kageaki.inventory[kageaki.equipment["weapon"]]
    weapon.durability = 298
    # Keep the already-authoritative +2 Sharpness / +1 Quickness enhancement state from Day 3.
    reina.col = 2_760
    reina.skill_proficiencies["rapier"] = 214.0
    reina.skill_proficiencies["sprint"] = 122.0

    labyrinth = runtime.world_map.locations["floor_1_labyrinth"]
    discover_location(runtime.world, kageaki, labyrinth)
    discover_location(runtime.world, reina, labyrinth)

    if kageaki.party_id is None:
        party = runtime.create_party(kageaki.actor_id)
        runtime.join_party(party.party_id, reina.actor_id)

    save_json = export_runtime(runtime)
    restored = SocialCommunicationAincradRuntime(seed=1)
    import_runtime(save_json, into=restored)
    assert export_runtime(restored) == save_json
    return save_json


def main() -> None:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "SAO_Kageaki_Frontline_Recovery_v1.3.2.save.json")
    output.write_text(build_recovery() + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
