import pytest

from sao_mcp.rules.state_authority import (
    assert_runtime_state_authority,
    authoritative_guild_id,
    locate_runtime_item,
    quest_owner_ids,
)
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime


def test_item_container_authority_distinguishes_single_shared_storage_and_marriage_inventory():
    runtime = PopulationAincradRuntime(seed=601)
    a = runtime.create_character("AuthorityA", level=5)
    b = runtime.create_character("AuthorityB", level=5)

    single_item_id = a.equipment["weapon"]
    located = locate_runtime_item(runtime, single_item_id)
    assert located is not None
    assert located.kind == "actor_inventory"
    assert located.actor_ids == (a.actor_id,)
    assert located.sole_actor_id == a.actor_id

    request = runtime.request_friend(a.actor_id, b.actor_id)
    runtime.accept_friend(request.request_id, b.actor_id)
    storage = runtime.create_friend_storage(a.actor_id, b.actor_id)
    runtime.unequip_item(a.actor_id, "weapon")
    stored = runtime.deposit_shared_storage(a.actor_id, storage.storage_id, single_item_id)
    located = locate_runtime_item(runtime, stored.instance_id)
    assert located is not None
    assert located.kind == "shared_storage"
    assert located.container_id == storage.storage_id
    assert located.actor_ids == ()
    assert located.item.owner_id is None

    marriage_request = runtime.request_marriage(a.actor_id, b.actor_id)
    runtime.accept_marriage(marriage_request.request_id, b.actor_id)
    shared_item_id = b.equipment["weapon"]
    located = locate_runtime_item(runtime, shared_item_id)
    assert located is not None
    assert located.kind == "actor_inventory"
    assert located.actor_ids == tuple(sorted((a.actor_id, b.actor_id)))
    assert located.sole_actor_id is None
    assert_runtime_state_authority(runtime)


def test_guildstate_is_membership_authority_and_actor_guild_id_is_only_projection():
    runtime = PopulationAincradRuntime(seed=607)
    leader = runtime.create_character("Leader", level=5)
    member = runtime.create_character("Member", level=5)
    guild = runtime.create_guild(leader.actor_id, "Authority Guild")
    invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
    runtime.accept_guild_invite(invite.invite_id, member.actor_id)

    assert authoritative_guild_id(runtime, leader.actor_id) == guild.guild_id
    assert authoritative_guild_id(runtime, member.actor_id) == guild.guild_id
    assert_runtime_state_authority(runtime)

    member.guild_id = None
    with pytest.raises(RuntimeError, match="guild_id projection"):
        authoritative_guild_id(runtime, member.actor_id)
    with pytest.raises(RuntimeError, match="guild_id projection"):
        export_runtime(runtime)


def test_quest_outer_actor_mapping_is_current_ownership_authority():
    runtime = PopulationAincradRuntime(seed=613)
    actor = runtime.create_character("Quester", level=3)
    runtime.accept_quest(actor.actor_id, "field_combat_orientation")

    assert quest_owner_ids(runtime, "field_combat_orientation") == (actor.actor_id,)
    assert_runtime_state_authority(runtime)

    progress = runtime.quests.progress_by_actor[actor.actor_id]["field_combat_orientation"]
    progress.quest_id = "secret_medicine_of_the_forest"
    with pytest.raises(RuntimeError, match="embedded quest_id"):
        assert_runtime_state_authority(runtime)


def test_market_escrow_is_item_container_and_owner_projection_is_empty():
    runtime = PopulationAincradRuntime(seed=617)
    seller = runtime.create_character("Seller", level=5)
    weapon_id = seller.equipment["weapon"]
    runtime.unequip_item(seller.actor_id, "weapon")
    listing = runtime.economy.create_player_listing(
        seller,
        weapon_id,
        location_id=seller.location_id,
        unit_price_col=100,
        quantity=None,
        now_ms=runtime.world.now_ms,
    )

    located = locate_runtime_item(runtime, listing.item.instance_id)
    assert located is not None
    assert located.kind == "market_escrow"
    assert located.container_id == listing.listing_id
    assert located.item.owner_id is None
    assert_runtime_state_authority(runtime)

    restored = import_runtime(export_runtime(runtime))
    restored_listing = restored.economy.player_listings[listing.listing_id]
    restored_location = locate_runtime_item(restored, restored_listing.item.instance_id)
    assert restored_location is not None
    assert restored_location.kind == "market_escrow"


def test_duplicate_live_item_container_is_rejected():
    runtime = PopulationAincradRuntime(seed=619)
    a = runtime.create_character("DuplicateA", level=5)
    b = runtime.create_character("DuplicateB", level=5)
    item_id = a.equipment["weapon"]
    b.inventory[item_id] = a.inventory[item_id]

    with pytest.raises(RuntimeError, match="multiple live containers"):
        assert_runtime_state_authority(runtime)
