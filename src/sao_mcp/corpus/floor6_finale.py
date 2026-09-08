from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind


PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
GOLDEN_CUBE_ID = "stachion_golden_cube"
COMBINED_IRON_KEY_ID = "floor6_combined_iron_key"


def apply_floor6_finale_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        GOLDEN_CUBE_ID,
        ItemTemplate(
            template_id=GOLDEN_CUBE_ID,
            name="Golden Cube",
            kind=ItemKind.QUEST,
            weight=3.5,
            stack_limit=1,
            tags=(
                "floor_6",
                "curse_of_stachion",
                "irrational_cube_core_component",
                "bind",
                "break",
                "prototype_war_tool",
            ),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_6,),
                notes=(
                    "The Golden Cube is the Stachion lordship symbol and Pithagrus murder weapon. Theano ultimately returns it to the black core of The Irrational Cube; "
                    "its power can Bind living targets and Break/erase objects, and the boss cannot be attacked until the cube is restored to its body. "
                    "Exact item weight is simulation."
                ),
            ),
        ),
    )
    catalog.items.setdefault(
        COMBINED_IRON_KEY_ID,
        ItemTemplate(
            template_id=COMBINED_IRON_KEY_ID,
            name="Combined Iron Key",
            kind=ItemKind.QUEST,
            weight=0.12,
            stack_limit=1,
            tags=(
                "floor_6",
                "curse_of_stachion",
                "paired_iron_keys_combined",
                "irrational_cube_reverse_keyhole",
                "golden_cube_ejector",
                "survives_boss_destruction",
            ),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_6,),
                notes=(
                    "Cylon's and Theano's mutually repelling iron keys can be combined into a single narrow metal key. "
                    "That key fits the reverse-side keyhole of The Irrational Cube and ejects the Golden Cube; after the boss and Golden Cube are destroyed, the steel key survives. "
                    "Exact item weight is simulation. Runtime preserves source instance IDs when the two keys are combined."
                ),
            ),
        ),
    )
    return catalog
