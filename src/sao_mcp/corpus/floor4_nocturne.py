from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import Provenance, ProvenanceKind, ZoneKind
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition


PROGRESSIVE_9 = "Sword Art Online Progressive Volume 9: Nocturne of the Blue Reflected Moon (Start)"
YOFILIS_ID = "npc_floor4_viscount_yofilis"
LAKE_YOFEL = "floor_4_lake_yofel"
RIVER_ULL = "floor_4_river_ull"
YOFEL_CASTLE = "floor_4_yofel_castle"
CALDERA_LAKE = "floor_4_caldera_lake"
BEAR_FOREST = "floor_4_bear_forest"
FALLEN_HIDEOUT = "floor_4_fallen_elf_hideout"


def _canon(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(PROGRESSIVE_9,), notes=notes)


def _inferred(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(PROGRESSIVE_9,), notes=notes)


def _sim(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, sources=(PROGRESSIVE_9,), notes=notes)


def apply_floor4_nocturne_corpus(catalog: Catalog) -> Catalog:
    CORE_NPCS.setdefault(
        YOFILIS_ID,
        NPCDefinition(
            npc_id=YOFILIS_ID,
            name="Viscount Yofilis",
            home_location_id=YOFEL_CASTLE,
            roles=("dark_elf", "viscount", "yofel_castle_lord", "elf_war_historical_witness"),
            quest_ids=(),
            knowledge_tags=(
                "yofel_castle",
                "lake_yofel",
                "lavik",
                "sandalwood_knights",
                "ancient_elven_dispute",
                "elf_war",
            ),
            provenance=_inferred(
                "Progressive 9 centers part of the returning Floor 4 storyline on Viscount Yofilis and his past. "
                "His title and Yofel association are canon; runtime role labels summarize that context."
            ),
        ),
    )
    return catalog


def floor4_nocturne_locations() -> dict[str, LocationDefinition]:
    return {
        LAKE_YOFEL: LocationDefinition(
            LAKE_YOFEL,
            4,
            "Lake Yofel",
            ZoneKind.FIELD,
            provenance=_canon(
                "Lake surrounding the Yofel Castle instance and revisited during Nocturne of the Blue Reflected Moon."
            ),
        ),
        RIVER_ULL: LocationDefinition(
            RIVER_ULL,
            4,
            "River Ull",
            ZoneKind.FIELD,
            provenance=_canon(
                "River route leaving the Lake Yofel area and used when travelling toward the hidden Fallen Elf base."
            ),
        ),
    }


def floor4_nocturne_connections() -> tuple[TravelConnection, ...]:
    whole_route = _inferred(
        "Progressive 9 describes the water route from Lake Yofel through River Ull, the central caldera lake and the Bear Forest approach to the submerged Fallen Elf hideout as roughly one hour. Segment durations are simulation splits preserving that one-hour total from Lake Yofel to the hideout."
    )
    castle_edge = _sim("Short Yofel Castle pier-to-lake travel time is runtime calibration.")
    return (
        TravelConnection(YOFEL_CASTLE, LAKE_YOFEL, 4 * 60_000, provenance=castle_edge),
        TravelConnection(LAKE_YOFEL, RIVER_ULL, 10 * 60_000, provenance=whole_route),
        TravelConnection(RIVER_ULL, CALDERA_LAKE, 10 * 60_000, provenance=whole_route),
        TravelConnection(CALDERA_LAKE, BEAR_FOREST, 18 * 60_000, provenance=whole_route),
    )
