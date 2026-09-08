from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import (
    CombatantState,
    ConsumableEffect,
    ConsumableTemplate,
    ItemInstance,
    StatusEffectState,
    StatusType,
)


POTION_COOLDOWN_KEY = "potion"
EQUIPMENT_HP_REGEN_RATIO_PER_SECOND = 0.0025  # Simulation rate for tagged continuous-regeneration equipment.


@dataclass(slots=True, frozen=True)
class ConsumableResolution:
    consumed: bool
    healed: int = 0
    status_added: StatusEffectState | None = None
    statuses_removed: tuple[StatusType, ...] = ()
    travel_effect: str | None = None
    reason: str | None = None


def _is_silenced(actor: CombatantState) -> bool:
    return any(status.status_type is StatusType.SILENCE for status in actor.statuses)


def use_consumable(
    actor: CombatantState,
    item: ItemInstance,
    template: ConsumableTemplate,
    *,
    now_ms: int,
    anti_crystal: bool = False,
) -> ConsumableResolution:
    if item.quantity <= 0:
        return ConsumableResolution(False, reason="no item remaining")
    if not actor.alive:
        return ConsumableResolution(False, reason="actor is defeated")

    is_crystal = "crystal" in template.tags
    if is_crystal and anti_crystal:
        return ConsumableResolution(False, reason="crystal use is blocked in this zone")
    if template.requires_voice and _is_silenced(actor):
        return ConsumableResolution(False, reason="voice activation is blocked")

    if template.effect is ConsumableEffect.HEAL_OVER_TIME:
        if actor.cooldowns_until_ms.get(POTION_COOLDOWN_KEY, 0) > now_ms:
            return ConsumableResolution(False, reason="potion cooldown is active")
        duration = max(1000, template.duration_ms)
        tick = min(1000, duration)
        total_heal = max(0, template.magnitude)
        ticks = max(1, duration // tick)
        regen = StatusEffectState(
            effect_id=f"regen:{item.instance_id}:{now_ms}",
            status_type=StatusType.REGEN,
            source_id=actor.actor_id,
            remaining_ms=duration,
            magnitude=float(total_heal) / ticks,
            tick_interval_ms=tick,
            until_next_tick_ms=tick,
            stack_key="potion_regen",
        )
        actor.statuses = [s for s in actor.statuses if s.stack_key != "potion_regen"]
        actor.statuses.append(regen)
        actor.cooldowns_until_ms[POTION_COOLDOWN_KEY] = now_ms + max(0, template.cooldown_ms)
        item.quantity -= 1
        return ConsumableResolution(True, status_added=regen)

    if template.effect is ConsumableEffect.HEAL_FULL:
        before = actor.hp
        actor.hp = actor.max_hp
        item.quantity -= 1
        return ConsumableResolution(True, healed=actor.hp - before)

    if template.effect is ConsumableEffect.CURE:
        allowed = set(template.status_tags)
        removed = tuple(s.status_type for s in actor.statuses if not allowed or s.status_type in allowed)
        if allowed:
            actor.statuses = [s for s in actor.statuses if s.status_type not in allowed]
        else:
            actor.statuses.clear()
        item.quantity -= 1
        return ConsumableResolution(True, statuses_removed=removed)

    if template.effect in (ConsumableEffect.TELEPORT, ConsumableEffect.CORRIDOR):
        item.quantity -= 1
        return ConsumableResolution(True, travel_effect=template.effect.value)

    return ConsumableResolution(False, reason="unsupported consumable effect")


def tick_statuses(actor: CombatantState, elapsed_ms: int) -> list[tuple[StatusType, int]]:
    if elapsed_ms < 0:
        raise ValueError("elapsed_ms must be >= 0")
    events: list[tuple[StatusType, int]] = []

    poison_nullifier = actor.metadata.get("equipment_poison_nullification_instance_id")
    if poison_nullifier and poison_nullifier in actor.equipment.values():
        actor.statuses = [status for status in actor.statuses if status.status_type is not StatusType.POISON]

    kept: list[StatusEffectState] = []
    for status in actor.statuses:
        remaining_step = elapsed_ms
        while remaining_step > 0 and status.remaining_ms > 0:
            step = min(remaining_step, status.until_next_tick_ms, status.remaining_ms)
            status.remaining_ms -= step
            status.until_next_tick_ms -= step
            remaining_step -= step
            if status.until_next_tick_ms <= 0:
                amount = int(round(status.magnitude))
                if status.status_type is StatusType.REGEN:
                    before = actor.hp
                    actor.hp = min(actor.max_hp, actor.hp + max(0, amount))
                    events.append((status.status_type, actor.hp - before))
                elif status.status_type in (StatusType.POISON, StatusType.BLEED):
                    before = actor.hp
                    actor.hp = max(0, actor.hp - max(0, amount))
                    actor.alive = actor.hp > 0
                    events.append((status.status_type, -(before - actor.hp)))
                status.until_next_tick_ms += max(1, status.tick_interval_ms)
        if status.remaining_ms > 0:
            kept.append(status)
    actor.statuses = kept

    regeneration_item = actor.metadata.get("equipment_hp_regeneration_instance_id")
    if (
        elapsed_ms > 0
        and actor.alive
        and actor.hp < actor.max_hp
        and regeneration_item
        and regeneration_item in actor.equipment.values()
    ):
        heal = int(actor.max_hp * EQUIPMENT_HP_REGEN_RATIO_PER_SECOND * elapsed_ms / 1000.0)
        if heal > 0:
            before = actor.hp
            actor.hp = min(actor.max_hp, actor.hp + heal)
            events.append((StatusType.REGEN, actor.hp - before))

    actor.clamp_hp()
    return events
