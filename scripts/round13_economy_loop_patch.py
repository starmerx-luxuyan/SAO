from pathlib import Path


def write(path: str, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor missing in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


write(
    "src/sao_mcp/rules/economy_loop.py",
    '''from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


ECONOMY_TICK_MS = 60 * 60 * 1000
MIN_PRICE_MULTIPLIER = 0.65
MAX_PRICE_MULTIPLIER = 1.75
MAX_VENDOR_STOCK_MULTIPLIER = 2


class MarketItemClass(StrEnum):
    CONSUMABLE = "consumable"
    EQUIPMENT = "equipment"
    MATERIAL = "material"


@dataclass(slots=True)
class VendorStockState:
    vendor_id: str
    stock_by_template: dict[str, int]
    target_by_template: dict[str, int]
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.vendor_id:
            raise ValueError("vendor stock requires vendor_id")
        if set(self.stock_by_template) != set(self.target_by_template):
            raise ValueError("vendor stock/target template sets must match")
        if any(not key for key in self.stock_by_template):
            raise ValueError("vendor stock template ids must be non-empty")
        if any(value < 0 for value in self.stock_by_template.values()):
            raise ValueError("vendor stock cannot be negative")
        if any(value <= 0 for value in self.target_by_template.values()):
            raise ValueError("vendor target stock must be positive")

    def available(self, template_id: str) -> int:
        return self.stock_by_template[template_id]

    def consume(self, template_id: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("vendor stock consumption must be positive")
        if quantity > self.stock_by_template[template_id]:
            raise ValueError("vendor stock is insufficient")
        self.stock_by_template[template_id] -= quantity
        self.revision += 1

    def restock(self, template_id: str, quantity: int) -> int:
        if quantity <= 0:
            return 0
        target = self.target_by_template[template_id]
        cap = target * MAX_VENDOR_STOCK_MULTIPLIER
        before = self.stock_by_template[template_id]
        self.stock_by_template[template_id] = min(cap, before + quantity)
        added = self.stock_by_template[template_id] - before
        if added:
            self.revision += 1
        return added


@dataclass(slots=True)
class RegionalMarketState:
    location_id: str
    demand_index: float = 1.0
    supply_index: float = 1.0
    last_tick_ms: int = 0
    cumulative_background_demand_units: int = 0
    cumulative_production_units: int = 0
    cumulative_player_market_units: int = 0
    cumulative_player_market_col: int = 0
    cumulative_named_trade_col: int = 0
    system_col_injected: int = 0
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.location_id:
            raise ValueError("regional market requires location_id")
        if self.last_tick_ms < 0:
            raise ValueError("regional market last_tick_ms cannot be negative")
        if self.demand_index < 0 or self.supply_index < 0:
            raise ValueError("regional market indices cannot be negative")
        for value in (
            self.cumulative_background_demand_units,
            self.cumulative_production_units,
            self.cumulative_player_market_units,
            self.cumulative_player_market_col,
            self.cumulative_named_trade_col,
            self.system_col_injected,
        ):
            if value < 0:
                raise ValueError("regional market cumulative counters cannot be negative")

    def set_pressure(self, demand_index: float, supply_index: float, *, tick_ms: int) -> None:
        if tick_ms < self.last_tick_ms:
            raise ValueError("regional market tick cannot move backward")
        if demand_index < 0 or supply_index < 0:
            raise ValueError("regional market pressure cannot be negative")
        self.demand_index = float(demand_index)
        self.supply_index = float(supply_index)
        self.last_tick_ms = int(tick_ms)
        self.revision += 1

    def record_background(self, *, demand_units: int = 0, production_units: int = 0) -> None:
        if demand_units < 0 or production_units < 0:
            raise ValueError("background market units cannot be negative")
        self.cumulative_background_demand_units += demand_units
        self.cumulative_production_units += production_units
        if demand_units or production_units:
            self.revision += 1

    def record_player_market(self, *, units: int, gross_col: int) -> None:
        if units <= 0 or gross_col <= 0:
            raise ValueError("background player-market settlement must be positive")
        self.cumulative_player_market_units += units
        self.cumulative_player_market_col += gross_col
        self.system_col_injected += gross_col
        self.revision += 1

    def record_named_trade(self, gross_col: int) -> None:
        if gross_col < 0:
            raise ValueError("named market trade cannot have negative Col volume")
        if gross_col:
            self.cumulative_named_trade_col += gross_col
            self.revision += 1


def market_item_class(catalog, template_id: str) -> MarketItemClass:
    catalog.item(template_id)
    if template_id in catalog.consumables:
        return MarketItemClass.CONSUMABLE
    if template_id in catalog.weapons or template_id in catalog.armors:
        return MarketItemClass.EQUIPMENT
    return MarketItemClass.MATERIAL


def target_stock_for_template(catalog, template_id: str) -> int:
    item_class = market_item_class(catalog, template_id)
    if item_class is MarketItemClass.CONSUMABLE:
        return 80
    if item_class is MarketItemClass.EQUIPMENT:
        return 12
    return 48


def regional_pressure(segment_totals: dict[str, int], headcount: int) -> tuple[float, float]:
    if headcount <= 0:
        return 1.0, 1.0
    frontline = int(segment_totals.get("frontline", 0))
    mid_tier = int(segment_totals.get("mid_tier", 0))
    casual = int(segment_totals.get("casual", 0))
    production = int(segment_totals.get("production", 0))
    demand = (
        frontline * 1.50
        + mid_tier * 1.15
        + casual * 0.75
        + production * 0.65
    ) / headcount
    supply = (production * 1.80 + mid_tier * 0.15) / headcount
    return round(demand, 6), round(supply, 6)


def background_demand_units(catalog, template_id: str, segment_totals: dict[str, int]) -> int:
    frontline = int(segment_totals.get("frontline", 0))
    mid_tier = int(segment_totals.get("mid_tier", 0))
    casual = int(segment_totals.get("casual", 0))
    production = int(segment_totals.get("production", 0))
    item_class = market_item_class(catalog, template_id)
    if item_class is MarketItemClass.CONSUMABLE:
        raw = frontline / 20 + mid_tier / 45 + casual / 120 + production / 80
    elif item_class is MarketItemClass.EQUIPMENT:
        raw = frontline / 100 + mid_tier / 180 + casual / 500 + production / 400
    else:
        raw = production / 70 + frontline / 140 + mid_tier / 90 + casual / 300
    return max(0, int(round(raw)))


def background_supply_units(catalog, template_id: str, segment_totals: dict[str, int]) -> int:
    production = int(segment_totals.get("production", 0))
    item_class = market_item_class(catalog, template_id)
    if item_class is MarketItemClass.CONSUMABLE:
        raw = production / 45
    elif item_class is MarketItemClass.EQUIPMENT:
        raw = production / 140
    else:
        raw = production / 20
    return max(0, int(round(raw)))


def system_restock_units(current_stock: int, target_stock: int) -> int:
    if current_stock >= target_stock:
        return 0
    return min(target_stock - current_stock, max(1, target_stock // 12))


def price_multiplier(region: RegionalMarketState, *, stock: int, target_stock: int) -> float:
    if target_stock <= 0:
        raise ValueError("target_stock must be positive")
    scarcity = (target_stock - stock) / target_stock
    pressure_gap = region.demand_index - region.supply_index
    value = 1.0 + pressure_gap * 0.22 + scarcity * 0.40
    return round(max(MIN_PRICE_MULTIPLIER, min(MAX_PRICE_MULTIPLIER, value)), 6)


def market_state_row(region: RegionalMarketState) -> dict[str, Any]:
    return {
        "location_id": region.location_id,
        "demand_index": region.demand_index,
        "supply_index": region.supply_index,
        "last_tick_ms": region.last_tick_ms,
        "cumulative_background_demand_units": region.cumulative_background_demand_units,
        "cumulative_production_units": region.cumulative_production_units,
        "cumulative_player_market_units": region.cumulative_player_market_units,
        "cumulative_player_market_col": region.cumulative_player_market_col,
        "cumulative_named_trade_col": region.cumulative_named_trade_col,
        "system_col_injected": region.system_col_injected,
        "revision": region.revision,
    }
''',
)

# EconomyRuntime remains the atomic transaction authority. Add overridable market hooks without
# teaching the low-level transaction object about population, guilds, or world time.
economy_path = Path("src/sao_mcp/rules/economy.py")
economy = economy_path.read_text(encoding="utf-8")
economy = economy.replace("from typing import Callable", "from typing import Any, Callable", 1)
economy = economy.replace(
    "from sao_mcp.rules.inventory import add_item, can_receive, carry_capacity, inventory_weight\n",
    "from sao_mcp.rules.inventory import add_item, can_receive, carry_capacity, inventory_weight\n\n\nECONOMY_STATE_SCHEMA = \"economy.v2\"\n",
    1,
)
old_hooks = '''    def _income(self, actor: CombatantState, amount: int, source: str) -> None:\n        if self.on_income is not None and amount:\n            self.on_income(actor, amount, source)\n\n    def _expense(self, actor: CombatantState, amount: int, source: str) -> None:\n        if self.on_expense is not None and amount:\n            self.on_expense(actor, amount, source)\n\n    def vendor_catalog(self, vendor_id: str) -> VendorDefinition:\n        return self.vendors[vendor_id]\n'''
new_hooks = '''    def _income(self, actor: CombatantState, amount: int, source: str) -> Any:\n        if self.on_income is not None and amount:\n            return self.on_income(actor, amount, source)\n        return None\n\n    def _expense(self, actor: CombatantState, amount: int, source: str) -> Any:\n        if self.on_expense is not None and amount:\n            return self.on_expense(actor, amount, source)\n        return None\n\n    @staticmethod\n    def _base_item_value(template_id: str, catalog: Catalog) -> int:\n        template = catalog.item(template_id)\n        base = template.base_value_col\n        if base is not None:\n            return int(base)\n        if template_id in catalog.weapons:\n            weapon = catalog.weapons[template_id]\n            return max(10, int(round((weapon.attack_min + weapon.attack_max) * 1.8)))\n        if template_id in catalog.armors:\n            armor = catalog.armors[template_id]\n            return max(8, armor.armor * 2)\n        return 5\n\n    def _vendor_unit_price(self, vendor_id: str, listing) -> int:\n        return int(listing.unit_price_col)\n\n    def _validate_vendor_purchase_quantity(self, vendor_id: str, template_id: str, quantity: int) -> None:\n        return None\n\n    def _vendor_buyback_multiplier(self, vendor_id: str, template_id: str) -> float:\n        return 1.0\n\n    def _commit_vendor_purchase(\n        self,\n        *,\n        vendor_id: str,\n        template_id: str,\n        quantity: int,\n        unit_price_col: int,\n        total_col: int,\n    ) -> None:\n        return None\n\n    def _commit_vendor_sale(\n        self,\n        *,\n        vendor_id: str,\n        template_id: str,\n        quantity: int,\n        received_col: int,\n    ) -> None:\n        return None\n\n    def _commit_player_purchase(\n        self,\n        *,\n        location_id: str,\n        template_id: str,\n        quantity: int,\n        total_col: int,\n    ) -> None:\n        return None\n\n    def vendor_catalog(self, vendor_id: str) -> VendorDefinition:\n        return self.vendors[vendor_id]\n'''
if old_hooks not in economy:
    raise RuntimeError("economy hook anchor missing")
economy = economy.replace(old_hooks, new_hooks, 1)
old_purchase = '''        total = listing.unit_price_col * quantity\n        if buyer.col < total:\n            raise ValueError("insufficient Col")\n'''
new_purchase = '''        self._validate_vendor_purchase_quantity(vendor_id, template_id, quantity)\n        unit_price_col = self._vendor_unit_price(vendor_id, listing)\n        if unit_price_col < 1:\n            raise RuntimeError("vendor quote must remain positive")\n        total = unit_price_col * quantity\n        if buyer.col < total:\n            raise ValueError("insufficient Col")\n'''
if old_purchase not in economy:
    raise RuntimeError("vendor purchase price anchor missing")
economy = economy.replace(old_purchase, new_purchase, 1)
old_purchase_commit = '''        self._expense(buyer, total, "vendor_purchase")\n        return VendorPurchaseResolution(\n'''
new_purchase_commit = '''        self._expense(buyer, total, "vendor_purchase")\n        self._commit_vendor_purchase(\n            vendor_id=vendor_id,\n            template_id=template_id,\n            quantity=quantity,\n            unit_price_col=unit_price_col,\n            total_col=total,\n        )\n        return VendorPurchaseResolution(\n'''
if old_purchase_commit not in economy:
    raise RuntimeError("vendor purchase commit anchor missing")
economy = economy.replace(old_purchase_commit, new_purchase_commit, 1)
old_sale_value = '''        template = catalog.item(item.template_id)\n        base = template.base_value_col\n        if base is None:\n            if item.template_id in catalog.weapons:\n                weapon = catalog.weapons[item.template_id]\n                base = max(10, int(round((weapon.attack_min + weapon.attack_max) * 1.8)))\n            elif item.template_id in catalog.armors:\n                armor = catalog.armors[item.template_id]\n                base = max(8, armor.armor * 2)\n            else:\n                base = 5\n        condition = 1.0\n'''
new_sale_value = '''        base = self._base_item_value(item.template_id, catalog)\n        condition = 1.0\n'''
if old_sale_value not in economy:
    raise RuntimeError("vendor sale value anchor missing")
economy = economy.replace(old_sale_value, new_sale_value, 1)
old_received = '''        received = max(1, int(round(base * qty * vendor.buyback_rate * condition * quality)))\n'''
new_received = '''        received = max(\n            1,\n            int(\n                round(\n                    base\n                    * qty\n                    * vendor.buyback_rate\n                    * condition\n                    * quality\n                    * self._vendor_buyback_multiplier(vendor_id, item.template_id)\n                )\n            ),\n        )\n'''
if old_received not in economy:
    raise RuntimeError("vendor sale received anchor missing")
economy = economy.replace(old_received, new_received, 1)
old_sale_commit = '''        self._income(seller, received, "vendor_sale")\n        return VendorSaleResolution(vendor_id, seller.actor_id, item.template_id, qty, received)\n'''
new_sale_commit = '''        self._income(seller, received, "vendor_sale")\n        self._commit_vendor_sale(\n            vendor_id=vendor_id,\n            template_id=item.template_id,\n            quantity=qty,\n            received_col=received,\n        )\n        return VendorSaleResolution(vendor_id, seller.actor_id, item.template_id, qty, received)\n'''
if old_sale_commit not in economy:
    raise RuntimeError("vendor sale commit anchor missing")
economy = economy.replace(old_sale_commit, new_sale_commit, 1)
old_player_commit = '''        self._expense(buyer, total, "player_market_purchase")\n        self._income(seller, total, "player_market_sale")\n        return PlayerPurchaseResolution(\n'''
new_player_commit = '''        self._expense(buyer, total, "player_market_purchase")\n        self._income(seller, total, "player_market_sale")\n        self._commit_player_purchase(\n            location_id=listing.location_id,\n            template_id=moving.template_id,\n            quantity=qty,\n            total_col=total,\n        )\n        return PlayerPurchaseResolution(\n'''
if old_player_commit not in economy:
    raise RuntimeError("player purchase commit anchor missing")
economy = economy.replace(old_player_commit, new_player_commit, 1)
marker = "    def dump_state(self) -> dict:\n"
index = economy.find(marker)
if index < 0:
    raise RuntimeError("economy dump marker missing")
economy = economy[:index] + '''    def dump_state(self) -> dict:\n        return {\n            "schema": ECONOMY_STATE_SCHEMA,\n            "mode": "transactional",\n            "player_listings": {\n                listing_id: {\n                    "listing_id": listing.listing_id,\n                    "seller_id": listing.seller_id,\n                    "location_id": listing.location_id,\n                    "item": asdict(listing.item),\n                    "unit_price_col": listing.unit_price_col,\n                    "created_at_ms": listing.created_at_ms,\n                }\n                for listing_id, listing in self.player_listings.items()\n            },\n        }\n\n    def load_state(self, payload: dict) -> None:\n        schema = payload.get("schema")\n        if schema not in {None, ECONOMY_STATE_SCHEMA}:\n            if payload.get("player_listings"):\n                raise ValueError(f"unsupported non-empty economy schema: {schema!r}")\n            self.player_listings = {}\n            return\n        self.player_listings = {}\n        for listing_id, value in payload.get("player_listings", {}).items():\n            if value.get("listing_id") != listing_id:\n                raise ValueError(f"economy listing key/id mismatch: {listing_id}")\n            if "location_id" not in value:\n                raise ValueError("legacy player listing lacks authoritative physical location")\n            item_payload = dict(value["item"])\n            enhancements = item_payload.get("enhancements", {})\n            from sao_mcp.domain.models import EnhancementTrack\n\n            item_payload["enhancements"] = {EnhancementTrack(key): int(level) for key, level in enhancements.items()}\n            self.player_listings[listing_id] = PlayerListing(\n                listing_id=value["listing_id"],\n                seller_id=value["seller_id"],\n                location_id=value["location_id"],\n                item=ItemInstance(**item_payload),\n                unit_price_col=int(value["unit_price_col"]),\n                created_at_ms=int(value["created_at_ms"]),\n            )\n'''
economy_path.write_text(economy, encoding="utf-8")

write(
    "src/sao_mcp/runtime/property_economy.py",
    '''from __future__ import annotations

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
''',
)

write(
    "src/sao_mcp/runtime/economy_loop_runtime.py",
    '''from __future__ import annotations

from typing import Any

from sao_mcp.runtime.community_hooks import attach_community_economy
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime
from sao_mcp.runtime.property_economy import GuardedEconomyRuntime, make_runtime_economy


class EconomyLoopAincradRuntime(PopulationAincradRuntime):
    """Top-level runtime that resolves the living Aincrad economy on world-time boundaries."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        economy = make_runtime_economy(self)
        if not isinstance(economy, GuardedEconomyRuntime):
            raise RuntimeError("Aincrad economy loop requires the runtime-bound economy authority")
        self.economy: GuardedEconomyRuntime = economy
        attach_community_economy(self, self.economy)
        self.register_world_advance_hook(self._resolve_due_economy_activities)

    def _resolve_due_economy_activities(self, before_ms: int, after_ms: int) -> None:
        while self.economy.next_tick_at_ms <= after_ms:
            tick_ms = self.economy.next_tick_at_ms
            if tick_ms != after_ms:
                raise RuntimeError("economy tick boundary was skipped by world scheduler")
            self.economy.advance_living_market_tick(tick_ms)

    def _next_scheduler_boundary(self, target_ms: int) -> int:
        boundary = super()._next_scheduler_boundary(target_ms)
        now = self.world.now_ms
        tick = self.economy.next_tick_at_ms
        if now < tick <= target_ms:
            return min(boundary, tick)
        return boundary

    def aincrad_economy_state(self, location_id: str | None = None) -> dict[str, Any]:
        return self.economy.state(location_id)

    def economy_vendor_state(self, vendor_id: str) -> dict[str, Any]:
        return self.economy.vendor_state(vendor_id)

    def economy_history(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self.economy.market_history
        if limit is None:
            return list(rows)
        if limit < 1:
            raise ValueError("economy history limit must be positive")
        return list(rows[-limit:])
''',
)

# System vendors in the living runtime use finite renewable stock. Their exact stock targets remain
# simulation calibration in the runtime rather than pretending to be canon data.
corpus_path = Path("src/sao_mcp/corpus/economy.py")
corpus = corpus_path.read_text(encoding="utf-8")
if corpus.count("infinite_stock=True") != 2:
    raise RuntimeError("unexpected core vendor infinite-stock anchors")
corpus = corpus.replace("infinite_stock=True", "infinite_stock=False")
corpus_path.write_text(corpus, encoding="utf-8")

# Community wrappers previously settled the same callback-backed transaction a second time.
community_path = Path("src/sao_mcp/runtime/community_runtime.py")
community = community_path.read_text(encoding="utf-8")
community = community.replace(
'''        result = economy.buy_from_vendor(\n            actor, vendor_id, template_id, quantity, self.catalog, actor_location_id=actor.location_id\n        )\n        self._settle_expense_after_existing_debit(actor_id, result.total_col)\n        return result\n''',
'''        return economy.buy_from_vendor(\n            actor, vendor_id, template_id, quantity, self.catalog, actor_location_id=actor.location_id\n        )\n''',
1,
)
community = community.replace(
'''        result = economy.sell_to_vendor(\n            actor, vendor_id, instance_id, self.catalog,\n            quantity=quantity, actor_location_id=actor.location_id,\n        )\n        self._settle_income_after_existing_credit(actor_id, result.received_col, source="vendor_sale")\n        return result\n''',
'''        return economy.sell_to_vendor(\n            actor, vendor_id, instance_id, self.catalog,\n            quantity=quantity, actor_location_id=actor.location_id,\n        )\n''',
1,
)
community = community.replace(
'''        result = economy.buy_player_listing(\n            buyer, seller, listing_id, self.catalog,\n            buyer_location_id=buyer.location_id, quantity=quantity,\n        )\n        self._settle_expense_after_existing_debit(buyer_id, result.total_col)\n        self._settle_income_after_existing_credit(seller_id, result.total_col, source="player_market_sale")\n        return result\n''',
'''        return economy.buy_player_listing(\n            buyer, seller, listing_id, self.catalog,\n            buyer_location_id=buyer.location_id, quantity=quantity,\n        )\n''',
1,
)
community_path.write_text(community, encoding="utf-8")

# Guild tax reads the GuildState membership ledger rather than the actor.guild_id projection.
relationships_path = Path("src/sao_mcp/rules/relationships.py")
relationships = relationships_path.read_text(encoding="utf-8")
old_tax = '''    def guild_tax_for(self, actor: CombatantState, gross_col: int) -> tuple[int, GuildState | None]:\n        if gross_col <= 0 or not actor.guild_id or actor.guild_id not in self.guilds:\n            return 0, None\n        guild = self.guilds[actor.guild_id]\n        return max(0, int(gross_col * guild.tax_rate)), guild\n'''
new_tax = '''    def guild_tax_for(self, actor: CombatantState, gross_col: int) -> tuple[int, GuildState | None]:\n        if gross_col <= 0:\n            return 0, None\n        matches = [guild for guild in self.guilds.values() if actor.actor_id in guild.member_ids]\n        if len(matches) > 1:\n            raise RuntimeError(f"actor belongs to multiple authoritative guilds: {actor.actor_id}")\n        if not matches:\n            return 0, None\n        guild = matches[0]\n        return max(0, int(gross_col * guild.tax_rate)), guild\n'''
if old_tax not in relationships:
    raise RuntimeError("guild tax anchor missing")
relationships_path.write_text(relationships.replace(old_tax, new_tax, 1), encoding="utf-8")

# Community economy callbacks now return their authoritative settlement row so background-market
# clearing can retain the tax provenance without creating another finance ledger.
hooks_path = Path("src/sao_mcp/runtime/community_hooks.py")
hooks = hooks_path.read_text(encoding="utf-8")
hooks = hooks.replace(
'''    def on_income(actor, amount: int, source: str) -> None:\n        runtime._settle_income_after_existing_credit(actor.actor_id, amount, source=source)\n\n    def on_expense(actor, amount: int, source: str) -> None:\n        runtime._settle_expense_after_existing_debit(actor.actor_id, amount)\n''',
'''    def on_income(actor, amount: int, source: str):\n        return runtime._settle_income_after_existing_credit(actor.actor_id, amount, source=source)\n\n    def on_expense(actor, amount: int, source: str):\n        return runtime._settle_expense_after_existing_debit(actor.actor_id, amount)\n''',
1,
)
hooks_path.write_text(hooks, encoding="utf-8")

# Default server and save restoration use the new single-inheritance top runtime. Economy creation is
# no longer repeated in bootstrap or persistence.
bootstrap_path = Path("src/sao_mcp/server_bootstrap.py")
bootstrap = bootstrap_path.read_text(encoding="utf-8")
bootstrap = bootstrap.replace("from sao_mcp.runtime.community_hooks import attach_community_economy\n", "")
bootstrap = bootstrap.replace(
    "from sao_mcp.runtime.population_runtime import PopulationAincradRuntime\nfrom sao_mcp.runtime.property_economy import make_runtime_economy\n",
    "from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime\n",
)
bootstrap = bootstrap.replace(
'''if not isinstance(core_server.runtime, PopulationAincradRuntime):\n    core_server.runtime = PopulationAincradRuntime(seed=0xA1C0)\n''',
'''if not isinstance(core_server.runtime, EconomyLoopAincradRuntime):\n    core_server.runtime = EconomyLoopAincradRuntime(seed=0xA1C0)\n''',
1,
)
bootstrap = bootstrap.replace(
'''if not hasattr(runtime, "economy"):\n    runtime.economy = make_runtime_economy(runtime)\nattach_community_economy(runtime, runtime.economy)\n\n''',
"",
1,
)
bootstrap_path.write_text(bootstrap, encoding="utf-8")

persistence_path = Path("src/sao_mcp/runtime/persistence.py")
persistence = persistence_path.read_text(encoding="utf-8")
persistence = persistence.replace(
'''        from sao_mcp.runtime.population_runtime import PopulationAincradRuntime\n        from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario\n\n        runtime: GameRuntime = PopulationAincradRuntime()\n''',
'''        from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime\n        from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario\n\n        runtime: GameRuntime = EconomyLoopAincradRuntime()\n''',
1,
)
persistence = persistence.replace(
'''    from sao_mcp.runtime.property_economy import make_runtime_economy\n\n    economy = make_runtime_economy(runtime)\n    runtime.economy = economy\n    economy.load_state(payload.get("economy_state", {}))\n''',
'''    from sao_mcp.runtime.property_economy import make_runtime_economy\n\n    economy = getattr(runtime, "economy", None)\n    if economy is None:\n        economy = make_runtime_economy(runtime)\n        runtime.economy = economy\n    economy.load_state(payload.get("economy_state", {}))\n''',
1,
)
persistence_path.write_text(persistence, encoding="utf-8")

# Add living economy inspection and quote tools while preserving the existing transactional tools.
server_path = Path("src/sao_mcp/server_economy.py")
server = server_path.read_text(encoding="utf-8")
anchor = '''def register_economy_tools(mcp, runtime, economy: EconomyRuntime) -> None:\n    @mcp.tool()\n    def list_vendors(location_id: str | None = None) -> str:\n'''
insert = '''def register_economy_tools(mcp, runtime, economy: EconomyRuntime) -> None:\n    @mcp.tool()\n    def get_aincrad_economy_state(location_id: str | None = None) -> str:\n        """Inspect living regional supply/demand, vendor stock, prices, population and guild-HQ resources."""\n        state = getattr(runtime, "aincrad_economy_state", None)\n        if state is None:\n            raise RuntimeError("living economy state is unavailable on this runtime")\n        return _json(state(location_id))\n\n    @mcp.tool()\n    def quote_vendor_item(vendor_id: str, template_id: str) -> str:\n        """Quote current finite stock and population-sensitive price for one NPC vendor item."""\n        quote = getattr(economy, "vendor_quote", None)\n        if quote is None:\n            raise RuntimeError("living vendor quotes are unavailable on this economy runtime")\n        return _json(quote(vendor_id, template_id))\n\n    @mcp.tool()\n    def get_economy_history(limit: int = 50) -> str:\n        """Inspect recent committed named/background market flows and hourly economy ticks."""\n        history = getattr(runtime, "economy_history", None)\n        if history is None:\n            raise RuntimeError("living economy history is unavailable on this runtime")\n        return _json({"events": history(limit=limit)})\n\n    @mcp.tool()\n    def list_vendors(location_id: str | None = None) -> str:\n'''
if anchor not in server:
    raise RuntimeError("server economy anchor missing")
server = server.replace(anchor, insert, 1)
old_rows = '''        rows = []\n        for vendor in economy.vendors.values():\n            if location_id is not None and vendor.location_id != location_id:\n                continue\n            rows.append(asdict(vendor))\n        return _json({"vendors": rows})\n'''
new_rows = '''        rows = []\n        living_state = getattr(economy, "vendor_state", None)\n        for vendor in economy.vendors.values():\n            if location_id is not None and vendor.location_id != location_id:\n                continue\n            rows.append(living_state(vendor.vendor_id) if living_state is not None else asdict(vendor))\n        return _json({"vendors": rows})\n'''
if old_rows not in server:
    raise RuntimeError("vendor list body anchor missing")
server_path.write_text(server.replace(old_rows, new_rows, 1), encoding="utf-8")

write(
    "tests/test_economy_loop.py",
    '''import pytest

from sao_mcp.rules.economy_loop import ECONOMY_TICK_MS
from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


TOWN = "floor_1_town_of_beginnings"
WEST = "floor_1_west_field"
VENDOR = "npc_vendor_town_of_beginnings"


def test_named_vendor_purchase_consumes_real_stock_and_requotes_from_scarcity():
    runtime = EconomyLoopAincradRuntime(seed=601)
    buyer = runtime.create_character("Buyer")
    buyer.col = 10_000
    before = runtime.economy.vendor_quote(VENDOR, "field_bread")
    result = runtime.economy.buy_from_vendor(
        buyer,
        VENDOR,
        "field_bread",
        10,
        runtime.catalog,
        actor_location_id=buyer.location_id,
    )
    after = runtime.economy.vendor_quote(VENDOR, "field_bread")
    assert after["stock"] == before["stock"] - 10
    assert buyer.col == 10_000 - result.total_col
    assert after["current_unit_price_col"] >= before["current_unit_price_col"]
    assert runtime.economy.market_history[-1]["event"] == "named_vendor_purchase"


def test_hourly_population_tick_consumes_stock_and_production_changes_supply_pressure():
    runtime = EconomyLoopAincradRuntime(seed=602)
    runtime.add_population_cohort("frontline", "frontline", 400, TOWN, 8.0, "clearing")
    runtime.add_population_cohort("producers", "production", 300, TOWN, 5.0, "crafting")
    before = runtime.economy.vendor_quote(VENDOR, "healing_potion_basic")
    runtime.advance_world(ECONOMY_TICK_MS)
    state = runtime.aincrad_economy_state(TOWN)["location"]
    after = runtime.economy.vendor_quote(VENDOR, "healing_potion_basic")
    assert runtime.world.now_ms == ECONOMY_TICK_MS
    assert runtime.economy.next_tick_at_ms == ECONOMY_TICK_MS * 2
    assert state["market"]["last_tick_ms"] == ECONOMY_TICK_MS
    assert state["market"]["demand_index"] > 1.0
    assert state["market"]["supply_index"] > 0.0
    assert state["market"]["cumulative_background_demand_units"] > 0
    assert state["market"]["cumulative_production_units"] > 0
    assert after["stock"] != before["stock"] or state["market"]["cumulative_production_units"] > 0


def test_population_migration_removes_demand_from_origin_after_real_departure():
    runtime = EconomyLoopAincradRuntime(seed=603)
    runtime.add_population_cohort("consumers", "casual", 600, TOWN, 2.0, "town_life")
    runtime.schedule_population_movement("consumers", WEST, reason="relocation")
    assert runtime.population_location_state(TOWN)["headcount"] == 0
    runtime.advance_world(ECONOMY_TICK_MS)
    town = runtime.aincrad_economy_state(TOWN)["location"]
    assert town["population"]["headcount"] == 0
    assert town["market"]["demand_index"] == pytest.approx(1.0)


def test_background_consumers_buy_competitive_player_listing_and_guild_tax_is_settled_once():
    runtime = EconomyLoopAincradRuntime(seed=604)
    seller = runtime.create_character("SmithMerchant")
    guild = runtime.create_guild(seller.actor_id, "MarketGuild", tax_rate=0.25)
    runtime.configure_guild(guild.guild_id, seller.actor_id, headquarters_location_id=TOWN)
    seller.col = 0
    potion_id = next(
        instance_id
        for instance_id, item in seller.inventory.items()
        if item.template_id == "healing_potion_basic"
    )
    listing = runtime.economy.create_player_listing(
        seller,
        potion_id,
        location_id=TOWN,
        unit_price_col=10,
        quantity=1,
        now_ms=runtime.world.now_ms,
    )
    runtime.add_population_cohort("town_consumers", "casual", 1_000, TOWN, 2.0, "town_life")
    runtime.advance_world(ECONOMY_TICK_MS)
    assert listing.listing_id not in runtime.economy.player_listings
    assert seller.col == 8
    assert runtime.relationships.guilds[guild.guild_id].vault_col == 2
    location = runtime.aincrad_economy_state(TOWN)["location"]
    assert location["market"]["cumulative_player_market_units"] == 1
    assert location["market"]["system_col_injected"] == 10
    assert location["guild_headquarters"][guild.guild_id]["vault_col"] == 2


def test_community_vendor_wrapper_no_longer_double_settles_marriage_wallet():
    runtime = EconomyLoopAincradRuntime(seed=605)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    a.col = 100
    b.col = 50
    request = runtime.request_marriage(a.actor_id, b.actor_id)
    runtime.accept_marriage(request.request_id, b.actor_id)
    quote = runtime.economy.vendor_quote(VENDOR, "field_bread")
    result = runtime.economy_buy_from_vendor(runtime.economy, a.actor_id, VENDOR, "field_bread", 2)
    assert result.total_col == quote["current_unit_price_col"] * 2
    assert a.col == b.col == 150 - result.total_col
    assert runtime.relationships.marriage_for(a.actor_id).shared_wallet_col == 150 - result.total_col


def test_living_economy_round_trip_preserves_stock_pressure_history_and_next_tick():
    runtime = EconomyLoopAincradRuntime(seed=606)
    buyer = runtime.create_character("Buyer")
    buyer.col = 1_000
    runtime.add_population_cohort("producers", "production", 200, TOWN, 4.0, "production")
    runtime.economy.buy_from_vendor(
        buyer,
        VENDOR,
        "field_bread",
        3,
        runtime.catalog,
        actor_location_id=buyer.location_id,
    )
    runtime.advance_world(ECONOMY_TICK_MS)
    before = runtime.aincrad_economy_state(TOWN)
    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, EconomyLoopAincradRuntime)
    assert restored.aincrad_economy_state(TOWN) == before
    assert restored.economy.next_tick_at_ms == ECONOMY_TICK_MS * 2
    restored.advance_world(ECONOMY_TICK_MS)
    assert restored.economy.next_tick_at_ms == ECONOMY_TICK_MS * 3
''',
)

write(
    "tests/test_economy_loop_authority.py",
    '''from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.economy_loop import RegionalMarketState, VendorStockState
from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_economy_loop_is_one_more_single_inheritance_layer_above_population():
    assert EconomyLoopAincradRuntime.__bases__ == (PopulationAincradRuntime,)


def test_market_state_does_not_duplicate_actor_guild_or_population_balances():
    regional_fields = set(RegionalMarketState.__dataclass_fields__)
    vendor_fields = set(VendorStockState.__dataclass_fields__)
    assert "headcount" not in regional_fields
    assert "actor_col" not in regional_fields
    assert "guild_vault_col" not in regional_fields
    assert "seller_col" not in vendor_fields
    assert "guild_storage" not in vendor_fields


def test_scenarios_cannot_mutate_living_economy_ledgers_directly():
    forbidden = {
        "vendor_stocks",
        "regional_markets",
        "market_history",
        "next_tick_at_ms",
        "advance_living_market_tick",
        "_commit_vendor_purchase",
        "_commit_vendor_sale",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []


def test_server_bootstrap_uses_economy_loop_as_the_authoritative_top_runtime():
    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")
    assert "EconomyLoopAincradRuntime" in source
    assert "PopulationAincradRuntime(seed=0xA1C0)" not in source
    assert "make_runtime_economy(runtime)" not in source


def test_economy_server_exposes_state_quote_and_history_without_another_mutation_surface():
    source = (ROOT / "src/sao_mcp/server_economy.py").read_text(encoding="utf-8")
    assert "def get_aincrad_economy_state" in source
    assert "def quote_vendor_item" in source
    assert "def get_economy_history" in source
''',
)

# Existing server bootstrap test should now lock the concrete top runtime too.
server_test_path = Path("tests/test_server_bootstrap.py")
server_test = server_test_path.read_text(encoding="utf-8")
server_test += '''\n\ndef test_full_server_uses_living_economy_loop_runtime():\n    from sao_mcp import server_bootstrap\n    from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime\n\n    assert isinstance(server_bootstrap.runtime, EconomyLoopAincradRuntime)\n    assert server_bootstrap.runtime.economy.next_tick_at_ms > server_bootstrap.runtime.world.now_ms\n'''
server_test_path.write_text(server_test, encoding="utf-8")
