from sao_mcp.domain.models import CombatantState, EntityKind
from sao_mcp.rules.progression import (
    MAX_SKILL_PROFICIENCY,
    equip_skill,
    gain_skill_proficiency,
    remove_skill,
    skill_slot_count,
)


def actor(level=1):
    return CombatantState("p", "Player", EntityKind.PLAYER, level, 1000, 1000, 10, 10)


def test_canonical_skill_slot_breakpoints():
    assert skill_slot_count(1) == 2
    assert skill_slot_count(5) == 2
    assert skill_slot_count(6) == 3
    assert skill_slot_count(11) == 3
    assert skill_slot_count(12) == 4
    assert skill_slot_count(19) == 4
    assert skill_slot_count(20) == 5
    assert skill_slot_count(29) == 5
    assert skill_slot_count(30) == 6
    assert skill_slot_count(90) == 12
    assert skill_slot_count(100) == 13


def test_skill_removal_resets_proficiency_by_default():
    p = actor()
    equip_skill(p, "one_hand_sword")
    p.skill_proficiencies["one_hand_sword"] = 777
    remove_skill(p, "one_hand_sword")
    assert "one_hand_sword" not in p.skill_proficiencies


def test_proficiency_is_capped_at_1000():
    p = actor()
    equip_skill(p, "one_hand_sword")
    p.skill_proficiencies["one_hand_sword"] = 999.9
    gain_skill_proficiency(p, "one_hand_sword", 100)
    assert p.skill_proficiencies["one_hand_sword"] == MAX_SKILL_PROFICIENCY
