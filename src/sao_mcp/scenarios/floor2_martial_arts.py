from __future__ import annotations

from sao_mcp.corpus.floor2 import QUEST_ID, ROCK_SPLIT_TARGET
from sao_mcp.rules.quests import QuestObjectiveKind


HUT_ID = "floor_2_martial_arts_hut"
MARTIAL_ARTS_SKILL_ID = "martial_arts"
ROCK_HEIGHT_M = 2.0
ROCK_WIDTH_M = 1.5
ROCK_PROGRESS_REQUIRED = 2000.0  # Simulation: a low-floor STR build lands near Kirito's multi-day effort.


class Floor2MartialArtsScenario:
    """The unnamed Floor 2 rock-splitting quest that unlocks Martial Arts."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def _trials(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor2_martial_arts_trials", {})

    def start_trial(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != HUT_ID:
            raise ValueError("the Martial Arts quest starts at the mountain-top hut")
        self.runtime.accept_quest(actor_id, QUEST_ID)
        trial = self._trials().setdefault(
            actor_id,
            {
                "actor_id": actor_id,
                "started_at_ms": self.runtime.world.now_ms,
                "practice_hours": 0,
                "rock_progress": 0.0,
                "completed_at_ms": None,
            },
        )
        actor.metadata["martial_arts_whisker_paint"] = True
        return self.status(actor_id)

    def practice_palm_strikes(self, actor_id: str, hours: int = 1) -> dict:
        if hours <= 0:
            raise ValueError("practice hours must be positive")
        actor = self.runtime.actors[actor_id]
        if actor.location_id != HUT_ID:
            raise ValueError("rock practice takes place outside the Martial Arts master's hut")
        trial = self._trials().get(actor_id)
        if trial is None:
            raise ValueError("the Martial Arts rock trial has not been started")
        if trial["completed_at_ms"] is not None:
            return self.status(actor_id)

        elapsed_ms = hours * 60 * 60 * 1000
        self.runtime.advance_world(elapsed_ms)
        trial["practice_hours"] += hours
        trial["rock_progress"] = min(
            ROCK_PROGRESS_REQUIRED,
            float(trial["rock_progress"]) + actor.strength * hours,
        )

        if trial["rock_progress"] >= ROCK_PROGRESS_REQUIRED:
            self.runtime.quests.record_event(
                actor_id,
                kind=QuestObjectiveKind.DISCOVER,
                target_id=ROCK_SPLIT_TARGET,
            )
            unlocked = set(actor.metadata.get("unlocked_special_skills", ()))
            unlocked.add(MARTIAL_ARTS_SKILL_ID)
            actor.metadata["unlocked_special_skills"] = sorted(unlocked)
            actor.metadata.pop("martial_arts_whisker_paint", None)
            self.runtime.claim_quest(actor_id, QUEST_ID)
            trial["completed_at_ms"] = self.runtime.world.now_ms

        return self.status(actor_id)

    def status(self, actor_id: str) -> dict:
        trial = self._trials().get(actor_id)
        if trial is None:
            raise ValueError("the Martial Arts rock trial has not been started")
        actor = self.runtime.actors[actor_id]
        return {
            **trial,
            "rock_height_m": ROCK_HEIGHT_M,
            "rock_width_m": ROCK_WIDTH_M,
            "rock_progress_required": ROCK_PROGRESS_REQUIRED,
            "progress_ratio": float(trial["rock_progress"]) / ROCK_PROGRESS_REQUIRED,
            "whisker_paint": bool(actor.metadata.get("martial_arts_whisker_paint")),
            "martial_arts_unlocked": MARTIAL_ARTS_SKILL_ID
            in set(actor.metadata.get("unlocked_special_skills", ())),
        }


def install_floor2_martial_arts_scenario(runtime) -> Floor2MartialArtsScenario:
    return Floor2MartialArtsScenario(runtime)
