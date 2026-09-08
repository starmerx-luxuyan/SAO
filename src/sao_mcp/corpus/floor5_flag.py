from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind


FLAG_OF_VALOR = "flag_of_valor"
PROGRESSIVE_4 = "Sword Art Online Progressive Volume 4: Scherzo of Deep Night"


def apply_floor5_flag_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        FLAG_OF_VALOR,
        ItemTemplate(
            template_id=FLAG_OF_VALOR,
            name="Flag of Valor",
            kind=ItemKind.MISC,
            weight=1.0,
            stack_limit=1,
            tags=(
                "floor_5",
                "fuscus_drop",
                "guild_flag",
                "all_stats_aura",
                "personal_hidden_drop",
            ),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_4,),
                notes=(
                    "Fuscus can drop the Flag of Valor directly into one raid participant's inventory without informing the others. "
                    "While wielded, it buffs every stat of the wielder's guildmates within range. Exact weight, aura radius and numeric bonus are simulation fields."
                ),
            ),
        ),
    )
    return catalog
