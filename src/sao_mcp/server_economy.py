from __future__ import annotations

import json
import random
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.corpus.recipes import WEAPON_RECIPES
from sao_mcp.domain.models import EnhancementTrack
from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.rules.production import craft_weapon, reclaim_weapon_to_ingot
from sao_mcp.rules.progression import gain_skill_proficiency
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.reinforcement import preview_reinforcement, reinforce_item


FORGE_LOCATIONS = {
    "floor_1_town_of_beginnings",  # simulation starter workshop
    "floor_48_lisbeth_smith_shop",  # canon player smith shop
    "floor_55_granzam",  # canon city with many blacksmiths
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


def _require_forge(actor) -> None:
    if actor.location_id not in FORGE_LOCATIONS:
        raise ValueError("operation requires an available forge/workshop")


def register_economy_tools(mcp, runtime, economy: EconomyRuntime) -> None:
    @mcp.tool()
    def get_aincrad_economy_state(location_id: str | None = None) -> str:
        """Inspect living regional supply/demand, vendor stock, prices, population and guild-HQ resources."""
        state = getattr(runtime, "aincrad_economy_state", None)
        if state is None:
            raise RuntimeError("living economy state is unavailable on this runtime")
        return _json(state(location_id))

    @mcp.tool()
    def quote_vendor_item(vendor_id: str, template_id: str) -> str:
        """Quote current finite stock and population-sensitive price for one NPC vendor item."""
        quote = getattr(economy, "vendor_quote", None)
        if quote is None:
            raise RuntimeError("living vendor quotes are unavailable on this economy runtime")
        return _json(quote(vendor_id, template_id))

    @mcp.tool()
    def get_economy_history(limit: int = 50) -> str:
        """Inspect recent committed named/background market flows and hourly economy ticks."""
        history = getattr(runtime, "economy_history", None)
        if history is None:
            raise RuntimeError("living economy history is unavailable on this runtime")
        return _json({"events": history(limit=limit)})

    @mcp.tool()
    def list_vendors(location_id: str | None = None) -> str:
        """List NPC vendors and their limited system-priced assortments."""
        rows = []
        living_state = getattr(economy, "vendor_state", None)
        for vendor in economy.vendors.values():
            if location_id is not None and vendor.location_id != location_id:
                continue
            rows.append(living_state(vendor.vendor_id) if living_state is not None else asdict(vendor))
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
    def list_player_market(
        template_id: str | None = None,
        location_id: str | None = None,
    ) -> str:
        """List physical player-vendor escrow listings, optionally filtered by item or location."""
        rows = []
        for listing in economy.player_listings.values():
            if template_id is not None and listing.item.template_id != template_id:
                continue
            if location_id is not None and listing.location_id != location_id:
                continue
            template = runtime.catalog.item(listing.item.template_id)
            rows.append(
                {
                    "listingId": listing.listing_id,
                    "sellerId": listing.seller_id,
                    "locationId": listing.location_id,
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
        """Place an unequipped item into player-vendor escrow at the seller's current safe location."""
        seller = runtime.actors[seller_id]
        location = runtime.world_map.locations.get(seller.location_id or "")
        if location is None or not location.safe_zone:
            raise ValueError("player market listings must be created in a safe settlement")
        listing = economy.create_player_listing(
            seller,
            instance_id,
            location_id=location.location_id,
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
        """Buy from a player-vendor listing only while physically at its listed location."""
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
                    buyer_location_id=buyer.location_id,
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
        _require_forge(actor)
        proficiency = _require_blacksmith(actor)
        recipe = WEAPON_RECIPES[recipe_id]
        local_rng = runtime.rng if seed is None else random.Random(seed)
        result = craft_weapon(
            actor,
            recipe,
            runtime.catalog,
            smith_proficiency=proficiency,
            material_quality=material_quality,
            rng=local_rng,
        )
        gain_skill_proficiency(actor, "blacksmithing", 6.0 + recipe.difficulty * 3.0, catalog=runtime.catalog)
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
        _require_forge(actor)
        _require_blacksmith(actor)
        result = reclaim_weapon_to_ingot(actor, instance_id, runtime.catalog)
        gain_skill_proficiency(actor, "blacksmithing", 1.5, catalog=runtime.catalog)
        return _json(asdict(result))

    @mcp.tool()
    def preview_detailed_reinforcement(
        actor_id: str,
        instance_id: str,
        track: str,
        additional_material_quantity: int = 1,
    ) -> str:
        """Preview canon-structured reinforcement: materials, +4 penalty, ten strikes and success chance."""
        actor = runtime.actors[actor_id]
        _require_forge(actor)
        proficiency = _require_blacksmith(actor)
        item = actor.inventory[instance_id]
        result = preview_reinforcement(
            item,
            EnhancementTrack(track),
            smith_proficiency=proficiency,
            additional_material_quantity=additional_material_quantity,
        )
        return _json(asdict(result))

    @mcp.tool()
    def reinforce_weapon_detailed(
        actor_id: str,
        instance_id: str,
        track: str,
        additional_material_quantity: int = 1,
        hammer_hits: int = 10,
        elapsed_since_first_hit_ms: int = 60_000,
        seed: int | None = None,
        force_end_product: bool = False,
    ) -> str:
        """Perform a material-consuming SAO reinforcement with ten-hit/three-minute and failure-side-effect rules."""
        actor = runtime.actors[actor_id]
        _require_forge(actor)
        proficiency = _require_blacksmith(actor)
        item = actor.inventory[instance_id]
        local_rng = runtime.rng if seed is None else random.Random(seed)
        result = reinforce_item(
            actor,
            item,
            EnhancementTrack(track),
            runtime.catalog,
            smith_proficiency=proficiency,
            additional_material_quantity=additional_material_quantity,
            hammer_hits=hammer_hits,
            elapsed_since_first_hit_ms=elapsed_since_first_hit_ms,
            rng=local_rng,
            force_end_product=force_end_product,
        )
        if result.attempted:
            gain_skill_proficiency(actor, "blacksmithing", 2.0 if result.success else 1.0, catalog=runtime.catalog)
        if result.success:
            runtime.quests.record_event(
                actor_id,
                kind=QuestObjectiveKind.ENHANCE,
                target_id=item.template_id,
            )
        return _json(asdict(result))
