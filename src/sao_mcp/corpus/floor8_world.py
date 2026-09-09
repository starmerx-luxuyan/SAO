from __future__ import annotations

from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import Provenance, ProvenanceKind, ZoneKind


PROGRESSIVE_9 = "Sword Art Online Progressive Volume 9: Nocturne of the Blue Reflected Moon (Start)"

FRIEBEN = "floor_8_frieben"
MANAGED_FOREST_OUTER = "floor_8_managed_forest_outer"
FOREST_ELF_SACRED_WOODS = "floor_8_forest_elf_sacred_woods"
FOREST_ELF_ESCAPE_CAVE = "floor_8_forest_elf_escape_cave"
SLUVA = "floor_8_sluva"

FLOOR8_MAIN_SETTLEMENT = (
    FRIEBEN,
    "Frieben",
    Provenance(
        ProvenanceKind.CANON_INFERRED,
        sources=(PROGRESSIVE_9,),
        notes="Progressive 9 identifies Frieben as the Floor 8 main settlement on the outer side of the floor's circular artificial lake.",
    ),
)


def floor8_locations() -> dict[str, LocationDefinition]:
    return {
        MANAGED_FOREST_OUTER: LocationDefinition(
            MANAGED_FOREST_OUTER,
            8,
            "Floor 8 Managed Forest - Outer Reach",
            ZoneKind.FIELD,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_9,),
                notes="Floor 8 is a waterlogged forest floor built around a circular artificial lake and managed woodland. This runtime node represents the outer approach from Frieben.",
            ),
        ),
        FOREST_ELF_SACRED_WOODS: LocationDefinition(
            FOREST_ELF_SACRED_WOODS,
            8,
            "Forest Elf Sacred Woods",
            ZoneKind.FIELD,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_9,),
                notes="Progressive 9's emergency involves frontline players cutting protected Forest Elf trees and provoking a pursuit. The exact runtime label is descriptive.",
            ),
        ),
        FOREST_ELF_ESCAPE_CAVE: LocationDefinition(
            FOREST_ELF_ESCAPE_CAVE,
            8,
            "Floor 8 Forest Escape Cave",
            ZoneKind.DUNGEON,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_9,),
                notes="Descriptive node for the cave used by the player group after the Forest Elf sacred-woods incident in Progressive 9.",
            ),
        ),
        SLUVA: LocationDefinition(
            SLUVA,
            8,
            "Sluva",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_9,),
                notes="Forest Elf capital inside the managed inner forest of Floor 8. Dark Elves are barred from entering; that faction restriction remains a scenario rule rather than a generic map fallback.",
            ),
        ),
    }


def floor8_connections() -> tuple[TravelConnection, ...]:
    p = Provenance(
        ProvenanceKind.SIMULATION,
        sources=(PROGRESSIVE_9,),
        notes="Named Floor 8 relationships are canon-backed; exact travel durations are simulation calibration.",
    )
    return (
        TravelConnection(FRIEBEN, MANAGED_FOREST_OUTER, 12 * 60_000, provenance=p),
        TravelConnection(MANAGED_FOREST_OUTER, FOREST_ELF_SACRED_WOODS, 18 * 60_000, provenance=p),
        TravelConnection(FOREST_ELF_SACRED_WOODS, FOREST_ELF_ESCAPE_CAVE, 8 * 60_000, provenance=p),
        TravelConnection(FOREST_ELF_SACRED_WOODS, SLUVA, 16 * 60_000, provenance=p),
    )