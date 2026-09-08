from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind


PROGRESSIVE_8 = "Sword Art Online Progressive Volume 8: Rhapsody of Crimson Heat (Finish)"
FRESH_AGHYELLR_BLOOD_ID = "fresh_aghyellr_dragon_blood"


def apply_floor7_nirrnir_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        FRESH_AGHYELLR_BLOOD_ID,
        ItemTemplate(
            template_id=FRESH_AGHYELLR_BLOOD_ID,
            name="Fresh Aghyellr Dragon Blood",
            kind=ItemKind.QUEST,
            weight=0.4,
            stack_limit=1,
            tags=(
                "floor_7",
                "aghyellr",
                "dragon_blood",
                "fresh",
                "undiluted",
                "unpreserved",
                "nirrnir_cure",
            ),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_8,),
                notes=(
                    "Fresh, undiluted, unpreserved dragon blood is the cure for Nirrnir's Argent Serpent silver poisoning, "
                    "and Aghyellr provides the required dragon blood. This bottle-sized runtime item abstraction and its weight are simulation."
                ),
            ),
        ),
    )
    return catalog
