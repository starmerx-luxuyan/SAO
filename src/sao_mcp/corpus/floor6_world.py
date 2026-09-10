from __future__ import annotations

from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import Provenance, ProvenanceKind, ZoneKind


PROGRESSIVE_5 = "Sword Art Online Progressive Volume 5: Canon of the Golden Rule (Start)"
PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
TIMELINE_REFERENCE = "https://swordartonline.fandom.com/wiki/Sword_Art_Online_Timeline"

STACHION_POST_AMBUSH_CONNECTION_ID = "floor6_stachion_post_ambush_roads"
TRIALS_SECRET_BACK_DOOR_CONNECTION_ID = "floor6_trials_secret_back_door"
TRIALS_MAIN_ENTRANCE_CONNECTION_ID = "floor6_trials_main_entrance"
GOLDEN_CUBE_LABYRINTH_BREACH_CONNECTION_ID = "floor6_golden_cube_labyrinth_breach"


def _canon(notes: str, source: str = PROGRESSIVE_5) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(source,), notes=notes)


def _inferred(notes: str, source: str = PROGRESSIVE_5) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(source,), notes=notes)


def _sim(notes: str, source: str = PROGRESSIVE_6) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, sources=(source,), notes=notes)


FLOOR6_MAIN_SETTLEMENT = (
    "floor_6_stachion",
    "Stachion",
    _canon(
        "Primary settlement of Floor 6. The city is strongly associated with puzzle mechanisms and the Canon of the Golden Rule storyline."
    ),
)


STACHION_POST_AMBUSH_CONNECTIONS = (
    TravelConnection(
        "floor_6_cylon_transport_carriage",
        "floor_6_suribus",
        14 * 60_000,
        provenance=_sim(
            "The ambush occurs on the road between Suribus and Stachion; exact remaining travel time is runtime calibration.",
            PROGRESSIVE_5,
        ),
        traversal_tags=("post_ambush_road", "suribus_stachion_route"),
    ),
    TravelConnection(
        "floor_6_cylon_transport_carriage",
        "floor_6_stachion",
        20 * 60_000,
        provenance=_sim(
            "The ambush occurs on the road between Suribus and Stachion; exact remaining travel time is runtime calibration.",
            PROGRESSIVE_5,
        ),
        traversal_tags=("post_ambush_road", "suribus_stachion_route"),
    ),
    TravelConnection(
        "floor_6_cylon_transport_carriage",
        "floor_6_field",
        12 * 60_000,
        provenance=_sim(
            "A roadside escape from the carriage ambush reaches the surrounding Floor 6 field without requiring entry into either safe settlement. Exact time is simulation.",
            PROGRESSIVE_5,
        ),
        traversal_tags=("post_ambush_road", "field_escape_route"),
    ),
)

TRIALS_SECRET_BACK_DOOR_CONNECTIONS = (
    TravelConnection(
        "floor_6_cylon_lord_manor",
        "floor_6_dungeon_of_trials_secret_back_door",
        1 * 60_000,
        provenance=_sim(
            "Terro revealing the movable statue-base secret route is canon; exact traversal time is runtime calibration."
        ),
        traversal_tags=("revealed_secret_passage", "dungeon_of_trials_back_door"),
    ),
    TravelConnection(
        "floor_6_dungeon_of_trials_secret_back_door",
        "floor_6_dungeon_of_trials_final_chamber",
        2 * 60_000,
        provenance=_sim(
            "The release route reaches the final chamber through the hidden rear route; exact traversal time is runtime calibration."
        ),
        traversal_tags=("revealed_secret_passage", "release_route_bypass"),
    ),
)

TRIALS_MAIN_ENTRANCE_CONNECTIONS = (
    TravelConnection(
        "floor_6_dungeon_of_trials_entrance",
        "floor_6_dungeon_of_trials",
        1 * 60_000,
        provenance=_sim(
            "The golden key opens the original Dungeon of Trials main entrance; exact door traversal time is runtime calibration."
        ),
        traversal_tags=("golden_key_opened", "dungeon_of_trials_main_entrance"),
    ),
)

GOLDEN_CUBE_LABYRINTH_BREACH_CONNECTIONS = (
    TravelConnection(
        "floor_6_labyrinth",
        "floor_6_labyrinth_golden_cube_breach",
        2 * 60_000,
        provenance=_sim(
            "Theano uses the Golden Cube to dismantle labyrinth walls into blocks; exact traversal time through the breach is simulation."
        ),
        traversal_tags=("golden_cube_break", "destroyed_labyrinth_wall"),
    ),
    TravelConnection(
        "floor_6_labyrinth_golden_cube_breach",
        "floor_6_boss_room",
        18 * 60_000,
        provenance=_sim(
            "The Golden Cube creates an abnormal direct route toward the boss chamber; exact traversal time is simulation."
        ),
        traversal_tags=("golden_cube_break", "abnormal_labyrinth_shortcut"),
    ),
)


