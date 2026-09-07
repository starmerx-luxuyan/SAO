from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import CombatantState, EnhancementTrack, ItemInstance, ItemKind


BASE_MATERIAL_ID = "reinforcement_base_material"
ADDITIONAL_MATERIAL_BY_TRACK: dict[EnhancementTrack, str] = {
    EnhancementTrack.SHARPNESS: "reinforcement_sharpness_material",
    EnhancementTrack.QUICKNESS: "reinforcement_quickness_material",
    EnhancementTrack.ACCURACY: "reinforcement_accuracy_material",
    EnhancementTrack.HEAVINESS: "reinforcement_heaviness_material",
    EnhancementTrack.DURABILITY: "reinforcement_durability_material",
}
REQUIRED_HAMMER_HITS = 10
HAMMER_DEADLINE_MS = 3 * 60 * 1000


class ReinforcementFailure(StrEnum):
    NONE = "none"
    MATERIALS_ONLY = "materials_only"
    PROPERTY_SHIFT = "property_shift"
    LEVEL_LOSS = "level_loss"
    TIMING_FAILURE = "timing_failure"
    END_PRODUCT_SHATTER = "end_product_shatter"


@dataclass(slots=True, frozen=True)
class ReinforcementPreview:
    track: EnhancementTrack
    success_probability: float
    attempts_remaining: int
    total_successful_enhancements: int
    base_material_id: str
    additional_material_id: str
    additional_material_quantity: int
    post_plus_four_penalty: bool
    hammer_hits_required: int = REQUIRED_HAMMER_HITS
    hammer_deadline_ms: int = HAMMER_DEADLINE_MS


@dataclass(slots=True, frozen=True)
class DetailedReinforcementResolution:
    attempted: bool
    success: bool
    destroyed: bool
    track: EnhancementTrack
    success_probability: float
    failure: ReinforcementFailure
    attempts_used_after: int
    attempts_remaining_after: int
    total_enhancement_after: int
    enhancements_before: dict[EnhancementTrack, int]
    enhancements_after: dict[EnhancementTrack, int]
    materials_consumed: tuple[tuple[str, int], ...]
    hammer_hits: int
    elapsed_since_first_hit_ms: int
    reason: str | None = None


def _count(actor: CombatantState, template_id: str) -> int:
    return sum(item.quantity for item in actor.inventory.values() if item.template_id == template_id)


def _consume(actor: CombatantState, template_id: str, quantity: int) -> None:
    remaining = quantity
    for instance_id, item in list(actor.inventory.items()):
        if item.template_id != template_id:
            continue
        if instance_id in actor.equipment.values():
            raise ValueError("equipped item cannot be consumed as reinforcement material")
        used = min(remaining, item.quantity)
        item.quantity -= used
        remaining -= used
        if item.quantity <= 0:
            actor.inventory.pop(instance_id)
        if remaining <= 0:
            return
    raise ValueError(f"insufficient reinforcement material: {template_id}")


def reinforcement_probability(
    item: ItemInstance,
    *,
    smith_proficiency: float,
    additional_material_quantity: int,
) -> float:
    """Simulation probability layered onto canon material/attempt/failure structure."""
    skill = max(0.0, min(1000.0, smith_proficiency)) / 1000.0
    extras = max(1, additional_material_quantity)
    total = sum(max(0, value) for value in item.enhancements.values())
    quality_adjustment = max(-0.08, min(0.10, (item.quality - 1.0) * 0.20))
    chance = 0.24 + skill * 0.56 + min(0.28, (extras - 1) * 0.025) + quality_adjustment
    if total >= 4:
        # Canon says success rate drops greatly after +4; exact curve is simulation tuning.
        chance *= max(0.32, 0.68 - (total - 4) * 0.055)
    return max(0.03, min(0.97, chance))


def preview_reinforcement(
    item: ItemInstance,
    track: EnhancementTrack,
    *,
    smith_proficiency: float,
    additional_material_quantity: int,
) -> ReinforcementPreview:
    if additional_material_quantity < 1:
        raise ValueError("at least one property-specific additional material is required")
    total = sum(max(0, value) for value in item.enhancements.values())
    return ReinforcementPreview(
        track=track,
        success_probability=reinforcement_probability(
            item,
            smith_proficiency=smith_proficiency,
            additional_material_quantity=additional_material_quantity,
        ),
        attempts_remaining=max(0, item.max_enhancement_attempts - item.enhancement_attempts_used),
        total_successful_enhancements=total,
        base_material_id=BASE_MATERIAL_ID,
        additional_material_id=ADDITIONAL_MATERIAL_BY_TRACK[track],
        additional_material_quantity=additional_material_quantity,
        post_plus_four_penalty=total >= 4,
    )


def _apply_durability_success(item: ItemInstance) -> None:
    if item.max_durability is None:
        return
    increase = max(1, int(round(item.max_durability * 0.05)))
    item.max_durability += increase
    if item.durability is not None:
        item.durability += increase


