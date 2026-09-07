from __future__ import annotations

import json
import math
from dataclasses import asdict
from enum import Enum
from typing import Any



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
        """Return authoritative 2-D positions, arena bounds and movement speeds for an encounter."""
        return _json(runtime.spatial_state(encounter_id))

    @mcp.tool()
    def measure_encounter_distance(encounter_id: str, actor_id: str, target_id: str) -> str:
        """Measure authoritative Euclidean distance between two encounter actors."""
        return _json(
            {
                "encounterId": encounter_id,
                "actorId": actor_id,
                "targetId": target_id,
                "distanceM": round(runtime.encounter_distance(encounter_id, actor_id, target_id), 4),
            }
        )

    @mcp.tool()
    def move_in_encounter(encounter_id: str, actor_id: str, x: float, y: float) -> str:
        """Move to an authoritative arena coordinate, consuming encounter time based on AGI and status effects."""
        return _json(asdict(runtime.move_encounter_actor(encounter_id, actor_id, x, y)))

    @mcp.tool()
    def move_toward_encounter_target(
        encounter_id: str,
        actor_id: str,
        target_id: str,
        stop_distance_m: float = 1.25,
        max_move_m: float | None = None,
    ) -> str:
        """Move toward a target without trusting model-supplied combat distance; useful for melee closing and boss approach."""
        if stop_distance_m < 0:
            raise ValueError("stop_distance_m must be >= 0")
        if max_move_m is not None and max_move_m < 0:
            raise ValueError("max_move_m must be >= 0")
        encounter = runtime.encounters[encounter_id]
        origin = encounter.positions[actor_id]
        target = encounter.positions[target_id]
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        distance = math.hypot(dx, dy)
        if distance <= stop_distance_m or distance == 0:
            return _json(
                {
                    "actorId": actor_id,
                    "targetId": target_id,
                    "moved": False,
                    "distanceM": round(distance, 4),
                    "reason": "already within requested stop distance",
                }
            )
        desired_move = distance - stop_distance_m
        if max_move_m is not None:
            desired_move = min(desired_move, max_move_m)
        scale = desired_move / distance
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
                "distanceAfterM": round(runtime.encounter_distance(encounter_id, actor_id, target_id), 4),
            }
        )
