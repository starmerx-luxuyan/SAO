from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import (
    DamageType,
    ItemKind,
    ItemTemplate,
    Provenance,
    ProvenanceKind,
    SkillDefinition,
    SkillKind,
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
    catalog.skills.setdefault(
        "blacksmithing",
        SkillDefinition(
            skill_id="blacksmithing",
            name="Blacksmithing / Weapon Creation",
            kind=SkillKind.LIFE,
            description="Runtime umbrella for the canon family of weapon-production and smithing skills.",
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(
                    "Sword Art Online Volume 2: Warmth of the Heart",
                    "Sword Art Online Progressive Volume 2: Concerto of Black and White",
                ),
                notes=(
                    "Player blacksmiths and specialised weapon-creation skills are canon. This umbrella skill ID "
                    "keeps the first runtime compact; later corpus expansion can split it into specialised creation skills."
                ),
            ),
        ),
    )
    catalog.skills.setdefault(
        "appraisal",
        SkillDefinition(
            skill_id="appraisal",
            name="Appraisal",
            kind=SkillKind.LIFE,
            description="Identifies item properties and player-made provenance.",
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=("Sword Art Online skill system; Volume 2: Warmth of the Heart",),
                notes="The exact numeric appraisal thresholds remain a future corpus/tuning task.",
            ),
        ),
    )
    return catalog
