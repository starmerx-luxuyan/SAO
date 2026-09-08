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


def register_floor7_tools(mcp, volupta) -> None:
    @mcp.tool()
    def get_floor7_volcoin_wallet(actor_id: str) -> str:
        """Inspect Cor/Volcoin balance and the exact Volupta exchange rate."""
        return _json(volupta.wallet(actor_id))

    @mcp.tool()
    def buy_floor7_volcoins(actor_id: str, amount: int) -> str:
        """Buy Volupta Grand Casino chips at the canon rate of 1 Volcoin = 100 Cor."""
        return _json(volupta.buy_volcoins(actor_id, amount))

    @mcp.tool()
    def open_floor7_monster_arena_match(match_definition_id: str) -> str:
        """Open one implemented Volupta Monster Arena matchup; live outcome/odds are simulation rather than forced history."""
        return _json(volupta.open_arena_match(match_definition_id))

    @mcp.tool()
    def place_floor7_monster_arena_bet(
        actor_id: str,
        match_instance_id: str,
        contender_id: str,
        wager_volcoin: int,
    ) -> str:
        """Place one Volcoin wager on a contender in an open Monster Arena match."""
        return _json(volupta.place_arena_bet(actor_id, match_instance_id, contender_id, wager_volcoin))

    @mcp.tool()
    def resolve_floor7_monster_arena_match(match_instance_id: str, seed: int | None = None) -> str:
        """Resolve a live Monster Arena match with simulation odds and pay winning Volcoin bets."""
        return _json(volupta.resolve_arena_match(match_instance_id, seed=seed))

    @mcp.tool()
    def get_floor7_monster_arena_match(match_instance_id: str) -> str:
        """Inspect contenders, wagers, live odds and resolved outcome for a Monster Arena match."""
        return _json(volupta.match_state(match_instance_id))

    @mcp.tool()
    def redeem_floor7_sword_of_volupta(actor_id: str) -> str:
        """Spend 100,000 Volcoins to redeem the unique Sword of Volupta prize as a real weapon instance."""
        return _json(volupta.redeem_sword_of_volupta(actor_id))
