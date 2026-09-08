from __future__ import annotations

from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import Provenance, ProvenanceKind, ZoneKind


PROGRESSIVE_5 = "Sword Art Online Progressive Volume 5: Canon of the Golden Rule (Start)"
PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
TIMELINE_REFERENCE = "https://swordartonline.fandom.com/wiki/Sword_Art_Online_Timeline"


def _canon(notes: str, source: str = PROGRESSIVE_5) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(source,), notes=notes)


def _inferred(notes: str, source: str = PROGRESSIVE_5) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(source,), notes=notes)


def _sim(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, notes=notes)


FLOOR6_MAIN_SETTLEMENT = (
    "floor_6_stachion",
    "Stachion",
    _canon(
        "Primary settlement of Floor 6. The city is strongly associated with puzzle mechanisms and the Canon of the Golden Rule storyline."
    ),
)


def floor6_locations() -> dict[str, LocationDefinition]:
    return {
        "floor_6_suribus": LocationDefinition(
            "floor_6_suribus",
            6,
            "Suribus",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=_canon(
                "Eastern Floor 6 settlement where Pithagrus maintains a second/secret residence and where the golden-key investigation advances."
            ),
        ),
        "floor_6_ararro": LocationDefinition(
            "floor_6_ararro",
            6,
            "Ararro",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=_inferred(
                "Named Floor 6 settlement appearing in the Progressive Floor 6 route; exact street geometry is abstracted."
            ),
        ),
        "floor_6_castle_galey": LocationDefinition(
            "floor_6_castle_galey",
            6,
            "Castle Galey",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=(PROGRESSIVE_5, PROGRESSIVE_6, TIMELINE_REFERENCE),
                notes=(
                    "Dark Elf stronghold reached after the early Floor 6 progression. Kirito and Asuna reunite with Kizmel there; "
                    "the Agathe Key and later Fallen Elf attack occur around this castle."
                ),
            ),
        ),
        "floor_6_lake_talpha": LocationDefinition(
            "floor_6_lake_talpha",
            6,
            "Lake Talpha",
            ZoneKind.FIELD,
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=(PROGRESSIVE_6, TIMELINE_REFERENCE),
                notes="Lake crossed with Kizmel while advancing through the southern areas of Floor 6.",
            ),
        ),
        "floor_6_pithagrus_suribus_house": LocationDefinition(
            "floor_6_pithagrus_suribus_house",
            6,
            "Pithagrus's Suribus House",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=_canon(
                "Pithagrus's second home in Suribus, where Kirito and Asuna obtain the golden key during Canon of the Golden Rule."
            ),
        ),
        "floor_6_stachion_puzzle_quarter": LocationDefinition(
            "floor_6_stachion_puzzle_quarter",
            6,
            "Stachion Puzzle Quarter",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=_inferred(
                "Descriptive runtime node for Stachion's canon puzzle-heavy urban content; this is not a canon proper district name."
            ),
        ),
    }


def floor6_connections() -> tuple[TravelConnection, ...]:
    p = _sim("Travel durations are simulation; named endpoint relationships follow the Progressive Floor 6 route.")
    return (
        TravelConnection("floor_6_stachion", "floor_6_stachion_puzzle_quarter", 4 * 60_000, provenance=p),
        TravelConnection("floor_6_stachion", "floor_6_field", 10 * 60_000, provenance=p),
        TravelConnection("floor_6_field", "floor_6_suribus", 28 * 60_000, provenance=p),
        TravelConnection("floor_6_suribus", "floor_6_pithagrus_suribus_house", 3 * 60_000, provenance=p),
        TravelConnection("floor_6_field", "floor_6_ararro", 22 * 60_000, provenance=p),
        TravelConnection("floor_6_field", "floor_6_castle_galey", 42 * 60_000, provenance=p),
        TravelConnection("floor_6_castle_galey", "floor_6_lake_talpha", 24 * 60_000, provenance=p),
        TravelConnection("floor_6_lake_talpha", "floor_6_labyrinth", 48 * 60_000, provenance=p),
    )
