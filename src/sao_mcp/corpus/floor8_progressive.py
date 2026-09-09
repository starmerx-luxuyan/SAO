from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.floor8_world import ACORN_SHOP
from sao_mcp.domain.models import Provenance, ProvenanceKind
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition


PROGRESSIVE_9 = "Sword Art Online Progressive Volume 9: Nocturne of the Blue Reflected Moon (Start)"
KLEIN_ID = "pc_klein"


def apply_floor8_progressive_corpus(catalog: Catalog) -> Catalog:
    CORE_NPCS.setdefault(
        KLEIN_ID,
        NPCDefinition(
            npc_id=KLEIN_ID,
            name="Klein",
            home_location_id=ACORN_SHOP,
            roles=("named_player", "frontline_player", "katana_user"),
            quest_ids=(),
            knowledge_tags=("floor_1", "floor_8", "frieben", "argo", "acorn_shop"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_9,),
                notes=(
                    "Progressive 9 reunites Kirito with Klein at Argo's Acorn Shop rendezvous in Frieben. "
                    "The runtime keeps Klein's exact combat level and numeric stats outside this corpus as simulation fields."
                ),
            ),
        ),
    )
    return catalog