def _failure_mutation(item: ItemInstance, rng: random.Random) -> ReinforcementFailure:
    positive = [track for track, value in item.enhancements.items() if value > 0]
    if not positive:
        return ReinforcementFailure.MATERIALS_ONLY
    roll = rng.random()
    if roll < 0.58:
        return ReinforcementFailure.MATERIALS_ONLY
    if roll < 0.82:
        source = rng.choice(positive)
        targets = [track for track in EnhancementTrack if track is not source]
        destination = rng.choice(targets)
        item.enhancements[source] -= 1
        if item.enhancements[source] <= 0:
            item.enhancements.pop(source, None)
        item.enhancements[destination] = item.enhancements.get(destination, 0) + 1
        return ReinforcementFailure.PROPERTY_SHIFT
    source = rng.choice(positive)
    item.enhancements[source] -= 1
    if item.enhancements[source] <= 0:
        item.enhancements.pop(source, None)
    return ReinforcementFailure.LEVEL_LOSS


def reinforce_item(
    actor: CombatantState,
    item: ItemInstance,
    track: EnhancementTrack,
    catalog: Catalog,
    *,
    smith_proficiency: float,
    additional_material_quantity: int,
    hammer_hits: int,
    elapsed_since_first_hit_ms: int,
    rng: random.Random,
    force_end_product: bool = False,
) -> DetailedReinforcementResolution:
    template = catalog.item(item.template_id)
    if template.kind not in (ItemKind.WEAPON, ItemKind.ARMOR, ItemKind.SHIELD):
        raise ValueError("item type cannot be reinforced")
    if item.owner_id != actor.actor_id or item.instance_id not in actor.inventory:
        raise ValueError("item must be in the smith/owner inventory for this runtime operation")
    if item.broken:
        raise ValueError("broken item must be repaired before reinforcement")
    if hammer_hits < 0 or elapsed_since_first_hit_ms < 0:
        raise ValueError("hammer timing values must be non-negative")

    preview = preview_reinforcement(
        item,
        track,
        smith_proficiency=smith_proficiency,
        additional_material_quantity=additional_material_quantity,
    )
    material_id = preview.additional_material_id
    if _count(actor, BASE_MATERIAL_ID) < 1:
        raise ValueError(f"insufficient reinforcement material: {BASE_MATERIAL_ID}")
    if _count(actor, material_id) < additional_material_quantity:
        raise ValueError(f"insufficient reinforcement material: {material_id}")

    before = dict(item.enhancements)
    consumed = ((BASE_MATERIAL_ID, 1), (material_id, additional_material_quantity))

    if item.enhancement_end_product and not force_end_product:
        return DetailedReinforcementResolution(
            attempted=False,
            success=False,
            destroyed=False,
            track=track,
            success_probability=0.0,
            failure=ReinforcementFailure.NONE,
            attempts_used_after=item.enhancement_attempts_used,
            attempts_remaining_after=0,
            total_enhancement_after=sum(item.enhancements.values()),
            enhancements_before=before,
            enhancements_after=dict(item.enhancements),
            materials_consumed=(),
            hammer_hits=hammer_hits,
            elapsed_since_first_hit_ms=elapsed_since_first_hit_ms,
            reason="item is already an enhancement end product",
        )

    # Materials enter the furnace before hammering and are therefore lost for every actual attempt.
    _consume(actor, BASE_MATERIAL_ID, 1)
    _consume(actor, material_id, additional_material_quantity)

    if item.enhancement_end_product:
        item.durability = 0
        return DetailedReinforcementResolution(
            attempted=True,
            success=False,
            destroyed=True,
            track=track,
            success_probability=0.0,
            failure=ReinforcementFailure.END_PRODUCT_SHATTER,
            attempts_used_after=item.enhancement_attempts_used,
            attempts_remaining_after=0,
            total_enhancement_after=sum(item.enhancements.values()),
            enhancements_before=before,
            enhancements_after=dict(item.enhancements),
            materials_consumed=consumed,
            hammer_hits=hammer_hits,
            elapsed_since_first_hit_ms=elapsed_since_first_hit_ms,
            reason="attempting to reinforce an end product shattered it",
        )

    item.enhancement_attempts_used += 1
    timed_out = elapsed_since_first_hit_ms > HAMMER_DEADLINE_MS
    invalid_hits = hammer_hits != REQUIRED_HAMMER_HITS
    if timed_out or invalid_hits:
        failure = ReinforcementFailure.TIMING_FAILURE
        success = False
    else:
        success = rng.random() < preview.success_probability
        failure = ReinforcementFailure.NONE if success else _failure_mutation(item, rng)

    if success:
        item.enhancements[track] = item.enhancements.get(track, 0) + 1
        if track is EnhancementTrack.DURABILITY:
            _apply_durability_success(item)

    remaining = max(0, item.max_enhancement_attempts - item.enhancement_attempts_used)
    reason = None
    if timed_out:
        reason = "ten hammer strikes were not completed within three minutes"
    elif invalid_hits:
        reason = "a completed reinforcement operation requires exactly ten hammer strikes"

    return DetailedReinforcementResolution(
        attempted=True,
        success=success,
        destroyed=False,
        track=track,
        success_probability=preview.success_probability,
        failure=failure,
        attempts_used_after=item.enhancement_attempts_used,
        attempts_remaining_after=remaining,
        total_enhancement_after=sum(item.enhancements.values()),
        enhancements_before=before,
        enhancements_after=dict(item.enhancements),
        materials_consumed=consumed,
        hammer_hits=hammer_hits,
        elapsed_since_first_hit_ms=elapsed_since_first_hit_ms,
        reason=reason,
    )
