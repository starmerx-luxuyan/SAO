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


def register_floor6_tools(mcp, cube, stachion) -> None:
    @mcp.tool()
    def start_floor6_stachion_curse(actor_id: str) -> str:
        """Accept Cylon's Curse of Stachion quest at the Stachion lord's manor."""
        return _json(stachion.start_quest(actor_id))

    @mcp.tool()
    def interview_floor6_stachion_witness(actor_id: str, witness_id: str) -> str:
        """Interview one of Pithagrus's seven former associates in Stachion."""
        return _json(stachion.interview_witness(actor_id, witness_id))

    @mcp.tool()
    def search_floor6_pithagrus_suribus_house(actor_id: str) -> str:
        """Search Pithagrus's second home in Suribus and obtain the golden key after the Stachion investigation."""
        return _json(stachion.search_pithagrus_house(actor_id))

    @mcp.tool()
    def get_floor6_stachion_curse_state(actor_id: str) -> str:
        """Inspect Curse of Stachion witness/key progress. Obtaining the key does not complete the quest."""
        return _json(stachion.status(actor_id))

    @mcp.tool()
    def start_floor6_irrational_cube_puzzle(player_ids: list[str]) -> str:
        """Begin The Irrational Cube's invulnerable 3x3 number-face puzzle in the Floor 6 Boss Room."""
        return _json(cube.start_puzzle(player_ids))

    @mcp.tool()
    def rotate_floor6_cube_row(instance_id: str, row: int, direction: str) -> str:
        """Rotate one numbered row left/right during The Irrational Cube's invulnerability puzzle."""
        return _json(cube.rotate_row(instance_id, row, direction))

    @mcp.tool()
    def rotate_floor6_cube_column(instance_id: str, column: int, direction: str) -> str:
        """Rotate one numbered column up/down during The Irrational Cube's invulnerability puzzle."""
        return _json(cube.rotate_column(instance_id, column, direction))

    @mcp.tool()
    def engage_floor6_irrational_cube(instance_id: str) -> str:
        """After the number face matches the nine-digit door code, start the normal Floor 6 boss combat phase."""
        return _json(cube.engage_boss(instance_id))

    @mcp.tool()
    def get_floor6_irrational_cube_state(instance_id: str) -> str:
        """Inspect the current number face, target code, puzzle stage and combat state."""
        return _json(cube.status(instance_id))
