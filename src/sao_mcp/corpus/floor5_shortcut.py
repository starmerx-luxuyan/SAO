from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES, MonsterDefinition
from sao_mcp.domain.models import DamageType, ItemKind, Provenance, ProvenanceKind, WeaponClass, WeaponTemplate
from sao_mcp.rules.loot import LootTable


PROGRESSIVE_4 = "Sword Art Online Progressive Volume 4: Scherzo of Deep Night"
ARGO_REFERENCE = "https://swordartonline.fandom.com/wiki/Hosaka_Carina_Tomo"
AREA_BOSS_ID = "karluin_catacombs_area_boss"
AREA_BOSS_WEAPON_ID = "karluin_catacombs_area_boss_natural_attack"
AREA_BOSS_LOOT_ID = "aincrad_karluin_catacombs_area_boss"
AREA_BOSS_ROOM = "floor_5_karluin_shortcut_boss_room"


def apply_floor5_shortcut_boss_corpus(catalog: Catalog) -> Catalog:
    catalog.weapons.setdefault(
        AREA_BOSS_WEAPON_ID,
        WeaponTemplate(
            template_id=AREA_BOSS_WEAPON_ID,
            name="Karluin Shortcut Guardian Natural Attack",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER,
            damage_type=DamageType.BLUNT,
            attack_min=88,
            attack_max=118,
            required_level=1,
            required_strength=1,
            weight=0,
            base_durability=15_000,
            base_speed_ms=940,
            reach_m=2.8,
            provenance=Provenance(
                ProvenanceKind.SIMULATION,
                sources=(PROGRESSIVE_4,),
                notes=(
                    "The source confirms a resilient area boss guarding the Karluin-Mananarena shortcut but the available text does not identify its species, name or attack set. "
                    "This natural-attack template is runtime calibration, not canon identity."
                ),
            ),
        ),
    )
    AINCRAD_MONSTERS.setdefault(
        AREA_BOSS_ID,
        MonsterDefinition(
            monster_id=AREA_BOSS_ID,
            name="Karluin Catacombs Area Boss",
            floor_number=5,
            level=12,
            location_id=AREA_BOSS_ROOM,
            hp_factor=7.5,
            quest_kill_id=AREA_BOSS_ID,
            loot_table_id=AREA_BOSS_LOOT_ID,
            tags=(
                "area_boss",
                "unnamed_in_available_source",
                "shortcut_guardian",
                "resilient",
                "puzzle_weakenable",
                "mananarena_shortcut",
            ),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_4, ARGO_REFERENCE),
                notes=(
                    "Canon confirms an area boss in the catacombs beneath Karluin guarding a shortcut tunnel to Mananarena. "
                    "It changed substantially from the beta and was unusually resilient; Argo spent about a day solving a puzzle that weakened it before the Clearers defeated it on December 30. "
                    "The available source does not provide the boss's proper name or species, so this display name is deliberately descriptive. Level, HP and combat stats are simulation."
                ),
            ),
        ),
    )
    AINCRAD_MONSTER_LOOT_TABLES.setdefault(
        AREA_BOSS_LOOT_ID,
        LootTable(
            table_id=AREA_BOSS_LOOT_ID,
            col_min=180,
            col_max=280,
            xp_min=720,
            xp_max=980,
            entries=(),
            provenance="simulation_rewards; source confirms shortcut unlock rather than a named item reward",
        ),
    )
    return catalog
