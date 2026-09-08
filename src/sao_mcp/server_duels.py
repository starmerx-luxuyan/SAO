from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.rules.duels import DuelMode


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_duel_tools(mcp, runtime) -> None:
    @mcp.tool()
    def challenge_duel(challenger_id: str, target_id: str, mode: str = "first_strike") -> str:
        """Issue an authorized Aincrad duel request: first_strike, half_loss, or total_loss."""
        return _json(asdict(runtime.challenge_duel(challenger_id, target_id, DuelMode(mode))))

    @mcp.tool()
    def accept_duel(duel_id: str, target_id: str) -> str:
        """Accept a pending duel and create its authoritative PvP encounter."""
        duel, encounter = runtime.accept_duel(duel_id, target_id)
        return _json(
            {
                "duel": asdict(duel),
                "encounterId": encounter.encounter_id,
                "zoneId": encounter.zone_id,
                "safeZone": encounter.safe_zone,
                "positions": encounter.positions,
            }
        )

    @mcp.tool()
    def decline_duel(duel_id: str, target_id: str) -> str:
        """Decline a pending duel request."""
        return _json(asdict(runtime.decline_duel(duel_id, target_id)))

    @mcp.tool()
    def resign_duel(duel_id: str, actor_id: str) -> str:
        """Resign an active duel, awarding the opponent the duel victory without inventing damage."""
        return _json(asdict(runtime.resign_duel(duel_id, actor_id)))

    @mcp.tool()
    def end_duel_as_draw(duel_id: str) -> str:
        """End an active duel without a winner, clearing its PvP authorization."""
        return _json(asdict(runtime.draw_duel(duel_id)))

    @mcp.tool()
    def get_duel_state(duel_id: str | None = None, actor_id: str | None = None) -> str:
        """Inspect one duel or the open/completed duel records involving a player."""
        if duel_id is not None:
            return _json(asdict(runtime.duels.duels[duel_id]))
        if actor_id is None:
            raise ValueError("provide duel_id or actor_id")
        rows = [
            asdict(duel)
            for duel in runtime.duels.duels.values()
            if actor_id in (duel.challenger_id, duel.target_id)
        ]
        return _json({"actorId": actor_id, "duels": rows})

    @mcp.tool()
    def revive_recently_fallen(
        encounter_id: str,
        reviver_id: str,
        target_id: str,
        item_instance_id: str,
    ) -> str:
        """Use the Divine Stone of Returning Soul during the brief post-death End Phase."""
        return _json(
            runtime.revive_recently_fallen(
                encounter_id,
                reviver_id,
                target_id,
                item_instance_id,
            )
        )
