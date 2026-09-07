import random

from sao_mcp.domain.models import EnhancementTrack, ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.reinforcement import (
    BASE_MATERIAL_ID,
    ReinforcementFailure,
    preview_reinforcement,
    reinforce_item,
)
from sao_mcp.runtime.engine import GameRuntime


def _give(runtime: GameRuntime, actor_id: str, template_id: str, quantity: int) -> ItemInstance:
    item = ItemInstance(
        instance_id=f"test_{template_id}",
        template_id=template_id,
        owner_id=actor_id,
        quantity=quantity,
    )
    add_item(runtime.actors[actor_id], item, runtime.catalog, allow_overweight=True)
    return item


def _materials(runtime: GameRuntime, actor_id: str, track: str, quantity: int = 5):
    base = _give(runtime, actor_id, BASE_MATERIAL_ID, quantity)
    extra = _give(runtime, actor_id, f"reinforcement_{track}_material", quantity)
    return base, extra


def test_reinforcement_consumes_materials_and_attempt_on_success():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Smith")
    weapon = actor.inventory[actor.equipment["weapon"]]
    base, extra = _materials(runtime, actor.actor_id, "sharpness", 5)
    result = reinforce_item(
        actor,
        weapon,
        EnhancementTrack.SHARPNESS,
        runtime.catalog,
        smith_proficiency=1000,
        additional_material_quantity=5,
        hammer_hits=10,
        elapsed_since_first_hit_ms=30_000,
        rng=random.Random(1),
    )
    assert result.attempted and result.success
    assert weapon.enhancement_attempts_used == 1
    assert weapon.enhancements[EnhancementTrack.SHARPNESS] == 1
    assert actor.inventory[base.instance_id].quantity == 4
    assert extra.instance_id not in actor.inventory


def test_timing_failure_consumes_attempt_and_materials():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Smith")
    weapon = actor.inventory[actor.equipment["weapon"]]
    _materials(runtime, actor.actor_id, "accuracy", 2)
    result = reinforce_item(
        actor,
        weapon,
        EnhancementTrack.ACCURACY,
        runtime.catalog,
        smith_proficiency=1000,
        additional_material_quantity=1,
        hammer_hits=10,
        elapsed_since_first_hit_ms=180_001,
        rng=random.Random(1),
    )
    assert result.attempted and not result.success
    assert result.failure is ReinforcementFailure.TIMING_FAILURE
    assert weapon.enhancement_attempts_used == 1
    assert EnhancementTrack.ACCURACY not in weapon.enhancements


def test_post_plus_four_success_penalty_is_explicit():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Smith")
    weapon = actor.inventory[actor.equipment["weapon"]]
    before = preview_reinforcement(
        weapon,
        EnhancementTrack.SHARPNESS,
        smith_proficiency=700,
        additional_material_quantity=1,
    )
    weapon.enhancements[EnhancementTrack.SHARPNESS] = 4
    after = preview_reinforcement(
        weapon,
        EnhancementTrack.SHARPNESS,
        smith_proficiency=700,
        additional_material_quantity=1,
    )
    assert after.post_plus_four_penalty
    assert after.success_probability < before.success_probability


def test_end_product_refusal_preserves_materials_but_forced_attempt_shatters():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Smith")
    weapon = actor.inventory[actor.equipment["weapon"]]
    weapon.enhancement_attempts_used = weapon.max_enhancement_attempts
    base, extra = _materials(runtime, actor.actor_id, "heaviness", 2)
    refused = reinforce_item(
        actor,
        weapon,
        EnhancementTrack.HEAVINESS,
        runtime.catalog,
        smith_proficiency=1000,
        additional_material_quantity=1,
        hammer_hits=10,
        elapsed_since_first_hit_ms=30_000,
        rng=random.Random(1),
    )
    assert not refused.attempted and not refused.destroyed
    assert actor.inventory[base.instance_id].quantity == 2
    assert actor.inventory[extra.instance_id].quantity == 2

    forced = reinforce_item(
        actor,
        weapon,
        EnhancementTrack.HEAVINESS,
        runtime.catalog,
        smith_proficiency=1000,
        additional_material_quantity=1,
        hammer_hits=10,
        elapsed_since_first_hit_ms=30_000,
        rng=random.Random(1),
        force_end_product=True,
    )
    assert forced.attempted and forced.destroyed
    assert forced.failure is ReinforcementFailure.END_PRODUCT_SHATTER
    assert weapon.durability == 0


def test_durability_reinforcement_raises_instance_durability_ceiling():
    runtime = GameRuntime(seed=1)
    actor = runtime.create_character("Smith")
    weapon = actor.inventory[actor.equipment["weapon"]]
    _materials(runtime, actor.actor_id, "durability", 5)
    old_max = weapon.max_durability
    result = reinforce_item(
        actor,
        weapon,
        EnhancementTrack.DURABILITY,
        runtime.catalog,
        smith_proficiency=1000,
        additional_material_quantity=5,
        hammer_hits=10,
        elapsed_since_first_hit_ms=20_000,
        rng=random.Random(1),
    )
    assert result.success
    assert weapon.max_durability > old_max
    assert weapon.durability == weapon.max_durability
