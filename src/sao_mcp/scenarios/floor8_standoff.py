from __future__ import annotations

from sao_mcp.corpus.floor8_world import (
    FOREST_ELF_ESCAPE_CAVE,
    FOREST_ELF_ESCAPE_CAVE_MOUTH,
    FOREST_ELF_SACRED_WOODS,
    SLUVA,
)
from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.group_travel import escorted_travel_together, group_travel_record, travel_together


FOREST_ELF_CUSTODY_RESTRICTION = "forest_elf_custody"


class Floor8CaveStandoffScenario:
    """Live resolution branches for the materialized local Floor 8 cave standoff."""

    def __init__(self, runtime, emergency) -> None:
        if emergency.runtime is not runtime:
            raise RuntimeError("Floor 8 standoff and emergency services must share one runtime")
        self.runtime = runtime
        self.emergency = emergency

    def _state(self, instance_id: str) -> dict:
        return self.emergency._state(instance_id)

    def _incident(self, state: dict) -> dict:
        return state["incident"]

    def _forest_ids(self, state: dict) -> list[str]:
        return list(self._incident(state)["forest_elf_actor_ids"])

    def _frontline_ids(self, state: dict) -> list[str]:
        return list(self._incident(state)["frontline_actor_ids"])

    def _forest_leader_id(self, state: dict) -> str:
        party_id = self._incident(state)["forest_elf_party_id"]
        return self.runtime.world.parties[party_id].leader_id

    def _require_ids_at(self, actor_ids: list[str], location_id: str) -> None:
        wrong = [actor_id for actor_id in actor_ids if self.runtime.actors[actor_id].location_id != location_id]
        if wrong:
            raise ValueError(f"actors are not all at {location_id}: {', '.join(wrong)}")

    def _require_live_standoff(self, state: dict) -> None:
        if state["stage"] != "responders_inside_cave_standoff":
            raise ValueError("the materialized Floor 8 cave standoff is not in its unresolved inside/outside state")
        self._require_ids_at(state["floor8_actor_ids"], FOREST_ELF_ESCAPE_CAVE)
        self._require_ids_at(self._frontline_ids(state), FOREST_ELF_ESCAPE_CAVE)
        self._require_ids_at(self._forest_ids(state), FOREST_ELF_ESCAPE_CAVE_MOUTH)
        if any(not self.runtime.actors[actor_id].alive for actor_id in self._forest_ids(state)):
            raise ValueError("the peaceful local standoff branch requires all Forest Elf pursuers to be alive")

    def offer_restitution(
        self,
        instance_id: str,
        mediator_actor_id: str,
        payer_actor_id: str,
        col_amount: int,
    ) -> dict:
        state = self._state(instance_id)
        self._require_live_standoff(state)
        if mediator_actor_id not in state["floor8_actor_ids"]:
            raise ValueError("restitution mediator must be an assigned Floor 8 responder")
        mediator = self.runtime.actors[mediator_actor_id]
        payer = self.runtime.actors[payer_actor_id]
        if mediator.location_id != FOREST_ELF_ESCAPE_CAVE or not mediator.alive:
            raise ValueError("the mediator must be alive inside the escape cave")
        if payer.kind is not EntityKind.PLAYER or payer.location_id != FOREST_ELF_ESCAPE_CAVE or not payer.alive:
            raise ValueError("restitution payer must be a living player inside the escape cave")
        if col_amount < 1:
            raise ValueError("restitution Col amount must be positive")
        if payer.col < col_amount:
            raise ValueError("restitution payer does not currently hold the offered Col")

        state["pending_restitution"] = {
            "mediator_actor_id": mediator_actor_id,
            "payer_actor_id": payer_actor_id,
            "col_amount": col_amount,
            "offered_at_ms": self.runtime.world.now_ms,
        }
        state["stage"] = "restitution_offered"
        return self.status(instance_id)

    def accept_restitution(self, instance_id: str, forest_elf_actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "restitution_offered":
            raise ValueError("there is no live restitution offer to accept")
        leader_id = self._forest_leader_id(state)
        if forest_elf_actor_id != leader_id:
            raise ValueError("the Forest Elf pursuit-party leader must accept the local settlement")
        self._require_ids_at(self._forest_ids(state), FOREST_ELF_ESCAPE_CAVE_MOUTH)
        offer = state["pending_restitution"]
        payer = self.runtime.actors[offer["payer_actor_id"]]
        leader = self.runtime.actors[leader_id]
        amount = int(offer["col_amount"])
        if payer.location_id != FOREST_ELF_ESCAPE_CAVE or not payer.alive:
            raise ValueError("the restitution payer is no longer alive inside the cave")
        if payer.col < amount:
            raise ValueError("the payer no longer holds the Col that was actually offered")

        payer.col -= amount
        leader.col += amount
        state["accepted_restitution"] = {
            **offer,
            "accepted_by_actor_id": leader_id,
            "accepted_at_ms": self.runtime.world.now_ms,
        }
        del state["pending_restitution"]
        withdrawal = travel_together(self.runtime, self._forest_ids(state), FOREST_ELF_SACRED_WOODS)
        state["accepted_restitution"]["withdrawal_route"] = [group_travel_record(withdrawal)]
        for actor_id in self._frontline_ids(state):
            actor = self.runtime.actors[actor_id]
            actor.metadata["floor8_local_standoff_resolution"] = "restitution"
            actor.metadata["floor8_local_standoff_resolved_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "standoff_resolved_restitution"
        return self.status(instance_id)

    def reject_restitution(self, instance_id: str, forest_elf_actor_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "restitution_offered":
            raise ValueError("there is no live restitution offer to reject")
        leader_id = self._forest_leader_id(state)
        if forest_elf_actor_id != leader_id:
            raise ValueError("the Forest Elf pursuit-party leader must reject the local settlement")
        self._require_ids_at(self._forest_ids(state), FOREST_ELF_ESCAPE_CAVE_MOUTH)
        state["last_rejected_restitution"] = {
            **state["pending_restitution"],
            "rejected_by_actor_id": leader_id,
            "rejected_at_ms": self.runtime.world.now_ms,
        }
        del state["pending_restitution"]
        state["stage"] = "responders_inside_cave_standoff"
        return self.status(instance_id)

    def surrender_local_representatives_to_custody(self, instance_id: str, mediator_actor_id: str) -> dict:
        state = self._state(instance_id)
        self._require_live_standoff(state)
        if mediator_actor_id not in state["floor8_actor_ids"]:
            raise ValueError("local custody handoff must be mediated by an assigned Floor 8 responder")
        mediator = self.runtime.actors[mediator_actor_id]
        if mediator.location_id != FOREST_ELF_ESCAPE_CAVE or not mediator.alive:
            raise ValueError("the custody mediator must be alive inside the cave")

        representative_ids = self._frontline_ids(state)
        forest_ids = self._forest_ids(state)
        approach = travel_together(self.runtime, representative_ids, FOREST_ELF_ESCAPE_CAVE_MOUTH)
        case_id = f"floor8_sluva:{instance_id}"
        authority_id = self._forest_leader_id(state)
        for actor_id in representative_ids:
            self.runtime.take_actor_custody(
                actor_id,
                custody_id=f"custody:{case_id}:{actor_id}",
                authority_id=authority_id,
                case_id=case_id,
                restriction_code=FOREST_ELF_CUSTODY_RESTRICTION,
                reason="protected_tree_incident_local_representative_handoff",
            )
        segments = [
            approach,
            escorted_travel_together(
                self.runtime, representative_ids, forest_ids, FOREST_ELF_SACRED_WOODS
            ),
            escorted_travel_together(self.runtime, representative_ids, forest_ids, SLUVA),
        ]
        state["custody_transfer_route"] = [group_travel_record(segment) for segment in segments]
        state["custody_actor_ids"] = list(representative_ids)
        state["custody_case_id"] = case_id
        state["custody_mediator_actor_id"] = mediator_actor_id
        state["custody_started_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "standoff_resolved_custody"
        return self.status(instance_id)

    def start_cave_mouth_combat(self, instance_id: str, player_combatant_ids: list[str]) -> dict:
        state = self._state(instance_id)
        self._require_live_standoff(state)
        player_ids = list(dict.fromkeys(player_combatant_ids))
        if not player_ids:
            raise ValueError("cave-mouth combat needs at least one player combatant")
        eligible = set(state["floor8_actor_ids"]) | set(self._frontline_ids(state))
        if any(actor_id not in eligible for actor_id in player_ids):
            raise ValueError("cave-mouth combatants must come from responders or the materialized local representatives")
        self._require_ids_at(player_ids, FOREST_ELF_ESCAPE_CAVE)
        if any(not self.runtime.actors[actor_id].alive for actor_id in player_ids):
            raise ValueError("defeated players cannot start the cave-mouth combat branch")
        forest_ids = self._forest_ids(state)
        self._require_ids_at(forest_ids, FOREST_ELF_ESCAPE_CAVE_MOUTH)

        approach = travel_together(self.runtime, player_ids, FOREST_ELF_ESCAPE_CAVE_MOUTH)
        encounter = self.runtime.start_encounter(
            player_ids + forest_ids,
            zone_id=FOREST_ELF_ESCAPE_CAVE_MOUTH,
            safe_zone=False,
        )
        state["cave_combat_approach_route"] = [group_travel_record(approach)]
        state["cave_combat_encounter_id"] = encounter.encounter_id
        state["cave_combat_player_ids"] = player_ids
        state["cave_combat_started_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "cave_mouth_combat"
        return self.status(instance_id)

    def resolve_cave_mouth_combat(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        if state["stage"] != "cave_mouth_combat":
            raise ValueError("there is no active cave-mouth combat branch to resolve")
        encounter = self.runtime.encounters[state["cave_combat_encounter_id"]]
        forest_ids = self._forest_ids(state)
        player_ids = list(state["cave_combat_player_ids"])
        forest_defeated = all(
            not encounter.participants[actor_id].alive or encounter.participants[actor_id].hp <= 0
            for actor_id in forest_ids
        )
        player_defeated = all(
            not encounter.participants[actor_id].alive or encounter.participants[actor_id].hp <= 0
            for actor_id in player_ids
        )
        if forest_defeated:
            state["cave_combat_outcome"] = "forest_elf_pursuit_party_defeated"
            state["cave_combat_resolved_at_ms"] = self.runtime.world.now_ms
            state["stage"] = "standoff_resolved_forest_elves_defeated"
            return self.status(instance_id)
        if player_defeated:
            state["cave_combat_outcome"] = "selected_player_combatants_defeated"
            state["cave_combat_resolved_at_ms"] = self.runtime.world.now_ms
            state["stage"] = "cave_mouth_combat_player_side_defeated"
            return self.status(instance_id)
        raise ValueError("the cave-mouth encounter still has living combatants on both sides")

    def status(self, instance_id: str) -> dict:
        state = self._state(instance_id)
        payload = self.emergency.status(instance_id)
        stage = state["stage"]
        if stage == "responders_inside_cave_standoff":
            actions = ["offer_restitution", "surrender_local_representatives_to_custody", "start_cave_mouth_combat"]
        elif stage == "restitution_offered":
            actions = ["accept_restitution", "reject_restitution"]
        elif stage == "cave_mouth_combat":
            actions = ["ordinary_combat", "resolve_cave_mouth_combat"]
        else:
            actions = []
        outcomes = {
            "standoff_resolved_restitution": "restitution_accepted_by_local_pursuit_party",
            "standoff_resolved_custody": "materialized_representatives_in_sluva_custody",
            "standoff_resolved_forest_elves_defeated": "local_forest_elf_pursuit_party_defeated",
            "cave_mouth_combat_player_side_defeated": "selected_local_player_combatants_defeated",
        }
        payload["standoff_available_actions"] = actions
        payload["local_standoff_resolution"] = {
            "scope": payload["local_materialization"]["resolution_scope"],
            "outcome": outcomes.get(stage),
        }
        return payload


def install_floor8_cave_standoff_scenario(runtime, emergency) -> Floor8CaveStandoffScenario:
    for location_id in (
        FOREST_ELF_ESCAPE_CAVE,
        FOREST_ELF_ESCAPE_CAVE_MOUTH,
        FOREST_ELF_SACRED_WOODS,
        SLUVA,
    ):
        if location_id not in runtime.world_map.locations:
            raise RuntimeError(f"Floor 8 standoff world corpus is missing {location_id}")
    return Floor8CaveStandoffScenario(runtime, emergency)
