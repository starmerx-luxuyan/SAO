from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Callable

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.economy import CORE_VENDORS, VendorDefinition
from sao_mcp.domain.models import CombatantState, ItemInstance
from sao_mcp.rules.inventory import add_item, can_receive, carry_capacity, inventory_weight


ECONOMY_STATE_SCHEMA = "economy.v2"


@dataclass(slots=True, frozen=True)
class VendorPurchaseResolution:
    vendor_id: str
    buyer_id: str
    template_id: str
    quantity: int
    total_col: int
    created_instance_ids: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class VendorSaleResolution:
    vendor_id: str
    seller_id: str
    template_id: str
    quantity: int
    received_col: int


@dataclass(slots=True)
class PlayerListing:
    listing_id: str
    seller_id: str
    location_id: str
    item: ItemInstance
    unit_price_col: int
    created_at_ms: int


@dataclass(slots=True, frozen=True)
class PlayerPurchaseResolution:
    listing_id: str
    seller_id: str
    buyer_id: str
    location_id: str
    template_id: str
    quantity: int
    total_col: int
    received_instance_id: str
    listing_closed: bool


def _new_instance_from_template(template_id: str, owner_id: str, catalog: Catalog, quantity: int = 1) -> ItemInstance:
    template = catalog.item(template_id)
    durability = getattr(template, "base_durability", None)
    return ItemInstance(
        instance_id=f"item_{uuid.uuid4().hex[:12]}",
        template_id=template_id,
        owner_id=owner_id,
        quantity=quantity,
        durability=durability,
        max_durability=durability,
        max_enhancement_attempts=(5 if template_id in catalog.weapons else 0),
    )


