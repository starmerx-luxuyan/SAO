from __future__ import annotations

from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import Provenance, ProvenanceKind, ZoneKind


PROGRESSIVE_1 = "Sword Art Online Progressive Volume 1: Rondo of a Fragile Blade"
PROGRESSIVE_2 = "Sword Art Online Progressive Volume 2: Concerto of Black and White"
PROGRESSIVE_3 = "Sword Art Online Progressive Volume 3: Barcarolle of Froth"
PROGRESSIVE_4 = "Sword Art Online Progressive Volume 4: Scherzo of Deep Night"


def _canon(source: str, notes: str = "") -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(source,), notes=notes)


def _inferred(source: str, notes: str = "") -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(source,), notes=notes)


def _sim(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, notes=notes)


LOW_FLOOR_MAIN_SETTLEMENTS: dict[int, tuple[str, str, Provenance]] = {
    2: (
        "floor_2_urbus",
        "Urbus",
        _canon(PROGRESSIVE_1, "Main settlement of Aincrad Floor 2."),
    ),
    3: (
        "floor_3_zumfut",
        "Zumfut",
        _canon(PROGRESSIVE_2, "Main settlement of Aincrad Floor 3, built into three giant baobab trees."),
    ),
    4: (
        "floor_4_rovia",
        "Rovia",
        _canon(PROGRESSIVE_3, "Main settlement of Aincrad Floor 4, a white waterway city requiring gondolas for easy travel."),
    ),
    5: (
        "floor_5_karluin",
        "Karluin",
        _canon(PROGRESSIVE_4, "Main settlement of Aincrad Floor 5, built among ancient ruins."),
    ),
}


def low_floor_locations() -> dict[str, LocationDefinition]:
    rows = {
        "floor_2_marome": LocationDefinition(
            "floor_2_marome", 2, "Marome", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon(PROGRESSIVE_1, "Small village roughly three kilometres southeast of Urbus."),
        ),
        "floor_2_taran": LocationDefinition(
            "floor_2_taran", 2, "Taran", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon(PROGRESSIVE_1, "Settlement closest to the Floor 2 Labyrinth."),
        ),
        "floor_2_martial_arts_hut": LocationDefinition(
            "floor_2_martial_arts_hut", 2, "Martial Arts Master's Hut", ZoneKind.FIELD,
            provenance=_canon(PROGRESSIVE_1, "Mountain-top hut used by the Martial Arts Extra Skill quest."),
        ),
        "floor_2_bullbous_den": LocationDefinition(
            "floor_2_bullbous_den", 2, "Bullbous Bow Den", ZoneKind.FIELD,
            provenance=_inferred(PROGRESSIVE_1, "Field-Boss encounter site for Bullbous Bow."),
        ),
        "floor_3_forest_of_wavering_mists": LocationDefinition(
            "floor_3_forest_of_wavering_mists", 3, "Forest of Wavering Mists", ZoneKind.FIELD,
            provenance=_canon(PROGRESSIVE_2, "Dense fog-filled southern forest covering the Floor 3 starting region."),
        ),
        "floor_3_queen_spider_nest": LocationDefinition(
            "floor_3_queen_spider_nest", 3, "Queen Spider's Nest", ZoneKind.DUNGEON,
            provenance=_canon(PROGRESSIVE_2, "Public dungeon containing Nephila Regina and used by several quests."),
        ),
        "floor_3_dark_elf_base": LocationDefinition(
            "floor_3_dark_elf_base", 3, "Dark Elf Base", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon(PROGRESSIVE_2, "Instanced Dark Elf base for the Elf War campaign."),
        ),
        "floor_3_forest_elf_base": LocationDefinition(
            "floor_3_forest_elf_base", 3, "Forest Elf Base", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon(PROGRESSIVE_2, "Instanced Forest Elf base for the Elf War campaign."),
        ),
        "floor_3_dessel": LocationDefinition(
            "floor_3_dessel", 3, "Dessel", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon(PROGRESSIVE_2, "Settlement closest to the Floor 3 Labyrinth."),
        ),
        "floor_4_bear_forest": LocationDefinition(
            "floor_4_bear_forest", 4, "Bear Forest", ZoneKind.FIELD,
            provenance=_canon(PROGRESSIVE_3, "Wet forest southeast of Rovia used to gather high-quality gondola materials."),
        ),
        "floor_4_fallen_elf_hideout": LocationDefinition(
            "floor_4_fallen_elf_hideout", 4, "Fallen Elf Hideout", ZoneKind.DUNGEON,
            provenance=_canon(PROGRESSIVE_3, "Submerged hideout behind a waterfall, used by Shipwright of Yore and Elf War quests."),
        ),
        "floor_4_caldera_lake": LocationDefinition(
            "floor_4_caldera_lake", 4, "Caldera Lake", ZoneKind.FIELD,
            provenance=_canon(PROGRESSIVE_3, "Central lake blocked by the field boss Biceps Archelon until defeated."),
        ),
        "floor_4_usco": LocationDefinition(
            "floor_4_usco", 4, "Usco Village", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon(PROGRESSIVE_3, "Floating village southwest of Caldera Lake."),
        ),
        "floor_4_yofel_castle": LocationDefinition(
            "floor_4_yofel_castle", 4, "Yofel Castle", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon(PROGRESSIVE_3, "Instanced Dark Elf castle and major Elf War campaign location."),
        ),
        "floor_4_forest_elf_castle": LocationDefinition(
            "floor_4_forest_elf_castle", 4, "Forest Elf Castle", ZoneKind.DUNGEON,
            provenance=_canon(PROGRESSIVE_3, "Forest Elf stronghold in the southwestern region of Floor 4."),
        ),
        "floor_5_mananarena": LocationDefinition(
            "floor_5_mananarena", 5, "Mananarena", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon(PROGRESSIVE_4, "Central village built into ruins above an old mineshaft dungeon."),
        ),
        "floor_5_mananarena_mine": LocationDefinition(
            "floor_5_mananarena_mine", 5, "Mananarena Mine", ZoneKind.DUNGEON,
            provenance=_inferred(PROGRESSIVE_4, "Mineshaft dungeon beneath Mananarena."),
        ),
        "floor_5_shiyaya": LocationDefinition(
            "floor_5_shiyaya", 5, "Shiyaya", ZoneKind.SAFE_TOWN, safe_zone=True,
            provenance=_canon(PROGRESSIVE_4, "Dark Elf village on Floor 5."),
        ),
        "floor_5_ruins": LocationDefinition(
            "floor_5_ruins", 5, "Ancient Ruins", ZoneKind.FIELD,
            provenance=_canon(PROGRESSIVE_4, "The majority of Floor 5 is a maze-like ancient ruined city."),
        ),
    }
    return rows


