from __future__ import annotations

import json
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


def register_floor6_buxum_tools(mcp, buxum, cube) -> None:
    @mcp.tool()
    def break_floor6_bind_with_awakening(cube_instance_id: str, actor_id: str) -> str:
        """Use Meditation 500 + Awakening to break this actor free from Buxum's Golden Cube Bind and return control to ordinary PvP."""
        return _json(buxum.break_bind_with_awakening(cube_instance_id, actor_id))

    @mcp.tool()
    def recover_floor6_golden_cube_after_buxum(cube_instance_id: str, actor_id: str) -> str:
        """Recover the exact Golden Cube instance Buxum dropped in the boss chamber."""
        return _json(buxum.recover_golden_cube(cube_instance_id, actor_id))

    @mcp.tool()
    def recover_floor6_surviving_combined_key(cube_instance_id: str, actor_id: str) -> str:
        """After The Irrational Cube and Golden Cube are destroyed, recover the same combined steel-key instance that survived in the reverse keyhole."""
        return _json(cube.recover_surviving_combined_key(cube_instance_id, actor_id))

    @mcp.tool()
    def get_floor6_buxum_state(cube_instance_id: str) -> str:
        """Inspect Buxum's betrayal, Bind, Awakening counterattack, Golden Cube drop and finale state."""
        return _json(buxum.status(cube_instance_id))
