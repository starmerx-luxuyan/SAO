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


def register_floor6_elfwar_tools(mcp, elfwar) -> None:
    @mcp.tool()
    def start_floor6_castle_galey_route(actor_id: str) -> str:
        """Start the Floor 6 Dark-Elf route on arrival at Castle Galey and reunite with Kizmel."""
        return _json(elfwar.start_castle_galey_route(actor_id))

    @mcp.tool()
    def retrieve_floor6_agate_key(actor_id: str) -> str:
        """Recover the Agate Key from its southern shrine after reaching the key site beyond Lake Talpha."""
        return _json(elfwar.retrieve_agate_key(actor_id))

    @mcp.tool()
    def return_floor6_agate_key(actor_id: str) -> str:
        """Return the real Agate Key instance to Castle Galey and advance the Elf War chapter."""
        return _json(elfwar.return_agate_key(actor_id))

    @mcp.tool()
    def complete_floor6_bouhroum_trial(actor_id: str) -> str:
        """Complete Bouhroum's three-hour concentration trial, granting Meditation 500 and the Awakening mod."""
        return _json(elfwar.complete_bouhroum_trial(actor_id))

    @mcp.tool()
    def purify_floor6_castle_galey_spring(actor_id: str) -> str:
        """Purify the poisoned spirit-tree spring and reveal why Qusack leader Gindo sabotaged it."""
        return _json(elfwar.purify_spirit_tree_spring(actor_id))

    @mcp.tool()
    def borrow_floor6_sacred_key_bag(actor_id: str) -> str:
        """Borrow the real bag containing the four Elf War sacred keys for the Qusack hostage rescue."""
        return _json(elfwar.borrow_sacred_key_bag(actor_id))

    @mcp.tool()
    def start_floor6_qusack_rescue(actor_id: str) -> str:
        """Reach the Qusack hostage cave with Gindo and Kizmel after the Castle Galey attack."""
        return _json(elfwar.start_qusack_rescue(actor_id))

    @mcp.tool()
    def get_floor6_elfwar_state(actor_id: str) -> str:
        """Inspect Agate Key, Meditation/Awakening, Castle Galey, Qusack and Kysarah key-theft state."""
        return _json(elfwar.status(actor_id))
