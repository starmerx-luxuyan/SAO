from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.floor4 import YOFILIS_ID
from sao_mcp.corpus.loot import CORE_LOOT_TABLES
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, MonsterDefinition
from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import (
    DamageType,
    ItemKind,
    ItemTemplate,
    Provenance,
    ProvenanceKind,
    WeaponClass,
    WeaponTemplate,
    ZoneKind,
)
from sao_mcp.rules.loot import LootEntry, LootTable
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition


PROGRESSIVE_9 = "Sword Art Online Progressive Volume 9: Nocturne of the Blue Reflected Moon (Start)"
CETRANN_ID = "npc_floor4_cetrann"
KELPIE_ID = "morvarch_the_lake_kelpie"
KELPIE_WEAPON_ID = "morvarch_kelpie_natural_attack"
ICHTHYOID_CULTIVATOR_ID = "ichthyoid_cultivator"
ICHTHYOID_TUBER_ID = "ichthyoid_tuber"

LAKE_YOFEL = "floor_4_lake_yofel"
RIVER_ULL = "floor_4_river_ull"
YOFEL_CASTLE = "floor_4_yofel_castle"
CALDERA_LAKE = "floor_4_caldera_lake"
BEAR_FOREST = "floor_4_bear_forest"
FALLEN_HIDEOUT = "floor_4_fallen_elf_hideout"
LAKE_YOFEL_WEST_SHORE = "floor_4_lake_yofel_west_shore"
LAKE_YOFEL_NORTH_BEACH = "floor_4_lake_yofel_north_beach"
LAKE_YOFEL_FOG_BOUNDARY = "floor_4_lake_yofel_fog_boundary"
KYSARAH_TRANSFER_ROOM = "floor_4_labyrinth_hidden_transfer_room"

KELPIE_LEVEL = 27  # Simulation calibration: canon describes it as slightly below Kirito's overall ability.
ICHTHYOID_LEVEL = 25  # Simulation calibration; identity/habitat/drop are canon-backed.


def _canon(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(PROGRESSIVE_9,), notes=notes)


def _inferred(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(PROGRESSIVE_9,), notes=notes)


def _sim(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, sources=(PROGRESSIVE_9,), notes=notes)