def floor6_locations() -> dict[str, LocationDefinition]:
    return {
        "floor_6_suribus": LocationDefinition(
            "floor_6_suribus", 6, "Suribus", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon("Eastern Floor 6 settlement where Pithagrus maintains a second/secret residence and where the golden-key investigation advances."),
        ),
        "floor_6_ararro": LocationDefinition(
            "floor_6_ararro", 6, "Ararro", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_inferred("Named Floor 6 settlement appearing in the Progressive Floor 6 route; exact street geometry is abstracted."),
        ),
        "floor_6_castle_galey": LocationDefinition(
            "floor_6_castle_galey", 6, "Castle Galey", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=(PROGRESSIVE_5, PROGRESSIVE_6, TIMELINE_REFERENCE),
                notes="Dark Elf stronghold reached after the early Floor 6 progression; the Agate Key and later Fallen Elf attack occur around this castle.",
            ),
        ),
        "floor_6_lake_talpha": LocationDefinition(
            "floor_6_lake_talpha", 6, "Lake Talpha", ZoneKind.FIELD,
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=(PROGRESSIVE_6, TIMELINE_REFERENCE),
                notes="Lake crossed with Kizmel while advancing through the southern areas of Floor 6.",
            ),
        ),
        "floor_6_pithagrus_suribus_house": LocationDefinition(
            "floor_6_pithagrus_suribus_house", 6, "Pithagrus's Suribus House", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon("Pithagrus's second home in Suribus, where Kirito and Asuna obtain the golden key during Canon of the Golden Rule."),
        ),
        "floor_6_stachion_puzzle_quarter": LocationDefinition(
            "floor_6_stachion_puzzle_quarter", 6, "Stachion Puzzle Quarter", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_inferred("Descriptive runtime node for Stachion's canon puzzle-heavy urban content; this is not a canon proper district name."),
        ),
        "floor_6_cylon_lord_manor": LocationDefinition(
            "floor_6_cylon_lord_manor", 6, "Cylon's Lord Manor", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_inferred("Stachion lord's manor where Cylon gives Curse of Stachion; exact building geometry is abstracted."),
        ),
        "floor_6_traveller_grave": LocationDefinition(
            "floor_6_traveller_grave", 6, "Traveller's Grave", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_inferred("Grave where Cylon asks the players to offer the missing golden cube. Exact city placement is abstracted."),
        ),
        "floor_6_cylon_transport_carriage": LocationDefinition(
            "floor_6_cylon_transport_carriage", 6, "Cylon's Carriage - Suribus to Stachion Road", ZoneKind.FIELD,
            provenance=_inferred("Scenario-space node for Cylon's carriage transport and the Morte/Joe ambush on the road between Suribus and Stachion."),
        ),
        "floor_6_myia_house": LocationDefinition(
            "floor_6_myia_house", 6, "Myia and Theano's House", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_inferred("Theano's home in Stachion where Myia receives her mother's note and iron key; exact street placement is abstracted.", PROGRESSIVE_6),
        ),
        "floor_6_dungeon_of_trials_entrance": LocationDefinition(
            "floor_6_dungeon_of_trials_entrance", 6, "Dungeon of Trials - Main Entrance", ZoneKind.DUNGEON,
            provenance=_inferred("Main basement entrance beneath the Stachion lord's mansion. The golden key opens the original-route entrance.", PROGRESSIVE_6),
        ),
        "floor_6_dungeon_of_trials": LocationDefinition(
            "floor_6_dungeon_of_trials", 6, "Dungeon of Trials", ZoneKind.DUNGEON,
            provenance=_canon("Puzzle-filled dungeon beneath the Stachion lord's mansion.", PROGRESSIVE_6),
        ),
        "floor_6_dungeon_of_trials_secret_back_door": LocationDefinition(
            "floor_6_dungeon_of_trials_secret_back_door", 6, "Dungeon of Trials - Secret Back Door", ZoneKind.DUNGEON,
            provenance=_inferred("Hidden rear entrance beneath a movable statue base in the manor garden. Terro reveals it in the release route.", PROGRESSIVE_6),
        ),
        "floor_6_dungeon_of_trials_final_chamber": LocationDefinition(
            "floor_6_dungeon_of_trials_final_chamber", 6, "Dungeon of Trials - Final Chamber", ZoneKind.DUNGEON,
            provenance=_canon("Deepest chamber of the Dungeon of Trials; the secret rear route reaches it directly.", PROGRESSIVE_6),
        ),
        "floor_6_agate_key_shrine": LocationDefinition(
            "floor_6_agate_key_shrine", 6, "Agate Key Shrine", ZoneKind.DUNGEON,
            provenance=_inferred("Southern shrine holding the Agate Key; the entrance has an unusually difficult puzzle. Exact room geometry is abstracted.", PROGRESSIVE_6),
        ),
        "floor_6_castle_galey_storyteller_summit": LocationDefinition(
            "floor_6_castle_galey_storyteller_summit", 6, "Bouhroum's Storyteller Summit", ZoneKind.FIELD,
            provenance=_inferred("Hidden stairway and summit above Castle Galey where Bouhroum offers the three-hour Meditation trial.", PROGRESSIVE_6),
        ),
        "floor_6_castle_galey_spirit_tree_spring": LocationDefinition(
            "floor_6_castle_galey_spirit_tree_spring", 6, "Castle Galey Spirit-Tree Spring", ZoneKind.DUNGEON,
            provenance=_canon("Underground hot spring nourishing Castle Galey's spirit tree. Gindo poisons it under coercion during the Fallen Elf attack.", PROGRESSIVE_6),
        ),
        "floor_6_qusack_rescue_cave": LocationDefinition(
            "floor_6_qusack_rescue_cave", 6, "Qusack Hostage Cave", ZoneKind.DUNGEON,
            provenance=_inferred("Cave where Qusack's members are held hostage and Kysarah attacks the rescue party; exact cave geometry is abstracted.", PROGRESSIVE_6),
        ),
        "floor_6_goskai": LocationDefinition(
            "floor_6_goskai", 6, "Cave City of Goskai", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon("Cave City in Floor 6's fourth area on the southern pursuit route.", PROGRESSIVE_6),
        ),
        "floor_6_goskai_caves": LocationDefinition(
            "floor_6_goskai_caves", 6, "Goskai Southern Caves", ZoneKind.FIELD,
            provenance=_inferred("Playable cave-field node around Goskai where Theano is sighted and Basalt Morpha is encountered; exact cave geometry is abstracted.", PROGRESSIVE_6),
        ),
        "floor_6_murutsuki": LocationDefinition(
            "floor_6_murutsuki", 6, "Murutsuki", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon("Central village in Floor 6's fifth area on the route to the Labyrinth.", PROGRESSIVE_6),
        ),
        "floor_6_labyrinth_golden_cube_breach": LocationDefinition(
            "floor_6_labyrinth_golden_cube_breach", 6, "Golden-Cube Labyrinth Breach", ZoneKind.DUNGEON,
            provenance=_inferred("Theano uses the Golden Cube to dismantle labyrinth walls into blocks, leaving an abnormal direct route toward the boss chamber.", PROGRESSIVE_6),
        ),
    }


