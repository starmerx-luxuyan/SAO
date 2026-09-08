from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind


PROGRESSIVE_7 = "Sword Art Online Progressive Volume 7: Rhapsody of Crimson Heat (Start)"
PROGRESSIVE_8 = "Sword Art Online Progressive Volume 8: Rhapsody of Crimson Heat (Finish)"

RUBRABIUM_DYE_ID = "rubrabium_flower_dye"
NARSOS_FRUIT_ID = "narsos_fruit"
WURTZ_STONE_ID = "wurtz_stone"
LYKAON_DECOLORANT_ID = "lykaon_decolorant"
ARENA_DYE_EVIDENCE_ID = "volupta_arena_red_dye_evidence"

NARSOS_REQUIRED = 20
WURTZ_REQUIRED = 50
DECOLORANT_SIMMER_MS = 3 * 60 * 60 * 1000


def _canon(notes: str, source: str = PROGRESSIVE_7) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(source,), notes=notes)


def _inferred(notes: str, *sources: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=tuple(sources) or (PROGRESSIVE_7,), notes=notes)


def apply_floor7_intrigue_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        RUBRABIUM_DYE_ID,
        ItemTemplate(
            template_id=RUBRABIUM_DYE_ID,
            name="Rubrabium Flower Dye",
            kind=ItemKind.MATERIAL,
            weight=0.3,
            stack_limit=10,
            tags=("floor_7", "volupta", "korloy", "red_dye", "caustic", "lykaon_disguise"),
            provenance=_canon(
                "Red plant-derived dye used by Korloy handlers to disguise a Storm Lykaon as a Rusty Lykaon. It can irritate/damage exposed eyes and wounds; weight/stack limit are simulation.",
                PROGRESSIVE_8,
            ),
        ),
    )
    catalog.items.setdefault(
        NARSOS_FRUIT_ID,
        ItemTemplate(
            template_id=NARSOS_FRUIT_ID,
            name="Narsos Fruit",
            kind=ItemKind.MATERIAL,
            weight=0.2,
            stack_limit=99,
            tags=("floor_7", "looserock_forest", "medicinal_fruit", "decolorant_ingredient"),
            provenance=_canon(
                "Medicinal fruit gathered from trees in Looserock Forest. Nirrnir requests twenty ripe fruits for the anti-dye preparation; weight is simulation.",
                PROGRESSIVE_7,
            ),
        ),
    )
    catalog.items.setdefault(
        WURTZ_STONE_ID,
        ItemTemplate(
            template_id=WURTZ_STONE_ID,
            name="Wurtz Stone",
            kind=ItemKind.MATERIAL,
            weight=0.08,
            stack_limit=99,
            tags=("floor_7", "west_riverbank", "black_stone", "decolorant_ingredient"),
            provenance=_canon(
                "Dark stones gathered from the riverbed west of Volupta. Nirrnir requests fifty stones for the anti-dye preparation; weight is simulation.",
                PROGRESSIVE_7,
            ),
        ),
    )
    catalog.items.setdefault(
        LYKAON_DECOLORANT_ID,
        ItemTemplate(
            template_id=LYKAON_DECOLORANT_ID,
            name="Lykaon Decolorant",
            kind=ItemKind.TOOL,
            weight=0.6,
            stack_limit=1,
            tags=("floor_7", "volupta", "decolorant", "removes_dye", "storm_lykaon_reveal"),
            provenance=_canon(
                "Powerful bleaching agent made from squeezed Narsos-fruit juice and Wurtz stones in equal-part preparation, simmered over low heat. "
                "The observed quest batch uses twenty ripe Narsos fruits and fifty Wurtz stones and cooks for about three hours; the runtime represents that whole batch as one bottle.",
                PROGRESSIVE_7,
            ),
        ),
    )
    catalog.items.setdefault(
        ARENA_DYE_EVIDENCE_ID,
        ItemTemplate(
            template_id=ARENA_DYE_EVIDENCE_ID,
            name="Red Dye Trace from the Monster Arena",
            kind=ItemKind.QUEST,
            weight=0.01,
            stack_limit=1,
            tags=("floor_7", "volupta", "cheating_evidence", "monster_arena", "red_plant_dye"),
            provenance=_inferred(
                "After the suspicious arena match, red residue in the cage is identified as plant-based dye rather than blood. This sample item is a runtime representation of that physical evidence.",
                PROGRESSIVE_7,
                PROGRESSIVE_8,
            ),
        ),
    )
    return catalog
