import pytest

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


def test_system_vendor_restock_is_accounted_separately_from_player_production():
    runtime = EconomyLoopAincradRuntime(seed=607)
    buyer = runtime.create_character("BulkBuyer")
    buyer.col = 100_000
    runtime.economy.buy_from_vendor(
        buyer,
        VENDOR,
        "field_bread",
        10,
        runtime.catalog,
        actor_location_id=buyer.location_id,
    )
    runtime.advance_world(ECONOMY_TICK_MS)
    market = runtime.aincrad_economy_state(TOWN)["location"]["market"]
    assert market["cumulative_production_units"] == 0
    assert market["cumulative_system_restock_units"] > 0
    row = next(
        row
        for row in reversed(runtime.economy.market_history)
        if row["event"] == "economy_tick" and row["location_id"] == TOWN
    )
    assert row["background_production_units"] == 0
    assert row["system_restock_units"] > 0
    assert row["background_supply_units"] == row["system_restock_units"]
