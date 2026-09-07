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


def build_world_map_catalog() -> WorldMapCatalog:
    locations: dict[str, LocationDefinition] = {}
    connections: list[TravelConnection] = []

    # Floor 1 contains a few named/functional anchors; unnamed geometry remains simulation scaffolding.
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
            sources=("Sword Art Online Aincrad Floor 1 setting",),
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
            sources=("Sword Art Online Aincrad Floor 1 setting",),
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

    # Every floor gets functional nodes so the runtime can progress to Floor 100 even where canon
    # never supplies a settlement or detailed map. These IDs/names are explicitly simulation scaffolding.
    for floor in range(2, 101):
        town_id = f"floor_{floor}_main_town"
        field_id = f"floor_{floor}_field"
        labyrinth_id = f"floor_{floor}_labyrinth"
        boss_id = f"floor_{floor}_boss_room"
        locations[town_id] = LocationDefinition(
            town_id, floor, f"Floor {floor} Main Settlement", ZoneKind.SAFE_TOWN, True, False, True
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

    return WorldMapCatalog(locations, tuple(connections))
