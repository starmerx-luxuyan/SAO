from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from sao_mcp.corpus.canonical_timeline import (
    CANONICAL_TIMELINE_PROFILES,
    DEFAULT_CANONICAL_TIMELINE_PROFILE_ID,
    CanonicalMilestoneSeed,
    CanonicalTimelineProfile,
)
from sao_mcp.domain.models import WorldState


class CanonicalTimingStatus(StrEnum):
    PENDING = "pending"
    DUE = "due"
    OVERDUE = "overdue"
    EARLY = "early"
    ON_WINDOW = "on_window"
    LATE = "late"


@dataclass(slots=True)
class CanonicalMilestoneObservation:
    seed_id: str
    actual_at_ms: int
    details: dict[str, Any]


class CanonicalTimelineLedger:
    """A non-authoritative canon expectation overlay over the real world state."""

    def __init__(
        self,
        profile_id: str | None = DEFAULT_CANONICAL_TIMELINE_PROFILE_ID,
        *,
        anchor_world_ms: int = 0,
    ) -> None:
        self.profile_id: str | None = None
        self.anchor_world_ms = 0
        self.observations: dict[str, CanonicalMilestoneObservation] = {}
        self.select_profile(profile_id, anchor_world_ms=anchor_world_ms)

    @property
    def profile(self) -> CanonicalTimelineProfile | None:
        if self.profile_id is None:
            return None
        return CANONICAL_TIMELINE_PROFILES[self.profile_id]

    def select_profile(self, profile_id: str | None, *, anchor_world_ms: int = 0) -> None:
        if anchor_world_ms < 0:
            raise ValueError("canonical timeline anchor_world_ms must be >= 0")
        if profile_id is not None and profile_id not in CANONICAL_TIMELINE_PROFILES:
            raise KeyError(profile_id)
        self.profile_id = profile_id
        self.anchor_world_ms = int(anchor_world_ms)
        self.observations = {}

    def seed(self, seed_id: str) -> CanonicalMilestoneSeed:
        profile = self.profile
        if profile is None:
            raise ValueError("canonical timeline profile is disabled")
        return profile.seed(seed_id)

    def expected_window(self, seed_id: str) -> tuple[int, int]:
        seed = self.seed(seed_id)
        return (
            self.anchor_world_ms + seed.window_start_offset_ms,
            self.anchor_world_ms + seed.window_end_offset_ms,
        )

    def seed_for_floor_boss(self, floor_number: int) -> CanonicalMilestoneSeed | None:
        profile = self.profile
        if profile is None:
            return None
        subject = f"floor:{floor_number}"
        matches = [
            seed
            for seed in profile.seeds
            if seed.milestone_kind == "floor_boss_defeated" and seed.subject_id == subject
        ]
        if len(matches) > 1:
            raise RuntimeError(f"canonical profile has duplicate floor-boss seeds for floor {floor_number}")
        return matches[0] if matches else None

    def observe(
        self,
        seed_id: str,
        *,
        actual_at_ms: int,
        details: dict[str, Any] | None = None,
    ) -> CanonicalMilestoneObservation:
        if actual_at_ms < 0:
            raise ValueError("canonical milestone actual_at_ms must be >= 0")
        self.seed(seed_id)
        existing = self.observations.get(seed_id)
        if existing is not None:
            if existing.actual_at_ms != actual_at_ms:
                raise RuntimeError(
                    f"canonical milestone {seed_id} already observed at {existing.actual_at_ms}, "
                    f"not {actual_at_ms}"
                )
            return existing
        observation = CanonicalMilestoneObservation(
            seed_id=seed_id,
            actual_at_ms=int(actual_at_ms),
            details=dict(details or {}),
        )
        self.observations[seed_id] = observation
        return observation

    def reconcile_floor_bosses(self, world: WorldState) -> None:
        profile = self.profile
        if profile is None:
            return
        for seed in profile.seeds:
            if seed.milestone_kind != "floor_boss_defeated":
                continue
            prefix = "floor:"
            if not seed.subject_id.startswith(prefix):
                raise RuntimeError(f"invalid floor-boss canonical subject: {seed.subject_id}")
            floor_number = int(seed.subject_id[len(prefix):])
            floor = world.floors[floor_number]
            actual = floor.floor_boss_defeated_at_ms
            if actual is None:
                continue
            self.observe(
                seed.seed_id,
                actual_at_ms=int(actual),
                details={"floor_number": floor_number},
            )

    def timing_status(self, seed_id: str, *, now_ms: int) -> CanonicalTimingStatus:
        if now_ms < 0:
            raise ValueError("canonical timeline now_ms must be >= 0")
        start_ms, end_ms = self.expected_window(seed_id)
        observation = self.observations.get(seed_id)
        if observation is not None:
            if observation.actual_at_ms < start_ms:
                return CanonicalTimingStatus.EARLY
            if observation.actual_at_ms <= end_ms:
                return CanonicalTimingStatus.ON_WINDOW
            return CanonicalTimingStatus.LATE
        if now_ms < start_ms:
            return CanonicalTimingStatus.PENDING
        if now_ms <= end_ms:
            return CanonicalTimingStatus.DUE
        return CanonicalTimingStatus.OVERDUE

    def state(self, *, now_ms: int) -> dict[str, Any]:
        profile = self.profile
        if profile is None:
            return {
                "profile_id": None,
                "profile_name": None,
                "continuity": None,
                "anchor_world_ms": self.anchor_world_ms,
                "anchor_label": None,
                "milestones": [],
            }
        milestones = []
        for seed in profile.seeds:
            start_ms, end_ms = self.expected_window(seed.seed_id)
            observation = self.observations.get(seed.seed_id)
            milestones.append(
                {
                    "seed_id": seed.seed_id,
                    "milestone_kind": seed.milestone_kind,
                    "subject_id": seed.subject_id,
                    "calendar_date": seed.calendar_date,
                    "expected_window_start_ms": start_ms,
                    "expected_window_end_ms": end_ms,
                    "timing_status": self.timing_status(seed.seed_id, now_ms=now_ms).value,
                    "actual_at_ms": observation.actual_at_ms if observation is not None else None,
                    "observation_details": dict(observation.details) if observation is not None else {},
                    "provenance": asdict(seed.provenance),
                    "notes": seed.notes,
                }
            )
        return {
            "profile_id": profile.profile_id,
            "profile_name": profile.name,
            "continuity": profile.continuity,
            "anchor_world_ms": self.anchor_world_ms,
            "anchor_label": profile.anchor_label,
            "milestones": milestones,
        }

    def dump_state(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "anchor_world_ms": self.anchor_world_ms,
            "observations": {
                seed_id: asdict(observation)
                for seed_id, observation in self.observations.items()
            },
        }

    def load_state(self, payload: dict[str, Any]) -> None:
        if not payload:
            return
        profile_id = payload.get("profile_id")
        anchor_world_ms = int(payload.get("anchor_world_ms", 0))
        self.select_profile(profile_id, anchor_world_ms=anchor_world_ms)
        profile = self.profile
        for seed_id, row in payload.get("observations", {}).items():
            if profile is None:
                raise ValueError("disabled canonical timeline cannot load observations")
            if row.get("seed_id") != seed_id:
                raise ValueError("canonical timeline observation key disagrees with seed_id")
            self.observe(
                seed_id,
                actual_at_ms=int(row["actual_at_ms"]),
                details=dict(row.get("details", {})),
            )


def canonical_timeline_profile_catalog() -> list[dict[str, Any]]:
    return [
        {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "continuity": profile.continuity,
            "anchor_label": profile.anchor_label,
            "seed_ids": [seed.seed_id for seed in profile.seeds],
        }
        for profile in CANONICAL_TIMELINE_PROFILES.values()
    ]
