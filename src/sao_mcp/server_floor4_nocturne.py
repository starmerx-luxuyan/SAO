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


def register_floor4_nocturne_tools(mcp, nocturne) -> None:
    @mcp.tool()
    def open_progressive9_five_key_backtrack(harin_instance_id: str, aghyellr_instance_id: str) -> str:
        """Continue the validated five-sacred-key state into Progressive 9; the trail returns to Floor 4 and Lavik waits outside Yofel Castle."""
        return _json(nocturne.open_five_key_backtrack(harin_instance_id, aghyellr_instance_id))

    @mcp.tool()
    def meet_progressive9_lavik_west_shore(instance_id: str) -> str:
        """Acknowledge the complete pursuit group at Lavik's Lake Yofel west-shore camp before anyone enters Yofel Castle."""
        return _json(nocturne.arrive_lavik_west_shore(instance_id))

    @mcp.tool()
    def accept_progressive9_lavik_request(instance_id: str, actor_id: str) -> str:
        """Accept Lavik's request to bring Viscount Yofilis to him without guards or attendants."""
        return _json(nocturne.accept_lavik_request(instance_id, actor_id))

    @mcp.tool()
    def arrive_progressive9_yofel_castle(instance_id: str) -> str:
        """After Lavik stays behind on the shore, acknowledge the pursuit group at Yofel Castle and meet Cetrann."""
        return _json(nocturne.arrive_yofel_castle(instance_id))

    @mcp.tool()
    def request_progressive9_yofilis_secret_meeting(instance_id: str, actor_id: str) -> str:
        """Ask the authoritative Floor 4 Yofilis NPC to leave the castle household for Lavik's secret meeting."""
        return _json(nocturne.request_yofilis_secret_meeting(instance_id, actor_id))

    @mcp.tool()
    def prepare_progressive9_kelpie_search(instance_id: str, search_actor_ids: list[str]) -> str:
        """Choose one or two players including the Floor 7 Civis Nocte, stow their exact equipment, and move them into Lake Yofel's fog boundary."""
        return _json(nocturne.prepare_kelpie_search(instance_id, search_actor_ids))

    @mcp.tool()
    def call_progressive9_kelpie_from_fog(instance_id: str) -> str:
        """With the selected searchers still equipment-free in deep fog, materialize Morvarc'h the Lake Kelpie as a real hostile field-boss actor."""
        return _json(nocturne.call_kelpie_from_fog(instance_id))

    @mcp.tool()
    def tame_progressive9_kelpie(instance_id: str, actor_id: str, nickname: str) -> str:
        """Use the generic Night lower-level monster-control rule on Morvarc'h; failure conditions remain real rule errors rather than scripted success."""
        return _json(nocturne.tame_kelpie(instance_id, actor_id, nickname))

    @mcp.tool()
    def restore_progressive9_kelpie_search_equipment(instance_id: str) -> str:
        """Re-equip each searcher's exact pre-search item instances after Morvarc'h has been tamed."""
        return _json(nocturne.restore_kelpie_search_equipment(instance_id))

    @mcp.tool()
    def escort_progressive9_yofilis_to_north_beach(instance_id: str) -> str:
        """Have Kizmel quietly escort Yofilis from Yofel Castle to the secluded north-beach rendezvous."""
        return _json(nocturne.escort_yofilis_to_north_beach(instance_id))

    @mcp.tool()
    def ride_progressive9_kelpie_to_yofilis(instance_id: str) -> str:
        """Ride the already-tamed Morvarc'h from the fog boundary to Kizmel and Yofilis on Lake Yofel's north beach."""
        return _json(nocturne.ride_kelpie_to_yofilis(instance_id))

    @mcp.tool()
    def carry_progressive9_yofilis_to_lavik(instance_id: str) -> str:
        """Use Morvarc'h's water-walking transport to carry the secret party and Yofilis to Lavik's west-shore camp."""
        return _json(nocturne.carry_yofilis_to_lavik(instance_id))

    @mcp.tool()
    def record_progressive9_lavik_yofilis_duel_promise(instance_id: str, actor_id: str) -> str:
        """Record the reunited Lavik and Yofilis agreeing to a future duel; this does not fabricate or immediately resolve that later duel."""
        return _json(nocturne.record_lavik_yofilis_duel_promise(instance_id, actor_id))

    @mcp.tool()
    def return_progressive9_yofilis_and_open_past(instance_id: str, actor_id: str) -> str:
        """Return Yofilis to Yofel Castle and open the documented family/history thread behind his dispute with Lavik."""
        return _json(nocturne.return_yofilis_and_open_past(instance_id, actor_id))

    @mcp.tool()
    def embark_progressive9_five_key_hideout_recon(instance_id: str) -> str:
        """Reassemble all pursuit players with Kizmel and leave Yofel Castle to resume the real five-key investigation."""
        return _json(nocturne.embark_five_key_hideout_recon(instance_id))

    @mcp.tool()
    def follow_progressive9_river_ull_to_hideout(instance_id: str) -> str:
        """Follow Lake Yofel, River Ull, the caldera and Bear Forest route to the existing submerged Floor 4 Fallen Elf hideout."""
        return _json(nocturne.follow_river_ull_to_fallen_hideout(instance_id))

    @mcp.tool()
    def get_progressive9_nocturne_state(instance_id: str) -> str:
        """Inspect inherited key assets, Lavik/Yofilis/Cetrann state, exact stowed equipment, Morvarc'h control and Floor 4 route progress."""
        return _json(nocturne.status(instance_id))