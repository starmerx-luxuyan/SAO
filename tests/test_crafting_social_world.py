import random

import pytest

from sao_mcp.domain.models import (
    CombatantState,
    CursorColor,
    EnhancementTrack,
    EntityKind,
    ItemInstance,
    PartyState,
    RaidState,
)
from sao_mcp.rules.crafting import attempt_enhancement
from sao_mcp.rules.social import add_party_member, add_raid_party, apply_unlawful_hostile_action
from sao_mcp.rules.world import NEXT_FLOOR_AUTO_GATE_DELAY_MS, advance_world_time, defeat_floor_boss, make_aincrad_world


def test_enhancement_consumes_attempt_on_success_or_failure():
    item = ItemInstance("w", "x", max_enhancement_attempts=2, durability=100, max_durability=100)
    first = attempt_enhancement(item, EnhancementTrack.SHARPNESS, smith_proficiency=0, material_quality=0.25, item_difficulty=2, rng=random.Random(1))
    assert first.attempted
    assert item.enhancement_attempts_used == 1
    second = attempt_enhancement(item, EnhancementTrack.DURABILITY, smith_proficiency=1000, material_quality=2, item_difficulty=0.5, rng=random.Random(2))
    assert second.attempted
    assert item.enhancement_attempts_used == 2
    refused = attempt_enhancement(item, EnhancementTrack.ACCURACY, smith_proficiency=1000, material_quality=2, item_difficulty=0.5, rng=random.Random(3))
    assert not refused.attempted


def test_party_and_raid_caps_are_canonical():
    party = PartyState("party", "p0", ["p0"])
    for i in range(1, 6):
        add_party_member(party, f"p{i}")
    with pytest.raises(ValueError):
        add_party_member(party, "p6")

    raid = RaidState("raid", "p0", ["party0"])
    for i in range(1, 8):
        add_raid_party(raid, f"party{i}")
    with pytest.raises(ValueError):
        add_raid_party(raid, "party8")


def test_green_on_green_hostility_turns_attacker_orange_but_orange_target_does_not():
    attacker = CombatantState("a", "A", EntityKind.PLAYER, 1, 100, 100, 10, 10)
    target = CombatantState("b", "B", EntityKind.PLAYER, 1, 100, 100, 10, 10)
    assert apply_unlawful_hostile_action(attacker, target, safe_zone=False)
    assert attacker.cursor is CursorColor.ORANGE

    hunter = CombatantState("h", "H", EntityKind.PLAYER, 1, 100, 100, 10, 10)
    assert not apply_unlawful_hostile_action(hunter, attacker, safe_zone=False)
    assert hunter.cursor is CursorColor.GREEN


def test_floor_boss_schedules_next_gate_after_two_hours():
    world = make_aincrad_world()
    defeat_floor_boss(world, 1)
    assert not world.floors[2].unlocked
    advance_world_time(world, NEXT_FLOOR_AUTO_GATE_DELAY_MS - 1)
    assert not world.floors[2].unlocked
    activated = advance_world_time(world, 1)
    assert activated == [2]
    assert world.floors[2].unlocked
    assert world.floors[2].main_town_gate_active
