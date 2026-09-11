from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor missing in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: str, start: str, end: str, replacement: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    left = text.find(start)
    if left < 0:
        raise RuntimeError(f"start marker missing in {path}: {start!r}")
    right = text.find(end, left)
    if right < 0:
        raise RuntimeError(f"end marker missing in {path}: {end!r}")
    target.write_text(text[:left] + replacement + text[right:], encoding="utf-8")


rules_path = "src/sao_mcp/rules/economy_loop.py"
replace_once(
    rules_path,
    "    cumulative_background_demand_units: int = 0\n    cumulative_production_units: int = 0\n",
    "    cumulative_background_demand_units: int = 0\n    cumulative_unmet_demand_units: int = 0\n    cumulative_production_units: int = 0\n",
)
replace_once(
    rules_path,
    "    system_col_injected: int = 0\n    revision: int = 0\n",
    "    system_col_injected: int = 0\n    system_col_sunk: int = 0\n    revision: int = 0\n",
)
replace_once(
    rules_path,
    "            self.cumulative_background_demand_units,\n            self.cumulative_production_units,\n",
    "            self.cumulative_background_demand_units,\n            self.cumulative_unmet_demand_units,\n            self.cumulative_production_units,\n",
)
replace_once(
    rules_path,
    "            self.system_col_injected,\n        ):\n",
    "            self.system_col_injected,\n            self.system_col_sunk,\n        ):\n",
)
replace_once(
    rules_path,
'''    def record_background(\n        self,\n        *,\n        demand_units: int = 0,\n        production_units: int = 0,\n        system_restock_units: int = 0,\n    ) -> None:\n        if demand_units < 0 or production_units < 0 or system_restock_units < 0:\n            raise ValueError("background market units cannot be negative")\n        self.cumulative_background_demand_units += demand_units\n        self.cumulative_production_units += production_units\n        self.cumulative_system_restock_units += system_restock_units\n        if demand_units or production_units or system_restock_units:\n            self.revision += 1\n''',
'''    def record_background(\n        self,\n        *,\n        demand_units: int = 0,\n        unmet_demand_units: int = 0,\n        production_units: int = 0,\n        system_restock_units: int = 0,\n    ) -> None:\n        if (\n            demand_units < 0\n            or unmet_demand_units < 0\n            or production_units < 0\n            or system_restock_units < 0\n        ):\n            raise ValueError("background market units cannot be negative")\n        self.cumulative_background_demand_units += demand_units\n        self.cumulative_unmet_demand_units += unmet_demand_units\n        self.cumulative_production_units += production_units\n        self.cumulative_system_restock_units += system_restock_units\n        if demand_units or unmet_demand_units or production_units or system_restock_units:\n            self.revision += 1\n''',
)
replace_once(
    rules_path,
'''    def record_named_trade(self, gross_col: int) -> None:\n        if gross_col < 0:\n            raise ValueError("named market trade cannot have negative Col volume")\n        if gross_col:\n            self.cumulative_named_trade_col += gross_col\n            self.revision += 1\n''',
'''    def record_named_trade(self, gross_col: int) -> None:\n        if gross_col < 0:\n            raise ValueError("named market trade cannot have negative Col volume")\n        if gross_col:\n            self.cumulative_named_trade_col += gross_col\n            self.revision += 1\n\n    def record_system_col_flow(self, *, injected_col: int = 0, sunk_col: int = 0) -> None:\n        if injected_col < 0 or sunk_col < 0:\n            raise ValueError("system Col flow cannot be negative")\n        self.system_col_injected += injected_col\n        self.system_col_sunk += sunk_col\n        if injected_col or sunk_col:\n            self.revision += 1\n''',
)
replace_once(
    rules_path,
    '        "cumulative_background_demand_units": region.cumulative_background_demand_units,\n        "cumulative_production_units": region.cumulative_production_units,\n',
    '        "cumulative_background_demand_units": region.cumulative_background_demand_units,\n        "cumulative_unmet_demand_units": region.cumulative_unmet_demand_units,\n        "cumulative_production_units": region.cumulative_production_units,\n',
)
replace_once(
    rules_path,
    '        "system_col_injected": region.system_col_injected,\n        "revision": region.revision,\n',
    '        "system_col_injected": region.system_col_injected,\n        "system_col_sunk": region.system_col_sunk,\n        "revision": region.revision,\n',
)

