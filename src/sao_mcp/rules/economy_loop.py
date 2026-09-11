from __future__ import annotations

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
