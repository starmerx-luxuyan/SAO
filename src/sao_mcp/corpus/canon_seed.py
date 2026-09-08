from __future__ import annotations

from sao_mcp.corpus.bosses_progressive import apply_progressive_boss_catalog_seed
from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.floor2 import apply_floor2_martial_arts_corpus
from sao_mcp.corpus.floor3 import apply_floor3_spider_corpus
from sao_mcp.corpus.floor4 import apply_floor4_shipwright_corpus
from sao_mcp.corpus.floor4_fieldboss import apply_floor4_fieldboss_corpus
from sao_mcp.corpus.floor5 import apply_floor5_karluin_corpus
from sao_mcp.corpus.floor5_flag import apply_floor5_flag_corpus
from sao_mcp.corpus.floor5_shortcut import apply_floor5_shortcut_boss_corpus
from sao_mcp.corpus.floor6_ambush import apply_floor6_ambush_corpus
from sao_mcp.corpus.floor6_stachion import apply_floor6_stachion_corpus
from sao_mcp.corpus.items import apply_aincrad_item_seed
from sao_mcp.corpus.skills import apply_aincrad_skill_seed
from sao_mcp.corpus.weapons import apply_aincrad_weapon_seed
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


def _reinforcement_material(template_id: str, name: str, track: str | None = None) -> ItemTemplate:
    tags = ("reinforcement", "base") if track is None else ("reinforcement", "additional", track)
    return ItemTemplate(
        template_id=template_id,
        name=name,
        kind=ItemKind.MATERIAL,
        weight=0.15,
        stack_limit=99,
        base_value_col=20 if track is None else 30,
        tags=tags,
        provenance=Provenance(
            ProvenanceKind.SIMULATION,
            sources=("Sword Art Online Progressive Volume 1: Rondo of a Fragile Blade",),
            notes=(
                "SAO canon distinguishes fixed base materials and property-specific additional materials. "
                "This generic material identity/name/value is runtime scaffolding rather than a canon item name."
            ),
        ),
    )


def apply_canon_seed(catalog: Catalog) -> Catalog:
    """Add canon identities plus clearly-labelled simulation fields required to execute them."""
    apply_aincrad_skill_seed(catalog)
    apply_aincrad_weapon_seed(catalog)
    apply_aincrad_item_seed(catalog)
    apply_progressive_boss_catalog_seed(catalog)
    apply_floor2_martial_arts_corpus(catalog)
    apply_floor3_spider_corpus(catalog)
    apply_floor4_shipwright_corpus(catalog)
    apply_floor4_fieldboss_corpus(catalog)
    apply_floor5_karluin_corpus(catalog)
    apply_floor5_flag_corpus(catalog)
    apply_floor5_shortcut_boss_corpus(catalog)
    apply_floor6_stachion_corpus(catalog)
    apply_floor6_ambush_corpus(catalog)

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

    reinforcement_materials = {
        "reinforcement_base_material": _reinforcement_material(
            "reinforcement_base_material", "Reinforcement Base Material"
        ),
        "reinforcement_sharpness_material": _reinforcement_material(
            "reinforcement_sharpness_material", "Sharpness Additional Material", "sharpness"
        ),
        "reinforcement_quickness_material": _reinforcement_material(
            "reinforcement_quickness_material", "Quickness Additional Material", "quickness"
        ),
        "reinforcement_accuracy_material": _reinforcement_material(
            "reinforcement_accuracy_material", "Accuracy Additional Material", "accuracy"
        ),
        "reinforcement_heaviness_material": _reinforcement_material(
            "reinforcement_heaviness_material", "Heaviness Additional Material", "heaviness"
        ),
        "reinforcement_durability_material": _reinforcement_material(
            "reinforcement_durability_material", "Durability Additional Material", "durability"
        ),
    }
    for template_id, template in reinforcement_materials.items():
        catalog.items.setdefault(template_id, template)

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
