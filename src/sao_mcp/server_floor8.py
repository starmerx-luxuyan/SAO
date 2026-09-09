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


def register_floor8_tools(mcp, emergency, standoff, sluva) -> None:
    @mcp.tool()
    def trigger_progressive9_floor8_forest_emergency(nocturne_instance_id: str, recipient_actor_id: str) -> str:
        """Materialize Argo plus the already-existing ALS/DKB cave parties and Forest Elf pursuit party, send a real persistent friend message, and link the Floor 8 incident to Nocturne."""
        return _json(emergency.trigger_from_nocturne(nocturne_instance_id, recipient_actor_id))

    @mcp.tool()
    def assign_progressive9_floor8_response_split(
        instance_id: str,
        floor8_actor_ids: list[str],
        hideout_actor_ids: list[str],
    ) -> str:
        """Assign every Nocturne player exactly once to the Floor 8 emergency or Floor 4 sacred-key branch; no canon split is forced."""
        return _json(emergency.assign_response_split(instance_id, floor8_actor_ids, hideout_actor_ids))

    @mcp.tool()
    def arrive_progressive9_floor8_frieben(instance_id: str) -> str:
        """Acknowledge assigned emergency responders only after their real actor locations reach Frieben through ordinary teleport/travel rules."""
        return _json(emergency.arrive_frieben(instance_id))

    @mcp.tool()
    def depart_progressive9_frieben_to_sacred_woods(instance_id: str) -> str:
        """Move all assigned responders through the real Frieben -> managed-forest -> protected-woods route with one shared travel clock."""
        return _json(emergency.depart_frieben_to_sacred_woods(instance_id))

    @mcp.tool()
    def inspect_progressive9_sacred_woods_incident(instance_id: str) -> str:
        """Confirm the already-materialized frontline parties are sheltering in the cave while the live Forest Elf pursuit party remains at the damaged protected woods."""
        return _json(emergency.inspect_sacred_woods_incident(instance_id))

    @mcp.tool()
    def follow_progressive9_forest_elves_to_cave_mouth(instance_id: str) -> str:
        """Advance responders and the Forest Elf pursuit party through the same real elapsed route to the escape-cave mouth without treating them as allies."""
        return _json(emergency.follow_to_escape_cave_mouth(instance_id))

    @mcp.tool()
    def enter_progressive9_escape_cave(instance_id: str) -> str:
        """Move only the responders into the cave to meet the ALS/DKB incident parties while the Forest Elf pursuers remain outside in an unresolved standoff."""
        return _json(emergency.enter_escape_cave(instance_id))

    @mcp.tool()
    def offer_progressive9_cave_restitution(
        instance_id: str,
        mediator_actor_id: str,
        payer_actor_id: str,
        col_amount: int,
    ) -> str:
        """Create an explicit Col restitution offer from a living player inside the cave. No money moves and no NPC accepts automatically."""
        return _json(standoff.offer_restitution(instance_id, mediator_actor_id, payer_actor_id, col_amount))

    @mcp.tool()
    def accept_progressive9_cave_restitution(instance_id: str, forest_elf_actor_id: str) -> str:
        """Have the actual Forest Elf pursuit-party leader accept the pending offer, transfer the exact Col, and withdraw the live pursuit party to the protected woods."""
        return _json(standoff.accept_restitution(instance_id, forest_elf_actor_id))

    @mcp.tool()
    def reject_progressive9_cave_restitution(instance_id: str, forest_elf_actor_id: str) -> str:
        """Have the actual Forest Elf pursuit-party leader reject the pending offer and restore the unresolved cave standoff without moving money."""
        return _json(standoff.reject_restitution(instance_id, forest_elf_actor_id))

    @mcp.tool()
    def surrender_progressive9_incident_players_to_custody(instance_id: str, mediator_actor_id: str) -> str:
        """Resolve the standoff by moving every live ALS/DKB incident actor out of the cave and, together with the real Forest Elf pursuit party, through the protected woods into Sluva custody."""
        return _json(standoff.surrender_incident_players_to_custody(instance_id, mediator_actor_id))

    @mcp.tool()
    def start_progressive9_sluva_hearing(instance_id: str, advocate_actor_id: str) -> str:
        """Open a simulation Sluva legal docket only after the real custody branch reaches the Forest Elf capital; formal charges immediately affect ALS/DKB faction standing."""
        return _json(sluva.open_hearing(instance_id, advocate_actor_id))

    @mcp.tool()
    def issue_progressive9_sluva_restorative_judgment(instance_id: str, arbiter_actor_id: str) -> str:
        """Have the authoritative Sluva arbiter issue the simulation restorative judgment: explicit Col restitution, restorative forest service, or refusal."""
        return _json(sluva.issue_restorative_judgment(instance_id, arbiter_actor_id))

    @mcp.tool()
    def satisfy_progressive9_sluva_judgment_with_col(instance_id: str, payer_actor_id: str) -> str:
        """Pay the exact Sluva judgment from a real linked player's Col balance, credit the real arbiter actor, release custody, and update Forest Elf political standing."""
        return _json(sluva.satisfy_with_restitution(instance_id, payer_actor_id))

    @mcp.tool()
    def satisfy_progressive9_sluva_judgment_with_service(instance_id: str) -> str:
        """Escort the real custody and Forest Elf actors back to the protected woods, spend the full restorative-service time, release custody there, and update faction standing."""
        return _json(sluva.satisfy_with_restorative_service(instance_id))

    @mcp.tool()
    def refuse_progressive9_sluva_judgment(instance_id: str, actor_id: str) -> str:
        """Refuse the issued Sluva judgment while leaving the refusing incident player and the rest of the custody group physically detained; payment or service may still be accepted later."""
        return _json(sluva.refuse_judgment(instance_id, actor_id))

    @mcp.tool()
    def start_progressive9_cave_mouth_combat(instance_id: str, player_combatant_ids: list[str]) -> str:
        """Escalate the unresolved standoff: selected live responder/frontline players walk out to the cave mouth and enter an ordinary encounter with the real Forest Elf pursuers."""
        return _json(standoff.start_cave_mouth_combat(instance_id, player_combatant_ids))

    @mcp.tool()
    def resolve_progressive9_cave_mouth_combat(instance_id: str) -> str:
        """After ordinary combat, resolve only when the real Forest Elf pursuit party or all selected player combatants are actually defeated."""
        return _json(standoff.resolve_cave_mouth_combat(instance_id))

    @mcp.tool()
    def get_progressive9_floor8_emergency_state(instance_id: str) -> str:
        """Inspect Argo's message, response branch, live PartyState actors, cave positions and any active restitution/custody/combat resolution state."""
        return _json(standoff.status(instance_id))

    @mcp.tool()
    def get_progressive9_sluva_justice_state(instance_id: str) -> str:
        """Inspect the Sluva docket, real custody locations, arbiter, judgment/resolution, and authoritative ALS/DKB standing toward the Forest Elves."""
        return _json(sluva.status(instance_id))
