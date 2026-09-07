from __future__ import annotations

from sao_mcp.corpus.social_seed import apply_social_catalog_seed
from sao_mcp.domain.models import CursorColor, EntityKind
from sao_mcp.rules.duels import DuelMode, DuelRuntime
from sao_mcp.runtime.timeline_runtime import TimelineRaidAincradRuntime


REVIVAL_WINDOW_MS = 10_000
REVIVAL_HP_RATIO = 0.25  # Simulation recovery amount; the ~10 second activation window is canon-backed.


class SocialTimelineAincradRuntime(TimelineRaidAincradRuntime):
    """Timeline runtime with authorized duels, criminal-town access and SAO death End Phase."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        apply_social_catalog_seed(self.catalog)
        self.duels = DuelRuntime()

    def challenge_duel(self, challenger_id: str, target_id: str, mode: DuelMode | str):
        challenger = self.actors[challenger_id]
        target = self.actors[target_id]
        if challenger.location_id != target.location_id:
            raise ValueError("duel participants must be at the same world location")
        return self.duels.challenge(challenger, target, mode, now_ms=self.world.now_ms)

    def accept_duel(self, duel_id: str, target_id: str):
        duel = self.duels.duels[duel_id]
        challenger = self.actors[duel.challenger_id]
        target = self.actors[duel.target_id]
        if challenger.location_id != target.location_id or challenger.location_id is None:
            raise ValueError("duel participants must remain colocated when accepting")
        accepted = self.duels.accept(
            duel_id,
            challenger,
            target,
            accepter_id=target_id,
            now_ms=self.world.now_ms,
        )
        encounter = self.start_encounter(
            [challenger.actor_id, target.actor_id],
            zone_id=challenger.location_id,
        )
        self._append(
            encounter,
            "duel_started",
            challenger.actor_id,
            target.actor_id,
            duel_id=duel_id,
            mode=accepted.mode.value,
        )
        return accepted, encounter

    def decline_duel(self, duel_id: str, target_id: str):
        return self.duels.decline(duel_id, target_id=target_id)

    def resign_duel(self, duel_id: str, actor_id: str):
        evaluation = self.duels.resign(duel_id, actor_id, self.actors, now_ms=self.world.now_ms)
        for encounter in self.encounters.values():
            if actor_id in encounter.participants and evaluation.winner_id in encounter.participants:
                self._append(
                    encounter,
                    "duel_completed",
                    evaluation.winner_id,
                    evaluation.loser_id,
                    duel_id=duel_id,
                    reason=evaluation.reason,
                )
        return evaluation

    def _evaluate_duel_after_attack(self, encounter_id: str, attacker_id: str, target_id: str, result) -> None:
        if not result.legal:
            return
        duel = self.duels.active_between(attacker_id, target_id)
        if duel is None:
            return
        encounter = self.encounters[encounter_id]
        attacker = encounter.participants[attacker_id]
        target = encounter.participants[target_id]
        evaluation = self.duels.evaluate_attack(
            attacker,
            target,
            damage=result.damage if result.hit else 0,
            clean_hit=bool(result.hit and not result.guarded and not result.parried),
            now_ms=encounter.time_ms,
            actors=self.actors,
        )
        if evaluation and evaluation.completed:
            self._append(
                encounter,
                "duel_completed",
                evaluation.winner_id,
                evaluation.loser_id,
                duel_id=evaluation.duel_id,
                reason=evaluation.reason,
                mode=duel.mode.value,
            )

    def attack(self, encounter_id: str, attacker_id: str, target_id: str, **kwargs):
        encounter = self.encounters[encounter_id]
        duel = self.duels.active_between(attacker_id, target_id)
        if encounter.safe_zone and duel is None:
            return super().attack(encounter_id, attacker_id, target_id, **kwargs)
        if encounter.safe_zone and duel is not None:
            encounter.safe_zone = False
            try:
                result = super().attack(encounter_id, attacker_id, target_id, **kwargs)
            finally:
                encounter.safe_zone = True
        else:
            result = super().attack(encounter_id, attacker_id, target_id, **kwargs)
        self._evaluate_duel_after_attack(encounter_id, attacker_id, target_id, result)
        return result

    def queue_player_attack(self, encounter_id: str, attacker_id: str, target_id: str, **kwargs):
        encounter = self.encounters[encounter_id]
        if encounter.safe_zone and self.duels.active_between(attacker_id, target_id) is None:
            raise ValueError("safe-area PvP damage requires an accepted duel")
        return super().queue_player_attack(encounter_id, attacker_id, target_id, **kwargs)

    def _resolve_queued_attack(self, action):
        result = super()._resolve_queued_attack(action)
        resolution = result.get("resolution")
        if resolution and action.attacker_id in self.actors and action.target_id in self.actors:
            class ResultView:
                pass

            view = ResultView()
            for key, value in resolution.items():
                setattr(view, key, value)
            self._evaluate_duel_after_attack(action.encounter_id, action.attacker_id, action.target_id, view)
        return result

    def _resolve_defeat(self, encounter, target, killer_id):
        already = bool(target.metadata.get("defeat_resolved"))
        super()._resolve_defeat(encounter, target, killer_id)
        if already or target.kind is not EntityKind.PLAYER:
            return
        target.metadata["death_state"] = "end_phase"
        target.metadata["death_at_encounter_ms"] = encounter.time_ms
        target.metadata["revive_until_encounter_ms"] = encounter.time_ms + REVIVAL_WINDOW_MS
        target.metadata["permanent_death"] = False
        self._append(
            encounter,
            "player_death_end_phase_started",
            killer_id,
            target.actor_id,
            revive_until_ms=target.metadata["revive_until_encounter_ms"],
        )

    def _finalize_expired_deaths(self, encounter) -> None:
        for actor in encounter.participants.values():
            if actor.kind is not EntityKind.PLAYER or actor.metadata.get("death_state") != "end_phase":
                continue
            deadline = int(actor.metadata.get("revive_until_encounter_ms", -1))
            if deadline >= 0 and encounter.time_ms >= deadline:
                actor.metadata["death_state"] = "permanent"
                actor.metadata["permanent_death"] = True
                self._append(
                    encounter,
                    "player_death_finalized",
                    None,
                    actor.actor_id,
                    death_at_ms=actor.metadata.get("death_at_encounter_ms"),
                )

    def _advance_encounter_to(self, encounter, new_time_ms: int) -> None:
        super()._advance_encounter_to(encounter, new_time_ms)
        self._finalize_expired_deaths(encounter)

    def revive_recently_fallen(
        self,
        encounter_id: str,
        reviver_id: str,
        target_id: str,
        item_instance_id: str,
    ) -> dict:
        encounter = self.encounters[encounter_id]
        reviver = encounter.participants[reviver_id]
        target = encounter.participants[target_id]
        if not reviver.alive:
            raise ValueError("defeated players cannot use the revival item")
        if target.metadata.get("death_state") != "end_phase":
            raise ValueError("target is not in the revival End Phase")
        deadline = int(target.metadata.get("revive_until_encounter_ms", -1))
        if deadline < encounter.time_ms:
            self._finalize_expired_deaths(encounter)
            raise ValueError("revival window has expired")
        item = reviver.inventory[item_instance_id]
        if item.template_id != "divine_stone_returning_soul":
            raise ValueError("item is not the Divine Stone of Returning Soul")
        item.quantity -= 1
        if item.quantity <= 0:
            reviver.inventory.pop(item_instance_id, None)
        target.hp = max(1, int(round(target.max_hp * REVIVAL_HP_RATIO)))
        target.alive = True
        target.metadata.pop("death_state", None)
        target.metadata.pop("death_at_encounter_ms", None)
        target.metadata.pop("revive_until_encounter_ms", None)
        target.metadata["permanent_death"] = False
        target.metadata.pop("defeat_resolved", None)
        target.recovery_until_ms = max(target.recovery_until_ms, encounter.time_ms + 1200)
        self._append(
            encounter,
            "player_revived",
            reviver_id,
            target_id,
            item_template_id="divine_stone_returning_soul",
            hp_after=target.hp,
            recovery_until_ms=target.recovery_until_ms,
        )
        return {
            "reviverId": reviver_id,
            "targetId": target_id,
            "hp": target.hp,
            "maxHp": target.max_hp,
            "revivalHpRatio": REVIVAL_HP_RATIO,
            "provenance": {
                "window": "canon approximately ten seconds",
                "revivedHpRatio": "simulation calibration",
            },
        }

    def travel_actor(self, actor_id: str, destination_id: str):
        actor = self.actors[actor_id]
        destination = self.world_map.locations[destination_id]
        if actor.cursor is CursorColor.ORANGE and destination.safe_zone:
            raise ValueError("Anti-Criminal Code settlement access is blocked for Orange Players")
        return super().travel_actor(actor_id, destination_id)

    def teleport_actor(self, actor_id: str, crystal_instance_id: str, destination_id: str, **kwargs):
        actor = self.actors[actor_id]
        destination = self.world_map.locations[destination_id]
        if actor.cursor is CursorColor.ORANGE and destination.safe_zone:
            raise ValueError("Anti-Criminal Code settlement access is blocked for Orange Players")
        return super().teleport_actor(actor_id, crystal_instance_id, destination_id, **kwargs)

    def dump_duel_state(self) -> dict:
        return self.duels.dump_state()

    def load_duel_state(self, payload: dict) -> None:
        self.duels.load_state(payload, self.actors)
