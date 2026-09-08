from sao_mcp.corpus.canon_seed import apply_canon_seed
from sao_mcp.corpus.core import build_core_catalog
from sao_mcp.domain.models import CombatantState, EntityKind, WeaponClass
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


def test_expanded_aincrad_skill_corpus_keeps_known_unlocks_and_combo_counts():
    catalog = apply_canon_seed(build_core_catalog())
    assert catalog.sword_skills["rage_spike"].prerequisite_proficiency == 50
    assert catalog.sword_skills["horizontal_square"].prerequisite_proficiency == 150
    assert len(catalog.sword_skills["horizontal_square"].hits) == 4
    assert catalog.sword_skills["vorpal_strike"].prerequisite_proficiency == 950
    assert catalog.sword_skills["star_splash"].weapon_class is WeaponClass.RAPIER
    assert len(catalog.sword_skills["star_splash"].hits) == 8
    assert "first_aid" in catalog.skills
    assert "meditation" in catalog.skills
