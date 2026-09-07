from __future__ import annotations

import json
import math
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.rules.spatial import actor_collision_radius_m


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_spatial_tools(mcp, runtime) -> None:
    @mcp.tool()
    def get_encounter_positions(encounter_id: str) -> str:
        """Return authoritative 2-D positions, collision bodies, arena bounds and movement speeds."""
        return _json(runtime.spatial_state(encounter_id))

    @mcp.tool()
    def measure_encounter_distance(encounter_id: str, actor_id: str, target_id: str) -> str:
        """Measure both center distance and collision-adjusted effective combat distance."""
        return _json(
            {
                "encounterId": encounter_id,
                "actorId": actor_id,
                "targetId": target_id,
                "centerDistanceM": round(runtime.encounter_center_distance(encounter_id, actor_id, target_id), 4),
                "combatDistanceM": round(runtime.encounter_distance(encounter_id, actor_id, target_id), 4),
            }
        )

    @mcp.tool()
    def move_in_encounter(encounter_id: str, actor_id: str, x: float, y: float) -> str:
        """Move to an authoritative arena coordinate, consuming time and respecting body collision/blocking."""
        return _json(asdict(runtime.move_encounter_actor(encounter_id, actor_id, x, y)))

    @mcp.tool()
    def move_toward_encounter_target(
        encounter_id: str,
        actor_id: str,
        target_id: str,
        stop_distance_m: float = 1.25,
        max_move_m: float | None = None,
    ) -> str:
        """Move toward a target until a requested effective surface distance remains."""
        if stop_distance_m < 0:
            raise ValueError("stop_distance_m must be >= 0")
        if max_move_m is not None and max_move_m < 0:
            raise ValueError("max_move_m must be >= 0")
        encounter = runtime.encounters[encounter_id]
        origin = encounter.positions[actor_id]
        target = encounter.positions[target_id]
        current_combat_distance = runtime.encounter_distance(encounter_id, actor_id, target_id)
        if current_combat_distance <= stop_distance_m:
            return _json(
                {
                    "actorId": actor_id,
                    "targetId": target_id,
                    "moved": False,
                    "combatDistanceM": round(current_combat_distance, 4),
                    "reason": "already within requested stop distance",
                }
            )
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        center_distance = math.hypot(dx, dy)
        if center_distance == 0:
            raise ValueError("actors occupy the same center coordinate")
        moving_actor = encounter.participants[actor_id]
        target_actor = encounter.participants[target_id]
        desired_center_distance = (
            stop_distance_m
            + actor_collision_radius_m(moving_actor)
            + actor_collision_radius_m(target_actor)
        )
        desired_move = max(0.0, center_distance - desired_center_distance)
        if max_move_m is not None:
            desired_move = min(desired_move, max_move_m)
        scale = desired_move / center_distance
        destination = (origin[0] + dx * scale, origin[1] + dy * scale)
        resolution = runtime.move_encounter_actor(
            encounter_id,
            actor_id,
            destination[0],
            destination[1],
        )
        return _json(
            {
                "actorId": actor_id,
                "targetId": target_id,
                "moved": resolution.completed,
                "movement": asdict(resolution),
                "combatDistanceAfterM": round(runtime.encounter_distance(encounter_id, actor_id, target_id), 4),
            }
        )
