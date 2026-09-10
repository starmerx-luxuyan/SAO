import pytest

from sao_mcp.domain.models import CursorColor, DefenseMode, ItemInstance
from sao_mcp.rules.duels import DuelMode, DuelStatus
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_runtime import REVIVAL_WINDOW_MS, SocialTimelineAincradRuntime


def _safe_duel(runtime: SocialTimelineAincradRuntime, mode: DuelMode):
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    duel = runtime.challenge_duel(a.actor_id, b.actor_id, mode)
    accepted, encounter = runtime.accept_duel(duel.duel_id, b.actor_id)
    assert encounter.safe_zone is True
    return a, b, accepted, encounter


def test_unaccepted_safe_area_pvp_is_blocked_without_crime():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    encounter = runtime.start_encounter(
        [a.actor_id, b.actor_id],
        zone_id="floor_1_town_of_beginnings",
    )
    before = b.hp
    result, _ = runtime.attack_authoritative(
        encounter.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )
    assert not result.legal
    assert b.hp == before
    assert a.cursor is CursorColor.GREEN


def test_accepted_safe_area_duel_deals_damage_without_orange_cursor():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a, b, duel, encounter = _safe_duel(runtime, DuelMode.HALF_LOSS)
    a.strength = 50
    a.skill_proficiencies["one_hand_sword"] = 1000
    result, _ = runtime.attack_authoritative(
        encounter.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )
    assert result.legal and result.hit
    assert b.hp < b.max_hp
    assert a.cursor is CursorColor.GREEN
    assert b.cursor is CursorColor.GREEN
    assert runtime.duels.duels[duel.duel_id].status is DuelStatus.ACTIVE


def test_first_strike_completion_removes_safe_area_pvp_authorization():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a, b, duel, encounter = _safe_duel(runtime, DuelMode.FIRST_STRIKE)
    a.strength = 80
    a.skill_proficiencies["one_hand_sword"] = 1000
    # Keep the canonical 10% clean-hit threshold small and deterministic for the test fixture.
    b.max_hp = 100
    b.hp = 100
    duel.starting_hp[b.actor_id] = 100
    first, _ = runtime.attack_authoritative(
        encounter.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )
    assert first.legal and first.hit and first.damage >= 10
    assert runtime.duels.duels[duel.duel_id].status is DuelStatus.COMPLETED
    assert b.actor_id not in a.metadata.get("authorized_duel_opponents", ())

    assert encounter.active is False
    assert encounter.end_reason == f"duel_completed:{duel.duel_id}"
    a.recovery_until_ms = 0
    b.recovery_until_ms = 0
    later = runtime.start_encounter(
        [a.actor_id, b.actor_id],
        zone_id="floor_1_town_of_beginnings",
    )
    hp_before = b.hp
    second, _ = runtime.attack_authoritative(
        later.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=2,
    )
    assert not second.legal
    assert b.hp == hp_before


def test_illegal_field_pvp_still_turns_green_attacker_orange():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    a.location_id = "floor_1_west_field"
    b.location_id = "floor_1_west_field"
    encounter = runtime.start_encounter([a.actor_id, b.actor_id], zone_id="floor_1_west_field")
    result, _ = runtime.attack_authoritative(
        encounter.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )
    assert result.legal
    assert a.cursor is CursorColor.ORANGE
    assert a.infamy >= 1


def test_total_loss_enters_end_phase_then_finalizes_after_ten_seconds():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a, b, duel, encounter = _safe_duel(runtime, DuelMode.TOTAL_LOSS)
    a.strength = 100
    a.skill_proficiencies["one_hand_sword"] = 1000
    b.max_hp = 100
    b.hp = 1
    duel.starting_hp[b.actor_id] = 1
    result, _ = runtime.attack_authoritative(
        encounter.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )
    assert result.legal and result.hit
    assert b.hp == 0 and not b.alive
    assert b.metadata["death_state"] == "end_phase"
    assert b.metadata["permanent_death"] is False
    deadline = b.metadata["revive_until_encounter_ms"]
    assert deadline - encounter.time_ms == REVIVAL_WINDOW_MS
    assert runtime.duels.duels[duel.duel_id].status is DuelStatus.COMPLETED

    runtime.advance_encounter(encounter.encounter_id, REVIVAL_WINDOW_MS - 1)
    assert b.metadata["death_state"] == "end_phase"
    runtime.advance_encounter(encounter.encounter_id, 1)
    assert b.metadata["death_state"] == "permanent"
    assert b.metadata["permanent_death"] is True


