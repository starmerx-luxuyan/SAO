import pytest

from sao_mcp.runtime.housing_runtime import HousingAincradRuntime, PROPERTY_ENTRY_TIME_MS
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def test_player_can_purchase_enter_exit_and_grant_guest_to_beginner_room():
    runtime = HousingAincradRuntime(seed=1)
    owner = runtime.create_character("Owner")
    guest = runtime.create_character("Guest")
    owner.col = 2_000
    state = runtime.purchase_residence(owner.actor_id, "town_beginner_room")
    assert owner.col == 800
    assert state.interior_location_id in runtime.world_map.locations
    assert state.storage_id in runtime.relationships.storages

    with pytest.raises(ValueError, match="not authorized"):
        runtime.enter_property(guest.actor_id, state.property_id)
    runtime.grant_property_guest(owner.actor_id, state.property_id, guest.actor_id)
    before = runtime.world.now_ms
    runtime.enter_property(guest.actor_id, state.property_id)
    assert guest.location_id == state.interior_location_id
    assert runtime.world.now_ms == before + PROPERTY_ENTRY_TIME_MS
    runtime.exit_property(guest.actor_id)
    assert guest.location_id == state.parent_location_id


def test_married_joint_residence_uses_shared_wallet_and_both_are_owners():
    runtime = HousingAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    a.col = 1_000
    b.col = 1_000
    request = runtime.request_marriage(a.actor_id, b.actor_id)
    marriage = runtime.accept_marriage(request.request_id, b.actor_id)
    state = runtime.purchase_residence(a.actor_id, "town_beginner_room", joint_marriage=True)
    assert set(state.owner_actor_ids) == {a.actor_id, b.actor_id}
    assert marriage.shared_wallet_col == 800
    assert a.col == b.col == 800
    runtime.enter_property(b.actor_id, state.property_id)
    assert b.location_id == state.interior_location_id


def test_forest_house_k4_purchase_requires_quest_and_is_unique():
    runtime = HousingAincradRuntime(seed=1)
    buyer = runtime.create_character("Buyer")
    buyer.location_id = "floor_22_coral"
    buyer.col = 6_000_000
    runtime.world.floors[22].unlocked = True
    with pytest.raises(ValueError, match="prerequisites are incomplete"):
        runtime.purchase_residence(buyer.actor_id, "floor22_forest_house_k4")

    runtime.quests.completed_by_actor.setdefault(buyer.actor_id, set()).add(
        "witch_of_the_west_and_three_treasures"
    )
    state = runtime.purchase_residence(buyer.actor_id, "floor22_forest_house_k4")
    assert state.listing_id == "floor22_forest_house_k4"
    buyer.col = 6_000_000
    with pytest.raises(ValueError, match="already been purchased"):
        runtime.purchase_residence(buyer.actor_id, "floor22_forest_house_k4")


def test_guild_headquarters_uses_vault_and_current_members_only():
    runtime = HousingAincradRuntime(seed=1)
    leader = runtime.create_character("Leader")
    member = runtime.create_character("Member")
    outsider = runtime.create_character("Outsider")
    leader.location_id = member.location_id = outsider.location_id = "floor_55_granzam"
    runtime.world.floors[55].unlocked = True
    guild = runtime.create_guild(leader.actor_id, "HQGuild")
    invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
    runtime.accept_guild_invite(invite.invite_id, member.actor_id)
    guild.vault_col = 60_000_000
    state = runtime.purchase_guild_headquarters(
        guild.guild_id,
        leader.actor_id,
        "granzam_guild_headquarters",
    )
    assert guild.vault_col == 10_000_000
    assert guild.headquarters_location_id == state.interior_location_id
    assert runtime.can_enter_property(member.actor_id, state.property_id)
    assert not runtime.can_enter_property(outsider.actor_id, state.property_id)
    runtime.enter_property(member.actor_id, state.property_id)
    runtime.exit_property(member.actor_id)

    runtime.relationships.leave_guild(member)
    assert not runtime.can_enter_property(member.actor_id, state.property_id)
    with pytest.raises(ValueError, match="not authorized"):
        runtime.enter_property(member.actor_id, state.property_id)


def test_private_property_storage_is_owner_only_not_guest():
    runtime = HousingAincradRuntime(seed=1)
    owner = runtime.create_character("Owner")
    guest = runtime.create_character("Guest")
    owner.col = 2_000
    state = runtime.purchase_residence(owner.actor_id, "town_beginner_room")
    runtime.grant_property_guest(owner.actor_id, state.property_id, guest.actor_id)
    potion_id = next(i for i, item in owner.inventory.items() if item.template_id == "healing_potion_basic")
    stored = runtime.deposit_property_storage(owner.actor_id, state.property_id, potion_id, quantity=1)
    assert stored.instance_id in runtime.relationships.storages[state.storage_id].items
    with pytest.raises(ValueError, match="guests cannot mutate"):
        runtime.withdraw_property_storage(guest.actor_id, state.property_id, stored.instance_id)


def test_housing_round_trip_rebuilds_dynamic_location_and_access():
    runtime = HousingAincradRuntime(seed=1)
    owner = runtime.create_character("Owner")
    owner.col = 2_000
    state = runtime.purchase_residence(owner.actor_id, "town_beginner_room")
    runtime.enter_property(owner.actor_id, state.property_id)

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, HousingAincradRuntime)
    loaded_owner = restored.actors[owner.actor_id]
    loaded = restored.housing.properties[state.property_id]
    assert loaded_owner.location_id == loaded.interior_location_id
    assert loaded.interior_location_id in restored.world_map.locations
    assert any(
        edge.to_location_id == loaded.parent_location_id
        for edge in restored.world_map.adjacency[loaded.interior_location_id]
    )
    restored.exit_property(owner.actor_id)
    assert loaded_owner.location_id == loaded.parent_location_id
