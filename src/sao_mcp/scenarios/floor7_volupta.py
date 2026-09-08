from __future__ import annotations

import random
import uuid

from sao_mcp.corpus.floor7 import (
    SWORD_OF_VOLUPTA_ID,
    SWORD_OF_VOLUPTA_PRICE_VOLCOIN,
    VOLCOIN_COR_VALUE,
)
from sao_mcp.corpus.floor7_monsters import apply_floor7_monster_corpus
from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.inventory import add_item


CASINO = "floor_7_volupta_grand_casino"
MONSTER_ARENA = "floor_7_monster_arena"

# The combatants and historical winners are canon. Odds/probabilities are simulation so a live campaign
# is not forced to reproduce Kirito and Asuna's historical betting result.
ARENA_MATCHES: dict[str, dict] = {
    "rusty_lykaon_vs_bouncy_slater": {
        "name": "Rusty Lykaon vs Bouncy Slater",
        "contenders": ("rusty_lykaon", "bouncy_slater"),
        "win_weights": {"rusty_lykaon": 0.54, "bouncy_slater": 0.46},
        "payout_multipliers": {"rusty_lykaon": 1.76, "bouncy_slater": 2.07},
        "canon_historical_winner": "rusty_lykaon",
        "provenance": "canon_contenders_and_historical_winner; simulation live odds/outcome",
    },
    "tiny_glyptodont_vs_verdian_bighorn": {
        "name": "Tiny Glyptodont vs Verdian Bighorn",
        "contenders": ("tiny_glyptodont", "verdian_bighorn"),
        "win_weights": {"tiny_glyptodont": 0.43, "verdian_bighorn": 0.57},
        "payout_multipliers": {"tiny_glyptodont": 2.21, "verdian_bighorn": 1.67},
        "canon_historical_winner": "verdian_bighorn",
        "provenance": "canon_contenders_and_historical_winner; simulation live odds/outcome",
    },
}