class EconomyRuntime:
    def __init__(self, vendors: dict[str, VendorDefinition] | None = None) -> None:
        self.vendors = dict(vendors or CORE_VENDORS)
        self.player_listings: dict[str, PlayerListing] = {}
        self.on_income: Callable[[CombatantState, int, str], None] | None = None
        self.on_expense: Callable[[CombatantState, int, str], None] | None = None
        self.validate_player_purchase: Callable[[CombatantState, CombatantState, int], None] | None = None

    def _income(self, actor: CombatantState, amount: int, source: str) -> Any:
        if self.on_income is not None and amount:
            return self.on_income(actor, amount, source)
        return None

    def _expense(self, actor: CombatantState, amount: int, source: str) -> Any:
        if self.on_expense is not None and amount:
            return self.on_expense(actor, amount, source)
        return None

    @staticmethod
    def _base_item_value(template_id: str, catalog: Catalog) -> int:
        template = catalog.item(template_id)
        base = template.base_value_col
        if base is not None:
            return int(base)
        if template_id in catalog.weapons:
            weapon = catalog.weapons[template_id]
            return max(10, int(round((weapon.attack_min + weapon.attack_max) * 1.8)))
        if template_id in catalog.armors:
            armor = catalog.armors[template_id]
            return max(8, armor.armor * 2)
        return 5

    def _vendor_unit_price(self, vendor_id: str, listing) -> int:
        return int(listing.unit_price_col)

    def _validate_vendor_purchase_quantity(self, vendor_id: str, template_id: str, quantity: int) -> None:
        return None

    def _vendor_buyback_multiplier(self, vendor_id: str, template_id: str) -> float:
        return 1.0

    def _commit_vendor_purchase(
        self,
        *,
        vendor_id: str,
        template_id: str,
        quantity: int,
        unit_price_col: int,
        total_col: int,
    ) -> None:
        return None

    def _commit_vendor_sale(
        self,
        *,
        vendor_id: str,
        template_id: str,
        quantity: int,
        received_col: int,
    ) -> None:
        return None

    def _commit_player_purchase(
        self,
        *,
        location_id: str,
        template_id: str,
        quantity: int,
        total_col: int,
    ) -> None:
        return None

    def vendor_catalog(self, vendor_id: str) -> VendorDefinition:
        return self.vendors[vendor_id]

    def buy_from_vendor(
        self,
        buyer: CombatantState,
        vendor_id: str,
        template_id: str,
        quantity: int,
        catalog: Catalog,
        *,
        actor_location_id: str | None,
    ) -> VendorPurchaseResolution:
        if quantity < 1:
            raise ValueError("quantity must be >= 1")
        vendor = self.vendors[vendor_id]
        if actor_location_id != vendor.location_id:
            raise ValueError("buyer is not at this vendor")
        listing = next((row for row in vendor.listings if row.template_id == template_id), None)
        if listing is None:
            raise ValueError("vendor does not sell this template")
        self._validate_vendor_purchase_quantity(vendor_id, template_id, quantity)
        unit_price_col = self._vendor_unit_price(vendor_id, listing)
        if unit_price_col < 1:
            raise RuntimeError("vendor quote must remain positive")
        total = unit_price_col * quantity
        if buyer.col < total:
            raise ValueError("insufficient Col")

        template = catalog.item(template_id)
        added_weight = template.weight * quantity
        if inventory_weight(buyer, catalog) + added_weight > carry_capacity(buyer):
            raise ValueError("purchase would exceed carrying capacity")

        created: list[ItemInstance] = []
        if template.stack_limit > 1:
            created.append(_new_instance_from_template(template_id, buyer.actor_id, catalog, quantity))
        else:
            for _ in range(quantity):
                created.append(_new_instance_from_template(template_id, buyer.actor_id, catalog))

        buyer.col -= total
        for item in created:
            add_item(buyer, item, catalog)
        self._expense(buyer, total, "vendor_purchase")
        self._commit_vendor_purchase(
            vendor_id=vendor_id,
            template_id=template_id,
            quantity=quantity,
            unit_price_col=unit_price_col,
            total_col=total,
        )
        return VendorPurchaseResolution(
            vendor_id,
            buyer.actor_id,
            template_id,
            quantity,
            total,
            tuple(item.instance_id for item in created),
        )

    def sell_to_vendor(
        self,
        seller: CombatantState,
        vendor_id: str,
        instance_id: str,
        catalog: Catalog,
        *,
        quantity: int | None,
        actor_location_id: str | None,
    ) -> VendorSaleResolution:
        vendor = self.vendors[vendor_id]
        if actor_location_id != vendor.location_id:
            raise ValueError("seller is not at this vendor")
        if instance_id not in seller.inventory:
            raise KeyError(instance_id)
        if instance_id in seller.equipment.values():
            raise ValueError("equipped items must be unequipped before sale")
        item = seller.inventory[instance_id]
        qty = item.quantity if quantity is None else quantity
        if qty < 1 or qty > item.quantity:
            raise ValueError("invalid sale quantity")
        base = self._base_item_value(item.template_id, catalog)
        condition = 1.0
        if item.durability is not None and item.max_durability:
            condition = max(0.15, item.durability / item.max_durability)
        quality = max(0.5, min(1.35, item.quality))
        received = max(
            1,
            int(
                round(
                    base
                    * qty
                    * vendor.buyback_rate
                    * condition
                    * quality
                    * self._vendor_buyback_multiplier(vendor_id, item.template_id)
                )
            ),
        )
        item.quantity -= qty
        if item.quantity <= 0:
            seller.inventory.pop(instance_id)
        seller.col += received
        self._income(seller, received, "vendor_sale")
        self._commit_vendor_sale(
            vendor_id=vendor_id,
            template_id=item.template_id,
            quantity=qty,
            received_col=received,
        )
        return VendorSaleResolution(vendor_id, seller.actor_id, item.template_id, qty, received)

    def create_player_listing(
        self,
        seller: CombatantState,
        instance_id: str,
        *,
        location_id: str,
        unit_price_col: int,
        quantity: int | None,
        now_ms: int,
    ) -> PlayerListing:
        if unit_price_col < 1:
            raise ValueError("unit_price_col must be >= 1")
        if not location_id:
            raise ValueError("player listing requires a physical location")
        if instance_id not in seller.inventory:
            raise KeyError(instance_id)
        if instance_id in seller.equipment.values():
            raise ValueError("equipped items must be unequipped before listing")
        source = seller.inventory[instance_id]
        qty = source.quantity if quantity is None else quantity
        if qty < 1 or qty > source.quantity:
            raise ValueError("invalid listing quantity")
        escrow = deepcopy(source)
        escrow.instance_id = f"escrow_{uuid.uuid4().hex[:12]}"
        escrow.quantity = qty
        escrow.owner_id = None
        source.quantity -= qty
        if source.quantity <= 0:
            seller.inventory.pop(instance_id)
        listing = PlayerListing(
            f"listing_{uuid.uuid4().hex[:12]}",
            seller.actor_id,
            location_id,
            escrow,
            unit_price_col,
            now_ms,
        )
        self.player_listings[listing.listing_id] = listing
        return listing

    def cancel_player_listing(self, seller: CombatantState, listing_id: str, catalog: Catalog) -> ItemInstance:
        listing = self.player_listings[listing_id]
        if listing.seller_id != seller.actor_id:
            raise ValueError("only the seller can cancel the listing")
        item = listing.item
        item.owner_id = seller.actor_id
        item.instance_id = f"item_{uuid.uuid4().hex[:12]}"
        add_item(seller, item, catalog, allow_overweight=True)
        self.player_listings.pop(listing_id)
        return item

    def buy_player_listing(
        self,
        buyer: CombatantState,
        seller: CombatantState,
        listing_id: str,
        catalog: Catalog,
        *,
        buyer_location_id: str | None,
        quantity: int | None = None,
    ) -> PlayerPurchaseResolution:
        listing = self.player_listings[listing_id]
        if listing.seller_id != seller.actor_id:
            raise ValueError("listing seller state does not match")
        if buyer.actor_id == seller.actor_id:
            raise ValueError("seller cannot buy own listing")
        if buyer_location_id != listing.location_id:
            raise ValueError("buyer is not at the player-vendor listing location")
        qty = listing.item.quantity if quantity is None else quantity
        if qty < 1 or qty > listing.item.quantity:
            raise ValueError("invalid purchase quantity")
        total = listing.unit_price_col * qty
        if buyer.col < total:
            raise ValueError("insufficient Col")
        if self.validate_player_purchase is not None:
            self.validate_player_purchase(buyer, seller, total)

        moving = deepcopy(listing.item)
        moving.instance_id = f"item_{uuid.uuid4().hex[:12]}"
        moving.quantity = qty
        moving.owner_id = buyer.actor_id
        if not can_receive(buyer, moving, catalog):
            raise ValueError("purchase would exceed carrying capacity")

        buyer.col -= total
        seller.col += total
        add_item(buyer, moving, catalog)
        listing.item.quantity -= qty
        closed = listing.item.quantity <= 0
        if closed:
            self.player_listings.pop(listing_id)
        self._expense(buyer, total, "player_market_purchase")
        self._income(seller, total, "player_market_sale")
        self._commit_player_purchase(
            location_id=listing.location_id,
            template_id=moving.template_id,
            quantity=qty,
            total_col=total,
        )
        return PlayerPurchaseResolution(
            listing_id,
            seller.actor_id,
            buyer.actor_id,
            listing.location_id,
            moving.template_id,
            qty,
            total,
            moving.instance_id,
            closed,
        )

    def dump_state(self) -> dict:
        return {
            "schema": ECONOMY_STATE_SCHEMA,
            "mode": "transactional",
            "player_listings": {
                listing_id: {
                    "listing_id": listing.listing_id,
                    "seller_id": listing.seller_id,
                    "location_id": listing.location_id,
                    "item": asdict(listing.item),
                    "unit_price_col": listing.unit_price_col,
                    "created_at_ms": listing.created_at_ms,
                }
                for listing_id, listing in self.player_listings.items()
            },
        }

    def load_state(self, payload: dict) -> None:
        schema = payload.get("schema")
        if schema not in {None, ECONOMY_STATE_SCHEMA}:
            if payload.get("player_listings"):
                raise ValueError(f"unsupported non-empty economy schema: {schema!r}")
            self.player_listings = {}
            return
        self.player_listings = {}
        for listing_id, value in payload.get("player_listings", {}).items():
            if value.get("listing_id") != listing_id:
                raise ValueError(f"economy listing key/id mismatch: {listing_id}")
            if "location_id" not in value:
                raise ValueError("legacy player listing lacks authoritative physical location")
            item_payload = dict(value["item"])
            enhancements = item_payload.get("enhancements", {})
            from sao_mcp.domain.models import EnhancementTrack

            item_payload["enhancements"] = {EnhancementTrack(key): int(level) for key, level in enhancements.items()}
            self.player_listings[listing_id] = PlayerListing(
                listing_id=value["listing_id"],
                seller_id=value["seller_id"],
                location_id=value["location_id"],
                item=ItemInstance(**item_payload),
                unit_price_col=int(value["unit_price_col"]),
                created_at_ms=int(value["created_at_ms"]),
            )
