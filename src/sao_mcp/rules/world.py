from __future__ import annotations

from sao_mcp.domain.models import FloorState, WorldState


NEXT_FLOOR_AUTO_GATE_DELAY_MS = 2 * 60 * 60 * 1000


def make_aincrad_world() -> WorldState:
    floors = {
        n: FloorState(number=n, unlocked=(n == 1), main_town_gate_active=(n == 1))
        for n in range(1, 101)
    }
    return WorldState(now_ms=0, floors=floors)


def defeat_floor_boss(world: WorldState, floor_number: int) -> FloorState:
    if floor_number < 1 or floor_number > 100:
        raise ValueError("floor_number must be in 1..100")
    floor = world.floors[floor_number]
    if floor.floor_boss_defeated:
        return floor
    floor.floor_boss_defeated = True
    floor.floor_boss_defeated_at_ms = world.now_ms
    if floor_number < 100:
        floor.scheduled_gate_activation_at_ms = world.now_ms + NEXT_FLOOR_AUTO_GATE_DELAY_MS
    return floor


def activate_next_floor_early(world: WorldState, defeated_floor_number: int) -> FloorState:
    if defeated_floor_number >= 100:
        raise ValueError("there is no next floor")
    floor = world.floors[defeated_floor_number]
    if not floor.floor_boss_defeated:
        raise ValueError("floor boss has not been defeated")
    next_floor = world.floors[defeated_floor_number + 1]
    next_floor.unlocked = True
    next_floor.main_town_gate_active = True
    floor.scheduled_gate_activation_at_ms = None
    return next_floor


def advance_world_time(world: WorldState, elapsed_ms: int) -> list[int]:
    if elapsed_ms < 0:
        raise ValueError("elapsed_ms must be >= 0")
    world.now_ms += elapsed_ms
    activated: list[int] = []
    for number in range(1, 100):
        floor = world.floors[number]
        when = floor.scheduled_gate_activation_at_ms
        if when is not None and when <= world.now_ms:
            next_floor = world.floors[number + 1]
            next_floor.unlocked = True
            next_floor.main_town_gate_active = True
            floor.scheduled_gate_activation_at_ms = None
            activated.append(number + 1)
    return activated
