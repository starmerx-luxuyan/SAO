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


def apply_canon_seed(catalog: Catalog) -> Catalog:
    """Add compact canon identities that need provenance more specific than generic templates."""
    catalog.weapons.setdefault(
        "anneal_blade",
        WeaponTemplate(
            template_id="anneal_blade",
            name="Anneal Blade",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.ONE_HAND_SWORD,
            damage_type=DamageType.SLASH,
            attack_min=31,
            attack_max=42,
            required_level=3,
            required_strength=10,
            weight=22,
            base_durability=310,
            base_speed_ms=690,
            reach_m=1.6,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(
                    "Sword Art Online Volume 8: First Day",
                    "Sword Art Online Progressive Volume 1",
                ),
                notes=(
                    "The weapon identity, Floor 1 quest reward role, and eight enhancement attempts are canon. "
                    "Attack, requirement, weight, durability and timing numbers here are simulation calibration."
                ),
            ),
        ),
    )
    catalog.items.setdefault(
        "little_nepenthes_ovule",
        ItemTemplate(
            template_id="little_nepenthes_ovule",
            name="Little Nepenthes Ovule",
            kind=ItemKind.QUEST,
            weight=0.1,
            stack_limit=1,
            tags=("quest_item", "secret_medicine_of_the_forest"),
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=("Sword Art Online Volume 8: First Day",),
                notes="Required rare drop for the Floor 1 Secret Medicine of the Forest quest.",
            ),
        ),
    )
    return catalog
