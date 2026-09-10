import random

import pytest

from sao_mcp.domain.models import DefenseMode
from sao_mcp.rules.combat import resolve_physical_attack
from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.rules.inventory import carry_capacity, inventory_weight
from sao_mcp.runtime.community_hooks import attach_community_economy
from sao_mcp.runtime.community_runtime import CommunityAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def test_friends_can_create_common_inventory_and_exchange_deposited_items():
    runtime = CommunityAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    request = runtime.request_friend(a.actor_id, b.actor_id)
    runtime.accept_friend(request.request_id, b.actor_id)
    storage = runtime.create_friend_storage(a.actor_id, b.actor_id)
    potion_id = next(i for i, item in a.inventory.items() if item.template_id == "healing_potion_basic")
    stored = runtime.deposit_shared_storage(a.actor_id, storage.storage_id, potion_id, quantity=2)
    assert stored.quantity == 2
    assert a.inventory[potion_id].quantity == 1
    withdrawn = runtime.withdraw_shared_storage(b.actor_id, storage.storage_id, stored.instance_id, quantity=1)
    assert withdrawn.template_id == "healing_potion_basic"
    assert runtime.relationships.storages[storage.storage_id].items[stored.instance_id].quantity == 1


def test_friend_common_inventory_becomes_inaccessible_after_member_permanent_death():
    runtime = CommunityAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    req = runtime.request_friend(a.actor_id, b.actor_id)
    runtime.accept_friend(req.request_id, b.actor_id)
    storage = runtime.create_friend_storage(a.actor_id, b.actor_id)
    potion_id = next(i for i, item in a.inventory.items() if item.template_id == "healing_potion_basic")
    stored = runtime.deposit_shared_storage(a.actor_id, storage.storage_id, potion_id, quantity=1)
    b.metadata["permanent_death"] = True
    with pytest.raises(ValueError, match="inaccessible"):
        runtime.withdraw_shared_storage(a.actor_id, storage.storage_id, stored.instance_id)


def test_guild_storage_is_locked_in_dungeon_and_contract_scroll_permissions_apply():
    runtime = CommunityAincradRuntime(seed=1)
    leader = runtime.create_character("Leader")
    member = runtime.create_character("Member")
    guild = runtime.create_guild(leader.actor_id, "Clearers", tax_rate=0.10)
    invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
    runtime.accept_guild_invite(invite.invite_id, member.actor_id)
    runtime.set_guild_manager(guild.guild_id, leader.actor_id, member.actor_id, True)
    runtime.configure_guild(guild.guild_id, member.actor_id, emblem="CL", tax_rate=0.12)
    assert runtime.relationships.guilds[guild.guild_id].tax_rate == pytest.approx(0.12)
    assert member.metadata["guild_emblem"] == "CL"

    member.location_id = "floor_1_labyrinth"
    potion_id = next(i for i, item in member.inventory.items() if item.template_id == "healing_potion_basic")
    with pytest.raises(ValueError, match="cannot be opened in a dungeon"):
        runtime.deposit_shared_storage(member.actor_id, guild.storage_id, potion_id, quantity=1)


def test_guild_vendor_income_is_taxed_into_vault_via_existing_economy_tool_path():
    runtime = CommunityAincradRuntime(seed=1)
    actor = runtime.create_character("Merchant")
    guild = runtime.create_guild(actor.actor_id, "TaxTest", tax_rate=0.25)
    economy = EconomyRuntime()
    attach_community_economy(runtime, economy)
    actor.col = 0
    weapon_id = actor.equipment["weapon"]
    runtime.unequip_item(actor.actor_id, "weapon")
    result = economy.sell_to_vendor(
        actor,
        "npc_vendor_town_of_beginnings",
        weapon_id,
        runtime.catalog,
        quantity=None,
        actor_location_id=actor.location_id,
    )
    expected_tax = int(result.received_col * 0.25)
    assert runtime.relationships.guilds[guild.guild_id].vault_col == expected_tax
    assert actor.col == result.received_col - expected_tax