def floor6_connections() -> tuple[TravelConnection, ...]:
    p5 = _sim("Travel durations are simulation; named endpoint relationships follow the Progressive Floor 6 route.", PROGRESSIVE_5)
    p6 = _sim("Travel durations are simulation; named endpoint relationships follow the Progressive Floor 6 route.", PROGRESSIVE_6)
    return (
        TravelConnection("floor_6_stachion", "floor_6_stachion_puzzle_quarter", 4 * 60_000, provenance=p5),
        TravelConnection("floor_6_stachion", "floor_6_field", 10 * 60_000, provenance=p5),
        TravelConnection("floor_6_field", "floor_6_suribus", 28 * 60_000, provenance=p5),
        TravelConnection("floor_6_suribus", "floor_6_pithagrus_suribus_house", 3 * 60_000, provenance=p5),
        TravelConnection("floor_6_field", "floor_6_ararro", 22 * 60_000, provenance=p5),
        TravelConnection("floor_6_field", "floor_6_castle_galey", 42 * 60_000, provenance=p6),
        TravelConnection("floor_6_castle_galey", "floor_6_lake_talpha", 24 * 60_000, provenance=p6),
        TravelConnection("floor_6_lake_talpha", "floor_6_labyrinth", 48 * 60_000, provenance=p6),
        TravelConnection("floor_6_stachion", "floor_6_cylon_lord_manor", 4 * 60_000, provenance=p5),
        TravelConnection("floor_6_stachion", "floor_6_traveller_grave", 5 * 60_000, provenance=p5),
        TravelConnection("floor_6_stachion_puzzle_quarter", "floor_6_cylon_lord_manor", 3 * 60_000, provenance=p5),
        TravelConnection("floor_6_stachion", "floor_6_myia_house", 5 * 60_000, provenance=p6),
        TravelConnection("floor_6_cylon_lord_manor", "floor_6_dungeon_of_trials_entrance", 2 * 60_000, provenance=p6),
        TravelConnection("floor_6_castle_galey", "floor_6_castle_galey_storyteller_summit", 14 * 60_000, provenance=p6),
        TravelConnection("floor_6_castle_galey", "floor_6_castle_galey_spirit_tree_spring", 6 * 60_000, provenance=p6),
        TravelConnection("floor_6_lake_talpha", "floor_6_agate_key_shrine", 20 * 60_000, provenance=p6),
        TravelConnection("floor_6_castle_galey", "floor_6_qusack_rescue_cave", 24 * 60_000, provenance=p6),
        TravelConnection("floor_6_field", "floor_6_lake_talpha", 38 * 60_000, provenance=p6),
        TravelConnection("floor_6_lake_talpha", "floor_6_goskai", 34 * 60_000, provenance=p6),
        TravelConnection("floor_6_goskai", "floor_6_goskai_caves", 8 * 60_000, provenance=p6),
        TravelConnection("floor_6_goskai", "floor_6_murutsuki", 42 * 60_000, provenance=p6),
        TravelConnection("floor_6_murutsuki", "floor_6_labyrinth", 30 * 60_000, provenance=p6),
    )
