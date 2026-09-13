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


# A null location is legal only for an active route or an explicitly unresolved canon actor.
replace(
    "src/sao_mcp/rules/live_state.py",
    '''        if actor.alive and actor.location_id is None and route is None:\n            raise RuntimeError(f"actor {actor_id} has no settled location and no active route authority")''',
    '''        if (\n            actor.alive\n            and actor.location_id is None\n            and route is None\n            and actor.metadata.get("world_location_unresolved") is not True\n        ):\n            raise RuntimeError(f"actor {actor_id} has no settled location and no active route authority")''',
)

# Party victory now terminates the encounter; a second attack must be rejected by lifecycle authority.
replace(
    "tests/test_inventory_loot.py",
    '''    again = rt.attack(enc.encounter_id, a.actor_id, monster.actor_id, defense="none", seed=5)\n    assert not again.legal\n    assert len([event for event in enc.events if event.event_type == "loot_awarded"]) == 1''',
    '''    assert not enc.active\n    with pytest.raises(ValueError, match="has ended"):\n        rt.attack(enc.encounter_id, a.actor_id, monster.actor_id, defense="none", seed=5)\n    assert len([event for event in enc.events if event.event_type == "loot_awarded"]) == 1''',
)

# Public v1.3.2 gameplay actions are part of the exact release surface.
replace(
    "tests/test_release_contract.py",
    '''    "health", "create_character", "get_character_state", "inspect_catalog_entry", "list_catalog",\n    "export_save_json", "import_save_json", "get_gm_observation", "get_gm_decision_contract",''',
    '''    "health", "create_character", "get_character_state", "inspect_catalog_entry", "list_catalog",\n    "create_party", "join_party", "list_vendors", "sell_to_vendor", "buy_from_vendor",\n    "export_save_json", "import_save_json", "get_gm_observation", "get_gm_decision_contract",''',
)

# Adding the Labyrinth pressure contract legitimately adds Tolbana as another quest board.
# Keep this test focused on locality by selecting the Town board explicitly.
replace(
    "tests/test_social_communication_autonomy.py",
    '''    contract = next(iter(runtime.quest_contracts.values()))\n    fact_id = f"quest_contract:{contract.contract_id}"\n    assert contract.posting_location_id == TOWN''',
    '''    contract = next(\n        row for row in runtime.quest_contracts.values()\n        if row.posting_location_id == TOWN\n    )\n    fact_id = f"quest_contract:{contract.contract_id}"\n    assert contract.posting_location_id == TOWN''',
)

print("applied v1.3.2 contract reconciliation patch")
