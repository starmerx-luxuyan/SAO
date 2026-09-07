import pytest

from sao_mcp.rules.communications import MAX_SHORT_MESSAGE_CHARS, MessageChannel
from sao_mcp.runtime.communications_runtime import CommunicatingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def test_stranger_message_requires_actual_identity_knowledge_and_same_floor_without_confirmation():
    runtime = CommunicatingAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    with pytest.raises(ValueError, match="know the recipient identity"):
        runtime.send_short_message(a.actor_id, b.actor_id, "hello")

    runtime.learn_player_identity(a.actor_id, b.actor_id)
    message = runtime.send_short_message(a.actor_id, b.actor_id, "hello")
    assert message.channel is MessageChannel.STRANGER_INSTANT
    assert message.delivery_confirmation_visible is False
    assert runtime.message_inbox(b.actor_id)[0].message_id == message.message_id

    b.location_id = "floor_2_main_town"
    runtime.world.floors[2].unlocked = True
    with pytest.raises(ValueError, match="same floor"):
        runtime.send_short_message(a.actor_id, b.actor_id, "still there?")


def test_identity_cannot_be_learned_without_meeting():
    runtime = CommunicatingAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    b.location_id = "floor_1_horunka"
    with pytest.raises(ValueError, match="actual meeting"):
        runtime.learn_player_identity(a.actor_id, b.actor_id)


def test_friend_short_message_works_across_floors_and_has_confirmation():
    runtime = CommunicatingAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    request = runtime.request_friend(a.actor_id, b.actor_id)
    runtime.accept_friend(request.request_id, b.actor_id)
    runtime.world.floors[2].unlocked = True
    b.location_id = "floor_2_main_town"
    message = runtime.send_short_message(a.actor_id, b.actor_id, "Floor 2 opened.")
    assert message.channel is MessageChannel.FRIEND
    assert message.delivery_confirmation_visible is True


def test_messages_to_dungeon_target_are_blocked_even_for_friends():
    runtime = CommunicatingAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    request = runtime.request_friend(a.actor_id, b.actor_id)
    runtime.accept_friend(request.request_id, b.actor_id)
    b.location_id = "floor_1_labyrinth"
    with pytest.raises(ValueError, match="currently in a dungeon"):
        runtime.send_short_message(a.actor_id, b.actor_id, "status?")


def test_guild_message_is_blocked_from_inside_dungeon():
    runtime = CommunicatingAincradRuntime(seed=1)
    leader = runtime.create_character("Leader")
    member = runtime.create_character("Member")
    guild = runtime.create_guild(leader.actor_id, "Messengers")
    invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
    runtime.accept_guild_invite(invite.invite_id, member.actor_id)
    leader.location_id = "floor_1_labyrinth"
    member.location_id = "floor_1_town_of_beginnings"
    with pytest.raises(ValueError, match="unavailable from within a dungeon"):
        runtime.send_short_message(leader.actor_id, member.actor_id, "retreat")


def test_fallen_friend_contact_is_disabled():
    runtime = CommunicatingAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    request = runtime.request_friend(a.actor_id, b.actor_id)
    runtime.accept_friend(request.request_id, b.actor_id)
    b.metadata["permanent_death"] = True
    b.alive = False
    with pytest.raises(ValueError, match="fallen player contact is disabled"):
        runtime.send_short_message(a.actor_id, b.actor_id, "B?")


def test_short_message_cap_is_explicit_simulation_constraint():
    runtime = CommunicatingAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    request = runtime.request_friend(a.actor_id, b.actor_id)
    runtime.accept_friend(request.request_id, b.actor_id)
    with pytest.raises(ValueError, match="runtime cap"):
        runtime.send_short_message(a.actor_id, b.actor_id, "x" * (MAX_SHORT_MESSAGE_CHARS + 1))


def test_read_state_and_messages_round_trip_through_save():
    runtime = CommunicatingAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    request = runtime.request_friend(a.actor_id, b.actor_id)
    runtime.accept_friend(request.request_id, b.actor_id)
    first = runtime.send_short_message(a.actor_id, b.actor_id, "one")
    second = runtime.send_short_message(a.actor_id, b.actor_id, "two")
    runtime.read_message(b.actor_id, first.message_id)

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, CommunicatingAincradRuntime)
    inbox = restored.message_inbox(b.actor_id)
    assert [row.text for row in inbox] == ["one", "two"]
    assert inbox[0].read_at_ms is not None
    assert inbox[1].read_at_ms is None
    unread = restored.message_inbox(b.actor_id, unread_only=True)
    assert [row.message_id for row in unread] == [second.message_id]
