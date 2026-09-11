from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.rules.economy import ECONOMY_STATE_SCHEMA, EconomyRuntime
from sao_mcp.rules.economy_loop import (
    ECONOMY_TICK_MS,
    RegionalMarketState,
    VendorStockState,
    background_demand_units,
    background_supply_units,
    market_state_row,
    price_multiplier,
    regional_pressure,
    system_restock_units,
    target_stock_for_template,
)


class GuardedEconomyRuntime(EconomyRuntime):
    """Runtime-bound economy with finite vendor stock and population-driven regional clearing."""

    def __init__(self, runtime, vendors=None) -> None:
        super().__init__(vendors=vendors)
        self.runtime = runtime
        self.vendor_stocks: dict[str, VendorStockState] = {}
        self.regional_markets: dict[str, RegionalMarketState] = {}
        self.market_history: list[dict[str, Any]] = []
        self.next_tick_at_ms = runtime.world.now_ms + ECONOMY_TICK_MS
        self._reset_living_market_state()

    def _reset_living_market_state(self) -> None:
        self.vendor_stocks = {}
        self.regional_markets = {}
        for vendor_id, vendor in self.vendors.items():
            targets = {
                listing.template_id: target_stock_for_template(self.runtime.catalog, listing.template_id)
                for listing in vendor.listings
            }
            self.vendor_stocks[vendor_id] = VendorStockState(
                vendor_id=vendor_id,
                stock_by_template=dict(targets),
                target_by_template=targets,
            )
            self.regional_markets.setdefault(
                vendor.location_id,
                RegionalMarketState(vendor.location_id, last_tick_ms=self.runtime.world.now_ms),
            )
        self.market_history = []
        self.next_tick_at_ms = self.runtime.world.now_ms + ECONOMY_TICK_MS

    def _region(self, location_id: str) -> RegionalMarketState:
        if location_id not in self.runtime.world_map.locations:
            raise KeyError(location_id)
        return self.regional_markets.setdefault(
            location_id,
            RegionalMarketState(location_id, last_tick_ms=self.runtime.world.now_ms),
        )

    def _stock(self, vendor_id: str) -> VendorStockState:
        try:
            return self.vendor_stocks[vendor_id]
        except KeyError as exc:
            raise RuntimeError(f"living economy lacks stock authority for vendor: {vendor_id}") from exc

    def _record_market(self, event: str, *, at_ms: int | None = None, **fields: Any) -> None:
        timestamp = self.runtime.world.now_ms if at_ms is None else int(at_ms)
        self.market_history.append({"event": event, **fields, "at_ms": timestamp})

    def _vendor_unit_price(self, vendor_id: str, listing) -> int:
        vendor = self.vendors[vendor_id]
        stock = self._stock(vendor_id)
        region = self._region(vendor.location_id)
        multiplier = price_multiplier(
            region,
            stock=stock.available(listing.template_id),
            target_stock=stock.target_by_template[listing.template_id],
        )
        return max(1, int(round(listing.unit_price_col * multiplier)))

    def _validate_vendor_purchase_quantity(self, vendor_id: str, template_id: str, quantity: int) -> None:
        available = self._stock(vendor_id).available(template_id)
        if quantity > available:
            raise ValueError(f"vendor stock is insufficient: requested={quantity} available={available}")

    def _vendor_buyback_multiplier(self, vendor_id: str, template_id: str) -> float:
        vendor = self.vendors[vendor_id]
        region = self._region(vendor.location_id)
        stock = self._stock(vendor_id)
        if template_id in stock.stock_by_template:
            return price_multiplier(
                region,
                stock=stock.available(template_id),
                target_stock=stock.target_by_template[template_id],
            )
        return max(0.75, min(1.35, 1.0 + (region.demand_index - region.supply_index) * 0.12))

    def _commit_vendor_purchase(
        self,
        *,
        vendor_id: str,
        template_id: str,
        quantity: int,
        unit_price_col: int,
        total_col: int,
    ) -> None:
        vendor = self.vendors[vendor_id]
        self._stock(vendor_id).consume(template_id, quantity)
        self._region(vendor.location_id).record_named_trade(total_col)
        self._record_market(
            "named_vendor_purchase",
            vendor_id=vendor_id,
            location_id=vendor.location_id,
            template_id=template_id,
            quantity=quantity,
            unit_price_col=unit_price_col,
            total_col=total_col,
        )

    def _commit_vendor_sale(
        self,
        *,
        vendor_id: str,
        template_id: str,
        quantity: int,
        received_col: int,
    ) -> None:
        vendor = self.vendors[vendor_id]
        stock = self._stock(vendor_id)
        restocked = 0
        if template_id in stock.stock_by_template:
            restocked = stock.restock(template_id, quantity)
        self._region(vendor.location_id).record_named_trade(received_col)
        self._record_market(
            "named_vendor_sale",
            vendor_id=vendor_id,
            location_id=vendor.location_id,
            template_id=template_id,
            quantity=quantity,
            vendor_stock_added=restocked,
            received_col=received_col,
        )

    def _commit_player_purchase(
        self,
        *,
        location_id: str,
        template_id: str,
        quantity: int,
        total_col: int,
    ) -> None:
        self._region(location_id).record_named_trade(total_col)
        self._record_market(
            "named_player_market_purchase",
            location_id=location_id,
            template_id=template_id,
            quantity=quantity,
            total_col=total_col,
        )

    def sell_to_vendor(self, seller, vendor_id, instance_id, catalog, *, quantity, actor_location_id):
        self.runtime.validate_item_disposition(seller.actor_id, instance_id)
        return super().sell_to_vendor(
            seller,
            vendor_id,
            instance_id,
            catalog,
            quantity=quantity,
            actor_location_id=actor_location_id,
        )

    def create_player_listing(
        self,
        seller,
        instance_id,
        *,
        location_id,
        unit_price_col,
        quantity,
        now_ms,
    ):
        self.runtime.validate_item_disposition(seller.actor_id, instance_id)
        return super().create_player_listing(
            seller,
            instance_id,
            location_id=location_id,
            unit_price_col=unit_price_col,
            quantity=quantity,
            now_ms=now_ms,
        )

    def vendor_quote(self, vendor_id: str, template_id: str) -> dict[str, Any]:
        vendor = self.vendors[vendor_id]
        listing = next((row for row in vendor.listings if row.template_id == template_id), None)
        if listing is None:
            raise ValueError("vendor does not sell this template")
        stock = self._stock(vendor_id)
        region = self._region(vendor.location_id)
        current = self._vendor_unit_price(vendor_id, listing)
        return {
            "vendor_id": vendor_id,
            "location_id": vendor.location_id,
            "template_id": template_id,
            "base_unit_price_col": listing.unit_price_col,
            "current_unit_price_col": current,
            "stock": stock.available(template_id),
            "target_stock": stock.target_by_template[template_id],
            "price_multiplier": round(current / listing.unit_price_col, 6),
            "demand_index": region.demand_index,
            "supply_index": region.supply_index,
            "next_tick_at_ms": self.next_tick_at_ms,
        }

    def reference_unit_price(self, location_id: str, template_id: str) -> int:
        quotes = [
            self.vendor_quote(vendor.vendor_id, template_id)["current_unit_price_col"]
            for vendor in self.vendors.values()
            if vendor.location_id == location_id and any(row.template_id == template_id for row in vendor.listings)
        ]
        if quotes:
            return min(quotes)
        region = self._region(location_id)
        base = self._base_item_value(template_id, self.runtime.catalog)
        multiplier = max(0.65, min(1.75, 1.0 + (region.demand_index - region.supply_index) * 0.22))
        return max(1, int(round(base * 1.20 * multiplier)))

    def _clear_background_player_market(
        self,
        *,
        location_id: str,
        segment_totals: dict[str, int],
        tick_ms: int,
    ) -> tuple[int, int]:
        budgets: dict[str, int] = {}
        for listing in self.player_listings.values():
            if listing.location_id != location_id:
                continue
            budgets.setdefault(
                listing.item.template_id,
                max(0, background_demand_units(self.runtime.catalog, listing.item.template_id, segment_totals) // 3),
            )
        units = 0
        gross_col = 0
        for listing in sorted(
            tuple(self.player_listings.values()),
            key=lambda row: (row.location_id, row.unit_price_col, row.created_at_ms, row.listing_id),
        ):
            if listing.location_id != location_id:
                continue
            budget = budgets.get(listing.item.template_id, 0)
            if budget <= 0:
                continue
            seller = self.runtime.actors.get(listing.seller_id)
            if seller is None or not seller.alive or seller.metadata.get("permanent_death"):
                continue
            reference = self.reference_unit_price(location_id, listing.item.template_id)
            if listing.unit_price_col > max(1, int(round(reference * 1.10))):
                continue
            quantity = min(budget, listing.item.quantity)
            if quantity <= 0:
                continue
            total = listing.unit_price_col * quantity
            listing.item.quantity -= quantity
            closed = listing.item.quantity <= 0
            if closed:
                self.player_listings.pop(listing.listing_id)
            seller.col += total
            finance = self._income(seller, total, "background_player_market_sale")
            budgets[listing.item.template_id] -= quantity
            units += quantity
            gross_col += total
            self._record_market(
                "background_player_market_purchase",
                at_ms=tick_ms,
                listing_id=listing.listing_id,
                seller_id=seller.actor_id,
                location_id=location_id,
                template_id=listing.item.template_id,
                quantity=quantity,
                unit_price_col=listing.unit_price_col,
                total_col=total,
                listing_closed=closed,
                finance=finance,
            )
        return units, gross_col

    def advance_living_market_tick(self, tick_ms: int) -> None:
        if tick_ms != self.next_tick_at_ms:
            raise RuntimeError(
                f"economy tick must resolve at its scheduled boundary: {tick_ms} != {self.next_tick_at_ms}"
            )
        if self.runtime.world.now_ms != tick_ms:
            raise RuntimeError("economy tick must resolve at authoritative current world time")
        locations = {
            vendor.location_id for vendor in self.vendors.values()
        } | {listing.location_id for listing in self.player_listings.values()}
        for location_id in sorted(locations):
            population = self.runtime.population_location_state(location_id)
            segment_totals = dict(population["segment_totals"])
            region = self._region(location_id)
            demand_index, supply_index = regional_pressure(segment_totals, int(population["headcount"]))
            region.set_pressure(demand_index, supply_index, tick_ms=tick_ms)
            location_demand = 0
            location_supply = 0
            vendor_rows = []
            for vendor in sorted(
                (row for row in self.vendors.values() if row.location_id == location_id),
                key=lambda row: row.vendor_id,
            ):
                stock = self._stock(vendor.vendor_id)
                item_rows = []
                for listing in vendor.listings:
                    template_id = listing.template_id
                    production = background_supply_units(self.runtime.catalog, template_id, segment_totals)
                    system_units = system_restock_units(
                        stock.available(template_id),
                        stock.target_by_template[template_id],
                    )
                    supplied = stock.restock(template_id, production + system_units)
                    demanded = background_demand_units(self.runtime.catalog, template_id, segment_totals)
                    consumed = min(stock.available(template_id), demanded)
                    if consumed:
                        stock.consume(template_id, consumed)
                    location_supply += supplied
                    location_demand += consumed
                    item_rows.append(
                        {
                            "template_id": template_id,
                            "production_units": production,
                            "system_restock_units": max(0, supplied - production),
                            "background_consumed_units": consumed,
                            "stock_after": stock.available(template_id),
                            "current_unit_price_col": self.vendor_quote(vendor.vendor_id, template_id)["current_unit_price_col"],
                        }
                    )
                vendor_rows.append({"vendor_id": vendor.vendor_id, "items": item_rows})
            region.record_background(demand_units=location_demand, production_units=location_supply)
            market_units, market_col = self._clear_background_player_market(
                location_id=location_id,
                segment_totals=segment_totals,
                tick_ms=tick_ms,
            )
            if market_units:
                region.record_player_market(units=market_units, gross_col=market_col)
            self._record_market(
                "economy_tick",
                at_ms=tick_ms,
                location_id=location_id,
                population_headcount=int(population["headcount"]),
                segment_totals=segment_totals,
                demand_index=region.demand_index,
                supply_index=region.supply_index,
                background_vendor_demand_units=location_demand,
                background_supply_units=location_supply,
                background_player_market_units=market_units,
                background_player_market_col=market_col,
                vendors=vendor_rows,
            )
        self.next_tick_at_ms += ECONOMY_TICK_MS
        self.assert_living_market_authority()

    def vendor_state(self, vendor_id: str) -> dict[str, Any]:
        vendor = self.vendors[vendor_id]
        return {
            "vendor_id": vendor_id,
            "name": vendor.name,
            "location_id": vendor.location_id,
            "buyback_rate": vendor.buyback_rate,
            "listings": [self.vendor_quote(vendor_id, row.template_id) for row in vendor.listings],
        }

    def location_market_state(self, location_id: str) -> dict[str, Any]:
        location = self.runtime.world_map.locations[location_id]
        region = self._region(location_id)
        listings = [
            {
                "listing_id": listing.listing_id,
                "seller_id": listing.seller_id,
                "template_id": listing.item.template_id,
                "quantity": listing.item.quantity,
                "unit_price_col": listing.unit_price_col,
                "reference_unit_price_col": self.reference_unit_price(location_id, listing.item.template_id),
                "created_at_ms": listing.created_at_ms,
            }
            for listing in sorted(self.player_listings.values(), key=lambda row: row.listing_id)
            if listing.location_id == location_id
        ]
        guilds = {}
        relationships = getattr(self.runtime, "relationships", None)
        if relationships is not None:
            for guild_id, guild in sorted(relationships.guilds.items()):
                if guild.headquarters_location_id != location_id:
                    continue
                storage = relationships.storages[guild.storage_id]
                templates: dict[str, int] = {}
                for item in storage.items.values():
                    templates[item.template_id] = templates.get(item.template_id, 0) + item.quantity
                guilds[guild_id] = {
                    "vault_col": guild.vault_col,
                    "storage_id": guild.storage_id,
                    "storage_templates": templates,
                }
        return {
            "location_id": location_id,
            "floor_number": location.floor_number,
            "population": self.runtime.population_location_state(location_id),
            "market": market_state_row(region),
            "vendors": [
                self.vendor_state(vendor.vendor_id)
                for vendor in sorted(self.vendors.values(), key=lambda row: row.vendor_id)
                if vendor.location_id == location_id
            ],
            "player_listings": listings,
            "guild_headquarters": guilds,
        }

    def state(self, location_id: str | None = None) -> dict[str, Any]:
        self.assert_living_market_authority()
        if location_id is not None:
            return {
                "world_now_ms": self.runtime.world.now_ms,
                "next_tick_at_ms": self.next_tick_at_ms,
                "tick_interval_ms": ECONOMY_TICK_MS,
                "location": self.location_market_state(location_id),
            }
        locations = sorted(
            set(self.regional_markets)
            | {vendor.location_id for vendor in self.vendors.values()}
            | {listing.location_id for listing in self.player_listings.values()}
        )
        return {
            "world_now_ms": self.runtime.world.now_ms,
            "next_tick_at_ms": self.next_tick_at_ms,
            "tick_interval_ms": ECONOMY_TICK_MS,
            "locations": {location_id: self.location_market_state(location_id) for location_id in locations},
        }

    def assert_living_market_authority(self) -> None:
        if self.next_tick_at_ms <= self.runtime.world.now_ms:
            raise RuntimeError("living economy next tick must be in the future")
        for vendor_id, vendor in self.vendors.items():
            if vendor_id not in self.vendor_stocks:
                raise RuntimeError(f"living economy lacks vendor stock state: {vendor_id}")
            stock = self.vendor_stocks[vendor_id]
            listing_ids = {listing.template_id for listing in vendor.listings}
            if set(stock.stock_by_template) != listing_ids:
                raise RuntimeError(f"vendor stock assortment disagrees with vendor definition: {vendor_id}")
        unknown_vendors = set(self.vendor_stocks) - set(self.vendors)
        if unknown_vendors:
            raise RuntimeError(f"living economy stock references unknown vendors: {sorted(unknown_vendors)}")
        for location_id, region in self.regional_markets.items():
            if location_id != region.location_id or location_id not in self.runtime.world_map.locations:
                raise RuntimeError(f"regional economy references invalid location: {location_id}")
            if region.last_tick_ms > self.runtime.world.now_ms:
                raise RuntimeError("regional economy tick is in the future")
        for row in self.market_history:
            if int(row["at_ms"]) > self.runtime.world.now_ms:
                raise RuntimeError("economy history cannot be in the future")
        for listing_id, listing in self.player_listings.items():
            if listing.location_id not in self.runtime.world_map.locations:
                raise RuntimeError(f"player listing references unknown location: {listing_id}")
            if listing.seller_id not in self.runtime.actors:
                raise RuntimeError(f"player listing references unknown seller: {listing_id}")

    def dump_state(self) -> dict:
        self.assert_living_market_authority()
        payload = super().dump_state()
        payload["mode"] = "living"
        payload.update(
            {
                "next_tick_at_ms": self.next_tick_at_ms,
                "vendor_stocks": {
                    vendor_id: asdict(stock)
                    for vendor_id, stock in self.vendor_stocks.items()
                },
                "regional_markets": {
                    location_id: asdict(region)
                    for location_id, region in self.regional_markets.items()
                },
                "market_history": list(self.market_history),
            }
        )
        return payload

    def load_state(self, payload: dict) -> None:
        super().load_state(payload)
        schema = payload.get("schema")
        mode = payload.get("mode")
        if not payload or schema is None or mode in {None, "transactional"}:
            # The older/transactional subsystem had no market-loop state to reconstruct. Its exact
            # listings are preserved above; the new living market begins from a fresh current-time baseline.
            listings = dict(self.player_listings)
            self._reset_living_market_state()
            self.player_listings = listings
            return
        if schema != ECONOMY_STATE_SCHEMA or mode != "living":
            raise ValueError("unsupported living economy state")
        next_tick_at_ms = int(payload["next_tick_at_ms"])
        if next_tick_at_ms <= self.runtime.world.now_ms:
            raise ValueError("living economy save next tick must be after current world time")
        stocks: dict[str, VendorStockState] = {}
        for vendor_id, row in payload.get("vendor_stocks", {}).items():
            stocks[vendor_id] = VendorStockState(
                vendor_id=row["vendor_id"],
                stock_by_template={str(k): int(v) for k, v in row["stock_by_template"].items()},
                target_by_template={str(k): int(v) for k, v in row["target_by_template"].items()},
                revision=int(row.get("revision", 0)),
            )
            if stocks[vendor_id].vendor_id != vendor_id:
                raise ValueError("vendor stock save key/id mismatch")
        markets: dict[str, RegionalMarketState] = {}
        for location_id, row in payload.get("regional_markets", {}).items():
            markets[location_id] = RegionalMarketState(
                location_id=row["location_id"],
                demand_index=float(row["demand_index"]),
                supply_index=float(row["supply_index"]),
                last_tick_ms=int(row["last_tick_ms"]),
                cumulative_background_demand_units=int(row.get("cumulative_background_demand_units", 0)),
                cumulative_production_units=int(row.get("cumulative_production_units", 0)),
                cumulative_player_market_units=int(row.get("cumulative_player_market_units", 0)),
                cumulative_player_market_col=int(row.get("cumulative_player_market_col", 0)),
                cumulative_named_trade_col=int(row.get("cumulative_named_trade_col", 0)),
                system_col_injected=int(row.get("system_col_injected", 0)),
                revision=int(row.get("revision", 0)),
            )
            if markets[location_id].location_id != location_id:
                raise ValueError("regional market save key/id mismatch")
        self.vendor_stocks = stocks
        self.regional_markets = markets
        self.market_history = list(payload.get("market_history", []))
        self.next_tick_at_ms = next_tick_at_ms
        self.assert_living_market_authority()


def make_runtime_economy(runtime) -> EconomyRuntime:
    if hasattr(runtime, "validate_item_disposition"):
        return GuardedEconomyRuntime(runtime)
    return EconomyRuntime()
