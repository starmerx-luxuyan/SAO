from __future__ import annotations

import random
from dataclasses import dataclass

from sao_mcp.domain.models import EnhancementTrack, ItemInstance


@dataclass(slots=True, frozen=True)
class EnhancementPreview:
    success_probability: float
    attempts_remaining_before: int
    end_product: bool
    destructive_if_forced: bool


@dataclass(slots=True, frozen=True)
class EnhancementResolution:
    attempted: bool
    success: bool = False
    destroyed: bool = False
    probability: float = 0.0
    attempts_remaining_after: int = 0
    new_track_level: int = 0
    reason: str | None = None


def enhancement_probability(
    *,
    smith_proficiency: float,
    material_quality: float,
    item_difficulty: float,
    existing_total_enhancements: int,
) -> float:
    """Simulation probability. Canon defines attempts/tracks, not this numeric formula."""
    proficiency = max(0.0, min(1000.0, smith_proficiency)) / 1000.0
    material = max(0.25, min(2.0, material_quality))
    difficulty = max(0.1, item_difficulty)
    pressure = 1.0 + max(0, existing_total_enhancements) * 0.07
    raw = 0.18 + proficiency * 0.68 + (material - 1.0) * 0.18 - (difficulty - 1.0) * 0.15
    return max(0.05, min(0.95, raw / pressure))


def preview_enhancement(
    item: ItemInstance,
    *,
    smith_proficiency: float,
    material_quality: float,
    item_difficulty: float,
) -> EnhancementPreview:
    remaining = max(0, item.max_enhancement_attempts - item.enhancement_attempts_used)
    total = sum(item.enhancements.values())
    chance = enhancement_probability(
        smith_proficiency=smith_proficiency,
        material_quality=material_quality,
        item_difficulty=item_difficulty,
        existing_total_enhancements=total,
    )
    return EnhancementPreview(chance, remaining, item.enhancement_end_product, item.enhancement_end_product)


def attempt_enhancement(
    item: ItemInstance,
    track: EnhancementTrack,
    *,
    smith_proficiency: float,
    material_quality: float,
    item_difficulty: float,
    rng: random.Random,
    allow_destructive_overcap: bool = False,
) -> EnhancementResolution:
    preview = preview_enhancement(
        item,
        smith_proficiency=smith_proficiency,
        material_quality=material_quality,
        item_difficulty=item_difficulty,
    )
    if item.enhancement_end_product:
        if not allow_destructive_overcap:
            return EnhancementResolution(
                attempted=False,
                probability=preview.success_probability,
                attempts_remaining_after=0,
                new_track_level=item.enhancements.get(track, 0),
                reason="item is already an enhancement end product",
            )
        # In the finished SAO ruleset, attempting to reinforce an end product shatters it.
        item.durability = 0
        return EnhancementResolution(
            attempted=True,
            success=False,
            destroyed=True,
            probability=0.0,
            attempts_remaining_after=0,
            new_track_level=item.enhancements.get(track, 0),
            reason="forced enhancement of an end product shattered the item",
        )

    item.enhancement_attempts_used += 1
    success = rng.random() < preview.success_probability
    if success:
        item.enhancements[track] = item.enhancements.get(track, 0) + 1
    remaining = max(0, item.max_enhancement_attempts - item.enhancement_attempts_used)
    return EnhancementResolution(
        attempted=True,
        success=success,
        probability=preview.success_probability,
        attempts_remaining_after=remaining,
        new_track_level=item.enhancements.get(track, 0),
    )


@dataclass(slots=True, frozen=True)
class CraftQuality:
    multiplier: float
    grade: str


def roll_craft_quality(
    *,
    smith_proficiency: float,
    material_quality: float,
    item_difficulty: float,
    rng: random.Random,
) -> CraftQuality:
    """Valid-material crafting creates a product; its quality varies."""
    skill = max(0.0, min(1000.0, smith_proficiency)) / 1000.0
    center = 0.78 + skill * 0.38 + (material_quality - 1.0) * 0.16 - max(0.0, item_difficulty - 1.0) * 0.10
    multiplier = max(0.60, min(1.35, rng.gauss(center, 0.07)))
    if multiplier >= 1.18:
        grade = "exceptional"
    elif multiplier >= 1.04:
        grade = "high"
    elif multiplier >= 0.90:
        grade = "standard"
    else:
        grade = "rough"
    return CraftQuality(multiplier=multiplier, grade=grade)