runtime_path = "src/sao_mcp/runtime/property_economy.py"
replace_once(
    runtime_path,
'''        self._stock(vendor_id).consume(template_id, quantity)\n        self._region(vendor.location_id).record_named_trade(total_col)\n''',
'''        self._stock(vendor_id).consume(template_id, quantity)\n        region = self._region(vendor.location_id)\n        region.record_named_trade(total_col)\n        region.record_system_col_flow(sunk_col=total_col)\n''',
)
replace_once(
    runtime_path,
'''        self._region(vendor.location_id).record_named_trade(received_col)\n        self._record_market(\n            "named_vendor_sale",\n''',
'''        region = self._region(vendor.location_id)\n        region.record_named_trade(received_col)\n        region.record_system_col_flow(injected_col=received_col)\n        self._record_market(\n            "named_vendor_sale",\n''',
)
replace_between(
    runtime_path,
    "    def _clear_background_player_market(\n",
    "    def advance_living_market_tick(self, tick_ms: int) -> None:\n",
'''    def _clear_background_player_market(\n        self,\n        *,\n        location_id: str,\n        max_units_by_template: dict[str, int],\n        tick_ms: int,\n    ) -> tuple[dict[str, int], int]:\n        budgets = {\n            template_id: max(0, int(units))\n            for template_id, units in max_units_by_template.items()\n        }\n        sold_by_template: dict[str, int] = {}\n        gross_col = 0\n        for listing in sorted(\n            tuple(self.player_listings.values()),\n            key=lambda row: (row.location_id, row.unit_price_col, row.created_at_ms, row.listing_id),\n        ):\n            if listing.location_id != location_id:\n                continue\n            template_id = listing.item.template_id\n            budget = budgets.get(template_id, 0)\n            if budget <= 0:\n                continue\n            seller = self.runtime.actors.get(listing.seller_id)\n            if seller is None or not seller.alive or seller.metadata.get("permanent_death"):\n                continue\n            reference = self.reference_unit_price(location_id, template_id)\n            if listing.unit_price_col > max(1, int(round(reference * 1.10))):\n                continue\n            quantity = min(budget, listing.item.quantity)\n            if quantity <= 0:\n                continue\n            total = listing.unit_price_col * quantity\n            listing.item.quantity -= quantity\n            closed = listing.item.quantity <= 0\n            if closed:\n                self.player_listings.pop(listing.listing_id)\n            seller.col += total\n            finance = self._income(seller, total, "background_player_market_sale")\n            budgets[template_id] -= quantity\n            sold_by_template[template_id] = sold_by_template.get(template_id, 0) + quantity\n            gross_col += total\n            self._record_market(\n                "background_player_market_purchase",\n                at_ms=tick_ms,\n                listing_id=listing.listing_id,\n                seller_id=seller.actor_id,\n                location_id=location_id,\n                template_id=template_id,\n                quantity=quantity,\n                unit_price_col=listing.unit_price_col,\n                total_col=total,\n                listing_closed=closed,\n                finance=finance,\n            )\n        return sold_by_template, gross_col\n\n''',
)
replace_between(
    runtime_path,
    "    def advance_living_market_tick(self, tick_ms: int) -> None:\n",
    "    def vendor_state(self, vendor_id: str) -> dict[str, Any]:\n",
'''    def advance_living_market_tick(self, tick_ms: int) -> None:\n        if tick_ms != self.next_tick_at_ms:\n            raise RuntimeError(\n                f"economy tick must resolve at its scheduled boundary: {tick_ms} != {self.next_tick_at_ms}"\n            )\n        if self.runtime.world.now_ms != tick_ms:\n            raise RuntimeError("economy tick must resolve at authoritative current world time")\n        locations = {\n            vendor.location_id for vendor in self.vendors.values()\n        } | {listing.location_id for listing in self.player_listings.values()}\n        for location_id in sorted(locations):\n            population = self.runtime.population_location_state(location_id)\n            segment_totals = dict(population["segment_totals"])\n            region = self._region(location_id)\n            demand_index, supply_index = regional_pressure(segment_totals, int(population["headcount"]))\n            region.set_pressure(demand_index, supply_index, tick_ms=tick_ms)\n\n            vendors = sorted(\n                (row for row in self.vendors.values() if row.location_id == location_id),\n                key=lambda row: row.vendor_id,\n            )\n            template_ids = {\n                listing.template_id\n                for vendor in vendors\n                for listing in vendor.listings\n            } | {\n                listing.item.template_id\n                for listing in self.player_listings.values()\n                if listing.location_id == location_id\n            }\n            demand_requested = {\n                template_id: background_demand_units(self.runtime.catalog, template_id, segment_totals)\n                for template_id in template_ids\n            }\n            production_remaining = {\n                template_id: background_supply_units(self.runtime.catalog, template_id, segment_totals)\n                for template_id in template_ids\n            }\n            player_market_caps = {\n                template_id: units // 3\n                for template_id, units in demand_requested.items()\n            }\n            sold_by_template, market_col = self._clear_background_player_market(\n                location_id=location_id,\n                max_units_by_template=player_market_caps,\n                tick_ms=tick_ms,\n            )\n            market_units = sum(sold_by_template.values())\n            demand_remaining = {\n                template_id: max(0, units - sold_by_template.get(template_id, 0))\n                for template_id, units in demand_requested.items()\n            }\n\n            location_vendor_demand = 0\n            location_production = 0\n            location_system_restock = 0\n            vendor_rows = []\n            for vendor in vendors:\n                stock = self._stock(vendor.vendor_id)\n                item_rows = []\n                for listing in vendor.listings:\n                    template_id = listing.template_id\n                    production_requested_units = production_remaining.get(template_id, 0)\n                    production_supplied = stock.restock(template_id, production_requested_units)\n                    production_remaining[template_id] = max(\n                        0, production_requested_units - production_supplied\n                    )\n                    system_requested = system_restock_units(\n                        stock.available(template_id),\n                        stock.target_by_template[template_id],\n                    )\n                    system_supplied = stock.restock(template_id, system_requested)\n                    demanded_requested = demand_remaining.get(template_id, 0)\n                    consumed = min(stock.available(template_id), demanded_requested)\n                    if consumed:\n                        stock.consume(template_id, consumed)\n                    demand_remaining[template_id] = max(0, demanded_requested - consumed)\n                    location_production += production_supplied\n                    location_system_restock += system_supplied\n                    location_vendor_demand += consumed\n                    item_rows.append(\n                        {\n                            "template_id": template_id,\n                            "production_requested_units": production_requested_units,\n                            "production_supplied_units": production_supplied,\n                            "system_restock_requested_units": system_requested,\n                            "system_restock_units": system_supplied,\n                            "background_demand_requested_units": demanded_requested,\n                            "background_consumed_units": consumed,\n                            "background_demand_remaining_units": demand_remaining[template_id],\n                            "stock_after": stock.available(template_id),\n                            "current_unit_price_col": self.vendor_quote(\n                                vendor.vendor_id, template_id\n                            )["current_unit_price_col"],\n                        }\n                    )\n                vendor_rows.append({"vendor_id": vendor.vendor_id, "items": item_rows})\n\n            fulfilled_demand = market_units + location_vendor_demand\n            unmet_demand = sum(demand_remaining.values())\n            unabsorbed_production = sum(production_remaining.values())\n            region.record_background(\n                demand_units=fulfilled_demand,\n                unmet_demand_units=unmet_demand,\n                production_units=location_production,\n                system_restock_units=location_system_restock,\n            )\n            if market_units:\n                region.record_player_market(units=market_units, gross_col=market_col)\n            self._record_market(\n                "economy_tick",\n                at_ms=tick_ms,\n                location_id=location_id,\n                population_headcount=int(population["headcount"]),\n                segment_totals=segment_totals,\n                demand_index=region.demand_index,\n                supply_index=region.supply_index,\n                background_requested_demand_units=sum(demand_requested.values()),\n                background_fulfilled_demand_units=fulfilled_demand,\n                background_unmet_demand_units=unmet_demand,\n                background_vendor_demand_units=location_vendor_demand,\n                background_production_units=location_production,\n                unabsorbed_production_units=unabsorbed_production,\n                system_restock_units=location_system_restock,\n                background_supply_units=location_production + location_system_restock,\n                background_player_market_units=market_units,\n                background_player_market_col=market_col,\n                player_market_units_by_template=sold_by_template,\n                vendors=vendor_rows,\n            )\n        self.next_tick_at_ms += ECONOMY_TICK_MS\n        self.assert_living_market_authority()\n\n''',
)
replace_once(
    runtime_path,
'''                cumulative_background_demand_units=int(row.get("cumulative_background_demand_units", 0)),\n                cumulative_production_units=int(row.get("cumulative_production_units", 0)),\n''',
'''                cumulative_background_demand_units=int(row.get("cumulative_background_demand_units", 0)),\n                cumulative_unmet_demand_units=int(row.get("cumulative_unmet_demand_units", 0)),\n                cumulative_production_units=int(row.get("cumulative_production_units", 0)),\n''',
)
replace_once(
    runtime_path,
'''                system_col_injected=int(row.get("system_col_injected", 0)),\n                revision=int(row.get("revision", 0)),\n''',
'''                system_col_injected=int(row.get("system_col_injected", 0)),\n                system_col_sunk=int(row.get("system_col_sunk", 0)),\n                revision=int(row.get("revision", 0)),\n''',
)

