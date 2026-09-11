import pytest

from sao_mcp.runtime.gm_observation import GMObservationGate
from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


TOWN = "floor_1_town_of_beginnings"
HORUNKA = "floor_1_horunka"
WEST = "floor_1_west_field"


def test_gate_requires_explicit_unique_player_viewpoints():
    runtime = SocialCommunicationAincradRuntime(seed=1701)
    player = runtime.create_character("Player")
    gate = GMObservationGate(runtime)
    with pytest.raises(ValueError, match="at least one explicit player viewpoint"):
        gate.observe([])
    with pytest.raises(ValueError, match="unique"):
        gate.observe([player.actor_id, player.actor_id])
    with pytest.raises(KeyError):
        gate.observe(["missing"])


def test_remote_private_state_and_other_entities_knowledge_do_not_enter_player_packet():
    runtime = SocialCommunicationAincradRuntime(seed=1702)
    player = runtime.create_character("Observer")
    remote = runtime.create_character("Remote")
    remote.location_id = HORUNKA
    runtime.record_observation(remote.actor_id, "private:remote", "secret", observation_location_id=HORUNKA)
    runtime.set_npc_goal("npc_tutorial_instructor", "hidden:goal", WEST, priority=999)
    gate = GMObservationGate(runtime)
    packet = gate.observe([player.actor_id])
    view = packet["viewpoints"][player.actor_id]
    dumped = repr(packet)
    assert "private:remote" not in dumped
    assert "hidden:goal" not in dumped
    assert "long_term_goals" not in dumped
    assert "short_term_plan" not in dumped
    assert "world_events" not in dumped
    assert remote.actor_id not in repr(view["visible_entities"])


def test_colocated_unknown_player_has_no_stable_identity_until_observed_identity_fact_exists():
    runtime = SocialCommunicationAincradRuntime(seed=1703)
    observer = runtime.create_character("Observer")
    stranger = runtime.create_character("Stranger")
    gate = GMObservationGate(runtime)
    before = gate.observe([observer.actor_id])["viewpoints"][observer.actor_id]["visible_entities"]
    unknown = next(row for row in before if row.get("display_name") == "Unknown Player")
    assert "actor_id" not in unknown
    assert unknown["scene_ref"].startswith("unknown_player_")

    runtime.learn_player_identity(observer.actor_id, stranger.actor_id)
    after = gate.observe([observer.actor_id])["viewpoints"][observer.actor_id]["visible_entities"]
    known = next(row for row in after if row.get("actor_id") == stranger.actor_id)
    assert known["display_name"] == "Stranger"


def test_gate_uses_observers_actual_belief_without_substituting_runtime_truth():
    runtime = SocialCommunicationAincradRuntime(seed=1704)
    observer = runtime.create_character("Observer")
    runtime.record_observation(
        observer.actor_id,
        "rumor:boss_state",
        {"alive": False},
        observation_location_id=TOWN,
        confidence=0.55,
    )
    packet = GMObservationGate(runtime).observe([observer.actor_id])
    fact = packet["viewpoints"][observer.actor_id]["knowledge"]["facts"]["rumor:boss_state"]
    assert fact["value"] == {"alive": False}
    assert fact["confidence"] == 0.55


def test_hidden_encounter_is_not_visible_to_unrelated_viewpoint():
    runtime = SocialCommunicationAincradRuntime(seed=1705)
    observer = runtime.create_character("Observer")
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    a.location_id = WEST
    b.location_id = WEST
    encounter = runtime.start_encounter([a.actor_id, b.actor_id], zone_id=WEST)
    packet = GMObservationGate(runtime).observe([observer.actor_id])
    assert encounter.encounter_id not in packet["viewpoints"][observer.actor_id]["encounters"]


def test_player_can_see_own_ui_state_but_not_guild_strategy_resources():
    runtime = SocialCommunicationAincradRuntime(seed=1706)
    leader = runtime.create_character("Leader")
    member = runtime.create_character("Member")
    guild = runtime.create_guild(leader.actor_id, "Visible Roster")
    invite = runtime.invite_to_guild(guild.guild_id, leader.actor_id, member.actor_id)
    runtime.accept_guild_invite(invite.invite_id, member.actor_id)
    guild.vault_col = 99999
    runtime.set_guild_strategy_goal(
        guild.guild_id, leader.actor_id, "secret_strategy", WEST, auto_dispatch=False
    )
    packet = GMObservationGate(runtime).observe([leader.actor_id])
    view = packet["viewpoints"][leader.actor_id]
    assert view["observer"]["col"] == leader.col
    assert view["guild"]["member_ids"] == guild.member_ids
    dumped = repr(view)
    assert "99999" not in dumped
    assert "secret_strategy" not in dumped
    assert "vault_col" not in dumped
    assert "strategic_goals" not in dumped
