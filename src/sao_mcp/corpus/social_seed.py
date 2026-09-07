from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind


def apply_social_catalog_seed(catalog: Catalog) -> Catalog:
    """Add rare social/death-system identities without making them normal vendor inventory."""
    catalog.items.setdefault(
        "divine_stone_returning_soul",
        ItemTemplate(
            template_id="divine_stone_returning_soul",
            name="Divine Stone of Returning Soul",
            kind=ItemKind.CONSUMABLE,
            weight=0.2,
            stack_limit=1,
            tags=("unique", "revival", "end_phase"),
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=("Sword Art Online Volume 2: Red-nosed Reindeer",),
                notes=(
                    "Unique revival item whose activation is limited to the brief End Phase after death, "
                    "approximately ten seconds. The runtime's revived-HP ratio is simulation calibration."
                ),
            ),
        ),
    )
    return catalog
