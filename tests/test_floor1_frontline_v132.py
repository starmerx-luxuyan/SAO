from __future__ import annotations

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


def test_public_surface_routes_party_and_vendor_mutations_through_turn_execute():
    async def run():
        async with Client(server_public.mcp, raise_exceptions=True) as client:
            return {tool.name for tool in (await client.list_tools()).tools}

    names = asyncio.run(run())
    assert {"list_vendors", "get_turn_contract", "turn_execute", "system_menu"} <= names
    assert {"create_party", "join_party", "sell_to_vendor", "buy_from_vendor"}.isdisjoint(names)
