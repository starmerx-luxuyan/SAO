from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.economy import CORE_VENDORS, VendorDefinition
from sao_mcp.domain.models import CombatantState, ItemInstance
from sao_mcp.rules.inventory import add_item, can_receive, carry_capacity, inventory_weight


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
    item: ItemInstance
    unit_price_col: int
    created_at_ms: int


@dataclass(slots=True, frozen=True)
class PlayerPurchaseResolution:
    listing_id: str
    seller_id: str
    buyer_id: str
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
        total = listing.unit_price_col * quantity
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
        template = catalog.item(item.template_id)
        base = template.base_value_col
        if base is None:
            if item.template_id in catalog.weapons:
                weapon = catalog.weapons[item.template_id]
                base = max(10, int(round((weapon.attack_min + weapon.attack_max) * 1.8)))
            elif item.template_id in catalog.armors:
                armor = catalog.armors[item.template_id]
                base = max(8, armor.armor * 2)
            else:
                base = 5
        condition = 1.0
        if item.durability is not None and item.max_durability:
            condition = max(0.15, item.durability / item.max_durability)
        quality = max(0.5, min(1.35, item.quality))
        received = max(1, int(round(base * qty * vendor.buyback_rate * condition * quality)))
        item.quantity -= qty
        if item.quantity <= 0:
            seller.inventory.pop(instance_id)
        seller.col += received
        return VendorSaleResolution(vendor_id, seller.actor_id, item.template_id, qty, received)

    def create_player_listing(
        self,
        seller: CombatantState,
        instance_id: str,
        *,
        unit_price_col: int,
        quantity: int | None,
        now_ms: int,
    ) -> PlayerListing:
        if unit_price_col < 1:
            raise ValueError("unit_price_col must be >= 1")
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
        quantity: int | None = None,
    ) -> PlayerPurchaseResolution:
        listing = self.player_listings[listing_id]
        if listing.seller_id != seller.actor_id:
            raise ValueError("listing seller state does not match")
        if buyer.actor_id == seller.actor_id:
            raise ValueError("seller cannot buy own listing")
        qty = listing.item.quantity if quantity is None else quantity
        if qty < 1 or qty > listing.item.quantity:
            raise ValueError("invalid purchase quantity")
        total = listing.unit_price_col * qty
        if buyer.col < total:
            raise ValueError("insufficient Col")

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
        return PlayerPurchaseResolution(
            listing_id,
            seller.actor_id,
            buyer.actor_id,
            moving.template_id,
            qty,
            total,
            moving.instance_id,
            closed,
        )

    def dump_state(self) -> dict:
        return {
            "player_listings": {
                listing_id: {
                    "listing_id": listing.listing_id,
                    "seller_id": listing.seller_id,
                    "item": asdict(listing.item),
                    "unit_price_col": listing.unit_price_col,
                    "created_at_ms": listing.created_at_ms,
                }
                for listing_id, listing in self.player_listings.items()
            }
        }

    def load_state(self, payload: dict) -> None:
        self.player_listings = {}
        for listing_id, value in payload.get("player_listings", {}).items():
            item_payload = dict(value["item"])
            enhancements = item_payload.get("enhancements", {})
            from sao_mcp.domain.models import EnhancementTrack

            item_payload["enhancements"] = {EnhancementTrack(key): int(level) for key, level in enhancements.items()}
            self.player_listings[listing_id] = PlayerListing(
                listing_id=value["listing_id"],
                seller_id=value["seller_id"],
                item=ItemInstance(**item_payload),
                unit_price_col=int(value["unit_price_col"]),
                created_at_ms=int(value["created_at_ms"]),
            )
