import pytest

from sao_mcp.runtime.community_hooks import attach_community_economy
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.property_economy import GuardedEconomyRuntime
from sao_mcp.runtime.property_runtime import PropertyFamilyAincradRuntime


def _married_runtime():
    runtime = PropertyFamilyAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    a.strength = b.strength = 100
    request = runtime.request_marriage(a.actor_id, b.actor_id)
    runtime.accept_marriage(request.request_id, b.actor_id)
    economy = GuardedEconomyRuntime(runtime)
    attach_community_economy(runtime, economy)
    runtime.economy = economy
    return runtime, economy, a, b


def test_spouse_cannot_equip_same_instance_already_equipped_by_partner():
    runtime, _, a, b = _married_runtime()
    weapon_id = a.equipment["weapon"]
    assert weapon_id in b.inventory
    with pytest.raises(ValueError, match="already equipped by another actor"):
        runtime.equip_item(b.actor_id, weapon_id)
    assert b.equipment["weapon"] != weapon_id


def test_spouse_cannot_sell_or_list_partner_equipped_instance():
    runtime, economy, a, b = _married_runtime()
    weapon_id = a.equipment["weapon"]
    with pytest.raises(ValueError, match="equipped by actor"):
        economy.sell_to_vendor(
            b,
            "npc_vendor_town_of_beginnings",
            weapon_id,
            runtime.catalog,
            quantity=None,
            actor_location_id=b.location_id,
        )
    with pytest.raises(ValueError, match="equipped by actor"):
        economy.create_player_listing(
            b,
            weapon_id,
            location_id=b.location_id,
            unit_price_col=99,
            quantity=1,
            now_ms=0,
        )
    assert weapon_id in a.inventory
    assert a.equipment["weapon"] == weapon_id


def test_spouse_cannot_transfer_or_store_partner_equipped_instance():
    runtime, _, a, b = _married_runtime()
    friend = runtime.create_character("Friend")
    friend_req = runtime.request_friend(b.actor_id, friend.actor_id)
    runtime.accept_friend(friend_req.request_id, friend.actor_id)
    storage = runtime.create_friend_storage(b.actor_id, friend.actor_id)
    weapon_id = a.equipment["weapon"]

    with pytest.raises(ValueError, match="equipped by actor"):
        runtime.transfer_inventory_item(b.actor_id, friend.actor_id, weapon_id)
    with pytest.raises(ValueError, match="equipped by actor"):
        runtime.deposit_shared_storage(b.actor_id, storage.storage_id, weapon_id)


def test_after_owner_unequips_shared_instance_partner_may_equip_it():
    runtime, _, a, b = _married_runtime()
    weapon_id = a.equipment["weapon"]
    runtime.unequip_item(a.actor_id, "weapon")
    change = runtime.equip_item(b.actor_id, weapon_id)
    assert change.equipped_instance_id == weapon_id
    assert b.equipment["weapon"] == weapon_id
    assert "weapon" not in a.equipment


def test_property_guard_survives_save_load():
    runtime, _, a, b = _married_runtime()
    weapon_id = a.equipment["weapon"]
    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, PropertyFamilyAincradRuntime)
    assert isinstance(restored.economy, GuardedEconomyRuntime)
    rb = restored.actors[b.actor_id]
    with pytest.raises(ValueError, match="already equipped by another actor"):
        restored.equip_item(rb.actor_id, weapon_id)
    with pytest.raises(ValueError, match="equipped by actor"):
        restored.economy.create_player_listing(
            rb,
            weapon_id,
            location_id=rb.location_id,
            unit_price_col=50,
            quantity=1,
            now_ms=0,
        )
