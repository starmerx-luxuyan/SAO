from sao_mcp.corpus.core import build_core_catalog
from sao_mcp.domain.models import CombatantState, EntityKind, ItemInstance, StatusEffectState, StatusType
from sao_mcp.rules.items import tick_statuses, use_consumable


def player():
    return CombatantState("p", "Player", EntityKind.PLAYER, 1, 1000, 100, 10, 10)


def test_potion_heals_total_magnitude_over_time_and_starts_cooldown():
    catalog = build_core_catalog()
    actor = player()
    item = ItemInstance("pot", "healing_potion_basic", actor.actor_id, quantity=2)
    result = use_consumable(actor, item, catalog.consumables[item.template_id], now_ms=0)
    assert result.consumed
    assert item.quantity == 1
    assert actor.hp == 100
    tick_statuses(actor, 20_000)
    assert actor.hp == 700
    blocked = use_consumable(actor, item, catalog.consumables[item.template_id], now_ms=20_000)
    assert not blocked.consumed
    assert item.quantity == 1


def test_healing_crystal_is_instant_and_blocked_by_anti_crystal_zone():
    catalog = build_core_catalog()
    actor = player()
    crystal = ItemInstance("c", "healing_crystal", actor.actor_id, quantity=2)
    blocked = use_consumable(actor, crystal, catalog.consumables[crystal.template_id], now_ms=0, anti_crystal=True)
    assert not blocked.consumed
    assert crystal.quantity == 2
    healed = use_consumable(actor, crystal, catalog.consumables[crystal.template_id], now_ms=0)
    assert healed.consumed
    assert actor.hp == actor.max_hp
    assert crystal.quantity == 1


def test_voice_crystal_is_blocked_by_silence_without_consumption():
    catalog = build_core_catalog()
    actor = player()
    actor.statuses.append(StatusEffectState("sil", StatusType.SILENCE, None, 1000))
    crystal = ItemInstance("c", "teleport_crystal", actor.actor_id, quantity=1)
    result = use_consumable(actor, crystal, catalog.consumables[crystal.template_id], now_ms=0)
    assert not result.consumed
    assert crystal.quantity == 1
