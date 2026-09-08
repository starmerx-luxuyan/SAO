from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import (
    DamageType,
    ItemKind,
    Provenance,
    ProvenanceKind,
    WeaponClass,
    WeaponTemplate,
)


ITEMS_REFERENCE = "https://swordartonline.fandom.com/wiki/Items"


def _weapon(
    template_id: str,
    name: str,
    weapon_class: WeaponClass,
    damage_type: DamageType,
    attack_min: int,
    attack_max: int,
    required_level: int,
    required_strength: int,
    weight: float,
    durability: int,
    speed_ms: int,
    reach_m: float,
    *,
    tags: tuple[str, ...] = (),
    sources: tuple[str, ...] = (ITEMS_REFERENCE,),
    notes: str = "",
    bonus_strength: int = 0,
    bonus_agility: int = 0,
) -> WeaponTemplate:
    provenance_notes = (
        "Weapon identity/category and explicitly described acquisition or special properties are canon-backed. "
        "Unless stated otherwise, combat stats and equip requirements are simulation calibration."
    )
    if notes:
        provenance_notes += f" {notes}"
    return WeaponTemplate(
        template_id=template_id,
        name=name,
        kind=ItemKind.WEAPON,
        weapon_class=weapon_class,
        damage_type=damage_type,
        attack_min=attack_min,
        attack_max=attack_max,
        required_level=required_level,
        required_strength=required_strength,
        weight=weight,
        base_durability=durability,
        base_speed_ms=speed_ms,
        reach_m=reach_m,
        bonus_strength=bonus_strength,
        bonus_agility=bonus_agility,
        tags=tags,
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=sources,
            notes=provenance_notes,
        ),
    )


