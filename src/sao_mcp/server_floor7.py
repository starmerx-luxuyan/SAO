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


def register_floor7_tools(mcp, volupta, aghyellr, intrigue) -> None:
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
        """Open one implemented Volupta Monster Arena matchup; live outcome remains simulation rather than forced history."""
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
        """Resolve a live Monster Arena match and pay winning Volcoin bets."""
        return _json(volupta.resolve_arena_match(match_instance_id, seed=seed))

    @mcp.tool()
    def get_floor7_monster_arena_match(match_instance_id: str) -> str:
        """Inspect contenders, wagers, observed odds and resolved outcome for a Monster Arena match."""
        return _json(volupta.match_state(match_instance_id))

    @mcp.tool()
    def redeem_floor7_sword_of_volupta(actor_id: str) -> str:
        """Spend 100,000 Volcoins to redeem the unique Sword of Volupta prize as a real weapon instance."""
        return _json(volupta.redeem_sword_of_volupta(actor_id))

    @mcp.tool()
    def inspect_floor7_arena_dye_evidence(actor_id: str, match_instance_id: str) -> str:
        """After the suspicious first arena match, inspect the cage's red residue and preserve it as a real evidence item."""
        return _json(intrigue.inspect_first_match_cage(actor_id, match_instance_id))

    @mcp.tool()
    def report_floor7_arena_cheat_to_nirrnir(actor_id: str) -> str:
        """Report the red plant-dye evidence to Nirrnir and receive the 20-Narsos/50-Wurtz decolorant request."""
        return _json(intrigue.report_evidence_to_nirrnir(actor_id))

    @mcp.tool()
    def gather_floor7_narsos_fruit(actor_id: str) -> str:
        """Gather the requested twenty ripe Narsos fruits in Looserock Forest."""
        return _json(intrigue.gather_narsos_fruit(actor_id))

    @mcp.tool()
    def gather_floor7_wurtz_stones(actor_id: str) -> str:
        """Spend the documented five-hour collection window gathering fifty Wurtz stones at the riverbed west of Volupta."""
        return _json(intrigue.gather_wurtz_stones(actor_id))

    @mcp.tool()
    def brew_floor7_lykaon_decolorant(actor_id: str) -> str:
        """Consume 20 Narsos fruits and 50 Wurtz stones and simmer the observed quest batch for three hours."""
        return _json(intrigue.brew_decolorant(actor_id))

    @mcp.tool()
    def discover_floor7_dyed_lykaon(actor_id: str) -> str:
        """Infiltrate the Korloy monster stables and discover the exhausted red-dyed Lykaon registered as a Rusty Lykaon."""
        return _json(intrigue.discover_dyed_lykaon(actor_id))

    @mcp.tool()
    def apply_floor7_lykaon_decolorant(actor_id: str) -> str:
        """Use the prepared bottle to strip Rubrabium dye and reveal the monster's real Storm Lykaon identity."""
        return _json(intrigue.apply_decolorant(actor_id))

    @mcp.tool()
    def free_floor7_storm_lykaon(actor_id: str) -> str:
        """Optional campaign choice: cut the revealed Storm Lykaon's restraint and escape with it to the west riverbank."""
        return _json(intrigue.free_storm_lykaon(actor_id))

    @mcp.tool()
    def expire_floor7_storm_lykaon_control(actor_id: str) -> str:
        """Let the freed Lykaon's Korloy control expire; its cursor turns red and ordinary encounter rules take over."""
        return _json(intrigue.expire_storm_lykaon_control(actor_id))

    @mcp.tool()
    def get_floor7_casino_intrigue_state(actor_id: str) -> str:
        """Inspect the arena evidence, ingredient, decolorant and Storm Lykaon reveal state."""
        return _json(intrigue.status(actor_id))

    @mcp.tool()
    def trigger_floor7_nirrnir_poisoning(actor_id: str) -> str:
        """Trigger the Argent Serpent silver-poison event at the Korloy monster stables and start Nirrnir's 48-hour stabilised survival window."""
        return _json(aghyellr.trigger_nirrnir_poisoning(actor_id))

    @mcp.tool()
    def get_floor7_nirrnir_status() -> str:
        """Inspect Nirrnir's silver-poison state, world-time deadline and required cure."""
        return _json(aghyellr.nirrnir_status())

    @mcp.tool()
    def start_floor7_aghyellr_raid(player_ids: list[str], bring_nirrnir: bool = True) -> str:
        """Start Aghyellr the Igneous Wyrm and optionally carry the poisoned Nirrnir into the Floor 7 Boss Room."""
        return _json(aghyellr.start_aghyellr_raid(player_ids, bring_nirrnir=bring_nirrnir))

    @mcp.tool()
    def telegraph_floor7_aghyellr_gaze(instance_id: str) -> str:
        """Telegraph Aghyellr's canon wing-spread/red-eye Intimidating Gaze before players choose whether to look away."""
        return _json(aghyellr.telegraph_intimidating_gaze(instance_id))

    @mcp.tool()
    def resolve_floor7_aghyellr_gaze(instance_id: str, look_away_actor_ids: list[str] | None = None) -> str:
        """Resolve Intimidating Gaze: under-Level-20 players who keep looking are immediately stunned."""
        return _json(aghyellr.resolve_intimidating_gaze(instance_id, look_away_actor_ids=look_away_actor_ids))

    @mcp.tool()
    def collect_floor7_aghyellr_dragon_blood(instance_id: str, actor_id: str) -> str:
        """After Aghyellr dies, collect a real fresh, undiluted, unpreserved dragon-blood item from the boss."""
        return _json(aghyellr.collect_fresh_dragon_blood(instance_id, actor_id))

    @mcp.tool()
    def administer_floor7_dragon_blood_to_nirrnir(actor_id: str, blood_instance_id: str) -> str:
        """Give Nirrnir fresh Aghyellr blood before her silver-poison deadline expires."""
        return _json(aghyellr.administer_dragon_blood(actor_id, blood_instance_id))

    @mcp.tool()
    def get_floor7_aghyellr_state(instance_id: str) -> str:
        """Inspect Aghyellr's segmented Boss state, pending gaze and the linked Nirrnir countdown."""
        return _json(aghyellr.raid_status(instance_id))
