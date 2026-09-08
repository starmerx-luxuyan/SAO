from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import (
    Provenance,
    ProvenanceKind,
    SkillDefinition,
    SkillKind,
    SwordSkillDefinition,
    WeaponClass,
)


SKILLS_REFERENCE = "https://swordartonline.fandom.com/wiki/Skills"
SWORD_SKILLS_REFERENCE = "https://swordartonline.fandom.com/wiki/Sword_Skills"


def _skill(skill_id: str, name: str, kind: SkillKind, *, description: str = "") -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        name=name,
        kind=kind,
        description=description,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=(SKILLS_REFERENCE,),
        ),
    )


def _sword_skill(
    skill_id: str,
    name: str,
    weapon_class: WeaponClass,
    prerequisite_proficiency: float,
    hits: tuple[float, ...],
    windup_ms: int,
    active_ms: int,
    post_motion_ms: int,
    *,
    accuracy_modifier: float = 0.0,
    lunge_m: float = 0.0,
    stagger: float = 0.0,
    sources: tuple[str, ...] = (SWORD_SKILLS_REFERENCE,),
    canon_notes: str = "",
) -> SwordSkillDefinition:
    notes = (
        "Name, weapon category and stated combo structure are canon-backed. "
        "Damage multipliers, action timing, accuracy, lunge and stagger values are runtime simulation tuning."
    )
    if canon_notes:
        notes += f" {canon_notes}"
    return SwordSkillDefinition(
        skill_id=skill_id,
        name=name,
        weapon_class=weapon_class,
        prerequisite_proficiency=prerequisite_proficiency,
        hits=hits,
        windup_ms=windup_ms,
        active_ms=active_ms,
        post_motion_ms=post_motion_ms,
        accuracy_modifier=accuracy_modifier,
        lunge_m=lunge_m,
        stagger=stagger,
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=sources,
            notes=notes,
        ),
    )


