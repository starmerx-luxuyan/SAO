import pytest

from sao_mcp.corpus.core import build_core_catalog
from sao_mcp.domain.models import CombatantState, EntityKind, ItemInstance
from sao_mcp.rules.inventory import (
    carry_capacity,
    equip,
    inventory_weight,
    repair_item,
    transfer_item,
)
from sao_mcp.runtime.engine import GameRuntime


def test_new_character_has_equipped_body_armor_within_weight_limit():
    rt = GameRuntime(seed=1)
    actor = rt.create_character("A")
    assert actor.armor > 0
    assert "weapon" in actor.equipment
    assert "body" in actor.equipment
    assert inventory_weight(actor, rt.catalog) <= carry_capacity(actor)


def test_equipped_item_cannot_be_transferred_until_unequipped():
    rt = GameRuntime(seed=1)
    source = rt.create_character("A")
    dest = rt.create_character("B")
    weapon_id = source.equipment["weapon"]
    with pytest.raises(ValueError):
        transfer_item(source, dest, weapon_id, rt.catalog)


def test_broken_item_cannot_be_equipped_and_repair_restores_durability():
    catalog = build_core_catalog()
    actor = CombatantState("p", "P", EntityKind.PLAYER, 1, 625, 625, 10, 10, col=100)
    template = catalog.weapons["starter_one_hand_sword"]
    item = ItemInstance("w", template.template_id, actor.actor_id, durability=0, max_durability=100)
    actor.inventory[item.instance_id] = item
    with pytest.raises(ValueError):
        equip(actor, item.instance_id, catalog)
    repaired = repair_item(actor, item.instance_id, catalog, smith_proficiency=1000)
    assert repaired.repaired == 100
    assert item.durability == 100
    assert actor.col < 100


def test_monster_defeat_rewards_once_and_party_shares_xp_col():
    rt = GameRuntime(seed=7)
    a = rt.create_character("A", level=3)
    b = rt.create_character("B", level=3)
    party = rt.create_party(a.actor_id)
    rt.join_party(party.party_id, b.actor_id)
    monster = rt.create_training_monster(level=1)
    monster.hp = 1
    monster.max_hp = 1
    monster.agility = -100
    enc = rt.start_encounter([a.actor_id, b.actor_id, monster.actor_id])
    a_xp_before = int(a.metadata["experience"])
    b_xp_before = int(b.metadata["experience"])
    a_col_before = a.col
    b_col_before = b.col

    result = rt.attack(enc.encounter_id, a.actor_id, monster.actor_id, defense="none", seed=5)
    assert result.hit
    assert not monster.alive
    assert int(a.metadata["experience"]) > a_xp_before
    assert int(b.metadata["experience"]) > b_xp_before
    assert a.col + b.col > a_col_before + b_col_before
    loot_events = [event for event in enc.events if event.event_type == "loot_awarded"]
    assert len(loot_events) == 1

    again = rt.attack(enc.encounter_id, a.actor_id, monster.actor_id, defense="none", seed=5)
    assert not again.legal
    assert len([event for event in enc.events if event.event_type == "loot_awarded"]) == 1
