from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise RuntimeError(f"{path}: expected {count} occurrences, found {found}: {old[:100]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Party encounters end when the hostile side is defeated, not only when total living actors <= 1.
replace(
    "src/sao_mcp/runtime/engine.py",
    '''        if (\n            target.kind in (EntityKind.MONSTER, EntityKind.BOSS)\n            and encounter.active\n            and not any(\n                actor.kind is EntityKind.PLAYER and actor.metadata.get("death_state") == "end_phase"\n                for actor in encounter.participants.values()\n            )\n            and sum(1 for actor in encounter.participants.values() if actor.alive) <= 1\n        ):\n            self.end_encounter(encounter.encounter_id, reason="combat_resolved")''',
    '''        if (\n            target.kind in (EntityKind.MONSTER, EntityKind.BOSS)\n            and encounter.active\n            and not any(\n                actor.kind is EntityKind.PLAYER and actor.metadata.get("death_state") == "end_phase"\n                for actor in encounter.participants.values()\n            )\n        ):\n            living_players = any(\n                actor.alive and actor.kind is EntityKind.PLAYER\n                for actor in encounter.participants.values()\n            )\n            living_hostiles = any(\n                actor.alive and actor.kind in (EntityKind.MONSTER, EntityKind.BOSS)\n                for actor in encounter.participants.values()\n            )\n            if not living_players or not living_hostiles:\n                self.end_encounter(encounter.encounter_id, reason="combat_resolved")''',
)

# Permanent release CI public surface and bundle version.
ci = ROOT / ".github/workflows/ci.yml"
text = ci.read_text(encoding="utf-8")
text = text.replace('"export_save_json", "import_save_json", "get_gm_observation",', '"create_party", "join_party", "list_vendors", "sell_to_vendor", "buy_from_vendor",\n              "export_save_json", "import_save_json", "get_gm_observation",')
text = text.replace("v1.3.1", "v1.3.2").replace('"1.3.1"', '"1.3.2"')
text = text.replace("docs/V1.3.1.md", "docs/V1.3.2.md")
ci.write_text(text, encoding="utf-8")

# Recovery builder: preserve the last trustworthy values from the interrupted live session.
(ROOT / "scripts/build_kageaki_frontline_recovery_v132.py").write_text(r'''from __future__ import annotations

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
''', encoding="utf-8")

(ROOT / "tests/test_floor1_frontline_v132.py").write_text(r'''from __future__ import annotations

import asyncio
import json

import pytest
from mcp import Client

from sao_mcp import server_public
from sao_mcp.rules.travel import discover_location
from sao_mcp.runtime.gm_observation import GMObservationGate
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


def test_ordinary_travel_failure_keeps_authoritative_origin():
    runtime = SocialCommunicationAincradRuntime(seed=2)
    actor = runtime.create_character("Traveler", level=2)
    origin = actor.location_id

    def explode(_: int):
        raise RuntimeError("scheduler failure")

    runtime.advance_world = explode
    with pytest.raises(RuntimeError, match="scheduler failure"):
        runtime.travel_actor(actor.actor_id, "floor_1_west_field")
    assert actor.location_id == origin
    assert "autonomous_travel_restriction" not in actor.metadata


def test_floor1_labyrinth_party_loot_and_tolbana_sale_loop():
    runtime = SocialCommunicationAincradRuntime(seed=7)
    kageaki = runtime.create_character("Frontliner", level=7)
    reina = runtime.create_character("Partner", level=6, starter_weapon_id="starter_rapier")
    tolbana = runtime.world_map.locations["floor_1_tolbana"]
    discover_location(runtime.world, kageaki, tolbana)
    discover_location(runtime.world, reina, tolbana)

    party = runtime.create_party(kageaki.actor_id)
    runtime.join_party(party.party_id, reina.actor_id)
    runtime.travel_actor(kageaki.actor_id, "floor_1_labyrinth")
    runtime.travel_actor(reina.actor_id, "floor_1_labyrinth")

    observation = GMObservationGate(runtime).observe([kageaki.actor_id, reina.actor_id])
    for actor_id in (kageaki.actor_id, reina.actor_id):
        options = observation["viewpoints"][actor_id]["capabilities"]["encounter_options"]
        assert any(row["monster_id"] == "ruin_kobold_trooper" and row["level"] == 6 for row in options)

    xp_before = int(kageaki.metadata["experience"])
    col_before = kageaki.col
    partner_xp_before = int(reina.metadata["experience"])
    encounter = runtime.engage_ecological_monster(kageaki.actor_id, "ruin_kobold_trooper")
    assert kageaki.actor_id in encounter.participants
    assert reina.actor_id in encounter.participants
    monster = next(actor for actor in encounter.participants.values() if actor.metadata.get("ecology_monster_id") == "ruin_kobold_trooper")
    monster.hp = 1
    monster.max_hp = max(monster.max_hp, 1)
    kageaki.agility = 999
    result = runtime.attack(encounter.encounter_id, kageaki.actor_id, monster.actor_id, seed=1)
    assert result.hit and not monster.alive
    assert not runtime.encounters[encounter.encounter_id].active
    assert int(kageaki.metadata["experience"]) > xp_before
    assert int(reina.metadata["experience"]) > partner_xp_before
    assert kageaki.col > col_before

    fragment = next(item for item in kageaki.inventory.values() if item.template_id == "ruin_kobold_axe_fragment")
    runtime.travel_actor(kageaki.actor_id, "floor_1_tolbana")
    runtime.travel_actor(reina.actor_id, "floor_1_tolbana")
    sale_col_before = kageaki.col
    sale = runtime.economy.sell_to_vendor(
        kageaki,
        "npc_smith_tolbana_frontline",
        fragment.instance_id,
        runtime.catalog,
        quantity=1,
        actor_location_id=kageaki.location_id,
    )
    assert sale.received_col > 0
    assert kageaki.col > sale_col_before
    assert export_runtime(runtime)


def test_old_v131_state_gains_new_ecology_and_vendor_authorities():
    runtime = SocialCommunicationAincradRuntime(seed=9)
    actor = runtime.create_character("Migration", level=2)
    payload = json.loads(export_runtime(runtime))
    payload["monster_ecology_state"]["species"].pop("ruin_kobold_trooper")
    payload["economy_state"]["vendor_stocks"].pop("npc_smith_tolbana_frontline")
    payload["economy_state"]["regional_markets"].pop("floor_1_tolbana", None)
    restored = SocialCommunicationAincradRuntime(seed=10)
    import_runtime(json.dumps(payload, ensure_ascii=False), into=restored)
    assert "ruin_kobold_trooper" in restored.monster_ecology
    assert "npc_smith_tolbana_frontline" in restored.economy.vendor_stocks
    assert restored.actors[actor.actor_id].location_id == actor.location_id


def test_public_surface_has_party_and_vendor_actions():
    async def run():
        async with Client(server_public.mcp, raise_exceptions=True) as client:
            return {tool.name for tool in (await client.list_tools()).tools}
    names = asyncio.run(run())
    assert {"create_party", "join_party", "list_vendors", "sell_to_vendor", "buy_from_vendor"} <= names
''', encoding="utf-8")

print("applied v1.3.2 party/recovery/tests patch")
