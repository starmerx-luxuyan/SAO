from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise RuntimeError(f"{path}: expected {count} occurrences, found {found}: {old[:100]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# 1) Ordinary travel stays settled at its origin while world-time hooks run.
replace(
    "src/sao_mcp/rules/travel.py",
    '''    origin = actor.location_id\n    if advance_time is None:\n        world.now_ms += edge.travel_ms\n    else:\n        actor.location_id = None\n        advance_time(edge.travel_ms)\n        if actor.location_id is not None:\n            raise RuntimeError("travelling actor acquired a settled location before travel commit")\n    newly_discovered = discover_location(world, actor, destination)''',
    '''    origin = actor.location_id\n    if advance_time is None:\n        world.now_ms += edge.travel_ms\n    else:\n        # Ordinary player travel is one atomic state transition. Keep the actor at the\n        # authoritative origin while scheduler hooks advance, and block autonomous movement\n        # with the existing movement-authority key. Only commit the destination afterwards.\n        actor.metadata[AUTONOMOUS_TRAVEL_RESTRICTION_KEY] = "ordinary_world_travel"\n        try:\n            advance_time(edge.travel_ms)\n        finally:\n            actor.metadata.pop(AUTONOMOUS_TRAVEL_RESTRICTION_KEY, None)\n        if actor.location_id != origin:\n            raise RuntimeError("travelling actor changed settled location before travel commit")\n    newly_discovered = discover_location(world, actor, destination)''',
)

# 2) Live-state authority recognises named-player transit and rejects orphan null locations.
replace(
    "src/sao_mcp/rules/live_state.py",
    '''    guild_operations = getattr(runtime, "guild_operations", {})\n    for operation_id, operation in guild_operations.items():\n        if operation.active and actor_id in operation.assigned_member_ids:\n            matches.append(\n                {\n                    "kind": "guild_travel",\n                    "owner_id": operation_id,\n                    "guild_id": operation.guild_id,\n                    "actor_ids": list(operation.assigned_member_ids),\n                    "from_location_id": operation.from_location_id,\n                    "to_location_id": operation.next_location_id,\n                    "started_at_ms": operation.started_at_ms,\n                    "due_at_ms": operation.due_at_ms,\n                    "traversal_tags": list(operation.traversal_tags),\n                }\n            )\n\n    if len(matches) > 1:''',
    '''    guild_operations = getattr(runtime, "guild_operations", {})\n    for operation_id, operation in guild_operations.items():\n        if operation.active and actor_id in operation.assigned_member_ids:\n            matches.append(\n                {\n                    "kind": "guild_travel",\n                    "owner_id": operation_id,\n                    "guild_id": operation.guild_id,\n                    "actor_ids": list(operation.assigned_member_ids),\n                    "from_location_id": operation.from_location_id,\n                    "to_location_id": operation.next_location_id,\n                    "started_at_ms": operation.started_at_ms,\n                    "due_at_ms": operation.due_at_ms,\n                    "traversal_tags": list(operation.traversal_tags),\n                }\n            )\n\n    autonomy = actor.metadata.get("named_player_autonomy")\n    if isinstance(autonomy, dict) and isinstance(autonomy.get("transit"), dict):\n        transit = autonomy["transit"]\n        matches.append(\n            {\n                "kind": "named_player_travel",\n                "owner_id": actor_id,\n                "actor_ids": [actor_id],\n                "from_location_id": transit["from_location_id"],\n                "to_location_id": transit["to_location_id"],\n                "started_at_ms": transit["started_at_ms"],\n                "due_at_ms": transit["due_at_ms"],\n                "traversal_tags": [],\n            }\n        )\n\n    if len(matches) > 1:''',
)
replace(
    "src/sao_mcp/rules/live_state.py",
    '''    for actor_id, route_owner in route_actor.items():\n        if actor_id in active_actor_encounter:\n            raise RuntimeError(f"actor {actor_id} is both in active encounter and active route")''',
    '''    for actor_id, actor in runtime.actors.items():\n        route = actor_route_state(runtime, actor_id)\n        if actor.alive and actor.location_id is None and route is None:\n            raise RuntimeError(f"actor {actor_id} has no settled location and no active route authority")\n        if route is not None and route["kind"] == "named_player_travel":\n            if actor.location_id is not None:\n                raise RuntimeError(f"travelling named player {actor_id} has a settled location")\n            route_actor[actor_id] = f"named:{actor_id}"\n\n    for actor_id, route_owner in route_actor.items():\n        if actor_id in active_actor_encounter:\n            raise RuntimeError(f"actor {actor_id} is both in active encounter and active route")''',
)

# 3) Canon floor-1 labyrinth mob + a clearly simulation-tagged sellable material drop.
replace(
    "src/sao_mcp/corpus/monsters.py",
    '    _monster("large_nepenthes", "Large Nepenthes", 1, level=4, hp_factor=1.15, tags=("plant",)),\n',
    '''    _monster("large_nepenthes", "Large Nepenthes", 1, level=4, hp_factor=1.15, tags=("plant",)),\n    _monster(\n        "ruin_kobold_trooper", "Ruin Kobold Trooper", 1, level=6, location="labyrinth", hp_factor=1.18,\n        tags=("humanoid", "kobold", "weapon_user", "respawning_labyrinth"),\n        sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),\n        notes="Found in the 1st Floor Labyrinth and capable of weapon Sword Skills; it respawns at a set rate.",\n        exact_level=True,\n    ),\n''',
)
replace(
    "src/sao_mcp/corpus/monsters.py",
    '''AINCRAD_MONSTER_LOOT_TABLES: dict[str, LootTable] = {\n    row.loot_table_id: _sim_loot(row) for row in _MONSTER_ROWS\n}\n\n# Canon-locked rewards/drops where source material is explicit.''',
    '''AINCRAD_MONSTER_LOOT_TABLES: dict[str, LootTable] = {\n    row.loot_table_id: _sim_loot(row) for row in _MONSTER_ROWS\n}\nAINCRAD_MONSTER_LOOT_TABLES[AINCRAD_MONSTERS["ruin_kobold_trooper"].loot_table_id] = LootTable(\n    table_id=AINCRAD_MONSTERS["ruin_kobold_trooper"].loot_table_id,\n    col_min=18,\n    col_max=30,\n    xp_min=120,\n    xp_max=180,\n    entries=(LootEntry("ruin_kobold_axe_fragment", 1.0, 1, 2),),\n    provenance="canon_identity_level_location_plus_simulation_rewards",\n)\n\n# Canon-locked rewards/drops where source material is explicit.''',
)
replace(
    "src/sao_mcp/corpus/monsters.py",
    '''    rows = {\n        "needle_of_windwasp": ItemTemplate(''',
    '''    rows = {\n        "ruin_kobold_axe_fragment": ItemTemplate(\n            "ruin_kobold_axe_fragment", "Ruin Kobold Axe Fragment", ItemKind.MATERIAL,\n            weight=0.18, stack_limit=50, base_value_col=22, tags=("floor_1", "kobold_material"),\n            provenance=Provenance(\n                ProvenanceKind.SIMULATION,\n                sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),\n                notes="Trooper identity and axe usage are canon; this sellable fragment drop and its economy values are simulation calibration.",\n            ),\n        ),\n        "needle_of_windwasp": ItemTemplate(''',
)

# 4) New species migrates into old ecology saves instead of invalidating them.
replace(
    "src/sao_mcp/runtime/monster_ecology_runtime.py",
    '''        species_payload = payload.get("species", {})\n        if set(species_payload) != set(AINCRAD_MONSTERS):\n            raise ValueError("monster ecology save species registry disagrees with current corpus")\n        restored = {}''',
    '''        species_payload = payload.get("species", {})\n        unknown_species = set(species_payload) - set(AINCRAD_MONSTERS)\n        if unknown_species:\n            raise ValueError(f"monster ecology save references unknown species: {sorted(unknown_species)}")\n        restored = {}''',
)
replace(
    "src/sao_mcp/runtime/monster_ecology_runtime.py",
    '''        next_tick = int(payload["next_ecology_tick_at_ms"])\n        if next_tick <= self.world.now_ms:''',
    '''        for monster_id in sorted(set(AINCRAD_MONSTERS) - set(restored)):\n            definition = AINCRAD_MONSTERS[monster_id]\n            profile = spawn_profile(definition.tags)\n            restored[monster_id] = MonsterSpeciesEcologyState(\n                monster_id=monster_id,\n                location_id=definition.location_id,\n                carrying_capacity=profile.carrying_capacity,\n                available_units=profile.carrying_capacity,\n                recovery_interval_ms=profile.recovery_interval_ms,\n                recovery_batch=profile.recovery_batch,\n                next_recovery_at_ms=self.world.now_ms + profile.recovery_interval_ms,\n            )\n        next_tick = int(payload["next_ecology_tick_at_ms"])\n        if next_tick <= self.world.now_ms:''',
)

# 5) Party members at the same location enter ecological encounters together.
replace(
    "src/sao_mcp/runtime/monster_ecology_runtime.py",
    '''        monster = self.actors[candidates[0]] if candidates else self.materialize_ecological_monster(monster_id)\n        return self.start_encounter([actor_id, monster.actor_id], zone_id=definition.location_id)''',
    '''        monster = self.actors[candidates[0]] if candidates else self.materialize_ecological_monster(monster_id)\n        player_ids = [actor_id]\n        if actor.party_id and actor.party_id in self.world.parties:\n            party = self.world.parties[actor.party_id]\n            for member_id in party.member_ids:\n                if member_id == actor_id or member_id not in self.actors:\n                    continue\n                member = self.actors[member_id]\n                if member.alive and member.location_id == actor.location_id and not any(\n                    encounter.active and member_id in encounter.participants for encounter in self.encounters.values()\n                ):\n                    player_ids.append(member_id)\n        return self.start_encounter([*player_ids, monster.actor_id], zone_id=definition.location_id)''',
)

# 6) Tolbana gets a real living-economy smith/vendor node.
replace(
    "src/sao_mcp/corpus/economy.py",
    '''CORE_VENDORS: dict[str, VendorDefinition] = {\n    BEGINNER_VENDOR.vendor_id: BEGINNER_VENDOR,\n    BEGINNER_REINFORCEMENT_VENDOR.vendor_id: BEGINNER_REINFORCEMENT_VENDOR,\n}''',
    '''TOLBANA_FRONTLINE_SMITH = VendorDefinition(\n    vendor_id="npc_smith_tolbana_frontline",\n    name="Tolbana Frontline Smith",\n    location_id="floor_1_tolbana",\n    listings=(\n        VendorListingDefinition("reinforcement_base_material", 17),\n        VendorListingDefinition("reinforcement_sharpness_material", 29),\n        VendorListingDefinition("reinforcement_quickness_material", 29),\n        VendorListingDefinition("reinforcement_accuracy_material", 29),\n        VendorListingDefinition("reinforcement_heaviness_material", 29),\n        VendorListingDefinition("reinforcement_durability_material", 29),\n        VendorListingDefinition("iron_ingot", 31),\n    ),\n    buyback_rate=0.58,\n    infinite_stock=False,\n    provenance=Provenance(\n        ProvenanceKind.SIMULATION,\n        notes="A simulation-calibrated frontline smith node in Tolbana; Tolbana's frontline role is canon-backed, exact shop identity/prices are not asserted canon.",\n    ),\n)\n\n\nCORE_VENDORS: dict[str, VendorDefinition] = {\n    BEGINNER_VENDOR.vendor_id: BEGINNER_VENDOR,\n    BEGINNER_REINFORCEMENT_VENDOR.vendor_id: BEGINNER_REINFORCEMENT_VENDOR,\n    TOLBANA_FRONTLINE_SMITH.vendor_id: TOLBANA_FRONTLINE_SMITH,\n}''',
)

# New vendor stock migrates into older living-economy saves.
replace(
    "src/sao_mcp/runtime/property_economy.py",
    '''        self.vendor_stocks = stocks\n        self.regional_markets = markets''',
    '''        for vendor_id, vendor in self.vendors.items():\n            if vendor_id in stocks:\n                continue\n            targets = {\n                listing.template_id: target_stock_for_template(self.runtime.catalog, listing.template_id)\n                for listing in vendor.listings\n            }\n            stocks[vendor_id] = VendorStockState(\n                vendor_id=vendor_id,\n                stock_by_template=dict(targets),\n                target_by_template=targets,\n            )\n            markets.setdefault(\n                vendor.location_id,\n                RegionalMarketState(vendor.location_id, last_tick_ms=self.runtime.world.now_ms),\n            )\n        self.vendor_stocks = stocks\n        self.regional_markets = markets''',
)

replace(
    "src/sao_mcp/server_economy.py",
    '    "floor_1_town_of_beginnings",  # simulation starter workshop\n',
    '    "floor_1_town_of_beginnings",  # simulation starter workshop\n    "floor_1_tolbana",  # simulation frontline smith/workshop\n',
)
replace(
    "src/sao_mcp/ui/system_views.py",
    '    "floor_1_town_of_beginnings",\n',
    '    "floor_1_town_of_beginnings",\n    "floor_1_tolbana",\n',
)

# 7) Public gameplay surface exposes party and ordinary vendor transactions.
replace(
    "src/sao_mcp/server_public.py",
    '''@mcp.tool()\ndef export_save_json() -> str:''',
    '''@mcp.tool()\ndef create_party(leader_id: str) -> str:\n    """Create a live party for a player leader."""\n    return _json(asdict(runtime.create_party(leader_id)))\n\n\n@mcp.tool()\ndef join_party(party_id: str, actor_id: str) -> str:\n    """Join a player to an existing live party."""\n    return _json(asdict(runtime.join_party(party_id, actor_id)))\n\n\n@mcp.tool()\ndef list_vendors(location_id: str | None = None) -> str:\n    """List living NPC vendor nodes, optionally at one location."""\n    rows = []\n    for vendor in runtime.economy.vendors.values():\n        if location_id is not None and vendor.location_id != location_id:\n            continue\n        state = getattr(runtime.economy, "vendor_state", None)\n        rows.append(state(vendor.vendor_id) if state is not None else asdict(vendor))\n    return _json({"vendors": rows})\n\n\n@mcp.tool()\ndef sell_to_vendor(actor_id: str, vendor_id: str, instance_id: str, quantity: int | None = None) -> str:\n    """Sell an unequipped carried item to a colocated NPC vendor."""\n    actor = runtime.actors[actor_id]\n    return _json(asdict(runtime.economy.sell_to_vendor(\n        actor, vendor_id, instance_id, runtime.catalog, quantity=quantity, actor_location_id=actor.location_id\n    )))\n\n\n@mcp.tool()\ndef buy_from_vendor(actor_id: str, vendor_id: str, template_id: str, quantity: int = 1) -> str:\n    """Buy a stocked item from a colocated NPC vendor."""\n    actor = runtime.actors[actor_id]\n    return _json(asdict(runtime.economy.buy_from_vendor(\n        actor, vendor_id, template_id, quantity, runtime.catalog, actor_location_id=actor.location_id\n    )))\n\n\n@mcp.tool()\ndef export_save_json() -> str:''',
)

# 8) Release version metadata.
replace("src/sao_mcp/__init__.py", '__version__ = "1.3.1"', '__version__ = "1.3.2"')
manifest_path = ROOT / ".codex-plugin/plugin.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("version") != "1.3.1":
    raise RuntimeError("unexpected plugin version")
manifest["version"] = "1.3.2"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
replace("tests/test_release_contract.py", 'assert __version__ == "1.3.1"', 'assert __version__ == "1.3.2"')

(ROOT / "docs/V1.3.2.md").write_text(
    "# SAO Aincrad v1.3.2 — Floor 1 Frontline Loop\n\n"
    "Closes the first-floor gameplay loop: atomic travel, Ruin Kobold Trooper labyrinth ecology, "
    "party-aware encounters, Tolbana frontline economy, and public party/vendor actions.\n",
    encoding="utf-8",
)

print("applied v1.3.2 floor1 frontline patch")
