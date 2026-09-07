import random

from sao_mcp.corpus.core import build_core_catalog
from sao_mcp.domain.models import CombatantState, DefenseMode, EntityKind, ItemInstance
from sao_mcp.rules.combat import effective_attack_speed_ms, resolve_physical_attack


def fighter(actor_id: str, agility: int = 20):
    return CombatantState(actor_id, actor_id, EntityKind.PLAYER, 10, 2000, 2000, 30, agility, skill_proficiencies={"one_hand_sword": 500, "parry": 0})


def test_quickness_reduces_attack_time():
    catalog = build_core_catalog()
    weapon = catalog.weapons["starter_one_hand_sword"]
    normal = ItemInstance("a", weapon.template_id, durability=100, max_durability=100)
    quick = ItemInstance("b", weapon.template_id, durability=100, max_durability=100)
    from sao_mcp.domain.models import EnhancementTrack
    quick.enhancements[EnhancementTrack.QUICKNESS] = 5
    assert effective_attack_speed_ms(weapon, quick) < effective_attack_speed_ms(weapon, normal)


def test_sword_skill_has_post_motion_recovery():
    catalog = build_core_catalog()
    weapon = catalog.weapons["starter_one_hand_sword"]
    item = ItemInstance("w", weapon.template_id, durability=100, max_durability=100)
    attacker = fighter("a", 30)
    defender = fighter("d", 10)
    result = resolve_physical_attack(
        attacker,
        defender,
        item,
        weapon,
        now_ms=0,
        rng=random.Random(4),
        sword_skill=catalog.sword_skills["horizontal"],
        defense=DefenseMode.NONE,
    )
    assert result.legal
    assert result.action_end_ms > 0
    assert result.recovery_end_ms > result.action_end_ms


def test_high_parry_can_cancel_hit_before_damage():
    catalog = build_core_catalog()
    weapon = catalog.weapons["starter_one_hand_sword"]
    item = ItemInstance("w", weapon.template_id, durability=100, max_durability=100)
    attacker = fighter("a", 20)
    defender = fighter("d", 30)
    defender.skill_proficiencies["parry"] = 1000
    result = resolve_physical_attack(attacker, defender, item, weapon, now_ms=0, rng=random.Random(1), defense=DefenseMode.PARRY)
    assert result.legal
    assert result.parried
    assert not result.hit
    assert result.damage == 0