def low_floor_connections() -> tuple[TravelConnection, ...]:
    p = _sim("Travel duration is simulation; named endpoint relationship follows Progressive floor geography.")
    return (
        TravelConnection("floor_2_urbus", "floor_2_marome", 10 * 60_000, provenance=p),
        TravelConnection("floor_2_urbus", "floor_2_field", 8 * 60_000, provenance=p),
        TravelConnection("floor_2_field", "floor_2_martial_arts_hut", 24 * 60_000, provenance=p),
        TravelConnection("floor_2_field", "floor_2_bullbous_den", 20 * 60_000, provenance=p),
        TravelConnection("floor_2_field", "floor_2_taran", 30 * 60_000, provenance=p),
        TravelConnection("floor_2_taran", "floor_2_labyrinth", 16 * 60_000, provenance=p),
        TravelConnection("floor_3_zumfut", "floor_3_forest_of_wavering_mists", 7 * 60_000, provenance=p),
        TravelConnection("floor_3_forest_of_wavering_mists", "floor_3_queen_spider_nest", 20 * 60_000, provenance=p),
        TravelConnection("floor_3_forest_of_wavering_mists", "floor_3_dark_elf_base", 16 * 60_000, provenance=p),
        TravelConnection("floor_3_forest_of_wavering_mists", "floor_3_forest_elf_base", 18 * 60_000, provenance=p),
        TravelConnection("floor_3_forest_of_wavering_mists", "floor_3_dessel", 34 * 60_000, provenance=p),
        TravelConnection("floor_3_dessel", "floor_3_labyrinth", 15 * 60_000, provenance=p),
        TravelConnection("floor_4_rovia", "floor_4_bear_forest", 18 * 60_000, provenance=p),
        TravelConnection("floor_4_rovia", "floor_4_caldera_lake", 28 * 60_000, provenance=p),
        TravelConnection("floor_4_bear_forest", "floor_4_fallen_elf_hideout", 22 * 60_000, provenance=p),
        TravelConnection("floor_4_caldera_lake", "floor_4_usco", 18 * 60_000, provenance=p),
        TravelConnection("floor_4_usco", "floor_4_yofel_castle", 22 * 60_000, provenance=p),
        TravelConnection("floor_4_usco", "floor_4_forest_elf_castle", 26 * 60_000, provenance=p),
        TravelConnection("floor_4_usco", "floor_4_labyrinth", 32 * 60_000, provenance=p),
        TravelConnection("floor_5_karluin", "floor_5_ruins", 6 * 60_000, provenance=p),
        TravelConnection("floor_5_ruins", "floor_5_mananarena", 22 * 60_000, provenance=p),
        TravelConnection("floor_5_mananarena", "floor_5_mananarena_mine", 2 * 60_000, provenance=p),
        TravelConnection("floor_5_ruins", "floor_5_shiyaya", 28 * 60_000, provenance=p),
        TravelConnection("floor_5_ruins", "floor_5_labyrinth", 38 * 60_000, provenance=p),
    )
