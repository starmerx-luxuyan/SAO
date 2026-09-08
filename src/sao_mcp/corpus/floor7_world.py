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
        "floor_7_field_of_bones_watch_hill": LocationDefinition(
            "floor_7_field_of_bones_watch_hill", 7, "Field of Bones Watch Hill", ZoneKind.FIELD,
            provenance=_inferred(
                "Descriptive runtime node for the rocky hill used to watch the Dragon Bone from over three hundred yards away before the seven-o'clock Fallen Elf rendezvous.",
                PROGRESSIVE_8,
            ),
        ),
        "floor_7_dragon_bone": LocationDefinition(
            "floor_7_dragon_bone", 7, "Dragon Bone", ZoneKind.FIELD,
            provenance=_canon(
                "Huge dead tree in the Field of Bones selected by the Fallen Elves as their counteroffer meeting point at seven in the morning.",
                PROGRESSIVE_8,
            ),
        ),
        "floor_7_looserock_forest": LocationDefinition(
            "floor_7_looserock_forest", 7, "Looserock Forest", ZoneKind.FIELD,
            provenance=_canon("Forest whose moving/loose boulders form a major Floor 7 route hazard."),
        ),
        "floor_7_harin_tree_palace": LocationDefinition(
            "floor_7_harin_tree_palace", 7, "Harin Tree Palace", ZoneKind.DUNGEON,
            provenance=_canon("Dark Elf palace reached through the Looserock Forest during the continuing Elf War campaign."),
        ),
        "floor_7_harin_b2_cell": LocationDefinition(
            "floor_7_harin_b2_cell", 7, "Harin Tree Palace - B2 Prison Cell", ZoneKind.DUNGEON,
            provenance=_canon(
                "Kirito and Asuna are held on the west side of the second basement prison level after being suspected of collaborating with the Fallen Elves."
            ),
        ),
        "floor_7_harin_b2_guard_station": LocationDefinition(
            "floor_7_harin_b2_guard_station", 7, "Harin Tree Palace - B2 Guard Station", ZoneKind.DUNGEON,
            provenance=_canon("Central guard post between the basement cell blocks."),
        ),
        "floor_7_harin_weapon_store": LocationDefinition(
            "floor_7_harin_weapon_store", 7, "Harin Tree Palace - Confiscated Weapon Store", ZoneKind.DUNGEON,
            provenance=_inferred(
                "Small storage room beside the basement guard station where the players' swords, their Lyusula sigils, the Elven Stout Sword and Kizmel's saber are held."
            ),
        ),
        "floor_7_harin_lavik_cell": LocationDefinition(
            "floor_7_harin_lavik_cell", 7, "Harin Tree Palace - Lavik's Cell", ZoneKind.DUNGEON,
            provenance=_inferred(
                "Descriptive node for the basement cell occupied for roughly thirty years by Lavik Fen Cortassios; exact cell number is not asserted."
            ),
        ),
        "floor_7_harin_seventh_prison": LocationDefinition(
            "floor_7_harin_seventh_prison", 7, "Harin Tree Palace - Seventh-Story Clergy Prison", ZoneKind.DUNGEON,
            provenance=_canon(
                "Prison in the priests' living quarters on the seventh story where Kizmel is held on suspicion of Fallen Elf treachery."
            ),
        ),
        "floor_7_harin_escape_window": LocationDefinition(
            "floor_7_harin_escape_window", 7, "Harin Tree Palace - Seventh-Story Escape Window", ZoneKind.DUNGEON,
            provenance=_inferred(
                "Scenario node for the seventh-story window used by Kirito, Asuna, Kizmel and Lavik to begin their exterior descent."
            ),
        ),
        "floor_7_harin_outer_trunk": LocationDefinition(
            "floor_7_harin_outer_trunk", 7, "Harin Tree Palace - Outer Trunk", ZoneKind.FIELD,
            provenance=_canon(
                "The escape route descends roughly fifty metres down the natural outer trunk using thin lifelines while the palace is blacked out."
            ),
        ),
        "floor_7_ant_tunnel_valley": LocationDefinition(
            "floor_7_ant_tunnel_valley", 7, "Ant Tunnel Valley", ZoneKind.FIELD,
            provenance=_canon(
                "Canyon region of cramped ravines and three-dimensional tunnels inhabited by rapidly reinforcing ant monsters; the pursued Fallen Elves pass directly through it.",
                PROGRESSIVE_8,
            ),
        ),
        "floor_7_ant_tunnel_plateau": LocationDefinition(
            "floor_7_ant_tunnel_plateau", 7, "Plateau Beyond Ant Tunnel Valley", ZoneKind.FIELD,
            provenance=_inferred(
                "Descriptive node for the plateau the two Fallen Elves cross after Ant Tunnel Valley immediately before entering the Floor 7 Labyrinth.",
                PROGRESSIVE_8,
            ),
        ),
        "floor_7_labyrinth_saferoom": LocationDefinition(
            "floor_7_labyrinth_saferoom", 7, "Floor 7 Labyrinth Saferoom", ZoneKind.LABYRINTH,
            provenance=_canon(
                "Saferoom near the upper part of the Floor 7 Labyrinth where the pursuing party rests at four in the morning on January 8 after losing the Fallen Elves.",
                PROGRESSIVE_8,
            ),
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
        TravelConnection("floor_7_harin_tree_palace", "floor_7_harin_b2_guard_station", 7 * 60_000, provenance=p),
        TravelConnection("floor_7_harin_b2_guard_station", "floor_7_harin_weapon_store", 1 * 60_000, provenance=p),
        TravelConnection("floor_7_harin_b2_guard_station", "floor_7_harin_lavik_cell", 2 * 60_000, provenance=p),
        TravelConnection("floor_7_harin_b2_guard_station", "floor_7_harin_seventh_prison", 22 * 60_000, provenance=p),
        TravelConnection("floor_7_harin_seventh_prison", "floor_7_harin_escape_window", 2 * 60_000, provenance=p),
        TravelConnection("floor_7_harin_escape_window", "floor_7_harin_outer_trunk", 28 * 60_000, provenance=p),
        TravelConnection("floor_7_harin_outer_trunk", "floor_7_looserock_forest", 8 * 60_000, provenance=p),
        TravelConnection("floor_7_verdian_plains", "floor_7_ant_tunnel_valley", 30 * 60_000, provenance=p),
        TravelConnection("floor_7_ant_tunnel_valley", "floor_7_tribula", 20 * 60_000, provenance=p),
        TravelConnection("floor_7_volupta", "floor_7_field_of_bones", 44 * 60_000, provenance=p),
        TravelConnection("floor_7_field_of_bones", "floor_7_field_of_bones_watch_hill", 25 * 60_000, provenance=p),
        TravelConnection("floor_7_field_of_bones_watch_hill", "floor_7_dragon_bone", 10 * 60_000, provenance=p),
        TravelConnection("floor_7_dragon_bone", "floor_7_ant_tunnel_valley", 75 * 60_000, provenance=p),
        TravelConnection("floor_7_ant_tunnel_valley", "floor_7_ant_tunnel_plateau", 35 * 60_000, provenance=p),
        TravelConnection("floor_7_ant_tunnel_plateau", "floor_7_labyrinth", 25 * 60_000, provenance=p),
        TravelConnection("floor_7_labyrinth", "floor_7_labyrinth_saferoom", 6 * 60 * 60_000, provenance=p),
    )
