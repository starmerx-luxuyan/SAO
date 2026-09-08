from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import Provenance, ProvenanceKind, ZoneKind


@dataclass(slots=True, frozen=True)
class LocationDefinition:
    location_id: str
    floor_number: int
    name: str
    zone_kind: ZoneKind
    safe_zone: bool = False
    anti_crystal: bool = False
    teleport_gate: bool = False
    provenance: Provenance = Provenance(ProvenanceKind.SIMULATION)


@dataclass(slots=True, frozen=True)
class TravelConnection:
    from_location_id: str
    to_location_id: str
    travel_ms: int
    bidirectional: bool = True
    requires_floor_unlocked: bool = True
    provenance: Provenance = Provenance(ProvenanceKind.SIMULATION)


class WorldMapCatalog:
    def __init__(self, locations: dict[str, LocationDefinition], connections: tuple[TravelConnection, ...]):
        self.locations = locations
        self.connections = connections
        adjacency: dict[str, list[TravelConnection]] = {}
        for connection in connections:
            adjacency.setdefault(connection.from_location_id, []).append(connection)
            if connection.bidirectional:
                adjacency.setdefault(connection.to_location_id, []).append(
                    TravelConnection(
                        connection.to_location_id,
                        connection.from_location_id,
                        connection.travel_ms,
                        True,
                        connection.requires_floor_unlocked,
                        connection.provenance,
                    )
                )
        self.adjacency = adjacency


_CANON_MAIN_SETTLEMENTS: dict[int, tuple[str, str, Provenance]] = {
    22: (
        "floor_22_coral",
        "Coral",
        Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 1, Chapter 19",),
            notes="Main settlement of Floor 22; a small village near a large lake.",
        ),
    ),
    48: (
        "floor_48_lindarth",
        "Lindarth",
        Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 2: Warmth of the Heart, Part 1",),
            notes="Main settlement of Floor 48; canals, waterwheels and support-class shops.",
        ),
    ),
    50: (
        "floor_50_algade",
        "Algade",
        Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 1, Chapter 5",),
            notes="Major Floor 50 city and the location of Agil's player-run item shop.",
        ),
    ),
    55: (
        "floor_55_granzam",
        "Granzam",
        Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 1, Chapter 12",),
            notes="Main settlement of Floor 55, the Steel City and later Knights of the Blood headquarters.",
        ),
    ),
    61: (
        "floor_61_selmburg",
        "Selmburg",
        Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 1, Chapter 6",),
            notes="Main settlement of Floor 61, a castle city on an island in a lake.",
        ),
    ),
    75: (
        "floor_75_collinia",
        "Collinia",
        Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 1, Chapter 13",),
            notes="Main settlement of Floor 75, a busy city with an Ancient-Rome-like appearance.",
        ),
    ),
}


