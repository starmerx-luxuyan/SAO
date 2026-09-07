from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(slots=True)
class Catalog:
    weapons: dict[str, WeaponTemplate]
    armors: dict[str, ArmorTemplate]
    consumables: dict[str, ConsumableTemplate]
    items: dict[str, ItemTemplate]
    skills: dict[str, SkillDefinition]
    sword_skills: dict[str, SwordSkillDefinition]

    def item(self, template_id: str) -> ItemTemplate:
        for mapping in (self.weapons, self.armors, self.consumables, self.items):
            if template_id in mapping:
                return mapping[template_id]
        raise KeyError(template_id)


REFERENCE_SKILLS = "https://swordartonline.fandom.com/wiki/Skills"
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
        "starter_rapier": WeaponTemplate(
            template_id="starter_rapier",
            name="Starter Rapier",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.RAPIER,
            damage_type=DamageType.THRUST,
            attack_min=17,
            attack_max=25,
            required_level=1,
            required_strength=4,
            weight=12,
            base_durability=185,
            base_speed_ms=610,
            reach_m=1.65,
            provenance=_sim("Generic low-tier rapier template for runnable character creation."),
        ),
        "starter_dagger": WeaponTemplate(
            template_id="starter_dagger",
            name="Starter Dagger",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.DAGGER,
            damage_type=DamageType.THRUST,
            attack_min=13,
            attack_max=20,
            required_level=1,
            required_strength=2,
            weight=7,
            base_durability=155,
            base_speed_ms=480,
            reach_m=0.85,
            provenance=_sim("Generic low-tier dagger template for runnable character creation."),
        ),
        "starter_mace": WeaponTemplate(
            template_id="starter_mace",
            name="Starter Mace",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.MACE,
            damage_type=DamageType.BLUNT,
            attack_min=23,
            attack_max=32,
            required_level=1,
            required_strength=8,
            weight=24,
            base_durability=275,
            base_speed_ms=820,
            reach_m=1.25,
            provenance=_sim("Generic low-tier mace template for runnable character creation."),
        ),
        "starter_spear": WeaponTemplate(
            template_id="starter_spear",
            name="Starter Spear",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.SPEAR,
            damage_type=DamageType.THRUST,
            attack_min=19,
            attack_max=29,
            required_level=1,
            required_strength=6,
            weight=20,
            base_durability=205,
            base_speed_ms=740,
            reach_m=2.45,
            provenance=_sim("Generic low-tier spear template for runnable character creation."),
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

    armors = {
        "starter_leather_coat": ArmorTemplate(
            template_id="starter_leather_coat",
            name="Starter Leather Coat",
            kind=ItemKind.ARMOR,
            weight=10,
            armor=32,
            base_durability=180,
            slot="body",
            provenance=_sim("Generic starter armour template."),
        ),
        "starter_leather_gloves": ArmorTemplate(
            template_id="starter_leather_gloves",
            name="Starter Leather Gloves",
            kind=ItemKind.ARMOR,
            weight=3,
            armor=8,
            base_durability=120,
            slot="hands",
            provenance=_sim("Generic starter armour template."),
        ),
        "starter_leather_boots": ArmorTemplate(
            template_id="starter_leather_boots",
            name="Starter Leather Boots",
            kind=ItemKind.ARMOR,
            weight=4,
            armor=10,
            base_durability=130,
            slot="feet",
            provenance=_sim("Generic starter armour template."),
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

    items = {
        "boar_hide": ItemTemplate("boar_hide", "Boar Hide", ItemKind.MATERIAL, weight=1.2, stack_limit=50, base_value_col=8, provenance=_sim("Training-floor material template.")),
        "iron_ore": ItemTemplate("iron_ore", "Iron Ore", ItemKind.MATERIAL, weight=2.0, stack_limit=50, base_value_col=12, provenance=_sim("Generic crafting material template.")),
        "iron_ingot": ItemTemplate("iron_ingot", "Iron Ingot", ItemKind.MATERIAL, weight=1.6, stack_limit=50, base_value_col=20, provenance=_sim("Generic crafting material template.")),
        "red_jewel_fragment": ItemTemplate("red_jewel_fragment", "Red Jewel Fragment", ItemKind.MATERIAL, weight=0.1, stack_limit=99, base_value_col=35, provenance=_sim("Generic enhancement material template.")),
        "field_bread": ItemTemplate("field_bread", "Field Bread", ItemKind.FOOD, weight=0.3, stack_limit=20, base_value_col=5, provenance=_sim("Generic food/economy template.")),
    }

    skills = {
        "one_hand_sword": SkillDefinition("one_hand_sword", "One-Handed Sword", SkillKind.WEAPON, provenance=_canon_reference(REFERENCE_SKILLS)),
        "rapier": SkillDefinition("rapier", "Rapier", SkillKind.WEAPON, provenance=_canon_reference(REFERENCE_SKILLS)),
        "dagger": SkillDefinition("dagger", "Dagger", SkillKind.WEAPON, provenance=_canon_reference(REFERENCE_SKILLS)),
        "mace": SkillDefinition("mace", "One-Handed Mace", SkillKind.WEAPON, provenance=_canon_reference(REFERENCE_SKILLS)),
        "spear": SkillDefinition("spear", "Two-Handed Spear", SkillKind.WEAPON, provenance=_canon_reference(REFERENCE_SKILLS)),
        "parry": SkillDefinition("parry", "Parry", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "battle_healing": SkillDefinition("battle_healing", "Battle Healing", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "searching": SkillDefinition("searching", "Searching", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "tracking": SkillDefinition("tracking", "Tracking", SkillKind.SUPPORT, prerequisites=("searching",), provenance=_canon_reference(REFERENCE_SKILLS)),
        "hiding": SkillDefinition("hiding", "Hiding", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "sprint": SkillDefinition("sprint", "Sprint", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "extended_weight_limit": SkillDefinition("extended_weight_limit", "Extended Weight Limit", SkillKind.SUPPORT, provenance=_canon_reference(REFERENCE_SKILLS)),
        "fishing": SkillDefinition("fishing", "Fishing", SkillKind.LIFE, provenance=_canon_reference(REFERENCE_SKILLS)),
        "blacksmithing": SkillDefinition("blacksmithing", "Blacksmithing", SkillKind.LIFE, provenance=_canon_reference(REFERENCE_SKILLS)),
        "cooking": SkillDefinition("cooking", "Cooking", SkillKind.LIFE, provenance=_canon_reference(REFERENCE_SKILLS)),
        "dual_blades": SkillDefinition("dual_blades", "Dual Blades", SkillKind.UNIQUE, provenance=_canon_reference(REFERENCE_SKILLS)),
    }

    ss_prov = _sim("Sword Skill name/weapon association is canon-backed; timing, multipliers and thresholds are simulation fields.")
    sword_skills = {
        "horizontal": SwordSkillDefinition("horizontal", "Horizontal", WeaponClass.ONE_HAND_SWORD, 0, (1.05,), 260, 260, 330, 0.02, 0.5, 0.00, ss_prov),
        "vertical": SwordSkillDefinition("vertical", "Vertical", WeaponClass.ONE_HAND_SWORD, 0, (1.08,), 280, 270, 350, 0.02, 0.4, 0.05, ss_prov),
        "slant": SwordSkillDefinition("slant", "Slant", WeaponClass.ONE_HAND_SWORD, 40, (1.12,), 300, 280, 360, 0.03, 0.6, 0.08, ss_prov),
        "sonic_leap": SwordSkillDefinition("sonic_leap", "Sonic Leap", WeaponClass.ONE_HAND_SWORD, 120, (1.28,), 380, 330, 520, 0.01, 3.5, 0.10, ss_prov),
        "rage_spike": SwordSkillDefinition("rage_spike", "Rage Spike", WeaponClass.ONE_HAND_SWORD, 180, (1.38,), 420, 340, 590, -0.01, 4.0, 0.16, ss_prov),
        "horizontal_arc": SwordSkillDefinition("horizontal_arc", "Horizontal Arc", WeaponClass.ONE_HAND_SWORD, 260, (0.82, 0.88), 410, 500, 650, 0.02, 1.0, 0.15, ss_prov),
        "vorpal_strike": SwordSkillDefinition("vorpal_strike", "Vorpal Strike", WeaponClass.ONE_HAND_SWORD, 850, (2.05,), 620, 420, 980, -0.03, 6.0, 0.30, ss_prov),
        "linear": SwordSkillDefinition("linear", "Linear", WeaponClass.RAPIER, 0, (1.06,), 220, 250, 310, 0.04, 1.1, 0.00, ss_prov),
        "oblique": SwordSkillDefinition("oblique", "Oblique", WeaponClass.RAPIER, 150, (1.20,), 280, 260, 390, 0.05, 1.4, 0.04, ss_prov),
        "rapid_bite": SwordSkillDefinition("rapid_bite", "Rapid Bite", WeaponClass.DAGGER, 180, (0.62, 0.66), 220, 390, 420, 0.04, 0.8, 0.02, ss_prov),
        "uppercut": SwordSkillDefinition("uppercut", "Uppercut", WeaponClass.MACE, 80, (1.32,), 380, 310, 520, -0.01, 0.5, 0.20, ss_prov),
        "vent_forth": SwordSkillDefinition("vent_forth", "Vent Forth", WeaponClass.SPEAR, 100, (1.28,), 340, 330, 480, 0.01, 2.5, 0.12, ss_prov),
    }

    return Catalog(weapons=weapons, armors=armors, consumables=consumables, items=items, skills=skills, sword_skills=sword_skills)
