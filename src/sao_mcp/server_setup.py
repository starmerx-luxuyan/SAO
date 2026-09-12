from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.domain.models import (
    ArmorTemplate,
    ConsumableEffect,
    ConsumableTemplate,
    DamageType,
    ItemKind,
    ItemTemplate,
    Provenance,
    ProvenanceKind,
    SkillDefinition,
    SkillKind,
    StatusType,
    SwordSkillDefinition,
    WeaponClass,
    WeaponTemplate,
)
from sao_mcp.runtime.character_setup import (
    begin_campaign_setup as _begin_campaign_setup,
    campaign_setup_state,
    character_setup_state,
    configure_character,
    finalize_campaign_setup as _finalize_campaign_setup,
    grant_character_item as _grant_character_item,
    remove_character_item,
    reopen_campaign_setup as _reopen_campaign_setup,
    require_campaign_setup_open,
)
from sao_mcp.rules.custom_mechanics import configure_custom_mechanics
from sao_mcp.runtime.custom_catalog import (
    dump_custom_catalog_state,
    register_custom_armor,
    register_custom_consumable,
    register_custom_item,
    register_custom_skill,
    register_custom_sword_skill,
    register_custom_weapon,
    remove_custom_item_template,
)


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def _provenance(kind: str, sources: list[str] | None, notes: str) -> Provenance:
    return Provenance(
        ProvenanceKind(kind),
        sources=tuple(sources or ()),
        notes=notes,
    )


