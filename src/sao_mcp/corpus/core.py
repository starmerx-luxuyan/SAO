from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import (
    ConsumableEffect,
    ConsumableTemplate,
    DamageType,
    ItemKind,
    Provenance,
    ProvenanceKind,
    SkillDefinition,
    SkillKind,
    StatusType,
    SwordSkillDefinition,
    WeaponClass,
    WeaponTemplate,
)


@dataclass(slots=True)
class Catalog:
    weapons: dict[str, WeaponTemplate]
    consumables: dict[str, ConsumableTemplate]
    skills: dict[str, SkillDefinition]
    sword_skills: dict[str, SwordSkillDefinition]

    def item(self, template_id: str):
        if template_id in self.weapons:
            return self.weapons[template_id]
        if template_id in self.consumables:
            return self.consumables[template_id]
        raise KeyError(template_id)


REFERENCE_SKILLS = "https://swordartonline.fandom.com/wiki/Skills"
REFERENCE_SWORD_SKILLS = "https://swordartonline.fandom.com/wiki/Sword_Skills"
REFERENCE_CRYSTALS = "https://swordartonline.fandom.com/wiki/Crystal"


def _canon_reference(*sources: str, notes: str = "") -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=sources, notes=notes)


def _sim(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, notes=notes)


def build_core_catalog() -> Catalog:
    weapons = {
        "starter_one_hand_sword": WeaponTemplate(
            template_id="starter_one_hand_sword",
            name="Starter One-Handed Sword",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.ONE_HAND_SWORD,
            damage_type=DamageType.SLASH,
            attack_min=20,
            attack_max=28,
            required_level=1,
            required_strength=5,
            weight=18,
            base_durability=220,
            base_speed_ms=720,
            reach_m=1.55,
            provenance=_sim("Starter equipment and numeric stats are runtime calibration."),
        ),
        "elucidator": WeaponTemplate(
            template_id="elucidator",
            name="Elucidator",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.ONE_HAND_SWORD,
            damage_type=DamageType.SLASH,
            attack_min=700,
            attack_max=710,
            required_level=61,
            required_strength=61,
            weight=170,
            base_durability=1350,
            base_speed_ms=620,
            reach_m=1.7,
            bonus_strength=48,
            bonus_agility=28,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=("Sword Art Online Material Edition character-profile stat block; secondary-reference cross-check required",),
                notes="Named item is canon; numeric stat block remains a re-verification target before final corpus lock.",
            ),
        ),
    }

    consumables = {
        "healing_potion_basic": ConsumableTemplate(
            template_id="healing_potion_basic",
            name="Basic Healing Potion",
            kind=ItemKind.CONSUMABLE,
            weight=0.4,
            stack_limit=20,
            effect=ConsumableEffect.HEAL_OVER_TIME,
            magnitude=600,
            duration_ms=20_000,
            cooldown_ms=60_000,
            provenance=_sim("Potion existence/slow healing/cooldown are canon-backed; exact amount and timing are simulation tuning."),
        ),
        "healing_crystal": ConsumableTemplate(
            template_id="healing_crystal",
            name="Healing Crystal",
            kind=ItemKind.CONSUMABLE,
            weight=0.2,
            stack_limit=10,
            tags=("crystal",),
            effect=ConsumableEffect.HEAL_FULL,
            requires_voice=True,
            provenance=_canon_reference(REFERENCE_CRYSTALS),
        ),
        "curing_crystal": ConsumableTemplate(
            template_id="curing_crystal",
            name="Curing Crystal",
            kind=ItemKind.CONSUMABLE,
            weight=0.2,
            stack_limit=10,
            tags=("crystal",),
            effect=ConsumableEffect.CURE,
            requires_voice=True,
            status_tags=(StatusType.POISON, StatusType.PARALYSIS, StatusType.BLEED),
            provenance=_canon_reference(REFERENCE_CRYSTALS),
        ),
        "teleport_crystal": ConsumableTemplate(
            template_id="teleport_crystal",
            name="Teleport Crystal",
            kind=ItemKind.CONSUMABLE,
            weight=0.2,
            stack_limit=10,
            tags=("crystal",),
            effect=ConsumableEffect.TELEPORT,
            requires_voice=True,
            provenance=_canon_reference(REFERENCE_CRYSTALS),
        ),
        "corridor_crystal": ConsumableTemplate(
            template_id="corridor_crystal",
            name="Corridor Crystal",
            kind=ItemKind.CONSUMABLE,
            weight=0.2,
            stack_limit=5,
            tags=("crystal",),
            effect=ConsumableEffect.CORRIDOR,
            requires_voice=True,
            provenance=_canon_reference(REFERENCE_CRYSTALS),
        ),
    }

    skills = {
        "one_hand_sword": SkillDefinition("one_hand_sword", "One-Handed Sword", SkillKind.WEAPON, provenance=_canon_reference(REFERENCE_SKILLS)),
        "parry": SkillDefinition("parry", "Parry", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "battle_healing": SkillDefinition("battle_healing", "Battle Healing", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "searching": SkillDefinition("searching", "Searching", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "tracking": SkillDefinition("tracking", "Tracking", SkillKind.SUPPORT, prerequisites=("searching",), provenance=_canon_reference(REFERENCE_SKILLS)),
        "hiding": SkillDefinition("hiding", "Hiding", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "sprint": SkillDefinition("sprint", "Sprint", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "extended_weight_limit": SkillDefinition("extended_weight_limit", "Extended Weight Limit", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "fishing": SkillDefinition("fishing", "Fishing", SkillKind.LIFE, provenance=_canon_reference(REFERENCE_SKILLS)),
        "dual_blades": SkillDefinition("dual_blades", "Dual Blades", SkillKind.UNIQUE, provenance=_canon_reference(REFERENCE_SKILLS)),
    }

    # Names/weapon associations are canon-backed; timing, multipliers and thresholds are simulation calibration.
    ss_prov = _sim("Sword Skill name/weapon association is canon-backed; timing, multipliers and thresholds are simulation fields.")
    sword_skills = {
        "horizontal": SwordSkillDefinition("horizontal", "Horizontal", WeaponClass.ONE_HAND_SWORD, 0, (1.05,), 260, 260, 330, 0.02, 0.5, 0.00, ss_prov),
        "vertical": SwordSkillDefinition("vertical", "Vertical", WeaponClass.ONE_HAND_SWORD, 0, (1.08,), 280, 270, 350, 0.02, 0.4, 0.05, ss_prov),
        "slant": SwordSkillDefinition("slant", "Slant", WeaponClass.ONE_HAND_SWORD, 40, (1.12,), 300, 280, 360, 0.03, 0.6, 0.08, ss_prov),
        "sonic_leap": SwordSkillDefinition("sonic_leap", "Sonic Leap", WeaponClass.ONE_HAND_SWORD, 120, (1.28,), 380, 330, 520, 0.01, 3.5, 0.10, ss_prov),
        "rage_spike": SwordSkillDefinition("rage_spike", "Rage Spike", WeaponClass.ONE_HAND_SWORD, 180, (1.38,), 420, 340, 590, -0.01, 4.0, 0.16, ss_prov),
        "horizontal_arc": SwordSkillDefinition("horizontal_arc", "Horizontal Arc", WeaponClass.ONE_HAND_SWORD, 260, (0.82, 0.88), 410, 500, 650, 0.02, 1.0, 0.15, ss_prov),
        "vorpal_strike": SwordSkillDefinition("vorpal_strike", "Vorpal Strike", WeaponClass.ONE_HAND_SWORD, 850, (2.05,), 620, 420, 980, -0.03, 6.0, 0.30, ss_prov),
    }

    return Catalog(weapons=weapons, consumables=consumables, skills=skills, sword_skills=sword_skills)