def test_divine_stone_revives_during_end_phase_and_is_consumed():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a, b, duel, encounter = _safe_duel(runtime, DuelMode.TOTAL_LOSS)
    a.strength = 100
    a.skill_proficiencies["one_hand_sword"] = 1000
    b.hp = 1
    runtime.attack_authoritative(
        encounter.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )
    stone = ItemInstance(
        instance_id="revival_stone",
        template_id="divine_stone_returning_soul",
        owner_id=a.actor_id,
        quantity=1,
    )
    a.inventory[stone.instance_id] = stone
    result = runtime.revive_recently_fallen(
        encounter.encounter_id,
        a.actor_id,
        b.actor_id,
        stone.instance_id,
    )
    assert b.alive and b.hp > 0
    assert b.metadata.get("death_state") is None
    assert b.metadata["permanent_death"] is False
    assert stone.instance_id not in a.inventory
    assert result["revivalHpRatio"] == pytest.approx(0.25)


def test_expired_end_phase_cannot_be_revived():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a, b, _, encounter = _safe_duel(runtime, DuelMode.TOTAL_LOSS)
    a.strength = 100
    a.skill_proficiencies["one_hand_sword"] = 1000
    b.hp = 1
    runtime.attack_authoritative(
        encounter.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )
    runtime.advance_encounter(encounter.encounter_id, REVIVAL_WINDOW_MS)
    stone = ItemInstance("late_stone", "divine_stone_returning_soul", owner_id=a.actor_id)
    a.inventory[stone.instance_id] = stone
    with pytest.raises(ValueError, match="not in the revival End Phase"):
        runtime.revive_recently_fallen(encounter.encounter_id, a.actor_id, b.actor_id, stone.instance_id)
    assert stone.instance_id in a.inventory


def test_orange_player_cannot_use_normal_travel_into_protected_town():
    runtime = SocialTimelineAincradRuntime(seed=1)
    actor = runtime.create_character("Orange")
    actor.cursor = CursorColor.ORANGE
    actor.location_id = "floor_1_west_field"
    with pytest.raises(ValueError, match="Anti-Criminal Code"):
        runtime.travel_actor(actor.actor_id, "floor_1_town_of_beginnings")
    assert actor.location_id == "floor_1_west_field"


def test_failed_duel_acceptance_does_not_authorize_players():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    duel = runtime.challenge_duel(a.actor_id, b.actor_id, DuelMode.FIRST_STRIKE)
    b.location_id = "floor_1_west_field"
    with pytest.raises(ValueError, match="colocated"):
        runtime.accept_duel(duel.duel_id, b.actor_id)
    assert runtime.duels.duels[duel.duel_id].status is DuelStatus.PENDING
    assert b.actor_id not in a.metadata.get("authorized_duel_opponents", ())


def test_active_duel_round_trips_through_save():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a, b, duel, encounter = _safe_duel(runtime, DuelMode.HALF_LOSS)
    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, SocialTimelineAincradRuntime)
    loaded = restored.duels.duels[duel.duel_id]
    assert loaded.status is DuelStatus.ACTIVE
    assert b.actor_id in restored.actors[a.actor_id].metadata["authorized_duel_opponents"]
    assert encounter.encounter_id in restored.encounters


def test_draw_ends_duel_without_erasing_encounter_or_blocking_travel():
    runtime = SocialTimelineAincradRuntime(seed=1)
    a, b, duel, encounter = _safe_duel(runtime, DuelMode.FIRST_STRIKE)
    positions_before = dict(encounter.positions)

    evaluation = runtime.draw_duel(duel.duel_id)

    assert evaluation.completed is True
    assert runtime.duels.duels[duel.duel_id].status is DuelStatus.COMPLETED
    assert set(encounter.participants) == {a.actor_id, b.actor_id}
    assert encounter.positions == positions_before
    assert not runtime._in_live_encounter(a.actor_id)

    runtime.travel_actor(a.actor_id, "floor_1_west_field")
    assert a.location_id == "floor_1_west_field"
