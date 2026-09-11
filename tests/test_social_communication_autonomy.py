import pytest

from sao_mcp.rules.social_communication import (
    ARGO_REPORT_DELAY_MS,
    GUILD_NOTICE_DELAY_MS,
    LOCAL_RUMOR_DELAY_MS,
    SOCIAL_TICK_MS,
)
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


TOWN = "floor_1_town_of_beginnings"
WEST = "floor_1_west_field"
LABYRINTH = "floor_1_labyrinth"


def test_known_fact_short_message_changes_knowledge_only_when_recipient_reads():
    runtime = SocialCommunicationAincradRuntime(seed=901)
    sender = runtime.create_character("Sender")
    recipient = runtime.create_character("Recipient")
    request = runtime.request_friend(sender.actor_id, recipient.actor_id)
    runtime.accept_friend(request.request_id, recipient.actor_id)
    source = runtime.record_observation(
        sender.actor_id, "route:test", {"open": True}, observation_location_id=TOWN
    )
    message = runtime.send_known_fact_message(
        sender.actor_id, recipient.actor_id, "route:test", "West route is open."
    )
    assert message.source_knowledge_event_id == source.event_id
    assert runtime.belief(recipient.actor_id, "route:test") is None
    runtime.read_message(recipient.actor_id, message.message_id)
    received = runtime.belief(recipient.actor_id, "route:test")
    assert received is not None
    assert received.value == {"open": True}
    assert received.evidence_event_ids == (source.event_id,)
    assert runtime.communications.messages[message.message_id].received_knowledge_event_id == received.event_id


def test_guild_notice_delivers_at_exact_boundary_and_unlocks_existing_guild_strategy():
    runtime = SocialCommunicationAincradRuntime(seed=902)
    leader = runtime.create_character("Leader")
    member = runtime.create_character("Member")
    guild = runtime.create_guild(leader.actor_id, "Signalers")
    invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
    runtime.accept_guild_invite(invite.invite_id, member.actor_id)
    runtime.record_observation(
        leader.actor_id, "route:west_safe", True, observation_location_id=TOWN
    )
    runtime.set_guild_strategy_goal(
        guild.guild_id,
        leader.actor_id,
        "social:test_deploy",
        WEST,
        required_member_fact_id="route:west_safe",
        min_members=1,
        max_members=1,
        desired_squads=1,
        max_concurrent_squads=1,
        allow_leader_assignment=False,
    )
    assert runtime.guild_agenda_state(guild.guild_id)["live_operation_ids"] == []
    rows = runtime.post_guild_fact_notice(leader.actor_id, guild.guild_id, "route:west_safe")
    assert len(rows) == 1
    runtime.advance_world(GUILD_NOTICE_DELAY_MS - 1)
    assert runtime.belief(member.actor_id, "route:west_safe") is None
    runtime.advance_world(1)
    assert runtime.belief(member.actor_id, "route:west_safe") is not None
    assert runtime.guild_agenda_state(guild.guild_id)["live_operation_ids"]


def test_local_rumor_propagates_the_senders_actual_belief_not_global_truth():
    runtime = SocialCommunicationAincradRuntime(seed=903)
    sender = runtime.create_character("Rumormonger")
    source = runtime.record_observation(
        sender.actor_id, "rumor:test", {"boss_alive": False}, observation_location_id=TOWN
    )
    rows = runtime.spread_local_rumor(sender.actor_id, "rumor:test")
    tutorial_rows = [row for row in rows if row.recipient_id == "npc_tutorial_instructor"]
    assert tutorial_rows
    runtime.advance_world(LOCAL_RUMOR_DELAY_MS)
    received = runtime.belief("npc_tutorial_instructor", "rumor:test")
    assert received is not None
    assert received.value == {"boss_alive": False}
    assert received.evidence_event_ids == (source.event_id,)
    assert received.confidence < source.confidence


