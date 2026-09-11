from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor missing in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "src/sao_mcp/rules/economy_loop.py"
replace_once(
    path,
    "    cumulative_production_units: int = 0\n    cumulative_player_market_units: int = 0\n",
    "    cumulative_production_units: int = 0\n    cumulative_system_restock_units: int = 0\n    cumulative_player_market_units: int = 0\n",
)
replace_once(
    path,
    "            self.cumulative_production_units,\n            self.cumulative_player_market_units,\n",
    "            self.cumulative_production_units,\n            self.cumulative_system_restock_units,\n            self.cumulative_player_market_units,\n",
)
replace_once(
    path,
'''    def record_background(self, *, demand_units: int = 0, production_units: int = 0) -> None:\n        if demand_units < 0 or production_units < 0:\n            raise ValueError("background market units cannot be negative")\n        self.cumulative_background_demand_units += demand_units\n        self.cumulative_production_units += production_units\n        if demand_units or production_units:\n            self.revision += 1\n''',
'''    def record_background(\n        self,\n        *,\n        demand_units: int = 0,\n        production_units: int = 0,\n        system_restock_units: int = 0,\n    ) -> None:\n        if demand_units < 0 or production_units < 0 or system_restock_units < 0:\n            raise ValueError("background market units cannot be negative")\n        self.cumulative_background_demand_units += demand_units\n        self.cumulative_production_units += production_units\n        self.cumulative_system_restock_units += system_restock_units\n        if demand_units or production_units or system_restock_units:\n            self.revision += 1\n''',
)
replace_once(
    path,
    '        "cumulative_production_units": region.cumulative_production_units,\n        "cumulative_player_market_units": region.cumulative_player_market_units,\n',
    '        "cumulative_production_units": region.cumulative_production_units,\n        "cumulative_system_restock_units": region.cumulative_system_restock_units,\n        "cumulative_player_market_units": region.cumulative_player_market_units,\n',
)

path = "src/sao_mcp/runtime/property_economy.py"
replace_once(
    path,
'''            location_demand = 0\n            location_supply = 0\n            vendor_rows = []\n''',
'''            location_demand = 0\n            location_production = 0\n            location_system_restock = 0\n            vendor_rows = []\n''',
)
replace_once(
    path,
'''                    production = background_supply_units(self.runtime.catalog, template_id, segment_totals)\n                    system_units = system_restock_units(\n                        stock.available(template_id),\n                        stock.target_by_template[template_id],\n                    )\n                    supplied = stock.restock(template_id, production + system_units)\n                    demanded = background_demand_units(self.runtime.catalog, template_id, segment_totals)\n                    consumed = min(stock.available(template_id), demanded)\n                    if consumed:\n                        stock.consume(template_id, consumed)\n                    location_supply += supplied\n                    location_demand += consumed\n                    item_rows.append(\n                        {\n                            "template_id": template_id,\n                            "production_units": production,\n                            "system_restock_units": max(0, supplied - production),\n                            "background_consumed_units": consumed,\n                            "stock_after": stock.available(template_id),\n                            "current_unit_price_col": self.vendor_quote(vendor.vendor_id, template_id)["current_unit_price_col"],\n                        }\n                    )\n''',
'''                    production_requested = background_supply_units(\n                        self.runtime.catalog, template_id, segment_totals\n                    )\n                    production_supplied = stock.restock(template_id, production_requested)\n                    system_requested = system_restock_units(\n                        stock.available(template_id),\n                        stock.target_by_template[template_id],\n                    )\n                    system_supplied = stock.restock(template_id, system_requested)\n                    demanded = background_demand_units(self.runtime.catalog, template_id, segment_totals)\n                    consumed = min(stock.available(template_id), demanded)\n                    if consumed:\n                        stock.consume(template_id, consumed)\n                    location_production += production_supplied\n                    location_system_restock += system_supplied\n                    location_demand += consumed\n                    item_rows.append(\n                        {\n                            "template_id": template_id,\n                            "production_requested_units": production_requested,\n                            "production_supplied_units": production_supplied,\n                            "system_restock_requested_units": system_requested,\n                            "system_restock_units": system_supplied,\n                            "background_consumed_units": consumed,\n                            "stock_after": stock.available(template_id),\n                            "current_unit_price_col": self.vendor_quote(vendor.vendor_id, template_id)["current_unit_price_col"],\n                        }\n                    )\n''',
)
replace_once(
    path,
'''            region.record_background(demand_units=location_demand, production_units=location_supply)\n''',
'''            region.record_background(\n                demand_units=location_demand,\n                production_units=location_production,\n                system_restock_units=location_system_restock,\n            )\n''',
)
replace_once(
    path,
'''                background_vendor_demand_units=location_demand,\n                background_supply_units=location_supply,\n                background_player_market_units=market_units,\n''',
'''                background_vendor_demand_units=location_demand,\n                background_production_units=location_production,\n                system_restock_units=location_system_restock,\n                background_supply_units=location_production + location_system_restock,\n                background_player_market_units=market_units,\n''',
)
replace_once(
    path,
'''                cumulative_production_units=int(row.get("cumulative_production_units", 0)),\n                cumulative_player_market_units=int(row.get("cumulative_player_market_units", 0)),\n''',
'''                cumulative_production_units=int(row.get("cumulative_production_units", 0)),\n                cumulative_system_restock_units=int(row.get("cumulative_system_restock_units", 0)),\n                cumulative_player_market_units=int(row.get("cumulative_player_market_units", 0)),\n''',
)

# Match callback annotations to the settlement provenance rows returned by community hooks.
path = "src/sao_mcp/rules/economy.py"
replace_once(
    path,
'''        self.on_income: Callable[[CombatantState, int, str], None] | None = None\n        self.on_expense: Callable[[CombatantState, int, str], None] | None = None\n''',
'''        self.on_income: Callable[[CombatantState, int, str], Any] | None = None\n        self.on_expense: Callable[[CombatantState, int, str], Any] | None = None\n''',
)

# Lock the accounting separation: system shop regeneration must never masquerade as player production.
test_path = Path("tests/test_economy_loop.py")
test = test_path.read_text(encoding="utf-8")
test += '''\n\ndef test_system_vendor_restock_is_accounted_separately_from_player_production():\n    runtime = EconomyLoopAincradRuntime(seed=607)\n    buyer = runtime.create_character("BulkBuyer")\n    buyer.col = 100_000\n    runtime.economy.buy_from_vendor(\n        buyer,\n        VENDOR,\n        "field_bread",\n        20,\n        runtime.catalog,\n        actor_location_id=buyer.location_id,\n    )\n    runtime.advance_world(ECONOMY_TICK_MS)\n    market = runtime.aincrad_economy_state(TOWN)["location"]["market"]\n    assert market["cumulative_production_units"] == 0\n    assert market["cumulative_system_restock_units"] > 0\n    row = next(\n        row\n        for row in reversed(runtime.economy.market_history)\n        if row["event"] == "economy_tick" and row["location_id"] == TOWN\n    )\n    assert row["background_production_units"] == 0\n    assert row["system_restock_units"] > 0\n    assert row["background_supply_units"] == row["system_restock_units"]\n'''
test_path.write_text(test, encoding="utf-8")