def apply_floor4_nocturne_corpus(catalog: Catalog) -> Catalog:
    if YOFILIS_ID not in CORE_NPCS:
        raise RuntimeError("Floor 4 Shipwright corpus must seed the authoritative Yofilis NPC before Nocturne")
    yofilis = CORE_NPCS[YOFILIS_ID]
    CORE_NPCS[YOFILIS_ID] = NPCDefinition(
        npc_id=YOFILIS_ID,
        name=yofilis.name,
        home_location_id=YOFEL_CASTLE,
        roles=tuple(dict.fromkeys(yofilis.roles + ("elf_war_historical_witness", "nocturne_request_subject"))),
        quest_ids=yofilis.quest_ids,
        knowledge_tags=tuple(
            dict.fromkeys(
                yofilis.knowledge_tags
                + (
                    "lake_yofel",
                    "lavik",
                    "sandalwood_knights",
                    "ancient_elven_dispute",
                    "almarc",
                    "water_spirit",
                    "elven_aging",
                )
            )
        ),
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=tuple(dict.fromkeys(yofilis.provenance.sources + (PROGRESSIVE_9,))),
            notes=(
                "This is the same Leyshren Zed Yofilis already used by the Floor 4 Shipwright/Elf War corpus. "
                "Progressive 9 returns to Yofel Castle, explores his past and ties him to Lavik's request; "
                "Nocturne extends the existing NPC instead of creating a second Yofilis identity."
            ),
        ),
    )
    CORE_NPCS.setdefault(
        CETRANN_ID,
        NPCDefinition(
            npc_id=CETRANN_ID,
            name="Cetrann",
            home_location_id=YOFEL_CASTLE,
            roles=("dark_elf", "yofilis_heir", "yofel_castle_household"),
            quest_ids=(),
            knowledge_tags=("yofel_castle", "viscount_yofilis", "lake_yofel", "elf_war"),
            provenance=_canon(
                "Progressive 9 identifies Cetrann as Viscount Yofilis's heir. The runtime does not invent a longer name or unverified combat role."
            ),
        ),
    )

    catalog.items.setdefault(
        ICHTHYOID_TUBER_ID,
        ItemTemplate(
            template_id=ICHTHYOID_TUBER_ID,
            name="Ichthyoid Tuber",
            kind=ItemKind.FOOD,
            weight=0.35,
            stack_limit=20,
            tags=("floor_4", "labyrinth", "ichthyoid_cultivator_drop", "kysarah_request"),
            provenance=_inferred(
                "Ichthyoid Cultivators in the Floor 4 Labyrinth drop a sweet-potato-like tuber. The compact English runtime name, weight and stack limit are simulation-facing choices."
            ),
        ),
    )
    CORE_LOOT_TABLES.setdefault(
        "floor4_ichthyoid_cultivator",
        LootTable(
            table_id="floor4_ichthyoid_cultivator",
            col_min=55,
            col_max=90,
            xp_min=220,
            xp_max=330,
            entries=(LootEntry(ICHTHYOID_TUBER_ID, 1.0),),
            provenance="canon_tuber_drop_plus_simulation_col_xp",
        ),
    )

    catalog.weapons.setdefault(
        KELPIE_WEAPON_ID,
        WeaponTemplate(
            template_id=KELPIE_WEAPON_ID,
            name="Morvarc'h Hooves and Bite",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER,
            damage_type=DamageType.BLUNT,
            attack_min=118,
            attack_max=154,
            required_level=1,
            required_strength=1,
            weight=0.0,
            base_durability=12_000,
            base_speed_ms=720,
            reach_m=1.8,
            tags=("floor_4", "kelpie", "natural_attack", "water_field_boss"),
            provenance=_sim(
                "Morvarc'h is canonically a Floor 4 Lake Yofel field boss. Natural-attack damage, timing and reach are simulation calibration."
            ),
        ),
    )
    AINCRAD_MONSTERS.setdefault(
        KELPIE_ID,
        MonsterDefinition(
            monster_id=KELPIE_ID,
            name="Morvarc'h the Lake Kelpie",
            floor_number=4,
            level=KELPIE_LEVEL,
            location_id=LAKE_YOFEL_FOG_BOUNDARY,
            hp_factor=4.2,
            quest_kill_id=KELPIE_ID,
            loot_table_id="",
            tags=("field_boss", "kelpie", "water_walking", "night_tameable", "blue_horse"),
            provenance=_inferred(
                "Morvarc'h the Lake Kelpie is the blue horse-like field boss inhabiting Lake Yofel. "
                "Its exact runtime level and HP factor are simulation; the Night-tameable flag exposes the Progressive 9 interaction through generic Night rules."
            ),
        ),
    )
    AINCRAD_MONSTERS.setdefault(
        ICHTHYOID_CULTIVATOR_ID,
        MonsterDefinition(
            monster_id=ICHTHYOID_CULTIVATOR_ID,
            name="Ichthyoid Cultivator",
            floor_number=4,
            level=ICHTHYOID_LEVEL,
            location_id="floor_4_labyrinth",
            hp_factor=1.15,
            quest_kill_id=ICHTHYOID_CULTIVATOR_ID,
            loot_table_id="floor4_ichthyoid_cultivator",
            tags=("ichthyoid", "cultivator", "tuber_drop", "flee_at_half_hp"),
            provenance=_inferred(
                "The Ichthyoid Cultivator inhabits the Floor 4 Labyrinth, carries/cultivates the tuber requested in the Kysarah chapter, and attempts to flee when badly hurt. Exact level and HP are simulation calibration."
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
            provenance=_canon("Lake surrounding Yofel Castle and revisited during Nocturne of the Blue Reflected Moon."),
        ),
        RIVER_ULL: LocationDefinition(
            RIVER_ULL,
            4,
            "River Ull",
            ZoneKind.FIELD,
            provenance=_canon("River connected to Lake Yofel on the north-west side of the lake."),
        ),
        LAKE_YOFEL_WEST_SHORE: LocationDefinition(
            LAKE_YOFEL_WEST_SHORE,
            4,
            "Lake Yofel - West Shore",
            ZoneKind.FIELD,
            provenance=_inferred(
                "Descriptive Nocturne node for the shore where Lavik remains outside Yofel Castle and asks the party to bring Yofilis without attendants."
            ),
        ),
        LAKE_YOFEL_NORTH_BEACH: LocationDefinition(
            LAKE_YOFEL_NORTH_BEACH,
            4,
            "Lake Yofel - Secluded North Beach",
            ZoneKind.FIELD,
            provenance=_inferred(
                "Descriptive node for the secluded Lake Yofel rendezvous used to move Yofilis away from the castle household."
            ),
        ),
        LAKE_YOFEL_FOG_BOUNDARY: LocationDefinition(
            LAKE_YOFEL_FOG_BOUNDARY,
            4,
            "Lake Yofel - Fog Boundary",
            ZoneKind.FIELD,
            provenance=_inferred(
                "The approach to Yofel Castle passes through deep fog and an instanced boundary. Nocturne uses that fog together with stowed metal equipment for the Kelpie encounter."
            ),
        ),
        KYSARAH_TRANSFER_ROOM: LocationDefinition(
            KYSARAH_TRANSFER_ROOM,
            4,
            "Floor 4 Labyrinth - Hidden Transfer Room",
            ZoneKind.LABYRINTH,
            provenance=_inferred(
                "Descriptive hidden room branching from the Floor 4 Labyrinth route used for the later Progressive 9 Fallen Elf transfer/interception sequence; the source does not provide a proper room name."
            ),
        ),
    }


def floor4_nocturne_connections() -> tuple[TravelConnection, ...]:
    whole_route = _inferred(
        "Progressive 9 revisits the old Floor 4 waterways connecting the Yofel area with the submerged Fallen Elf hideout. "
        "Segment durations are simulation calibration; the Lake Yofel-to-hideout split preserves the previously established one-hour runtime route."
    )
    local = _sim("Lake Yofel local shore and fog-boundary travel times are runtime calibration.")
    return (
        TravelConnection(YOFEL_CASTLE, LAKE_YOFEL, 4 * 60_000, provenance=local),
        TravelConnection("floor_4_usco", LAKE_YOFEL_WEST_SHORE, 20 * 60_000, provenance=local),
        TravelConnection(LAKE_YOFEL_WEST_SHORE, LAKE_YOFEL, 8 * 60_000, provenance=local),
        TravelConnection(LAKE_YOFEL, LAKE_YOFEL_NORTH_BEACH, 8 * 60_000, provenance=local),
        TravelConnection(LAKE_YOFEL, LAKE_YOFEL_FOG_BOUNDARY, 10 * 60_000, provenance=local),
        TravelConnection(LAKE_YOFEL, RIVER_ULL, 10 * 60_000, provenance=whole_route),
        TravelConnection(RIVER_ULL, CALDERA_LAKE, 10 * 60_000, provenance=whole_route),
        TravelConnection(CALDERA_LAKE, BEAR_FOREST, 18 * 60_000, provenance=whole_route),
        TravelConnection("floor_4_labyrinth", KYSARAH_TRANSFER_ROOM, 2 * 60_000, provenance=local),
    )