# Add regional-demand and Col-flow regressions. They deliberately use existing starter inventory and
# real carry limits; no synthetic bypass state is introduced.
test_path = Path("tests/test_economy_loop.py")
test = test_path.read_text(encoding="utf-8")
test = test.replace(
    "from sao_mcp.rules.economy_loop import ECONOMY_TICK_MS\n",
    "from sao_mcp.rules.economy_loop import ECONOMY_TICK_MS, background_demand_units\n",
    1,
)
test += '''\n\ndef test_background_demand_budget_is_shared_between_player_market_and_vendor_channel():\n    runtime = EconomyLoopAincradRuntime(seed=608)\n    seller = runtime.create_character("PotionSeller")\n    potion_id = next(\n        instance_id\n        for instance_id, item in seller.inventory.items()\n        if item.template_id == "healing_potion_basic"\n    )\n    runtime.economy.create_player_listing(\n        seller,\n        potion_id,\n        location_id=TOWN,\n        unit_price_col=10,\n        quantity=2,\n        now_ms=0,\n    )\n    runtime.add_population_cohort("buyers", "casual", 1_000, TOWN, 2.0, "town_consumers")\n    expected = background_demand_units(\n        runtime.catalog,\n        "healing_potion_basic",\n        runtime.population_location_state(TOWN)["segment_totals"],\n    )\n    runtime.advance_world(ECONOMY_TICK_MS)\n    tick = next(\n        row\n        for row in reversed(runtime.economy.market_history)\n        if row["event"] == "economy_tick" and row["location_id"] == TOWN\n    )\n    potion_row = next(\n        item\n        for vendor in tick["vendors"]\n        if vendor["vendor_id"] == VENDOR\n        for item in vendor["items"]\n        if item["template_id"] == "healing_potion_basic"\n    )\n    player_units = tick["player_market_units_by_template"]["healing_potion_basic"]\n    assert player_units == 2\n    assert potion_row["background_consumed_units"] + player_units == expected\n    assert potion_row["background_demand_remaining_units"] == 0\n\n\ndef test_named_vendor_col_sink_and_injection_are_recorded_without_copying_actor_balance():\n    runtime = EconomyLoopAincradRuntime(seed=609)\n    actor = runtime.create_character("Trader")\n    actor.col = 10_000\n    purchase = runtime.economy.buy_from_vendor(\n        actor,\n        VENDOR,\n        "field_bread",\n        1,\n        runtime.catalog,\n        actor_location_id=actor.location_id,\n    )\n    runtime.unequip_item(actor.actor_id, "weapon")\n    weapon_id = next(\n        instance_id\n        for instance_id, item in actor.inventory.items()\n        if item.template_id == "starter_one_hand_sword"\n    )\n    sale = runtime.economy.sell_to_vendor(\n        actor,\n        VENDOR,\n        weapon_id,\n        runtime.catalog,\n        quantity=1,\n        actor_location_id=actor.location_id,\n    )\n    market = runtime.aincrad_economy_state(TOWN)["location"]["market"]\n    assert market["system_col_sunk"] == purchase.total_col\n    assert market["system_col_injected"] == sale.received_col\n    assert "actor_col" not in market\n'''
test_path.write_text(test, encoding="utf-8")
