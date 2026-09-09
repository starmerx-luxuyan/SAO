from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.corpus.world import LocationDefinition, WorldMapCatalog
from sao_mcp.domain.models import CombatantState, WorldState
from sao_mcp.rules.access import require_location_access


@dataclass(slots=True, frozen=True)
class TravelResolution:
    from_location_id: str
    to_location_id: str
    elapsed_ms: int
    newly_discovered: bool
    teleport: bool = False


def discover_location(world: WorldState, actor: CombatantState, location: LocationDefinition) -> bool:
    floor = world.floors[location.floor_number]
    before = location.location_id in floor.discovered_locations
    floor.discovered_locations.add(location.location_id)
    actor.location_id = location.location_id
    return not before


def travel(
    world: WorldState,
    actor: CombatantState,
    destination_id: str,
    catalog: WorldMapCatalog,
) -> TravelResolution:
    if actor.location_id is None:
        raise ValueError("actor has no current location")
    if destination_id not in catalog.locations:
        raise KeyError(destination_id)
    destination = catalog.locations[destination_id]
    if not world.floors[destination.floor_number].unlocked:
        raise ValueError("destination floor is not unlocked")
    require_location_access(actor, destination_id)

    candidates = [
        edge
        for edge in catalog.adjacency.get(actor.location_id, ())
        if edge.to_location_id == destination_id
    ]
    if not candidates:
        raise ValueError("destination is not directly connected to the current location")
    edge = min(candidates, key=lambda value: value.travel_ms)
    origin = actor.location_id
    world.now_ms += edge.travel_ms
    newly_discovered = discover_location(world, actor, destination)
    return TravelResolution(origin, destination_id, edge.travel_ms, newly_discovered)


def require_active_teleport_gate(
    world: WorldState,
    actor: CombatantState,
    destination_id: str,
    catalog: WorldMapCatalog,
) -> LocationDefinition:
    if actor.location_id is None:
        raise ValueError("actor has no current location")
    destination = catalog.locations[destination_id]
    if not destination.teleport_gate:
        raise ValueError("destination has no teleport gate")
    floor = world.floors[destination.floor_number]
    if not floor.unlocked or not floor.main_town_gate_active:
        raise ValueError("destination teleport gate is not active")
    require_location_access(actor, destination_id)
    return destination


def apply_teleport_to_gate(
    world: WorldState,
    actor: CombatantState,
    destination: LocationDefinition,
) -> TravelResolution:
    if actor.location_id is None:
        raise RuntimeError("teleport commit requires an actor with a prevalidated current location")
    origin = actor.location_id
    newly_discovered = discover_location(world, actor, destination)
    return TravelResolution(origin, destination.location_id, 0, newly_discovered, teleport=True)


def teleport_to_active_gate(
    world: WorldState,
    actor: CombatantState,
    destination_id: str,
    catalog: WorldMapCatalog,
) -> TravelResolution:
    destination = require_active_teleport_gate(world, actor, destination_id, catalog)
    return apply_teleport_to_gate(world, actor, destination)