def apply_aincrad_skill_seed(catalog: Catalog) -> Catalog:
    """Expand Aincrad skill identities without turning content rows into new runtime systems."""
    skills = {
        "first_aid": _skill("first_aid", "First Aid", SkillKind.SUPPORT),
        "acrobatics": _skill("acrobatics", "Acrobatics", SkillKind.SUPPORT),
        "armor_pierce": _skill("armor_pierce", "Armor Pierce", SkillKind.SUPPORT),
        "fighting_spirit": _skill("fighting_spirit", "Fighting Spirit", SkillKind.SUPPORT),
        "howl": _skill("howl", "Howl", SkillKind.SUPPORT),
        "leather_armor": _skill("leather_armor", "Leather Armor", SkillKind.ARMOR),
        "light_metal_armor": _skill("light_metal_armor", "Light Metal Armor", SkillKind.ARMOR),
        "heavy_metal_armor": _skill("heavy_metal_armor", "Heavy Metal Armor", SkillKind.ARMOR),
        "shield": _skill("shield", "Shield", SkillKind.ARMOR),
        "spiritual_light": _skill("spiritual_light", "Spiritual Light", SkillKind.SUPPORT),
        "meditation": SkillDefinition(
            skill_id="meditation",
            name="Meditation",
            kind=SkillKind.EXTRA,
            description="Extra Skill with the Awakening mod associated with high proficiency.",
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=(SKILLS_REFERENCE,),
                notes="The Skills reference identifies Meditation as an Extra Skill and Awakening as its level-500 mod.",
            ),
        ),
        "blade_throwing": _skill("blade_throwing", "Blade Throwing", SkillKind.WEAPON),
        "martial_arts": _skill("martial_arts", "Martial Arts", SkillKind.EXTRA),
        "sewing": _skill("sewing", "Sewing", SkillKind.LIFE),
    }
    for skill_id, definition in skills.items():
        catalog.skills.setdefault(skill_id, definition)

    # Explicit canon unlock thresholds override older provisional tuning where the novels/references state them.
    catalog.sword_skills["rage_spike"] = _sword_skill(
        "rage_spike",
        "Rage Spike",
        WeaponClass.ONE_HAND_SWORD,
        50,
        (1.10,),
        330,
        300,
        430,
        accuracy_modifier=0.03,
        lunge_m=8.5,
        stagger=0.10,
        sources=("https://swordartonline.fandom.com/wiki/Rage_Spike",),
        canon_notes="In SAO it unlocks at One-Handed Sword proficiency 50; its defining property is a long ground charge.",
    )
    catalog.sword_skills["vorpal_strike"] = _sword_skill(
        "vorpal_strike",
        "Vorpal Strike",
        WeaponClass.ONE_HAND_SWORD,
        950,
        (2.05,),
        620,
        420,
        980,
        accuracy_modifier=-0.03,
        lunge_m=2.0,
        stagger=0.30,
        sources=("https://swordartonline.fandom.com/wiki/Vorpal_Strike",),
        canon_notes="In SAO it unlocks at proficiency 950 and has roughly double-blade reach with a long post-motion delay.",
    )

    one_hand_sword = {
        "vertical_arc": _sword_skill(
            "vertical_arc", "Vertical Arc", WeaponClass.ONE_HAND_SWORD, 80,
            (0.82, 0.90), 360, 470, 560, lunge_m=0.6, stagger=0.12,
            sources=("https://swordartonline.fandom.com/wiki/Vertical_Arc",),
            canon_notes="Two-hit V-shaped combo; prerequisite value is simulation calibration.",
        ),
        "sharp_nail": _sword_skill(
            "sharp_nail", "Sharp Nail", WeaponClass.ONE_HAND_SWORD, 120,
            (0.58, 0.62, 0.72), 390, 560, 620, accuracy_modifier=0.01, stagger=0.10,
            canon_notes="Three-hit combo; prerequisite value is simulation calibration.",
        ),
        "horizontal_square": _sword_skill(
            "horizontal_square", "Horizontal Square", WeaponClass.ONE_HAND_SWORD, 150,
            (0.58, 0.61, 0.64, 0.76), 440, 700, 760, lunge_m=0.8, stagger=0.16,
            sources=("https://swordartonline.fandom.com/wiki/Horizontal_Square",),
            canon_notes="Four-hit combo unlocked at One-Handed Sword proficiency 150 in SAO.",
        ),
        "vertical_square": _sword_skill(
            "vertical_square", "Vertical Square", WeaponClass.ONE_HAND_SWORD, 170,
            (0.60, 0.62, 0.65, 0.82), 470, 720, 800, stagger=0.20,
            sources=("https://swordartonline.fandom.com/wiki/Vertical_Square",),
            canon_notes="Four-hit combo; prerequisite value is simulation calibration.",
        ),
        "snake_bite": _sword_skill(
            "snake_bite", "Snake Bite", WeaponClass.ONE_HAND_SWORD, 300,
            (0.94, 1.02), 390, 500, 660, accuracy_modifier=0.02, stagger=0.15,
            sources=("https://swordartonline.fandom.com/wiki/Snake_Bite",),
            canon_notes="Two-hit skill known for targeting an opponent's weapon; prerequisite value is simulation calibration.",
        ),
        "serration_wave": _sword_skill(
            "serration_wave", "Serration Wave", WeaponClass.ONE_HAND_SWORD, 360,
            (0.72,), 480, 430, 700, accuracy_modifier=0.04, lunge_m=1.1, stagger=0.05,
            canon_notes="Single-hit area skill intended primarily to impede movement; AoE/status execution remains future content behavior.",
        ),
        "deadly_sins": _sword_skill(
            "deadly_sins", "Deadly Sins", WeaponClass.ONE_HAND_SWORD, 700,
            (0.40, 0.42, 0.44, 0.46, 0.48, 0.52, 0.70), 590, 1050, 980, stagger=0.24,
            canon_notes="Seven-hit combo; prerequisite value is simulation calibration.",
        ),
    }
    for skill_id, definition in one_hand_sword.items():
        catalog.sword_skills.setdefault(skill_id, definition)

    rapier = {
        "parallel_sting": _sword_skill(
            "parallel_sting", "Parallel Sting", WeaponClass.RAPIER, 180,
            (0.78, 0.86), 270, 390, 440, accuracy_modifier=0.05, lunge_m=1.5,
            canon_notes="Two consecutive thrusts; prerequisite value is simulation calibration.",
        ),
        "shooting_star": _sword_skill(
            "shooting_star", "Shooting Star", WeaponClass.RAPIER, 260,
            (1.42,), 330, 330, 520, accuracy_modifier=0.04, lunge_m=4.4, stagger=0.12,
            canon_notes="Charging rapier skill; hit multiplier, reach and prerequisite are simulation calibration.",
        ),
        "triangular": _sword_skill(
            "triangular", "Triangular", WeaponClass.RAPIER, 380,
            (0.58, 0.62, 0.78), 340, 520, 570, accuracy_modifier=0.06, lunge_m=1.4,
            canon_notes="Powerful three-hit rapier combo; prerequisite value is simulation calibration.",
        ),
        "star_splash": _sword_skill(
            "star_splash", "Star Splash", WeaponClass.RAPIER, 720,
            (0.28, 0.28, 0.30, 0.38, 0.38, 0.46, 0.48, 0.72), 500, 980, 900,
            accuracy_modifier=0.05, lunge_m=1.2, stagger=0.18,
            sources=("https://swordartonline.fandom.com/wiki/Star_Splash",),
            canon_notes="High-level eight-hit Rapier combo; prerequisite value is simulation calibration.",
        ),
        "flashing_penetrator": _sword_skill(
            "flashing_penetrator", "Flashing Penetrator", WeaponClass.RAPIER, 900,
            (2.10,), 760, 430, 1180, accuracy_modifier=0.03, lunge_m=8.0, stagger=0.34,
            sources=("https://swordartonline.fandom.com/wiki/Flashing_Penetrator",),
            canon_notes="One-hit long-distance rapier thrust requiring a sprint/build-up and followed by a long delay; prerequisite value is simulation calibration.",
        ),
    }
    for skill_id, definition in rapier.items():
        catalog.sword_skills.setdefault(skill_id, definition)

    return catalog