def build_world_map_catalog() -> WorldMapCatalog:
    # Imported here to keep the low-floor content module data-only while it reuses the world dataclasses.
    from sao_mcp.corpus.low_floors import (
        LOW_FLOOR_MAIN_SETTLEMENTS,
        low_floor_connections,
        low_floor_locations,
    )

    locations: dict[str, LocationDefinition] = {}
    connections: list[TravelConnection] = []

    # Floor 1 contains named/functional anchors; unnamed geometry remains simulation scaffolding.
    locations["floor_1_town_of_beginnings"] = LocationDefinition(
        "floor_1_town_of_beginnings",
        1,
        "Town of Beginnings",
        ZoneKind.SAFE_TOWN,
        safe_zone=True,
        teleport_gate=True,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Aincrad Floor 1 setting",),
        ),
    )
    locations["floor_1_west_field"] = LocationDefinition(
        "floor_1_west_field", 1, "West Field", ZoneKind.FIELD
    )
    locations["floor_1_horunka"] = LocationDefinition(
        "floor_1_horunka",
        1,
        "Horunka Village",
        ZoneKind.SAFE_TOWN,
        safe_zone=True,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 8: First Day",),
        ),
    )
    locations["floor_1_tolbana"] = LocationDefinition(
        "floor_1_tolbana",
        1,
        "Tolbana",
        ZoneKind.SAFE_TOWN,
        safe_zone=True,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Progressive Volume 1",),
        ),
    )
    locations["floor_1_labyrinth"] = LocationDefinition(
        "floor_1_labyrinth", 1, "Floor 1 Labyrinth", ZoneKind.LABYRINTH
    )
    locations["floor_1_boss_room"] = LocationDefinition(
        "floor_1_boss_room", 1, "Floor 1 Boss Room", ZoneKind.BOSS_ROOM
    )
    connections.extend(
        (
            TravelConnection("floor_1_town_of_beginnings", "floor_1_west_field", 12 * 60_000),
            TravelConnection("floor_1_west_field", "floor_1_horunka", 18 * 60_000),
            TravelConnection("floor_1_west_field", "floor_1_tolbana", 42 * 60_000),
            TravelConnection("floor_1_tolbana", "floor_1_labyrinth", 28 * 60_000),
            TravelConnection("floor_1_labyrinth", "floor_1_boss_room", 50 * 60_000),
        )
    )

    # Every floor retains functional field/labyrinth/boss nodes so the runtime can progress to Floor 100.
    # Named settlements replace placeholders as verified corpus becomes available.
    for floor in range(2, 101):
        settlement = LOW_FLOOR_MAIN_SETTLEMENTS.get(floor) or _CANON_MAIN_SETTLEMENTS.get(floor)
        if settlement:
            town_id, town_name, town_provenance = settlement
        else:
            town_id = f"floor_{floor}_main_town"
            town_name = f"Floor {floor} Main Settlement"
            town_provenance = Provenance(
                ProvenanceKind.SIMULATION,
                notes="Functional placeholder until a canon settlement identity is verified and seeded.",
            )
        field_id = f"floor_{floor}_field"
        labyrinth_id = f"floor_{floor}_labyrinth"
        boss_id = f"floor_{floor}_boss_room"
        locations[town_id] = LocationDefinition(
            town_id,
            floor,
            town_name,
            ZoneKind.SAFE_TOWN,
            True,
            False,
            True,
            town_provenance,
        )
        locations[field_id] = LocationDefinition(field_id, floor, f"Floor {floor} Field", ZoneKind.FIELD)
        locations[labyrinth_id] = LocationDefinition(
            labyrinth_id, floor, f"Floor {floor} Labyrinth", ZoneKind.LABYRINTH
        )
        locations[boss_id] = LocationDefinition(
            boss_id, floor, f"Floor {floor} Boss Room", ZoneKind.BOSS_ROOM
        )
        connections.extend(
            (
                TravelConnection(town_id, field_id, 18 * 60_000),
                TravelConnection(field_id, labyrinth_id, 45 * 60_000),
                TravelConnection(labyrinth_id, boss_id, 60 * 60_000),
            )
        )

    # Canonical Progressive landmarks on Floors 2-5 are additive to the generic field/labyrinth backbone.
    locations.update(low_floor_locations())
    connections.extend(low_floor_connections())

    # Canon player-run shops are real world nodes rather than lore-only labels. The short in-city
    # travel times below are simulation conveniences; shop identity and floor/city are canon.
    locations["floor_48_lisbeth_smith_shop"] = LocationDefinition(
        "floor_48_lisbeth_smith_shop",
        48,
        "Lisbeth's Smith Shop",
        ZoneKind.SAFE_TOWN,
        safe_zone=True,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 2: Warmth of the Heart",),
            notes="Player-run smith/armour shop in Lindarth on Floor 48.",
        ),
    )
    connections.append(
        TravelConnection(
            "floor_48_lindarth",
            "floor_48_lisbeth_smith_shop",
            2 * 60_000,
            provenance=Provenance(
                ProvenanceKind.SIMULATION,
                notes="In-city travel time is runtime calibration.",
            ),
        )
    )

    locations["floor_50_agil_shop"] = LocationDefinition(
        "floor_50_agil_shop",
        50,
        "Agil's Shop",
        ZoneKind.SAFE_TOWN,
        safe_zone=True,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 1, Chapter 5",),
            notes="Agil's player-run item shop in Algade on Floor 50.",
        ),
    )
    connections.append(
        TravelConnection(
            "floor_50_algade",
            "floor_50_agil_shop",
            2 * 60_000,
            provenance=Provenance(
                ProvenanceKind.SIMULATION,
                notes="In-city travel time is runtime calibration.",
            ),
        )
    )

    locations["floor_55_west_mountain"] = LocationDefinition(
        "floor_55_west_mountain",
        55,
        "West Mountain",
        ZoneKind.DUNGEON,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 2: Warmth of the Heart, Part 2",),
            notes="Snowy western field dungeon associated with the high-grade metal quest.",
        ),
    )
    connections.append(
        TravelConnection(
            "floor_55_field",
            "floor_55_west_mountain",
            35 * 60_000,
            provenance=Provenance(
                ProvenanceKind.SIMULATION,
                notes="Exact travel duration is runtime calibration.",
            ),
        )
    )

    return WorldMapCatalog(locations, tuple(connections))
