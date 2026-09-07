from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.corpus.recipes import WEAPON_RECIPES
from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.rules.production import craft_weapon, reclaim_weapon_to_ingot
from sao_mcp.rules.progression import gain_skill_proficiency
from sao_mcp.rules.quests import QuestObjectiveKind


FORGE_LOCATIONS = {
    "floor_1_town_of_beginnings",
}


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def _require_blacksmith(actor) -> float:
    if "blacksmithing" not in actor.equipped_skills:
        raise ValueError("blacksmithing must occupy an equipped skill slot")
    return actor.skill_proficiencies.get("blacksmithing", 0.0)


def register_economy_tools(mcp, runtime, economy: EconomyRuntime) -> None:
    @mcp.tool()
    def list_vendors(location_id: str | None = None) -> str:
        """List NPC vendors and their limited system-priced assortments."""
        rows = []
        for vendor in economy.vendors.values():
            if location_id is not None and vendor.location_id != location_id:
                continue
            rows.append(asdict(vendor))
        return _json({"vendors": rows})

    @mcp.tool()
    def buy_from_vendor(
        actor_id: str,
        vendor_id: str,
        template_id: str,
        quantity: int = 1,
    ) -> str:
        """Buy items from a colocated NPC vendor using authoritative Col and carry limits."""
        actor = runtime.actors[actor_id]
        return _json(
            asdict(
                economy.buy_from_vendor(
                    actor,
                    vendor_id,
                    template_id,
                    quantity,
                    runtime.catalog,
                    actor_location_id=actor.location_id,
                )
            )
        )

    @mcp.tool()
    def sell_to_vendor(
        actor_id: str,
        vendor_id: str,
        instance_id: str,
        quantity: int | None = None,
    ) -> str:
        """Sell an unequipped item to a colocated NPC vendor for condition/quality-adjusted Col."""
        actor = runtime.actors[actor_id]
        return _json(
            asdict(
                economy.sell_to_vendor(
                    actor,
                    vendor_id,
                    instance_id,
                    runtime.catalog,
                    quantity=quantity,
                    actor_location_id=actor.location_id,
                )
            )
        )

    @mcp.tool()
    def list_player_market(template_id: str | None = None) -> str:
        """List player-vendor escrow listings, optionally filtered by item template."""
        rows = []
        for listing in economy.player_listings.values():
            if template_id is not None and listing.item.template_id != template_id:
                continue
            template = runtime.catalog.item(listing.item.template_id)
            rows.append(
                {
                    "listingId": listing.listing_id,
                    "sellerId": listing.seller_id,
                    "templateId": listing.item.template_id,
                    "name": template.name,
                    "quantity": listing.item.quantity,
                    "unitPriceCol": listing.unit_price_col,
                    "quality": listing.item.quality,
                    "durability": listing.item.durability,
                    "maxDurability": listing.item.max_durability,
                    "makerId": listing.item.maker_id,
                    "createdAtMs": listing.created_at_ms,
                }
            )
        return _json({"listings": rows})

    @mcp.tool()
    def create_player_market_listing(
        seller_id: str,
        instance_id: str,
        unit_price_col: int,
        quantity: int | None = None,
    ) -> str:
        """Place an unequipped item into player-vendor escrow at a chosen unit price."""
        seller = runtime.actors[seller_id]
        location = runtime.world_map.locations.get(seller.location_id or "")
        if location is None or not location.safe_zone:
            raise ValueError("player market listings must be created in a safe settlement")
        listing = economy.create_player_listing(
            seller,
            instance_id,
            unit_price_col=unit_price_col,
            quantity=quantity,
            now_ms=runtime.world.now_ms,
        )
        return _json(asdict(listing))

    @mcp.tool()
    def cancel_player_market_listing(seller_id: str, listing_id: str) -> str:
        """Cancel one's own player-vendor listing and return the escrowed item."""
        item = economy.cancel_player_listing(
            runtime.actors[seller_id],
            listing_id,
            runtime.catalog,
        )
        return _json(asdict(item))

    @mcp.tool()
    def buy_player_market_listing(
        buyer_id: str,
        listing_id: str,
        quantity: int | None = None,
    ) -> str:
        """Buy from a player-vendor listing and transfer Col directly to the seller."""
        listing = economy.player_listings[listing_id]
        seller = runtime.actors[listing.seller_id]
        buyer = runtime.actors[buyer_id]
        return _json(
            asdict(
                economy.buy_player_listing(
                    buyer,
                    seller,
                    listing_id,
                    runtime.catalog,
                    quantity=quantity,
                )
            )
        )

    @mcp.tool()
    def list_weapon_recipes() -> str:
        """List blacksmith weapon recipes with canon/simulation provenance."""
        return _json({"recipes": [asdict(recipe) for recipe in WEAPON_RECIPES.values()]})

    @mcp.tool()
    def craft_weapon_from_recipe(
        actor_id: str,
        recipe_id: str,
        material_quality: float = 1.0,
        seed: int | None = None,
    ) -> str:
        """Forge a weapon at a workshop; valid crafting always produces a product with variable quality."""
        actor = runtime.actors[actor_id]
        if actor.location_id not in FORGE_LOCATIONS:
            raise ValueError("weapon crafting requires an available forge/workshop")
        proficiency = _require_blacksmith(actor)
        recipe = WEAPON_RECIPES[recipe_id]
        local_rng = runtime.rng if seed is None else __import__("random").Random(seed)
        result = craft_weapon(
            actor,
            recipe,
            runtime.catalog,
            smith_proficiency=proficiency,
            material_quality=material_quality,
            rng=local_rng,
        )
        gain_skill_proficiency(actor, "blacksmithing", 6.0 + recipe.difficulty * 3.0)
        runtime.quests.record_event(
            actor_id,
            kind=QuestObjectiveKind.CRAFT,
            target_id=recipe.product_template_id,
        )
        return _json(asdict(result))

    @mcp.tool()
    def reclaim_weapon(actor_id: str, instance_id: str) -> str:
        """Reclaim an unequipped weapon into an ingot for later crafting."""
        actor = runtime.actors[actor_id]
        if actor.location_id not in FORGE_LOCATIONS:
            raise ValueError("weapon reclamation requires an available forge/workshop")
        _require_blacksmith(actor)
        result = reclaim_weapon_to_ingot(actor, instance_id, runtime.catalog)
        gain_skill_proficiency(actor, "blacksmithing", 1.5)
        return _json(asdict(result))
