from __future__ import annotations

import json
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


def register_floor4_tools(mcp, shipwright) -> None:
    @mcp.tool()
    def start_floor4_shipwright_quest(actor_id: str) -> str:
        """Begin Romolo's Shipwright of Yore quest in Rovia."""
        return _json(shipwright.start_quest(actor_id))

    @mcp.tool()
    def harvest_floor4_noblewood_core(actor_id: str, encounter_id: str) -> str:
        """Use a living Magnatherium's charge in the Bear Forest to fell an aged teak and obtain Noblewood Core."""
        return _json(asdict(shipwright.harvest_noblewood_core(actor_id, encounter_id)))

    @mcp.tool()
    def build_floor4_gondola(
        actor_id: str,
        name: str = "Gondola",
        passenger_seats: int = 2,
        install_ram: bool = True,
    ) -> str:
        """Give Romolo the best available materials, finalise a gondola design and advance the canonical three-hour build."""
        return _json(
            shipwright.build_gondola(
                actor_id,
                name=name,
                passenger_seats=passenger_seats,
                install_ram=install_ram,
            )
        )

    @mcp.tool()
    def sail_floor4_gondola(actor_id: str, destination_id: str) -> str:
        """Navigate an owned player gondola along an implemented Floor 4 water route."""
        return _json(shipwright.sail(actor_id, destination_id))

    @mcp.tool()
    def get_floor4_shipwright_state(actor_id: str) -> str:
        """Inspect Shipwright of Yore material/build/follow-up state and the actor's personal gondola."""
        return _json(shipwright.status(actor_id))
