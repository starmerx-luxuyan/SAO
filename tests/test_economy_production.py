import random

import pytest

from sao_mcp.corpus.recipes import WEAPON_RECIPES
from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.production import craft_weapon, reclaim_weapon_to_ingot
from sao_mcp.rules.progression import equip_skill, remove_skill
from sao_mcp.runtime.engine import GameRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def _give_ingots(runtime: GameRuntime, actor_id: str, quantity: int = 3) -> ItemInstance:
    actor = runtime.actors[actor_id]
    item = ItemInstance(
        instance_id="test_ingots",
        template_id="iron_ingot",
        owner_id=actor_id,
        quantity=quantity,
    )
    add_item(actor, item, runtime.catalog)
    return item


def test_vendor_purchase_is_transactional_and_uses_col():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Buyer")
    actor.col = 100
    economy = EconomyRuntime()
    before = actor.col
    result = economy.buy_from_vendor(
        actor,
        "npc_vendor_town_of_beginnings",
        "healing_potion_basic",
        2,
        runtime.catalog,
        actor_location_id=actor.location_id,
    )
    assert result.total_col == 36
    assert actor.col == before - 36
    assert sum(item.quantity for item in actor.inventory.values() if item.template_id == "healing_potion_basic") == 5


def test_vendor_wrong_location_does_not_mutate_col():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Buyer")
    actor.col = 100
    actor.location_id = "floor_1_west_field"
    economy = EconomyRuntime()
    with pytest.raises(ValueError):
        economy.buy_from_vendor(
            actor,
            "npc_vendor_town_of_beginnings",
            "field_bread",
            1,
            runtime.catalog,
            actor_location_id=actor.location_id,
        )
    assert actor.col == 100


def test_player_market_escrow_moves_col_and_item():
    runtime = GameRuntime(seed=1)
    seller = runtime.create_character("Seller")
    buyer = runtime.create_character("Buyer")
    buyer.col = 500
    economy = EconomyRuntime()
    potion_id = next(
        instance_id
        for instance_id, item in seller.inventory.items()
        if item.template_id == "healing_potion_basic"
    )
    listing = economy.create_player_listing(
        seller,
        potion_id,
        unit_price_col=25,
        quantity=2,
        now_ms=123,
    )
    assert listing.item.quantity == 2
    seller_before = seller.col
    result = economy.buy_player_listing(buyer, seller, listing.listing_id, runtime.catalog, quantity=1)
    assert result.total_col == 25
    assert buyer.col == 475
    assert seller.col == seller_before + 25
    assert economy.player_listings[listing.listing_id].item.quantity == 1


def test_blacksmith_valid_recipe_always_creates_maker_marked_weapon():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Smith")
    remove_skill(actor, "searching")
    equip_skill(actor, "blacksmithing")
    actor.skill_proficiencies["blacksmithing"] = 500
    actor.strength = 30  # Enough post-craft capacity for the test's second sword.
    _give_ingots(runtime, actor.actor_id, 3)
    result = craft_weapon(
        actor,
        WEAPON_RECIPES["iron_one_hand_sword"],
        runtime.catalog,
        smith_proficiency=500,
        material_quality=1.0,
        rng=random.Random(5),
    )
    product = actor.inventory[result.product_instance_id]
    assert product.maker_id == actor.actor_id
    assert product.quality > 0
    assert product.metadata["crafted"] is True
    assert product.template_id == "starter_one_hand_sword"


def test_blacksmith_capacity_rejection_does_not_consume_materials():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Smith")
    remove_skill(actor, "searching")
    equip_skill(actor, "blacksmithing")
    actor.skill_proficiencies["blacksmithing"] = 500
    ingots = _give_ingots(runtime, actor.actor_id, 3)
    with pytest.raises(ValueError, match="carrying capacity"):
        craft_weapon(
            actor,
            WEAPON_RECIPES["iron_one_hand_sword"],
            runtime.catalog,
            smith_proficiency=500,
            material_quality=1.0,
            rng=random.Random(5),
        )
    assert actor.inventory[ingots.instance_id].quantity == 3


def test_reclaim_weapon_returns_ingot():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Smith")
    weapon_id = actor.equipment["weapon"]
    runtime.unequip_item(actor.actor_id, "weapon")
    result = reclaim_weapon_to_ingot(actor, weapon_id, runtime.catalog)
    assert weapon_id not in actor.inventory
    assert actor.inventory[result.result_instance_id].template_id == "iron_ingot"
    assert result.quantity_created >= 1


def test_market_state_round_trips_with_save():
    runtime = GameRuntime(seed=1)
    seller = runtime.create_character("Seller")
    runtime.economy = EconomyRuntime()
    potion_id = next(
        instance_id
        for instance_id, item in seller.inventory.items()
        if item.template_id == "healing_potion_basic"
    )
    listing = runtime.economy.create_player_listing(
        seller,
        potion_id,
        unit_price_col=23,
        quantity=1,
        now_ms=777,
    )
    restored = import_runtime(export_runtime(runtime))
    assert hasattr(restored, "economy")
    assert listing.listing_id in restored.economy.player_listings
    loaded = restored.economy.player_listings[listing.listing_id]
    assert loaded.unit_price_col == 23
    assert loaded.item.quantity == 1
