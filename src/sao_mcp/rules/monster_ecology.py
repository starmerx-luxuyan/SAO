from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


ECOLOGY_TICK_MS = 60 * 60 * 1000


class MonsterSpawnClass(StrEnum):
    COMMON = "common"
    ELITE = "elite"
    RARE = "rare"
    BOSS = "boss"


@dataclass(slots=True, frozen=True)
class MonsterSpawnProfile:
    spawn_class: MonsterSpawnClass
    carrying_capacity: int
    recovery_interval_ms: int
    recovery_batch: int
    auto_materialize: bool


@dataclass(slots=True)
class MonsterSpeciesEcologyState:
    monster_id: str
    location_id: str
    carrying_capacity: int
    available_units: int
    recovery_interval_ms: int
    recovery_batch: int
    next_recovery_at_ms: int
    cumulative_background_kills: int = 0
    cumulative_named_kills: int = 0
    cumulative_recoveries: int = 0
    recent_kill_pressure: int = 0
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.monster_id or not self.location_id:
            raise ValueError("monster ecology state requires monster and location IDs")
        if self.carrying_capacity <= 0:
            raise ValueError("monster ecology carrying capacity must be positive")
        if not 0 <= self.available_units <= self.carrying_capacity:
            raise ValueError("monster ecology available units exceed carrying capacity")
        if self.recovery_interval_ms <= 0 or self.recovery_batch <= 0:
            raise ValueError("monster ecology recovery cadence must be positive")
        if self.next_recovery_at_ms < 0:
            raise ValueError("monster ecology recovery time cannot be negative")
        for value in (
            self.cumulative_background_kills,
            self.cumulative_named_kills,
            self.cumulative_recoveries,
            self.recent_kill_pressure,
            self.revision,
        ):
            if value < 0:
                raise ValueError("monster ecology counters cannot be negative")

    def reserve_materialization(self) -> None:
        if self.available_units <= 0:
            raise ValueError("monster ecology population is depleted")
        self.available_units -= 1
        self.revision += 1

    def return_materialized(self) -> None:
        if self.available_units >= self.carrying_capacity:
            raise RuntimeError("monster ecology return would exceed carrying capacity")
        self.available_units += 1
        self.revision += 1

    def background_defeat(self, count: int) -> None:
        if count <= 0:
            raise ValueError("background ecology defeat count must be positive")
        if count > self.available_units:
            raise ValueError("background ecology cannot defeat unavailable monsters")
        self.available_units -= count
        self.cumulative_background_kills += count
        self.recent_kill_pressure += count
        self.revision += 1

    def named_defeat(self) -> None:
        self.cumulative_named_kills += 1
        self.recent_kill_pressure += 1
        self.revision += 1

    def recover(self, *, reserved_units: int) -> int:
        if reserved_units < 0:
            raise ValueError("reserved ecology units cannot be negative")
        headroom = self.carrying_capacity - self.available_units - reserved_units
        if headroom <= 0:
            return 0
        added = min(headroom, self.recovery_batch)
        self.available_units += added
        self.cumulative_recoveries += added
        self.recent_kill_pressure = max(0, self.recent_kill_pressure - added)
        self.revision += 1
        return added

    def advance_recovery_clock(self, at_ms: int, *, reserved_units: int) -> int:
        recovered = 0
        while self.next_recovery_at_ms <= at_ms:
            recovered += self.recover(reserved_units=reserved_units)
            self.next_recovery_at_ms += self.recovery_interval_ms
        return recovered


def spawn_profile(tags: tuple[str, ...]) -> MonsterSpawnProfile:
    tagset = set(tags)
    if "field_boss" in tagset or "rare_named_monster" in tagset:
        return MonsterSpawnProfile(MonsterSpawnClass.BOSS, 1, 6 * ECOLOGY_TICK_MS, 1, False)
    if "rare" in tagset or "elusive" in tagset:
        return MonsterSpawnProfile(MonsterSpawnClass.RARE, 2, 4 * ECOLOGY_TICK_MS, 1, False)
    if "elite" in tagset:
        return MonsterSpawnProfile(MonsterSpawnClass.ELITE, 6, 2 * ECOLOGY_TICK_MS, 1, True)
    return MonsterSpawnProfile(MonsterSpawnClass.COMMON, 18, ECOLOGY_TICK_MS, 4, True)


def background_hunt_budget(segment: str, headcount: int) -> int:
    if headcount <= 0:
        return 0
    divisor = {
        "frontline": 24,
        "mid_tier": 55,
        "production": 140,
        "casual": 180,
    }[segment]
    return max(0, headcount // divisor)


def population_risk_units(
    *,
    segment: str,
    headcount: int,
    average_level: float,
    monster_level: float,
    density_ratio: float,
) -> float:
    if headcount <= 0 or monster_level <= 0 or density_ratio <= 0:
        return 0.0
    exposure = {
        "frontline": 0.20,
        "mid_tier": 0.45,
        "production": 0.80,
        "casual": 1.00,
    }[segment]
    gap = monster_level - average_level
    if gap >= 0:
        level_factor = 1.0 + gap * 0.35
    else:
        level_factor = max(0.20, 1.0 + gap * 0.10)
    return max(0.0, headcount * exposure * density_ratio * level_factor / 1000.0)


def retreat_level_margin(segment: str) -> float:
    return {
        "frontline": 5.0,
        "mid_tier": 3.0,
        "production": 1.5,
        "casual": 1.0,
    }[segment]
