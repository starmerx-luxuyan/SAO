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
        """Materialize Argo and Klein at the Acorn Shop plus a simulation 2+2 local representative cohort from the real ALS/DKB GuildStates and the Forest Elf pursuit party. Argo's report covers a wider majority-of-each-guild crisis; no exact total is fabricated."""
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
    def meet_progressive9_argo_and_klein(instance_id: str) -> str:
        """Walk the assigned responders from the Frieben Teleport Gate to the real Acorn Shop rendezvous where Argo and Klein are waiting, and confirm Argo's majority-of-both-guilds incident briefing."""
        return _json(emergency.meet_argo_and_klein(instance_id))

    @mcp.tool()
    def depart_progressive9_acorn_shop_to_sacred_woods(instance_id: str) -> str:
        """Leave the Acorn Shop through Frieben, cross the managed outer forest, and reach the protected Forest Elf woods on the shared world clock."""
        return _json(emergency.depart_acorn_shop_to_sacred_woods(instance_id))

    @mcp.tool()
    def inspect_progressive9_sacred_woods_incident(instance_id: str) -> str:
        """Inspect the local materialized ALS/DKB representative cohort sheltering in the cave and the live Forest Elf pursuit party at the damaged woods. The 2+2 representatives are not treated as the full reported guild majorities."""
        return _json(emergency.inspect_sacred_woods_incident(instance_id))

    @mcp.tool()
    def follow_progressive9_forest_elves_to_cave_mouth(instance_id: str) -> str:
        """Advance responders and the Forest Elf pursuit party through the same real elapsed route to the escape-cave mouth without treating them as allies."""
        return _json(emergency.follow_to_escape_cave_mouth(instance_id))

    @mcp.tool()
    def enter_progressive9_escape_cave(instance_id: str) -> str:
        """Move only the responders into the cave to meet the local materialized ALS/DKB representatives while the Forest Elf pursuers remain outside in an unresolved standoff."""
        return _json(emergency.enter_escape_cave(instance_id))

    @mcp.tool()
    def offer_progressive9_cave_restitution(
        instance_id: str,
        mediator_actor_id: str,
        payer_actor_id: str,
        col_amount: int,
    ) -> str:
        """Create an explicit Col restitution offer for the materialized local standoff from a living player inside the cave. No money moves and no NPC accepts automatically; the wider guild-scale crisis is not auto-resolved."""
        return _json(standoff.offer_restitution(instance_id, mediator_actor_id, payer_actor_id, col_amount))

    @mcp.tool()
    def accept_progressive9_cave_restitution(instance_id: str, forest_elf_actor_id: str) -> str:
        """Have the actual Forest Elf pursuit-party leader accept the pending local offer, transfer the exact Col, and withdraw the live pursuit party to the protected woods. This resolves only the materialized local standoff."""
        return _json(standoff.accept_restitution(instance_id, forest_elf_actor_id))

    @mcp.tool()
    def reject_progressive9_cave_restitution(instance_id: str, forest_elf_actor_id: str) -> str:
        """Have the actual Forest Elf pursuit-party leader reject the pending local offer and restore the unresolved cave standoff without moving money."""
        return _json(standoff.reject_restitution(instance_id, forest_elf_actor_id))

    @mcp.tool()
    def surrender_progressive9_local_representatives_to_custody(instance_id: str, mediator_actor_id: str) -> str:
        """Resolve only the materialized local standoff by moving its live ALS/DKB representative actors out of the cave and, with the real Forest Elf pursuit party, through the protected woods into Sluva custody. Unmaterialized members in Argo's wider report are not moved or sentenced."""
        return _json(standoff.surrender_local_representatives_to_custody(instance_id, mediator_actor_id))

    @mcp.tool()
    def start_progressive9_sluva_hearing(instance_id: str, advocate_actor_id: str) -> str:
        """Open a Sluva docket for the materialized detainees after the local custody branch reaches the Forest Elf capital; the wider DKB/ALS crisis remains separately represented by the corpus report."""
        return _json(sluva.open_hearing(instance_id, advocate_actor_id))

    @mcp.tool()
    def issue_progressive9_sluva_grave_judgment(instance_id: str, arbiter_actor_id: str) -> str:
        """Have the authoritative Sluva arbiter recognize the grave baseline for the materialized detainees: principal execution risk and other-participant imprisonment risk. The principal is still unresolved after this step."""
        return _json(sluva.issue_grave_judgment(instance_id, arbiter_actor_id))

    @mcp.tool()
    def adjudicate_progressive9_sluva_principal(
        instance_id: str,
        arbiter_actor_id: str,
        principal_actor_id: str,
    ) -> str:
        """Record the authoritative Sluva arbiter's explicit principal finding among the materialized local detainees. This is a simulation judicial finding; it does not assert that the selected actor personally felled the protected tree or identify a principal for the wider guild-scale crisis."""
        return _json(sluva.adjudicate_principal(instance_id, arbiter_actor_id, principal_actor_id))

    @mcp.tool()
    def deposit_progressive9_sluva_restitution_mitigation(instance_id: str, payer_actor_id: str) -> str:
        """Transfer the fixed simulation restitution deposit from a real linked player to the arbiter as mitigation for the local Sluva case; custody remains active and the charge is not erased."""
        return _json(sluva.deposit_restitution_mitigation(instance_id, payer_actor_id))

    @mcp.tool()
    def perform_progressive9_sluva_restorative_service_mitigation(instance_id: str) -> str:
        """Escort the materialized detainees under guard to the protected woods, spend the full restoration time, return them to Sluva, and record mitigation without releasing custody."""
        return _json(sluva.perform_restorative_service_mitigation(instance_id))

    @mcp.tool()
    def issue_progressive9_sluva_disposition(
        instance_id: str,
        arbiter_actor_id: str,
        disposition: str,
    ) -> str:
        """Issue strict, commuted, or pardon disposition only after the local Sluva docket already contains an explicit principal finding. Strict records an execution order for that adjudicated principal and imprisonment orders for the others but does not auto-kill; this disposition does not resolve the wider guild-scale crisis."""
        return _json(
            sluva.issue_disposition(
                instance_id,
                arbiter_actor_id,
                disposition,
            )
        )

    @mcp.tool()
    def begin_progressive9_sluva_imprisonment_enforcement(
        instance_id: str,
        arbiter_actor_id: str,
        imprisonment_duration_ms: int,
    ) -> str:
        """Begin enforcement of the imprisonment orders already present in a strict or commuted local Sluva disposition. The caller must provide the campaign's explicit simulation duration; the runtime stores the release timestamp but does not auto-advance world time or execute any death sentence."""
        return _json(
            sluva.begin_imprisonment_enforcement(
                instance_id,
                arbiter_actor_id,
                imprisonment_duration_ms,
            )
        )

    @mcp.tool()
    def complete_progressive9_sluva_imprisonment_enforcement(
        instance_id: str,
        arbiter_actor_id: str,
    ) -> str:
        """Complete the active local Sluva imprisonment term only after the shared world clock reaches its recorded release time. Imprisoned actors are released from custody; any strict execution order remains pending and is not auto-resolved."""
        return _json(sluva.complete_imprisonment_enforcement(instance_id, arbiter_actor_id))

    @mcp.tool()
    def start_progressive9_cave_mouth_combat(instance_id: str, player_combatant_ids: list[str]) -> str:
        """Escalate the local unresolved standoff: selected live responders or materialized representative players walk out to the cave mouth and enter an ordinary encounter with the real Forest Elf pursuers."""
        return _json(standoff.start_cave_mouth_combat(instance_id, player_combatant_ids))

    @mcp.tool()
    def resolve_progressive9_cave_mouth_combat(instance_id: str) -> str:
        """After ordinary combat, resolve the local encounter only when the real Forest Elf pursuit party or all selected player combatants are actually defeated."""
        return _json(standoff.resolve_cave_mouth_combat(instance_id))

    @mcp.tool()
    def get_progressive9_floor8_emergency_state(instance_id: str) -> str:
        """Inspect Argo/Klein rendezvous state, Argo's reported majority-of-both-guilds scope, real Lind/Kibaou GuildState decision authority, local materialized representatives, cave positions and any active local restitution/custody/combat resolution state."""
        return _json(standoff.status(instance_id))

    @mcp.tool()
    def get_progressive9_sluva_justice_state(instance_id: str) -> str:
        """Inspect the local Sluva docket together with the unchanged wider guild-crisis report, explicit principal finding, disposition, sentence-enforcement timing, real custody locations, arbiter, and authoritative ALS/DKB standing toward the Forest Elves."""
        return _json(sluva.status(instance_id))