def test_same_guild_same_party_sets_simulation_bonus_and_changes_damage():
    runtime = CommunityAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    monster = runtime.create_training_monster(level=1)
    guild = runtime.create_guild(a.actor_id, "PartyGuild")
    invite = runtime.invite_to_guild(guild.guild_id, a.actor_id, b.actor_id)
    runtime.accept_guild_invite(invite.invite_id, b.actor_id)
    party = runtime.create_party(a.actor_id)
    runtime.join_party(party.party_id, b.actor_id)
    a.location_id = monster.location_id
    b.location_id = monster.location_id
    runtime.start_encounter([a.actor_id, b.actor_id, monster.actor_id])
    assert a.metadata["guild_party_stat_bonus"] == pytest.approx(0.02)
    assert b.metadata["guild_party_stat_bonus"] == pytest.approx(0.02)

    weapon_item, weapon = runtime._equipped_weapon(a)
    a.skill_proficiencies[weapon.weapon_class.value] = 1000
    boosted = resolve_physical_attack(
        a, monster, weapon_item, weapon,
        now_ms=0, rng=random.Random(1), defense=DefenseMode.NONE, distance_m=1.0,
    )
    a.metadata.pop("guild_party_stat_bonus", None)
    normal = resolve_physical_attack(
        a, monster, weapon_item, weapon,
        now_ms=0, rng=random.Random(1), defense=DefenseMode.NONE, distance_m=1.0,
    )
    assert boosted.hit and normal.hit
    assert boosted.damage > normal.damage


def test_marriage_merges_inventory_wallet_and_two_person_capacity():
    runtime = CommunityAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    a.col = 100
    b.col = 50
    personal_a = carry_capacity(a)
    personal_b = carry_capacity(b)
    count_before = len(a.inventory) + len(b.inventory)
    req = runtime.request_marriage(a.actor_id, b.actor_id)
    marriage = runtime.accept_marriage(req.request_id, b.actor_id)
    assert a.inventory is b.inventory
    assert len(a.inventory) == count_before
    assert a.col == b.col == 150
    assert marriage.shared_wallet_col == 150
    assert carry_capacity(a) == pytest.approx(personal_a + personal_b)
    assert carry_capacity(b) == pytest.approx(personal_a + personal_b)
    assert inventory_weight(a, runtime.catalog) == inventory_weight(b, runtime.catalog)


def test_married_vendor_expense_updates_both_spouses_once():
    runtime = CommunityAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    a.col = 100
    b.col = 50
    req = runtime.request_marriage(a.actor_id, b.actor_id)
    runtime.accept_marriage(req.request_id, b.actor_id)
    economy = EconomyRuntime()
    attach_community_economy(runtime, economy)
    result = economy.buy_from_vendor(
        a,
        "npc_vendor_town_of_beginnings",
        "field_bread",
        2,
        runtime.catalog,
        actor_location_id=a.location_id,
    )
    assert result.total_col == 10
    assert a.col == b.col == 140
    assert runtime.relationships.marriage_for(a.actor_id).shared_wallet_col == 140


def test_spouses_cannot_buy_each_others_player_listing():
    runtime = CommunityAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    a.col = 100
    b.col = 100
    req = runtime.request_marriage(a.actor_id, b.actor_id)
    runtime.accept_marriage(req.request_id, b.actor_id)
    economy = EconomyRuntime()
    attach_community_economy(runtime, economy)
    potion_id = next(i for i, item in b.inventory.items() if item.template_id == "healing_potion_basic")
    listing = economy.create_player_listing(
        b,
        potion_id,
        location_id=b.location_id,
        unit_price_col=20,
        quantity=1,
        now_ms=0,
    )
    before = a.col
    with pytest.raises(ValueError, match="spouses already share"):
        economy.buy_player_listing(
            a, b, listing.listing_id, runtime.catalog,
            buyer_location_id=a.location_id, quantity=1,
        )
    assert a.col == b.col == before
    assert listing.listing_id in economy.player_listings


def test_relationships_shared_inventory_wallet_and_guild_vault_round_trip():
    runtime = CommunityAincradRuntime(seed=1)
    runtime.economy = EconomyRuntime()
    attach_community_economy(runtime, runtime.economy)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    friend_req = runtime.request_friend(a.actor_id, b.actor_id)
    runtime.accept_friend(friend_req.request_id, b.actor_id)
    runtime.create_friend_storage(a.actor_id, b.actor_id)
    guild = runtime.create_guild(a.actor_id, "PersistGuild", tax_rate=0.15)
    invite = runtime.invite_to_guild(guild.guild_id, a.actor_id, b.actor_id)
    runtime.accept_guild_invite(invite.invite_id, b.actor_id)
    a.col = 70
    b.col = 30
    marriage_req = runtime.request_marriage(a.actor_id, b.actor_id)
    marriage = runtime.accept_marriage(marriage_req.request_id, b.actor_id)

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, CommunityAincradRuntime)
    ra, rb = restored.actors[a.actor_id], restored.actors[b.actor_id]
    assert ra.inventory is rb.inventory
    assert ra.col == rb.col == marriage.shared_wallet_col == 100
    assert restored.relationships.are_friends(a.actor_id, b.actor_id)
    assert restored.relationships.marriage_for(a.actor_id).marriage_id == marriage.marriage_id
    assert restored.relationships.guilds[guild.guild_id].member_ids == [a.actor_id, b.actor_id]
    assert restored.economy.on_income is not None