class Floor7VoluptaScenario:
    """Volupta Grand Casino currency, Monster Arena wagering and Sword of Volupta redemption."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        apply_floor7_monster_corpus(runtime.catalog)

    def _matches(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor7_monster_arena_matches", {})

    @staticmethod
    def _balance(actor) -> int:
        return int(actor.metadata.get("floor7_volcoin_balance", 0))

    @staticmethod
    def _set_balance(actor, amount: int) -> None:
        actor.metadata["floor7_volcoin_balance"] = max(0, int(amount))

    def wallet(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        return {
            "actor_id": actor_id,
            "cor": actor.col,
            "volcoin": self._balance(actor),
            "exchange_rate": {"volcoin": 1, "cor": VOLCOIN_COR_VALUE},
            "sword_price_volcoin": SWORD_OF_VOLUPTA_PRICE_VOLCOIN,
        }

    def buy_volcoins(self, actor_id: str, amount: int) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != CASINO:
            raise ValueError("Volcoins are purchased at the Volupta Grand Casino")
        amount = int(amount)
        if amount <= 0:
            raise ValueError("Volcoin purchase amount must be positive")
        cost = amount * VOLCOIN_COR_VALUE
        if actor.col < cost:
            raise ValueError("insufficient Cor for the requested Volcoins")
        actor.col -= cost
        self._set_balance(actor, self._balance(actor) + amount)
        return self.wallet(actor_id)

    def open_arena_match(self, match_definition_id: str) -> dict:
        definition = ARENA_MATCHES[match_definition_id]
        instance_id = f"arena7_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "definition_id": match_definition_id,
            "name": definition["name"],
            "status": "open",
            "opened_at_ms": self.runtime.world.now_ms,
            "resolved_at_ms": None,
            "winner_id": None,
            "bets": {},
        }
        self._matches()[instance_id] = state
        return self.match_state(instance_id)

    def place_arena_bet(
        self,
        actor_id: str,
        match_instance_id: str,
        contender_id: str,
        wager_volcoin: int,
    ) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != MONSTER_ARENA:
            raise ValueError("Monster Arena bets are placed at the Volupta Grand Casino Monster Arena")
        state = self._matches()[match_instance_id]
        if state["status"] != "open":
            raise ValueError("this Monster Arena match is no longer accepting bets")
        definition = ARENA_MATCHES[state["definition_id"]]
        if contender_id not in definition["contenders"]:
            raise ValueError("contender is not part of this arena match")
        wager = int(wager_volcoin)
        if wager <= 0:
            raise ValueError("arena wager must be positive")
        if actor_id in state["bets"]:
            raise ValueError("actor already has a wager on this match")
        balance = self._balance(actor)
        if balance < wager:
            raise ValueError("insufficient Volcoins for this wager")
        self._set_balance(actor, balance - wager)
        state["bets"][actor_id] = {
            "contender_id": contender_id,
            "wager_volcoin": wager,
            "payout_volcoin": 0,
        }
        return {
            "match": self.match_state(match_instance_id),
            "wallet": self.wallet(actor_id),
        }

    def resolve_arena_match(self, match_instance_id: str, *, seed: int | None = None) -> dict:
        state = self._matches()[match_instance_id]
        if state["status"] != "open":
            return self.match_state(match_instance_id)
        definition = ARENA_MATCHES[state["definition_id"]]
        contenders = list(definition["contenders"])
        weights = [float(definition["win_weights"][contender]) for contender in contenders]
        rng = random.Random(seed) if seed is not None else self.runtime.rng
        winner = rng.choices(contenders, weights=weights, k=1)[0]
        state["winner_id"] = winner
        state["status"] = "resolved"
        state["resolved_at_ms"] = self.runtime.world.now_ms

        for actor_id, bet in state["bets"].items():
            if bet["contender_id"] != winner:
                continue
            payout = max(
                1,
                int(round(bet["wager_volcoin"] * float(definition["payout_multipliers"][winner]))),
            )
            bet["payout_volcoin"] = payout
            actor = self.runtime.actors[actor_id]
            self._set_balance(actor, self._balance(actor) + payout)
        return self.match_state(match_instance_id)

    def match_state(self, match_instance_id: str) -> dict:
        state = self._matches()[match_instance_id]
        definition = ARENA_MATCHES[state["definition_id"]]
        return {
            **state,
            "contenders": list(definition["contenders"]),
            "payout_multipliers": dict(definition["payout_multipliers"]),
            "live_outcome_model": "simulation_weighted_random",
            "canon_historical_winner": definition["canon_historical_winner"],
            "provenance": definition["provenance"],
        }

    def redeem_sword_of_volupta(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != CASINO:
            raise ValueError("the Sword of Volupta is redeemed at the Volupta Grand Casino")
        if self.runtime.world.global_flags.get("floor7_sword_of_volupta_redeemed"):
            raise ValueError("the unique Sword of Volupta prize has already been redeemed")
        balance = self._balance(actor)
        if balance < SWORD_OF_VOLUPTA_PRICE_VOLCOIN:
            raise ValueError("insufficient Volcoins for the Sword of Volupta")
        self._set_balance(actor, balance - SWORD_OF_VOLUPTA_PRICE_VOLCOIN)

        template = self.runtime.catalog.weapons[SWORD_OF_VOLUPTA_ID]
        item = ItemInstance(
            instance_id=f"weapon_{uuid.uuid4().hex[:12]}",
            template_id=SWORD_OF_VOLUPTA_ID,
            owner_id=actor_id,
            durability=template.base_durability,
            max_durability=template.base_durability,
            metadata={
                "redeemed_at_volupta_grand_casino": True,
                "redeemed_at_ms": self.runtime.world.now_ms,
                "advertised_identity": "Sword of Volupta",
                "true_identity_known_to_actor": False,
            },
        )
        add_item(actor, item, self.runtime.catalog, allow_overweight=True)
        self.runtime.world.global_flags["floor7_sword_of_volupta_redeemed"] = True
        self.runtime.world.global_flags["floor7_sword_of_volupta_instance_id"] = item.instance_id
        self.runtime.world.global_flags["floor7_sword_of_volupta_owner_id"] = actor_id
        return {
            "actor_id": actor_id,
            "sword_instance_id": item.instance_id,
            "template_id": item.template_id,
            "price_volcoin": SWORD_OF_VOLUPTA_PRICE_VOLCOIN,
            "wallet": self.wallet(actor_id),
        }


def install_floor7_volupta_scenario(runtime) -> Floor7VoluptaScenario:
    if SWORD_OF_VOLUPTA_ID not in runtime.catalog.weapons:
        raise RuntimeError("Floor 7 Sword of Volupta corpus was not loaded")
    return Floor7VoluptaScenario(runtime)
