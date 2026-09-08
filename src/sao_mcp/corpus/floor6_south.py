from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import DamageType, ItemKind, Provenance, ProvenanceKind, WeaponClass, WeaponTemplate


PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
BASALT_MORPHA_ID = "basalt_morpha"
BASALT_MORPHA_WEAPON_ID = "basalt_morpha_natural_crush"


def apply_floor6_south_corpus(catalog: Catalog) -> Catalog:
    catalog.weapons.setdefault(
        BASALT_MORPHA_WEAPON_ID,
        WeaponTemplate(
            template_id=BASALT_MORPHA_WEAPON_ID,
            name="Basalt Morpha Natural Crush",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER,
            damage_type=DamageType.BLUNT,
            attack_min=112,
            attack_max=148,
            required_level=1,
            required_strength=1,
            weight=0,
            base_durability=16_000,
            base_speed_ms=900,
            reach_m=2.7,
            provenance=Provenance(
                ProvenanceKind.SIMULATION,
                sources=(PROGRESSIVE_6,),
                notes=(
                    "Basalt Morpha is the rock-armored centipede mid-boss encountered in the southern fourth area. "
                    "Its name, centipede form and extremely durable stone armor are canon; this natural-attack package is simulation calibration."
                ),
            ),
        ),
    )
    return catalog