def register_setup_tools(mcp, runtime, *, include_admin: bool = False) -> None:
    @mcp.tool()
    def get_campaign_setup_status() -> str:
        """Return the campaign setup lifecycle state."""
        return _json(campaign_setup_state(runtime))

    @mcp.tool()
    def begin_campaign_setup() -> str:
        """Open the one-time public campaign setup phase before ordinary play begins."""
        return _json(_begin_campaign_setup(runtime))

    @mcp.tool()
    def finalize_campaign_setup() -> str:
        """Lock public setup mutations and begin ordinary campaign play."""
        return _json(_finalize_campaign_setup(runtime))

    if include_admin:
        @mcp.tool()
        def reopen_campaign_setup() -> str:
            """Internal maintenance tool: reopen a finalized campaign setup phase."""
            return _json(_reopen_campaign_setup(runtime))

    @mcp.tool()
    def create_configured_character(
        name: str,
        level: int = 1,
        starter_weapon_id: str = "starter_one_hand_sword",
        col: int = 0,
        profile: dict[str, Any] | None = None,
        skill_proficiencies: dict[str, float] | None = None,
        equipped_skills: list[str] | None = None,
        unlocked_special_skills: list[str] | None = None,
        progression_rules: dict[str, Any] | None = None,
        custom_mechanics: list[dict[str, Any]] | None = None,
    ) -> str:
        """Create a player and apply authoritative setup-time character configuration."""
        require_campaign_setup_open(runtime)
        actor = runtime.create_character(name, level=level, starter_weapon_id=starter_weapon_id)
        try:
            configure_character(
                runtime,
                actor.actor_id,
                col=col,
                profile=profile,
                skill_proficiencies=skill_proficiencies,
                equipped_skills=equipped_skills,
                unlocked_special_skills=unlocked_special_skills,
                progression_rule_patch=progression_rules,
                custom_mechanics=custom_mechanics,
            )
        except Exception:
            runtime.actors.pop(actor.actor_id, None)
            raise
        return _json(character_setup_state(runtime, actor.actor_id))

    @mcp.tool()
    def configure_character_setup(
        actor_id: str,
        level: int | None = None,
        experience: int | None = None,
        location_id: str | None = None,
        strength: int | None = None,
        agility: int | None = None,
        col: int | None = None,
        max_hp: int | None = None,
        heal_to_full: bool = True,
        profile: dict[str, Any] | None = None,
        replace_profile: bool = False,
        skill_proficiencies: dict[str, float] | None = None,
        replace_skill_proficiencies: bool = False,
        equipped_skills: list[str] | None = None,
        unlocked_special_skills: list[str] | None = None,
        progression_rules: dict[str, Any] | None = None,
        replace_progression_rules: bool = False,
        apply_level_growth_retroactive: bool = True,
        custom_mechanics: list[dict[str, Any]] | None = None,
        apply_custom_mechanics_retroactive: bool = True,
    ) -> str:
        """Apply setup-only character state; STR/AGI are base values before setup growth bonuses."""
        require_campaign_setup_open(runtime)
        actor = configure_character(
            runtime,
            actor_id,
            level=level,
            experience=experience,
            location_id=location_id,
            strength=strength,
            agility=agility,
            col=col,
            max_hp=max_hp,
            heal_to_full=heal_to_full,
            profile=profile,
            replace_profile=replace_profile,
            skill_proficiencies=skill_proficiencies,
            replace_skill_proficiencies=replace_skill_proficiencies,
            equipped_skills=equipped_skills,
            unlocked_special_skills=unlocked_special_skills,
            progression_rule_patch=progression_rules,
            replace_progression_rules=replace_progression_rules,
            apply_level_growth_retroactive=apply_level_growth_retroactive,
            custom_mechanics=custom_mechanics,
            apply_custom_mechanics_retroactive=apply_custom_mechanics_retroactive,
        )
        return _json(character_setup_state(runtime, actor.actor_id))

    @mcp.tool()
    def set_character_custom_mechanics(
        actor_id: str,
        mechanics: list[dict[str, Any]],
        apply_retroactive: bool = True,
    ) -> str:
        """Replace the character's declarative custom mechanics during setup."""
        require_campaign_setup_open(runtime)
        actor = runtime.actors[actor_id]
        configure_custom_mechanics(actor, runtime.catalog, mechanics, apply_retroactive=apply_retroactive)
        return _json(character_setup_state(runtime, actor_id))

    @mcp.tool()
    def get_character_setup_state(actor_id: str) -> str:
        """Return authoritative setup state, including metadata, inventory and progression rules."""
        return _json(character_setup_state(runtime, actor_id))

    @mcp.tool()
    def grant_character_item(
        actor_id: str,
        template_id: str,
        quantity: int = 1,
        durability: int | None = None,
        max_durability: int | None = None,
        max_enhancement_attempts: int | None = None,
        enhancement_attempts_used: int = 0,
        enhancements: dict[str, int] | None = None,
        quality: float = 1.0,
        maker_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        equip_now: bool = False,
        allow_overweight: bool = False,
    ) -> str:
        """Grant a real catalog item during the open setup phase."""
        require_campaign_setup_open(runtime)
        item = _grant_character_item(
            runtime,
            actor_id,
            template_id,
            quantity=quantity,
            durability=durability,
            max_durability=max_durability,
            max_enhancement_attempts=max_enhancement_attempts,
            enhancement_attempts_used=enhancement_attempts_used,
            enhancements=enhancements,
            quality=quality,
            maker_id=maker_id,
            metadata=metadata,
            equip_now=equip_now,
            allow_overweight=allow_overweight,
        )
        return _json({"item": asdict(item), "character": character_setup_state(runtime, actor_id)})

    @mcp.tool()
    def remove_character_item_setup(actor_id: str, instance_id: str) -> str:
        """Remove an item during the open setup phase, unequipping it first when necessary."""
        require_campaign_setup_open(runtime)
        item = remove_character_item(runtime, actor_id, instance_id)
        return _json({"removed": asdict(item), "character": character_setup_state(runtime, actor_id)})

    @mcp.tool()
    def get_custom_catalog_state() -> str:
        """Return campaign-local custom item/skill definitions."""
        return _json(dump_custom_catalog_state(runtime))

    @mcp.tool()
    def register_custom_weapon_definition(
        template_id: str,
        name: str,
        weapon_class: str,
        damage_type: str,
        attack_min: int,
        attack_max: int,
        required_level: int = 1,
        required_strength: int = 1,
        weight: float = 0.0,
        base_durability: int = 100,
        base_speed_ms: int = 700,
        reach_m: float = 1.5,
        bonus_strength: int = 0,
        bonus_agility: int = 0,
        base_value_col: int | None = None,
        tags: list[str] | None = None,
        provenance_kind: str = "optional_variant",
        sources: list[str] | None = None,
        notes: str = "",
        replace: bool = False,
    ) -> str:
        """Register a real campaign-local weapon template during setup."""
        require_campaign_setup_open(runtime)
        if not template_id.strip() or not name.strip():
            raise ValueError("template_id and name are required")
        if int(attack_min) < 0 or int(attack_max) < int(attack_min):
            raise ValueError("weapon attack range is invalid")
        if int(required_level) < 1 or int(required_strength) < 0:
            raise ValueError("weapon requirements are invalid")
        if float(weight) < 0 or int(base_durability) < 1 or int(base_speed_ms) < 1 or float(reach_m) <= 0:
            raise ValueError("weapon physical parameters are invalid")
        definition = WeaponTemplate(
            template_id=template_id.strip(), name=name.strip(), kind=ItemKind.WEAPON,
            weapon_class=WeaponClass(weapon_class), damage_type=DamageType(damage_type),
            attack_min=int(attack_min), attack_max=int(attack_max), required_level=int(required_level),
            required_strength=int(required_strength), weight=float(weight), base_durability=int(base_durability),
            base_speed_ms=int(base_speed_ms), reach_m=float(reach_m), bonus_strength=int(bonus_strength),
            bonus_agility=int(bonus_agility), base_value_col=base_value_col, tags=tuple(tags or ()),
            provenance=_provenance(provenance_kind, sources, notes),
        )
        register_custom_weapon(runtime, definition, replace=replace)
        return _json({"kind": "weapon", "record": asdict(definition)})

    @mcp.tool()
    def register_custom_armor_definition(
        template_id: str,
        name: str,
        armor: int,
        slot: str | None = None,
        item_kind: str = "armor",
        weight: float = 0.0,
        base_durability: int = 100,
        base_value_col: int | None = None,
        tags: list[str] | None = None,
        provenance_kind: str = "optional_variant",
        sources: list[str] | None = None,
        notes: str = "",
        replace: bool = False,
    ) -> str:
        """Register a real campaign-local armor or shield template during setup."""
        require_campaign_setup_open(runtime)
        kind = ItemKind(item_kind)
        if kind not in {ItemKind.ARMOR, ItemKind.SHIELD}:
            raise ValueError("item_kind must be armor or shield")
        if int(armor) < 0 or float(weight) < 0 or int(base_durability) < 1:
            raise ValueError("armor parameters are invalid")
        resolved_slot = slot or ("offhand" if kind is ItemKind.SHIELD else "body")
        definition = ArmorTemplate(
            template_id=template_id.strip(), name=name.strip(), kind=kind, armor=int(armor),
            slot=resolved_slot, weight=float(weight), base_durability=int(base_durability),
            base_value_col=base_value_col, tags=tuple(tags or ()),
            provenance=_provenance(provenance_kind, sources, notes),
        )
        register_custom_armor(runtime, definition, replace=replace)
        return _json({"kind": kind.value, "record": asdict(definition)})

    @mcp.tool()
    def register_custom_consumable_definition(
        template_id: str,
        name: str,
        effect: str,
        magnitude: int = 0,
        duration_ms: int = 0,
        cooldown_ms: int = 0,
        requires_voice: bool = False,
        status_tags: list[str] | None = None,
        weight: float = 0.0,
        stack_limit: int = 1,
        base_value_col: int | None = None,
        tags: list[str] | None = None,
        provenance_kind: str = "optional_variant",
        sources: list[str] | None = None,
        notes: str = "",
        replace: bool = False,
    ) -> str:
        """Register a consumable that uses the ordinary consumable runtime."""
        require_campaign_setup_open(runtime)
        if float(weight) < 0 or int(stack_limit) < 1 or min(int(magnitude), int(duration_ms), int(cooldown_ms)) < 0:
            raise ValueError("consumable parameters are invalid")
        definition = ConsumableTemplate(
            template_id=template_id.strip(), name=name.strip(), kind=ItemKind.CONSUMABLE,
            effect=ConsumableEffect(effect), magnitude=int(magnitude), duration_ms=int(duration_ms),
            cooldown_ms=int(cooldown_ms), requires_voice=bool(requires_voice),
            status_tags=tuple(StatusType(value) for value in (status_tags or ())), weight=float(weight),
            stack_limit=int(stack_limit), base_value_col=base_value_col, tags=tuple(tags or ()),
            provenance=_provenance(provenance_kind, sources, notes),
        )
        register_custom_consumable(runtime, definition, replace=replace)
        return _json({"kind": "consumable", "record": asdict(definition)})

    @mcp.tool()
    def register_custom_item_definition(
        template_id: str,
        name: str,
        item_kind: str = "misc",
        weight: float = 0.0,
        stack_limit: int = 1,
        base_value_col: int | None = None,
        tags: list[str] | None = None,
        provenance_kind: str = "optional_variant",
        sources: list[str] | None = None,
        notes: str = "",
        replace: bool = False,
    ) -> str:
        """Register a non-equipment, non-consumable campaign-local item template."""
        require_campaign_setup_open(runtime)
        kind = ItemKind(item_kind)
        if kind in {ItemKind.WEAPON, ItemKind.ARMOR, ItemKind.SHIELD, ItemKind.CONSUMABLE}:
            raise ValueError("use the specialized setup tool for weapon, armor/shield, or consumable definitions")
        if float(weight) < 0 or int(stack_limit) < 1:
            raise ValueError("item parameters are invalid")
        definition = ItemTemplate(
            template_id=template_id.strip(), name=name.strip(), kind=kind, weight=float(weight),
            stack_limit=int(stack_limit), base_value_col=base_value_col, tags=tuple(tags or ()),
            provenance=_provenance(provenance_kind, sources, notes),
        )
        register_custom_item(runtime, definition, replace=replace)
        return _json({"kind": kind.value, "record": asdict(definition)})

    @mcp.tool()
    def remove_custom_item_definition(template_id: str) -> str:
        """Remove an uninstantiated campaign-local item template during setup."""
        require_campaign_setup_open(runtime)
        removed = remove_custom_item_template(runtime, template_id)
        return _json({"removed": asdict(removed)})

    @mcp.tool()
    def register_custom_skill_definition(
        skill_id: str,
        name: str,
        kind: str,
        description: str = "",
        prerequisites: list[str] | None = None,
        provenance_kind: str = "optional_variant",
        sources: list[str] | None = None,
        notes: str = "",
        replace: bool = False,
    ) -> str:
        """Register a persistent campaign-local Skill during the open setup phase."""
        require_campaign_setup_open(runtime)
        if not skill_id.strip() or not name.strip():
            raise ValueError("skill_id and name are required")
        prereqs = tuple(prerequisites or ())
        for prerequisite in prereqs:
            if prerequisite not in runtime.catalog.skills:
                raise ValueError(f"unknown skill prerequisite: {prerequisite}")
        definition = SkillDefinition(
            skill_id=skill_id.strip(),
            name=name.strip(),
            kind=SkillKind(kind),
            description=description,
            prerequisites=prereqs,
            provenance=_provenance(provenance_kind, sources, notes),
        )
        register_custom_skill(runtime, definition, replace=replace)
        return _json({"kind": "skill", "record": asdict(definition)})

    @mcp.tool()
    def register_custom_sword_skill_definition(
        skill_id: str,
        name: str,
        weapon_class: str,
        prerequisite_proficiency: float,
        hits: list[float],
        windup_ms: int,
        active_ms: int,
        post_motion_ms: int,
        accuracy_modifier: float = 0.0,
        lunge_m: float = 0.0,
        stagger: float = 0.0,
        proficiency_skill_id: str | None = None,
        provenance_kind: str = "optional_variant",
        sources: list[str] | None = None,
        notes: str = "",
        replace: bool = False,
    ) -> str:
        """Register a persistent campaign-local Sword Skill during the open setup phase."""
        require_campaign_setup_open(runtime)
        if not skill_id.strip() or not name.strip():
            raise ValueError("skill_id and name are required")
        if not hits or any(float(hit) <= 0.0 for hit in hits):
            raise ValueError("hits must contain positive multipliers")
        if not 0.0 <= float(prerequisite_proficiency) <= 1000.0:
            raise ValueError("prerequisite_proficiency must be 0..1000")
        if min(int(windup_ms), int(active_ms), int(post_motion_ms)) < 0:
            raise ValueError("Sword Skill timing cannot be negative")
        if lunge_m < 0.0 or stagger < 0.0:
            raise ValueError("lunge_m and stagger must be non-negative")
        if proficiency_skill_id is not None and proficiency_skill_id not in runtime.catalog.skills:
            raise ValueError(f"unknown proficiency skill: {proficiency_skill_id}")
        definition = SwordSkillDefinition(
            skill_id=skill_id.strip(),
            name=name.strip(),
            weapon_class=WeaponClass(weapon_class),
            prerequisite_proficiency=float(prerequisite_proficiency),
            hits=tuple(float(hit) for hit in hits),
            windup_ms=int(windup_ms),
            active_ms=int(active_ms),
            post_motion_ms=int(post_motion_ms),
            accuracy_modifier=float(accuracy_modifier),
            lunge_m=float(lunge_m),
            stagger=float(stagger),
            provenance=_provenance(provenance_kind, sources, notes),
            proficiency_skill_id=proficiency_skill_id,
        )
        register_custom_sword_skill(runtime, definition, replace=replace)
        return _json({"kind": "sword_skill", "record": asdict(definition)})
