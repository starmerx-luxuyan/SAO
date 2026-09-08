from __future__ import annotations

from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import Provenance, ProvenanceKind, ZoneKind


PROGRESSIVE_7 = "Sword Art Online Progressive Volume 7: Rhapsody of Crimson Heat (Start)"
PROGRESSIVE_8 = "Sword Art Online Progressive Volume 8: Rhapsody of Crimson Heat (Finish)"


def _canon(notes: str, source: str = PROGRESSIVE_7) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(source,), notes=notes)


def _inferred(notes: str, source: str = PROGRESSIVE_7) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(source,), notes=notes)


def _sim(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, notes=notes)


FLOOR7_MAIN_SETTLEMENT = (
    "floor_7_lectio",
    "Lectio",
    _canon("Main settlement and Teleport Gate city of Aincrad Floor 7."),
)


def floor7_locations() -> dict[str, LocationDefinition]:
    return {
        "floor_7_verdian_plains": LocationDefinition(
            "floor_7_verdian_plains", 7, "Verdian Plains", ZoneKind.FIELD,
            provenance=_canon("Open plains on the route from Lectio toward Volupta."),
        ),
        "floor_7_volupta": LocationDefinition(
            "floor_7_volupta", 7, "Volupta", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon("Large resort/casino town governed through the Nachtoy-Korloy casino rivalry."),
        ),
        "floor_7_volupta_grand_casino": LocationDefinition(
            "floor_7_volupta_grand_casino", 7, "Volupta Grand Casino", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon("Grand casino at the centre of the Floor 7 casino storyline."),
        ),
        "floor_7_volupta_beach": LocationDefinition(
            "floor_7_volupta_beach", 7, "Volupta Beach", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon("Beach/resort area attached to Volupta."),
        ),
        "floor_7_monster_arena": LocationDefinition(
            "floor_7_monster_arena", 7, "Volupta Grand Casino Monster Arena", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon("Casino arena where spectators wager Volcoins on monster-versus-monster matches."),
        ),
        "floor_7_korloy_monster_stables": LocationDefinition(
            "floor_7_korloy_monster_stables", 7, "Korloy Monster Stables", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_inferred(
                "Korloy-controlled monster stable complex behind/under the casino where handlers dye the disguised Storm Lykaon and later where the Argent Serpent trap occurs. The runtime label is descriptive rather than a canon proper name.",
                PROGRESSIVE_8,
            ),
        ),
        "floor_7_west_riverbank": LocationDefinition(
            "floor_7_west_riverbank", 7, "Volupta West Riverbank", ZoneKind.FIELD,
            provenance=_inferred(
                "Descriptive runtime node for the riverbed west of Volupta where Wurtz stones are collected; the source establishes the river and relation to Volupta but does not supply a proper place name.",
                PROGRESSIVE_7,
            ),
        ),
        "floor_7_pramio": LocationDefinition(
            "floor_7_pramio", 7, "Pramio", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon("Named Floor 7 settlement on the Progressive route."),
        ),
        "floor_7_field_of_bones": LocationDefinition(
            "floor_7_field_of_bones", 7, "Field of Bones", ZoneKind.FIELD,
            provenance=_canon("Bone-strewn field used during the Fallen Elf pursuit toward the Floor 7 Labyrinth.", PROGRESSIVE_8),
        ),
        "floor_7_looserock_forest": LocationDefinition(
            "floor_7_looserock_forest", 7, "Looserock Forest", ZoneKind.FIELD,
            provenance=_canon("Forest whose moving/loose boulders form a major Floor 7 route hazard."),
        ),
        "floor_7_harin_tree_palace": LocationDefinition(
            "floor_7_harin_tree_palace", 7, "Harin Tree Palace", ZoneKind.DUNGEON,
            provenance=_canon("Dark Elf palace reached through the Looserock Forest during the continuing Elf War campaign."),
        ),
        "floor_7_ant_tunnel_valley": LocationDefinition(
            "floor_7_ant_tunnel_valley", 7, "Ant Tunnel Valley", ZoneKind.FIELD,
            provenance=_inferred("Named Floor 7 field region; exact internal geometry is abstracted."),
        ),
        "floor_7_tribula": LocationDefinition(
            "floor_7_tribula", 7, "Tribula Village", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_inferred("Named Floor 7 village; exact local geometry is abstracted."),
        ),
    }


def floor7_connections() -> tuple[TravelConnection, ...]:
    p = _sim("Travel durations are runtime calibration except where a source duration is explicitly noted in location provenance.")
    return (
        TravelConnection("floor_7_lectio", "floor_7_verdian_plains", 12 * 60_000, provenance=p),
        TravelConnection("floor_7_verdian_plains", "floor_7_volupta", 32 * 60_000, provenance=p),
        TravelConnection("floor_7_volupta", "floor_7_volupta_grand_casino", 4 * 60_000, provenance=p),
        TravelConnection("floor_7_volupta", "floor_7_volupta_beach", 6 * 60_000, provenance=p),
        TravelConnection("floor_7_volupta_grand_casino", "floor_7_monster_arena", 2 * 60_000, provenance=p),
        TravelConnection("floor_7_volupta_grand_casino", "floor_7_korloy_monster_stables", 3 * 60_000, provenance=p),
        TravelConnection("floor_7_volupta", "floor_7_west_riverbank", 14 * 60_000, provenance=p),
        TravelConnection("floor_7_verdian_plains", "floor_7_pramio", 28 * 60_000, provenance=p),
        TravelConnection(
            "floor_7_volupta",
            "floor_7_looserock_forest",
            90 * 60_000,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_7,),
                notes="The source states that reaching the Looserock Forest entrance and returning to Volupta is about a three-hour round trip; this edge uses half that duration each way.",
            ),
        ),
        TravelConnection("floor_7_looserock_forest", "floor_7_harin_tree_palace", 22 * 60_000, provenance=p),
        TravelConnection("floor_7_verdian_plains", "floor_7_ant_tunnel_valley", 30 * 60_000, provenance=p),
        TravelConnection("floor_7_ant_tunnel_valley", "floor_7_tribula", 20 * 60_000, provenance=p),
        TravelConnection("floor_7_volupta", "floor_7_field_of_bones", 44 * 60_000, provenance=p),
        TravelConnection("floor_7_field_of_bones", "floor_7_labyrinth", 35 * 60_000, provenance=p),
    )