def apply_aincrad_weapon_seed(catalog: Catalog) -> Catalog:
    """Add named Aincrad weapons as data rows; special tags describe content without new engine layers."""
    rows = {
        "small_sword": _weapon(
            "small_sword", "Small Sword", WeaponClass.ONE_HAND_SWORD, DamageType.SLASH,
            18, 25, 1, 4, 14, 190, 680, 1.45,
            tags=("starter",), notes="Known initial weapon for beginners in SAO.",
        ),
        "bronze_sword": _weapon(
            "bronze_sword", "Bronze Sword", WeaponClass.ONE_HAND_SWORD, DamageType.SLASH,
            24, 32, 2, 7, 19, 235, 710, 1.55,
            tags=("floor_1", "npc_shop", "horunka"),
            notes="Sold at Horunka Village on Floor 1.",
        ),
        "plain_rapier": _weapon(
            "plain_rapier", "Plain Rapier", WeaponClass.RAPIER, DamageType.THRUST,
            16, 24, 1, 3, 10, 175, 600, 1.65,
            tags=("starter",), notes="Known initial rapier for beginners.",
        ),
        "wind_fleuret": _weapon(
            "wind_fleuret", "Wind Fleuret", WeaponClass.RAPIER, DamageType.THRUST,
            30, 41, 2, 6, 10, 230, 565, 1.72,
            tags=("floor_1", "rare_drop", "max_enhancement_attempts:6"),
            sources=("https://swordartonline.fandom.com/wiki/Wind_Fleuret",),
            notes="Asuna's lower-floor rare monster drop; canon allows up to six enhancement attempts.",
        ),
        "stout_brand": _weapon(
            "stout_brand", "Stout Brand", WeaponClass.ONE_HAND_SWORD, DamageType.SLASH,
            34, 45, 3, 11, 25, 330, 760, 1.50,
            tags=("low_floor", "rare", "broadsword"),
            sources=("https://swordartonline.fandom.com/wiki/Stout_Brand",),
            notes="Rare broadsword-category one-handed sword, comparable in rarity to Wind Fleuret.",
        ),
        "chivalric_rapier": _weapon(
            "chivalric_rapier", "Chivalric Rapier", WeaponClass.RAPIER, DamageType.THRUST,
            55, 69, 4, 10, 12, 390, 550, 1.75,
            tags=("floor_3", "dark_elf_forged", "max_enhancement_attempts:15"),
            sources=("Sword Art Online Progressive Volume 2: Concerto of Black and White",),
            notes="Forged from an Argentium Ingot by a Dark Elf smith on Floor 3; fifteen upgrade attempts are canon.",
        ),
        "numb_dagger": _weapon(
            "numb_dagger", "Numb Dagger", WeaponClass.DAGGER, DamageType.THRUST,
            46, 60, 5, 7, 8, 250, 470, 0.90,
            tags=("floor_2", "labyrinth_drop", "stun_on_hit"),
            notes="Rare Floor 2 Labyrinth minotaur drop with an occasional stun effect.",
        ),
        "sword_of_eventide": _weapon(
            "sword_of_eventide", "Sword of Eventide", WeaponClass.ONE_HAND_SWORD, DamageType.SLASH,
            98, 122, 10, 20, 27, 470, 680, 1.62,
            tags=("quest_reward", "laketop_fortress"),
            notes="One possible reward from the Laketop Fortress quest.",
        ),
        "queens_knightsword": _weapon(
            "queens_knightsword", "Queen's Knightsword", WeaponClass.ONE_HAND_SWORD, DamageType.SLASH,
            90, 115, 9, 19, 25, 455, 670, 1.62,
            tags=("floor_9", "quest_reward"),
            notes="Quest reward obtainable on Floor 9.",
        ),
        "ebon_dagger": _weapon(
            "ebon_dagger", "Ebon Dagger", WeaponClass.DAGGER, DamageType.THRUST,
            245, 285, 35, 27, 9, 510, 430, 0.92,
            tags=("floor_35", "silica"),
            sources=("https://swordartonline.fandom.com/wiki/Ebon_Dagger",),
            notes="Dagger used by Silica and given to her by Kirito after the Floor 35 Forest of Wandering rescue.",
        ),
        "sword_breaker": _weapon(
            "sword_breaker", "Sword Breaker", WeaponClass.DAGGER, DamageType.SLASH,
            190, 225, 30, 25, 11, 690, 510, 0.80,
            tags=("middle_floor", "parry_weapon_break_bonus", "low_offense"),
            sources=("https://swordartonline.fandom.com/wiki/Sword_Breaker",),
            notes="Middle-floor dagger with low offensive power and a bonus to breaking weapons when parrying with its toothed back.",
        ),
        "guilty_thorn": _weapon(
            "guilty_thorn", "Guilty Thorn", WeaponClass.SPEAR, DamageType.THRUST,
            330, 375, 50, 38, 18, 620, 690, 1.20,
            tags=("player_made", "damage_over_time", "barbed"),
            sources=("https://swordartonline.fandom.com/wiki/Guilty_Thorn",),
            notes="Player-made barbed short spear created by Grimlock with a durability-damage-over-time purpose.",
        ),
        "mate_chopper": _weapon(
            "mate_chopper", "Mate Chopper", WeaponClass.DAGGER, DamageType.SLASH,
            490, 545, 48, 44, 29, 900, 600, 1.05,
            tags=("rare_drop", "cursed_weapon", "maken", "player_kill_growth", "monster_kill_decay"),
            sources=("https://swordartonline.fandom.com/wiki/Mate_Chopper",),
            notes="PoH's rare cursed dagger-class monster drop; canon curse weakens it on monster kills and strengthens it on player kills.",
        ),
        "tomogiri_maru": _weapon(
            "tomogiri_maru", "Tomogiri-maru", WeaponClass.KATANA, DamageType.SLASH,
            560, 625, 52, 46, 34, 980, 640, 1.72,
            tags=("mate_chopper_evolution", "katana"),
            notes="Powerful katana evolution obtained by lifting the Mate Chopper curse through monster kills.",
        ),
        "karakurenai": _weapon(
            "karakurenai", "Karakurenai", WeaponClass.KATANA, DamageType.SLASH,
            610, 665, 59, 48, 36, 1050, 625, 1.75,
            tags=("klein", "katana_extra_skill"),
            sources=("https://swordartonline.fandom.com/wiki/Karakurenai",),
            notes="Klein's curved katana; use is associated with the Katana Extra Skill derived from Curved Sword training.",
        ),
        "tyrant_dragon": _weapon(
            "tyrant_dragon", "Tyrant Dragon", WeaponClass.TWO_HAND_SWORD, DamageType.SLASH,
            650, 720, 65, 62, 82, 640, 940, 2.05,
            tags=("kuradeel", "decorated", "low_durability_for_tier"),
            sources=("https://swordartonline.fandom.com/wiki/Tyrant_Dragon",),
            notes="Kuradeel's heavily decorated two-handed sword; canon specifically establishes poor durability for its tier.",
        ),
        "dark_repulser": _weapon(
            "dark_repulser", "Dark Repulser", WeaponClass.ONE_HAND_SWORD, DamageType.SLASH,
            680, 700, 60, 60, 150, 1200, 620, 1.70,
            tags=("lisbeth_masterwork", "crystallite_ingot", "kirito"),
            sources=("https://swordartonline.fandom.com/wiki/Dark_Repulser",),
            notes="Attack 680-700, durability 1200, weight 150, Requires 60, STR +52 and AGI +12 come from the published appraisal block.",
            bonus_strength=52,
            bonus_agility=12,
        ),
        "lambent_light": _weapon(
            "lambent_light", "Lambent Light", WeaponClass.RAPIER, DamageType.THRUST,
            660, 695, 60, 46, 24, 1280, 485, 1.78,
            tags=("lisbeth_masterwork", "asuna", "enhanced:+32"),
            sources=("https://swordartonline.fandom.com/wiki/Lambent_Light",),
            notes="Asuna's final SAO rapier, Lisbeth masterwork, canonically enhanced to +32; combat stats here are simulation calibration.",
            bonus_agility=44,
        ),
        "blade_of_frost_steel": _weapon(
            "blade_of_frost_steel", "Blade of Frost Steel", WeaponClass.ONE_HAND_SWORD, DamageType.SLASH,
            420, 470, 45, 38, 31, 760, 660, 1.65,
            tags=("kirito", "nicholas_the_renegade"),
            notes="One-handed sword used by Kirito against Nicholas the Renegade.",
        ),
        "throwing_pick": _weapon(
            "throwing_pick", "Throwing Pick", WeaponClass.THROWING_BLADE, DamageType.THRUST,
            65, 88, 5, 4, 1.2, 85, 360, 8.0,
            tags=("throwing", "concealable", "argo"),
            notes="Small concealable throwing weapon used by Argo and Kirito; reach is runtime ranged calibration.",
        ),
        "spine_of_shmargor": _weapon(
            "spine_of_shmargor", "Spine of Shmargor", WeaponClass.THROWING_BLADE, DamageType.THRUST,
            120, 155, 12, 7, 1.0, 70, 350, 9.0,
            tags=("throwing", "fallen_elf", "paralysis_level_2", "three_hits"),
            notes="Poisonous-dragon spine granted by the Fallen Elves; canon describes level-two paralysis for up to three hits.",
        ),
    }

    for template_id, weapon in rows.items():
        catalog.weapons.setdefault(template_id, weapon)
    return catalog
