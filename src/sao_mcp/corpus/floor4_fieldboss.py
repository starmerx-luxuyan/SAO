from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES, MonsterDefinition
from sao_mcp.domain.models import DamageType, ItemKind, Provenance, ProvenanceKind, WeaponClass, WeaponTemplate
from sao_mcp.rules.loot import LootTable


PROGRESSIVE_3 = "Sword Art Online Progressive Volume 3: Barcarolle of Froth"
REFERENCE = "https://swordartonline.fandom.com/wiki/Biceps_Archelon"
BICEPS_ID = "biceps_archelon"
BICEPS_WEAPON_ID = "biceps_archelon_natural_attack"
BICEPS_LOOT_ID = "aincrad_biceps_archelon"
CALDERA_LAKE = "floor_4_caldera_lake"


def apply_floor4_fieldboss_corpus(catalog: Catalog) -> Catalog:
    catalog.weapons.setdefault(
        BICEPS_WEAPON_ID,
        WeaponTemplate(
            template_id=BICEPS_WEAPON_ID,
            name="Biceps Archelon Bite and Fin",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER,
            damage_type=DamageType.BLUNT,
            attack_min=82,
            attack_max=108,
            required_level=1,
            required_strength=1,
            weight=0,
            base_durability=20_000,
            base_speed_ms=1100,
            reach_m=4.0,
            provenance=Provenance(
                ProvenanceKind.SIMULATION,
                sources=(PROGRESSIVE_3, REFERENCE),
                notes="Bite and fin attacks are canon and described as comparatively weak; numeric attack fields are simulation.",
            ),
        ),
    )
    AINCRAD_MONSTERS.setdefault(
        BICEPS_ID,
        MonsterDefinition(
            monster_id=BICEPS_ID,
            name="Biceps Archelon",
            floor_number=4,
            level=28,
            location_id=CALDERA_LAKE,
            hp_factor=12.0,
            quest_kill_id=BICEPS_ID,
            loot_table_id=BICEPS_LOOT_ID,
            tags=(
                "field_boss",
                "two_hp_bars",
                "twenty_metre_turtle",
                "two_heads",
                "shell_sides_nearly_invulnerable",
                "weak_heads",
                "weak_abdomen",
                "dangerous_charge",
                "spin_below_ten_percent",
                "spin_preparation_defense_up",
            ),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_3, REFERENCE),
                notes=(
                    "Field Boss identity, Caldera Lake location, two HP bars, ~20 m body, protected shell sides, exposed heads/abdomen, "
                    "dangerous charge and sub-10% spin preparation are canon. Level, total HP and ordinary numeric stats are simulation."
                ),
            ),
        ),
    )
    AINCRAD_MONSTER_LOOT_TABLES.setdefault(
        BICEPS_LOOT_ID,
        LootTable(
            table_id=BICEPS_LOOT_ID,
            col_min=420,
            col_max=620,
            xp_min=1700,
            xp_max=2300,
            entries=(),
            provenance="simulation_rewards; canon Last Attack exists but its item identity is not specified",
        ),
    )
    return catalog
