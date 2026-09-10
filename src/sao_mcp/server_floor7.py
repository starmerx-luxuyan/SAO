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


def register_floor7_tools(mcp, volupta, aghyellr, intrigue, elfwar, pursuit) -> None:
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
    def start_floor7_harin_arrest(player_ids: list[str]) -> str:
        """Arrive at Harin Tree Palace, trigger the Fallen-Elf collaboration arrest and move real equipped weapons into the confiscated-weapon store."""
        return _json(elfwar.arrive_and_be_arrested(player_ids))

    @mcp.tool()
    def burn_floor7_harin_cell_lock(instance_id: str) -> str:
        """Char the all-wood B2 cell lock with the canon torch tactic until the party can escape quietly."""
        return _json(elfwar.burn_cell_lock(instance_id))

    @mcp.tool()
    def recover_floor7_harin_confiscated_weapons(instance_id: str) -> str:
        """Recover each player's exact confiscated equipment instances from the Harin basement weapon store."""
        return _json(elfwar.recover_confiscated_weapons(instance_id))

    @mcp.tool()
    def meet_floor7_lavik(instance_id: str) -> str:
        """Search the basement cells, meet Lavik Fen Cortassios and add the long-imprisoned Dark Elf fugitive to the escape party."""
        return _json(elfwar.meet_lavik(instance_id))

    @mcp.tool()
    def let_floor7_lavik_clear_guard_post(instance_id: str) -> str:
        """Let Lavik nonlethally subdue the Harin guards and lead the fugitives toward the seventh-story clergy prison."""
        return _json(elfwar.lavik_subdues_guard_post(instance_id))

    @mcp.tool()
    def rejoin_floor7_kizmel_at_harin(instance_id: str) -> str:
        """Find Kizmel in the seventh-story prison and return her exact confiscated weapon instance when one already exists in the campaign."""
        return _json(elfwar.rejoin_kizmel(instance_id))

    @mcp.tool()
    def convince_floor7_kizmel_to_escape(instance_id: str) -> str:
        """Convince the accused Kizmel to escape as a fugitive and clear her own name by recovering the sacred keys."""
        return _json(elfwar.convince_kizmel_to_escape(instance_id))

    @mcp.tool()
    def blackout_and_escape_floor7_harin(instance_id: str) -> str:
        """Leave a lit torch to extinguish Harin's bonfire-shroom lighting, then descend the roughly fifty-metre outer trunk and complete Prisoners of the Tree Palace."""
        return _json(elfwar.blackout_and_escape(instance_id))

    @mcp.tool()
    def gather_floor7_post_escape_narsos(instance_id: str, carrier_actor_id: str | None = None) -> str:
        """After escaping Harin, gather the same twenty Narsos fruits used by the Volupta decolorant line and part ways with Lavik."""
        return _json(elfwar.gather_narsos_and_part_with_lavik(instance_id, carrier_actor_id=carrier_actor_id))

    @mcp.tool()
    def return_floor7_harin_party_to_volupta(instance_id: str) -> str:
        """Return the escaped player party to Volupta with fugitive Kizmel while Lavik continues separately."""
        return _json(elfwar.return_to_volupta_with_kizmel(instance_id))

    @mcp.tool()
    def get_floor7_harin_escape_state(instance_id: str) -> str:
        """Inspect Harin imprisonment, weapon recovery, Lavik/Kizmel, blackout, Narsos and Volupta-return state."""
        return _json(elfwar.status(instance_id))

    @mcp.tool()
    def negotiate_floor7_scyia_counteroffer(lead_actor_id: str, duel_partner_id: str) -> str:
        """Recover Bardun's Scyia map after the Lykaon reveal, return together to Volupta, and use a First-Strike duel to exchange blood-marked rendezvous data."""
        return _json(pursuit.negotiate_scyia_counteroffer(lead_actor_id, duel_partner_id))

    @mcp.tool()
    def reach_floor7_field_of_bones_rendezvous(instance_id: str) -> str:
        """Prepare in Volupta, then move the complete Harin player party and Kizmel to the Field of Bones with one shared travel-time cost."""
        return _json(pursuit.rest_and_reach_dragon_bone_watch(instance_id))

    @mcp.tool()
    def observe_floor7_fallen_departure(instance_id: str) -> str:
        """Observe the two unnamed Fallen Elves answer the Scyia rendezvous and begin leaving the Field of Bones."""
        return _json(pursuit.observe_fallen_departure(instance_id))

    @mcp.tool()
    def pursue_floor7_fallen_to_ant_valley(instance_id: str) -> str:
        """Tail the two Fallen Elves from the Field of Bones into Ant Tunnel Valley using shared party travel time."""
        return _json(pursuit.pursue_to_ant_tunnel_valley(instance_id))

    @mcp.tool()
    def follow_floor7_fallen_into_labyrinth(instance_id: str) -> str:
        """Follow the Fallen Elves into the Floor 7 Labyrinth; the parallel Ruby-Key retrieval line also advances in real world state."""
        return _json(pursuit.follow_through_valley_into_labyrinth(instance_id))

    @mcp.tool()
    def advance_floor7_pursuit_to_boss_room(instance_id: str) -> str:
        """Advance the surviving pursuit group from the Labyrinth to the Floor 7 Boss Room for the existing Aghyellr raid."""
        return _json(pursuit.advance_to_boss_room(instance_id))

    @mcp.tool()
    def get_floor7_fallen_pursuit_state(instance_id: str) -> str:
        """Inspect the Harin-linked Scyia map, real four-key bag, Ruby-Key ownership, five-key Fallen state, positions and blocker encounter."""
        return _json(pursuit.status(instance_id))

    @mcp.tool()
    def trigger_floor7_nirrnir_poisoning(actor_id: str) -> str:
        """Trigger the Argent Serpent silver-poison event at the Korloy monster stables and start Nirrnir's 48-hour survival window."""
        return _json(aghyellr.trigger_nirrnir_poisoning(actor_id))

    @mcp.tool()
    def get_floor7_nirrnir_status() -> str:
        """Inspect Nirrnir's declining HP, silver-poison deadline, human-blood bridge and required cure."""
        return _json(aghyellr.nirrnir_status())

    @mcp.tool()
    def start_floor7_aghyellr_raid(player_ids: list[str], bring_nirrnir: bool = True) -> str:
        """Start Aghyellr the Igneous Wyrm and optionally carry the poisoned Nirrnir into the Floor 7 Boss Room."""
        return _json(aghyellr.start_aghyellr_raid(player_ids, bring_nirrnir=bring_nirrnir))

    @mcp.tool()
    def bridge_floor7_nirrnir_with_human_blood(instance_id: str, donor_actor_id: str) -> str:
        """At Nirrnir's critical HP, spend a large real HP cost from one raid player to create a temporary blood bridge and transform that donor into Civis Nocte."""
        return _json(aghyellr.sustain_nirrnir_with_human_blood(instance_id, donor_actor_id))

    @mcp.tool()
    def reveal_floor7_doleful_nocturne(instance_id: str, actor_id: str, sword_instance_id: str) -> str:
        """As a Civis Nocte raid player, reveal an equipped Sword of Volupta instance as Doleful Nocturne without changing the public item template."""
        return _json(aghyellr.reveal_doleful_nocturne(instance_id, actor_id, sword_instance_id))

    @mcp.tool()
    def get_floor7_nightfolk_state(actor_id: str) -> str:
        """Inspect authoritative Civis/Dominus Nocte rank, master relation, combat bonus, sunlight weakness and blood-feeding capability."""
        return _json(aghyellr.runtime.nightfolk_state(actor_id))

    @mcp.tool()
    def feed_floor7_civis_nocte(civis_actor_id: str, donor_actor_id: str, donor_hp_cost: int) -> str:
        """Let a Civis Nocte recover HP by consuming a specified amount of a colocated living donor's HP; ordinary feeding does not transform the donor."""
        return _json(aghyellr.runtime.feed_civis_nocte(civis_actor_id, donor_actor_id, donor_hp_cost))

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
        """After Aghyellr dies, materialize and collect its seventeen real jars of fresh, undiluted, unpreserved dragon blood."""
        return _json(aghyellr.collect_fresh_dragon_blood(instance_id, actor_id))

    @mcp.tool()
    def administer_floor7_dragon_blood_to_nirrnir(
        instance_id: str,
        actor_id: str,
        blood_instance_id: str,
    ) -> str:
        """Consume one jar from this Aghyellr raid's real blood drop to cure Nirrnir before the silver-poison deadline."""
        return _json(aghyellr.administer_dragon_blood(instance_id, actor_id, blood_instance_id))

    @mcp.tool()
    def get_floor7_aghyellr_state(instance_id: str) -> str:
        """Inspect Aghyellr bars, synchronized encounter/world time, Civis transformations, blood jars and linked Nirrnir countdown."""
        return _json(aghyellr.raid_status(instance_id))
