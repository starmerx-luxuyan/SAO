from __future__ import annotations

from sao_mcp.domain.models import CombatantState


def create_character_at(
    runtime,
    name: str,
    *,
    level: int,
    location_id: str,
    starter_weapon_id: str = "starter_one_hand_sword",
) -> CombatantState:
    """Create a new materialized player directly at one authoritative world location.

    This is an initialization/materialization authority, not a movement primitive. It may only be
    used while creating a brand-new actor; existing actors must travel or use an explicit transport.
    """

    if location_id not in runtime.world_map.locations:
        raise KeyError(location_id)
    location = runtime.world_map.locations[location_id]
    if not runtime.world.floors[location.floor_number].unlocked:
        raise ValueError("spawn location floor is not unlocked")
    actor = runtime.create_character(
        name,
        level=level,
        starter_weapon_id=starter_weapon_id,
    )
    actor.location_id = location_id
    actor.metadata["spawn_location_id"] = location_id
    actor.metadata["spawned_at_ms"] = runtime.world.now_ms
    return actor