def test_dynamic_quest_board_is_observed_locally_but_not_globally():
    runtime = SocialCommunicationAincradRuntime(seed=904)
    local = runtime.create_character("Local")
    remote = runtime.create_character("Remote")
    remote.location_id = "floor_1_horunka"
    runtime.advance_world(60 * 60 * 1000)
    contract = next(iter(runtime.quest_contracts.values()))
    fact_id = f"quest_contract:{contract.contract_id}"
    assert contract.posting_location_id == TOWN
    local_belief = runtime.belief(local.actor_id, fact_id)
    assert local_belief is not None
    assert local_belief.value["status"] == "active"
    assert runtime.belief(remote.actor_id, fact_id) is None


def test_argo_rebroadcasts_only_a_fact_she_really_received_from_a_colocated_source():
    runtime = SocialCommunicationAincradRuntime(seed=905)
    tipper = runtime.create_character("Tipper")
    subscriber = runtime.create_character("Subscriber")
    runtime.subscribe_argo_intelligence(subscriber.actor_id)
    source = runtime.record_observation(
        tipper.actor_id, "tip:test", "hidden route", observation_location_id=TOWN
    )
    argo_event = runtime.brief_argo(tipper.actor_id, "tip:test")
    assert argo_event.evidence_event_ids == (source.event_id,)
    subscriber.location_id = WEST
    runtime.advance_world(SOCIAL_TICK_MS)
    assert runtime.belief(subscriber.actor_id, "tip:test") is None
    runtime.advance_world(ARGO_REPORT_DELAY_MS)
    received = runtime.belief(subscriber.actor_id, "tip:test")
    assert received is not None
    assert received.value == "hidden route"
    assert received.evidence_event_ids == (argo_event.event_id,)


def test_guild_notice_to_dungeon_member_fails_without_creating_knowledge():
    runtime = SocialCommunicationAincradRuntime(seed=906)
    leader = runtime.create_character("Leader")
    member = runtime.create_character("Member")
    guild = runtime.create_guild(leader.actor_id, "Dungeon Signals")
    invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
    runtime.accept_guild_invite(invite.invite_id, member.actor_id)
    runtime.record_observation(leader.actor_id, "retreat:test", True, observation_location_id=TOWN)
    member.location_id = LABYRINTH
    delivery = runtime.post_guild_fact_notice(leader.actor_id, guild.guild_id, "retreat:test")[0]
    runtime.advance_world(GUILD_NOTICE_DELAY_MS)
    assert runtime.social_deliveries[delivery.delivery_id].status.value == "failed"
    assert runtime.belief(member.actor_id, "retreat:test") is None


def test_social_delivery_and_cursors_round_trip_midflight_and_deliver_once():
    runtime = SocialCommunicationAincradRuntime(seed=907)
    sender = runtime.create_character("A")
    receiver = runtime.create_character("B")
    source = runtime.record_observation(
        sender.actor_id, "rumor:save", 7, observation_location_id=TOWN
    )
    delivery = next(
        row for row in runtime.spread_local_rumor(sender.actor_id, "rumor:save")
        if row.recipient_id == receiver.actor_id
    )
    runtime.advance_world(LOCAL_RUMOR_DELAY_MS // 2)
    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, SocialCommunicationAincradRuntime)
    restored_delivery = restored.social_deliveries[delivery.delivery_id]
    assert restored_delivery.pending
    remaining = restored_delivery.due_at_ms - restored.world.now_ms
    restored.advance_world(remaining)
    received = restored.belief(receiver.actor_id, "rumor:save")
    assert received is not None
    assert received.evidence_event_ids == (source.event_id,)
    before = len(restored.knowledge_history(receiver.actor_id, "rumor:save"))
    restored.advance_world(SOCIAL_TICK_MS)
    after = len(restored.knowledge_history(receiver.actor_id, "rumor:save"))
    assert after == before


def test_top_runtime_player_identity_uses_knowledge_not_known_player_metadata():
    runtime = SocialCommunicationAincradRuntime(seed=908)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    runtime.learn_player_identity(a.actor_id, b.actor_id)
    assert "known_player_ids" not in a.metadata
    assert runtime.belief(a.actor_id, f"player_identity:{b.actor_id}") is not None
    runtime.send_short_message(a.actor_id, b.actor_id, "hello")
