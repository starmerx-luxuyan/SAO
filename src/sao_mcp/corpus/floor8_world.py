from __future__ import annotations

from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import Provenance, ProvenanceKind, ZoneKind


PROGRESSIVE_9 = "Sword Art Online Progressive Volume 9: Nocturne of the Blue Reflected Moon (Start)"

FRIEBEN = "floor_8_frieben"
ACORN_SHOP = "floor_8_frieben_acorn_shop"
MANAGED_FOREST_OUTER = "floor_8_managed_forest_outer"
FOREST_ELF_SACRED_WOODS = "floor_8_forest_elf_sacred_woods"
FOREST_ELF_ESCAPE_CAVE_MOUTH = "floor_8_forest_elf_escape_cave_mouth"
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

ARBOREAL_ROUTE_TAGS = (
    "tree_branch_route",
    "suspension_bridge_route",
    "flooded_ground_below",
)


def floor8_locations() -> dict[str, LocationDefinition]:
    return {
        ACORN_SHOP: LocationDefinition(
            ACORN_SHOP,
            8,
            "Acorn Shop",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_9,),
                notes=(
                    "Progressive 9 places Argo's Floor 8 rendezvous at the Acorn Shop (団栗屋), "
                    "a small shop on the twelfth level inside Frieben, where Klein is already waiting."
                ),
            ),
        ),
        MANAGED_FOREST_OUTER: LocationDefinition(
            MANAGED_FOREST_OUTER,
            8,
            "Floor 8 Managed Forest - Outer Reach",
            ZoneKind.FIELD,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_9,),
                notes=(
                    "Floor 8 is a waterlogged, carefully managed forest floor around a circular artificial lake. "
                    "This descriptive node represents the outer woodland approach from Frieben."
                ),
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
                notes=(
                    "Progressive 9's emergency involves frontline players damaging protected Forest Elf trees and provoking pursuit. "
                    "The English runtime label is descriptive rather than a claimed canon proper name."
                ),
            ),
        ),
        FOREST_ELF_ESCAPE_CAVE_MOUTH: LocationDefinition(
            FOREST_ELF_ESCAPE_CAVE_MOUTH,
            8,
            "Floor 8 Forest Escape Cave - Mouth",
            ZoneKind.FIELD,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_9,),
                notes=(
                    "Descriptive exterior node separating the pursuing Forest Elves from the player group sheltering inside the cave. "
                    "The separate node preserves the unresolved standoff without fabricating an automatic combat encounter."
                ),
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
                notes="Descriptive node for the cave used by the frontline player group after the Forest Elf protected-woods incident in Progressive 9.",
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
                notes=(
                    "Forest Elf capital inside the managed inner forest of Floor 8. Dark Elves are barred from entering; "
                    "that faction restriction is enforced by scenario/faction rules rather than silently bypassed in the map."
                ),
            ),
        ),
    }


def floor8_connections() -> tuple[TravelConnection, ...]:
    p = Provenance(
        ProvenanceKind.SIMULATION,
        sources=(PROGRESSIVE_9,),
        notes=(
            "Named Floor 8 relationships and the floor-wide use of branches and suspension bridges above flooded ground are canon-backed; "
            "exact travel durations are simulation calibration. Traversal tags describe the route family and do not assert that every metre uses every tagged structure."
        ),
    )
    return (
        TravelConnection(
            FRIEBEN,
            ACORN_SHOP,
            5 * 60_000,
            provenance=p,
            traversal_tags=("safe_town_route", "multi_level_access"),
        ),
        TravelConnection(
            FRIEBEN,
            MANAGED_FOREST_OUTER,
            12 * 60_000,
            provenance=p,
            traversal_tags=ARBOREAL_ROUTE_TAGS,
        ),
        TravelConnection(
            MANAGED_FOREST_OUTER,
            FOREST_ELF_SACRED_WOODS,
            18 * 60_000,
            provenance=p,
            traversal_tags=ARBOREAL_ROUTE_TAGS,
        ),
        TravelConnection(
            FOREST_ELF_SACRED_WOODS,
            FOREST_ELF_ESCAPE_CAVE_MOUTH,
            6 * 60_000,
            provenance=p,
            traversal_tags=ARBOREAL_ROUTE_TAGS,
        ),
        TravelConnection(
            FOREST_ELF_ESCAPE_CAVE_MOUTH,
            FOREST_ELF_ESCAPE_CAVE,
            2 * 60_000,
            provenance=p,
            traversal_tags=("cave_entry",),
        ),
        TravelConnection(
            FOREST_ELF_SACRED_WOODS,
            SLUVA,
            16 * 60_000,
            provenance=p,
            traversal_tags=ARBOREAL_ROUTE_TAGS + ("managed_inner_forest",),
        ),
    )
