from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import (
    DamageType,
    ItemKind,
    ItemTemplate,
    Provenance,
    ProvenanceKind,
    WeaponClass,
    WeaponTemplate,
)


PROGRESSIVE_5 = "Sword Art Online Progressive Volume 5: Canon of the Golden Rule (Start)"
PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
IRON_KEY_ID = "cylon_iron_key"
GAS_MASK_ID = "cylon_gas_mask"
MORTE_HATCHET_ID = "harsh_hatchet"
JOE_DAGGER_ID = "joe_floor6_black_dagger"


def apply_floor6_ambush_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        IRON_KEY_ID,
        ItemTemplate(
            template_id=IRON_KEY_ID,
            name="Cylon's Iron Key",
            kind=ItemKind.QUEST,
            weight=0.08,
            stack_limit=1,
            tags=("floor_6", "curse_of_stachion", "iron_key", "cylon", "dungeon_of_trials"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_6,),
                notes=(
                    "After Cylon's death the players recover an iron key among his dropped valuables. "
                    "A corresponding iron key later becomes important to the changed Dungeon of Trials route. Weight is simulation."
                ),
            ),
        ),
    )
    catalog.items.setdefault(
        GAS_MASK_ID,
        ItemTemplate(
            template_id=GAS_MASK_ID,
            name="Cylon's Gas Mask",
            kind=ItemKind.TOOL,
            weight=0.45,
            stack_limit=1,
            tags=("floor_6", "curse_of_stachion", "gas_mask", "paralysis_gas_protection"),
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=(PROGRESSIVE_5,),
                notes="Gas mask dropped with Cylon's valuables and used by Asuna to move through the paralysis cloud. Weight is simulation.",
            ),
        ),
    )
    catalog.weapons.setdefault(
        MORTE_HATCHET_ID,
        WeaponTemplate(
            template_id=MORTE_HATCHET_ID,
            name="Harsh Hatchet",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER,
            damage_type=DamageType.SLASH,
            attack_min=92,
            attack_max=126,
            required_level=10,
            required_strength=24,
            weight=28,
            base_durability=390,
            base_speed_ms=730,
            reach_m=1.25,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_5, "https://swordartonline.fandom.com/wiki/Items"),
                notes=(
                    "Harsh Hatchet is Morte's canon named one-handed axe. The current WeaponClass enum does not yet split one-handed axes, "
                    "so it uses OTHER; all numeric weapon stats are simulation calibration."
                ),
            ),
        ),
    )
    catalog.weapons.setdefault(
        JOE_DAGGER_ID,
        WeaponTemplate(
            template_id=JOE_DAGGER_ID,
            name="Joe's Black Dagger",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.DAGGER,
            damage_type=DamageType.THRUST,
            attack_min=70,
            attack_max=96,
            required_level=10,
            required_strength=12,
            weight=8,
            base_durability=270,
            base_speed_ms=450,
            reach_m=0.9,
            provenance=Provenance(
                ProvenanceKind.SIMULATION,
                sources=(PROGRESSIVE_5, PROGRESSIVE_6),
                notes=(
                    "The Floor 6 attacker alongside Morte is described as a dagger user and is suspected by Kirito to be Joe. "
                    "The proper weapon name is not locked by the available reliable source, so this display identity and all stats are simulation."
                ),
            ),
        ),
    )
    return catalog
