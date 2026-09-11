from pathlib import Path


def write(path: str, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor missing in {path}: {old[:160]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


write(
    "src/sao_mcp/rules/monster_ecology.py",
    '''from __future__ import annotations

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
''',
)

write(
    "src/sao_mcp/runtime/monster_ecology_runtime.py",
    '''from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.corpus.monsters import (
    AINCRAD_MONSTERS,
    AINCRAD_MONSTER_LOOT_TABLES,
    apply_aincrad_monster_drop_items,
)
from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.loot import roll_loot
from sao_mcp.rules.monster_ecology import (
    ECOLOGY_TICK_MS,
    MonsterSpeciesEcologyState,
    background_hunt_budget,
    population_risk_units,
    retreat_level_margin,
    spawn_profile,
)
from sao_mcp.rules.routing import shortest_route
from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime


MONSTER_ECOLOGY_SCHEMA = "monster-ecology.v1"


class MonsterEcologyAincradRuntime(EconomyLoopAincradRuntime):
    """Living monster populations, recovery, background hunting and danger pressure."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        apply_aincrad_monster_drop_items(self.catalog)
        self.monster_ecology: dict[str, MonsterSpeciesEcologyState] = {}
        self.monster_ecology_history: list[dict[str, Any]] = []
        self.monster_risk_debt: dict[str, float] = {}
        self.next_ecology_tick_at_ms = self.world.now_ms + ECOLOGY_TICK_MS
        self._reset_monster_ecology_state()
        self.register_defeat_hook(self._on_ecological_monster_defeat)
        self.register_world_advance_hook(self._resolve_due_monster_ecology)

    def _reset_monster_ecology_state(self) -> None:
        self.monster_ecology = {}
        for monster_id, definition in AINCRAD_MONSTERS.items():
            profile = spawn_profile(definition.tags)
            self.monster_ecology[monster_id] = MonsterSpeciesEcologyState(
                monster_id=monster_id,
                location_id=definition.location_id,
                carrying_capacity=profile.carrying_capacity,
                available_units=profile.carrying_capacity,
                recovery_interval_ms=profile.recovery_interval_ms,
                recovery_batch=profile.recovery_batch,
                next_recovery_at_ms=self.world.now_ms + profile.recovery_interval_ms,
            )
        self.monster_ecology_history = []
        self.monster_risk_debt = {}
        self.next_ecology_tick_at_ms = self.world.now_ms + ECOLOGY_TICK_MS

    def loot_table(self, table_id: str):
        if table_id in AINCRAD_MONSTER_LOOT_TABLES:
            return AINCRAD_MONSTER_LOOT_TABLES[table_id]
        return super().loot_table(table_id)

    def _record_ecology(self, event: str, *, at_ms: int | None = None, **fields: Any) -> None:
        self.monster_ecology_history.append(
            {"event": event, **fields, "at_ms": self.world.now_ms if at_ms is None else int(at_ms)}
        )

    def _ecology_actor_ids(
        self,
        *,
        monster_id: str | None = None,
        location_id: str | None = None,
        alive_only: bool = True,
    ) -> list[str]:
        rows = []
        for actor_id, actor in self.actors.items():
            ecology_id = actor.metadata.get("ecology_monster_id")
            if not ecology_id:
                continue
            if monster_id is not None and ecology_id != monster_id:
                continue
            if location_id is not None and actor.location_id != location_id:
                continue
            if alive_only and not actor.alive:
                continue
            rows.append(actor_id)
        return sorted(rows)

    def _reserved_units(self, monster_id: str) -> int:
        return len(self._ecology_actor_ids(monster_id=monster_id))

    def _live_units(self, monster_id: str) -> int:
        state = self.monster_ecology[monster_id]
        return state.available_units + self._reserved_units(monster_id)

    def materialize_ecological_monster(self, monster_id: str):
        definition = AINCRAD_MONSTERS[monster_id]
        floor = self.world.floors[definition.floor_number]
        if not floor.unlocked:
            raise ValueError("monster ecology floor is not unlocked")
        state = self.monster_ecology[monster_id]
        if state.available_units <= 0:
            raise ValueError("monster ecology population is depleted")
        state.reserve_materialization()
        actor = self._create_monster(
            name=definition.name,
            level=definition.level,
            location_id=definition.location_id,
            hp_factor=definition.hp_factor,
            loot_table_id=definition.loot_table_id,
            quest_kill_id=definition.quest_kill_id,
        )
        actor.metadata.update(
            {
                "ecology_monster_id": monster_id,
                "ecology_home_location_id": definition.location_id,
                "ecology_spawned_at_ms": self.world.now_ms,
            }
        )
        self._record_ecology(
            "monster_materialized",
            monster_id=monster_id,
            actor_id=actor.actor_id,
            location_id=definition.location_id,
            available_units=state.available_units,
        )
        return actor

    def release_ecological_monster(self, actor_id: str) -> None:
        actor = self.actors[actor_id]
        monster_id = actor.metadata.get("ecology_monster_id")
        if not monster_id:
            raise ValueError("actor is not an ecological monster")
        if not actor.alive:
            raise ValueError("defeated ecological monsters cannot be returned to the live population")
        if any(encounter.active and actor_id in encounter.participants for encounter in self.encounters.values()):
            raise ValueError("ecological monster cannot despawn from an active encounter")
        state = self.monster_ecology[str(monster_id)]
        state.return_materialized()
        self.actors.pop(actor_id)
        self._record_ecology(
            "monster_released",
            monster_id=monster_id,
            actor_id=actor_id,
            location_id=state.location_id,
            available_units=state.available_units,
        )

    def _ensure_wild_presence(self, location_id: str) -> str | None:
        location = self.world_map.locations[location_id]
        if location.safe_zone or not self.world.floors[location.floor_number].unlocked:
            return None
        existing = self._ecology_actor_ids(location_id=location_id)
        if existing:
            return existing[0]
        candidates = []
        for monster_id, state in self.monster_ecology.items():
            if state.location_id != location_id or state.available_units <= 0:
                continue
            definition = AINCRAD_MONSTERS[monster_id]
            profile = spawn_profile(definition.tags)
            if not profile.auto_materialize:
                continue
            candidates.append((definition.level, monster_id))
        if not candidates:
            return None
        _, monster_id = min(candidates)
        return self.materialize_ecological_monster(monster_id).actor_id

    def travel_actor(self, actor_id: str, destination_id: str):
        result = super().travel_actor(actor_id, destination_id)
        actor = self.actors[actor_id]
        if actor.kind is EntityKind.PLAYER and actor.alive and actor.location_id is not None:
            self._ensure_wild_presence(actor.location_id)
        return result

    def _on_ecological_monster_defeat(self, encounter, target, killer_id: str | None) -> None:
        monster_id = target.metadata.get("ecology_monster_id")
        if target.kind is not EntityKind.MONSTER or not monster_id:
            return
        state = self.monster_ecology[str(monster_id)]
        state.named_defeat()
        self._record_ecology(
            "named_monster_defeat",
            monster_id=monster_id,
            actor_id=target.actor_id,
            killer_id=killer_id,
            location_id=state.location_id,
            encounter_id=encounter.encounter_id,
            recent_kill_pressure=state.recent_kill_pressure,
        )

    def _recover_species(self, tick_ms: int) -> None:
        for monster_id, state in sorted(self.monster_ecology.items()):
            definition = AINCRAD_MONSTERS[monster_id]
            if not self.world.floors[definition.floor_number].unlocked:
                while state.next_recovery_at_ms <= tick_ms:
                    state.next_recovery_at_ms += state.recovery_interval_ms
                continue
            before = state.available_units
            added = state.advance_recovery_clock(
                tick_ms,
                reserved_units=self._reserved_units(monster_id),
            )
            if added:
                self._record_ecology(
                    "monster_population_recovered",
                    at_ms=tick_ms,
                    monster_id=monster_id,
                    location_id=state.location_id,
                    recovered_units=added,
                    available_before=before,
                    available_after=state.available_units,
                )

    def _background_hunt_location(self, location_id: str, tick_ms: int) -> None:
        location = self.world_map.locations[location_id]
        if location.safe_zone:
            return
        cohorts = sorted(self._settled_cohorts_at(location_id), key=lambda row: row.cohort_id)
        if not cohorts:
            return
        for cohort in cohorts:
            budget = background_hunt_budget(cohort.segment.value, cohort.headcount)
            if budget <= 0:
                continue
            kills: dict[str, int] = {}
            drops: dict[str, int] = {}
            for _ in range(budget):
                candidates = []
                for monster_id, state in self.monster_ecology.items():
                    if state.location_id != location_id or state.available_units <= 0:
                        continue
                    definition = AINCRAD_MONSTERS[monster_id]
                    tags = set(definition.tags)
                    if "field_boss" in tags or "rare_named_monster" in tags:
                        continue
                    if definition.level > cohort.average_level + 2.0:
                        continue
                    candidates.append((abs(definition.level - cohort.average_level), definition.level, monster_id))
                if not candidates:
                    break
                _, _, monster_id = min(candidates)
                state = self.monster_ecology[monster_id]
                definition = AINCRAD_MONSTERS[monster_id]
                state.background_defeat(1)
                kills[monster_id] = kills.get(monster_id, 0) + 1
                rolled = roll_loot(self.loot_table(definition.loot_table_id), self.rng)
                for drop in rolled.drops:
                    drops[drop.template_id] = drops.get(drop.template_id, 0) + drop.quantity
                    self.economy.record_external_supply(
                        location_id,
                        drop.template_id,
                        drop.quantity,
                        source=f"monster_ecology:{monster_id}",
                        at_ms=tick_ms,
                    )
            if kills:
                self._record_ecology(
                    "background_hunt",
                    at_ms=tick_ms,
                    cohort_id=cohort.cohort_id,
                    location_id=location_id,
                    kills=kills,
                    resource_drops=drops,
                )

    def _location_danger(self, location_id: str) -> dict[str, float | int]:
        rows = [
            (monster_id, state)
            for monster_id, state in self.monster_ecology.items()
            if state.location_id == location_id
        ]
        if not rows:
            return {
                "live_units": 0,
                "capacity": 0,
                "density_ratio": 0.0,
                "weighted_monster_level": 0.0,
            }
        live_units = 0
        capacity = 0
        level_sum = 0.0
        for monster_id, state in rows:
            live = self._live_units(monster_id)
            live_units += live
            capacity += state.carrying_capacity
            level_sum += AINCRAD_MONSTERS[monster_id].level * live
        return {
            "live_units": live_units,
            "capacity": capacity,
            "density_ratio": (live_units / capacity if capacity else 0.0),
            "weighted_monster_level": (level_sum / live_units if live_units else 0.0),
        }

    def _nearest_safe_location(self, origin_id: str) -> str | None:
        origin = self.world_map.locations[origin_id]
        choices = []
        for location_id, location in self.world_map.locations.items():
            if location.floor_number != origin.floor_number or not location.safe_zone:
                continue
            try:
                _, cost = shortest_route(self.world, self.world_map, origin_id, location_id)
            except ValueError:
                continue
            choices.append((cost, location_id))
        return min(choices)[1] if choices else None

    def _apply_population_danger(self, location_id: str, tick_ms: int) -> None:
        danger = self._location_danger(location_id)
        density = float(danger["density_ratio"])
        monster_level = float(danger["weighted_monster_level"])
        if density <= 0 or monster_level <= 0:
            return
        for cohort in sorted(self._settled_cohorts_at(location_id), key=lambda row: row.cohort_id):
            risk = population_risk_units(
                segment=cohort.segment.value,
                headcount=cohort.headcount,
                average_level=cohort.average_level,
                monster_level=monster_level,
                density_ratio=density,
            )
            debt = self.monster_risk_debt.get(cohort.cohort_id, 0.0) + risk
            deaths = min(cohort.headcount, int(debt))
            debt -= deaths
            if deaths:
                self.apply_population_losses(
                    cohort.cohort_id,
                    deaths,
                    cause=f"monster_ecology:{location_id}",
                )
                self._record_ecology(
                    "background_player_losses",
                    at_ms=tick_ms,
                    cohort_id=cohort.cohort_id,
                    location_id=location_id,
                    deaths=deaths,
                    monster_level=monster_level,
                    density_ratio=density,
                )
            if cohort.headcount <= 0:
                self.monster_risk_debt.pop(cohort.cohort_id, None)
                continue
            self.monster_risk_debt[cohort.cohort_id] = debt
            margin = retreat_level_margin(cohort.segment.value)
            if density < 0.45 or monster_level <= cohort.average_level + margin:
                continue
            if self._movement(cohort.cohort_id) is not None:
                continue
            destination = self._nearest_safe_location(location_id)
            if destination is None or destination == location_id:
                continue
            self.schedule_population_movement(
                cohort.cohort_id,
                destination,
                reason=f"monster_pressure:{location_id}",
            )
            self.monster_risk_debt.pop(cohort.cohort_id, None)
            self._record_ecology(
                "background_population_retreat",
                at_ms=tick_ms,
                cohort_id=cohort.cohort_id,
                from_location_id=location_id,
                target_location_id=destination,
                monster_level=monster_level,
                density_ratio=density,
            )

    def advance_monster_ecology_tick(self, tick_ms: int) -> None:
        if tick_ms != self.next_ecology_tick_at_ms:
            raise RuntimeError(
                f"monster ecology tick must resolve at its scheduled boundary: {tick_ms} != {self.next_ecology_tick_at_ms}"
            )
        if self.world.now_ms != tick_ms:
            raise RuntimeError("monster ecology tick must resolve at authoritative current world time")
        self._recover_species(tick_ms)
        active_locations = sorted(
            {
                state.location_id
                for monster_id, state in self.monster_ecology.items()
                if self.world.floors[AINCRAD_MONSTERS[monster_id].floor_number].unlocked
            }
        )
        for location_id in active_locations:
            self._background_hunt_location(location_id, tick_ms)
            self._apply_population_danger(location_id, tick_ms)
        for actor in sorted(self.actors.values(), key=lambda row: row.actor_id):
            if actor.kind is EntityKind.PLAYER and actor.alive and actor.location_id is not None:
                self._ensure_wild_presence(actor.location_id)
        self.next_ecology_tick_at_ms += ECOLOGY_TICK_MS
        self.assert_monster_ecology_authority()

    def _resolve_due_monster_ecology(self, before_ms: int, after_ms: int) -> None:
        while self.next_ecology_tick_at_ms <= after_ms:
            tick_ms = self.next_ecology_tick_at_ms
            if tick_ms != after_ms:
                raise RuntimeError("monster ecology tick boundary was skipped by world scheduler")
            self.advance_monster_ecology_tick(tick_ms)

    def _next_scheduler_boundary(self, target_ms: int) -> int:
        boundary = super()._next_scheduler_boundary(target_ms)
        now = self.world.now_ms
        if now < self.next_ecology_tick_at_ms <= target_ms:
            return min(boundary, self.next_ecology_tick_at_ms)
        return boundary

    def monster_ecology_location_state(self, location_id: str) -> dict[str, Any]:
        if location_id not in self.world_map.locations:
            raise KeyError(location_id)
        danger = self._location_danger(location_id)
        species = {}
        for monster_id, state in sorted(self.monster_ecology.items()):
            if state.location_id != location_id:
                continue
            definition = AINCRAD_MONSTERS[monster_id]
            row = asdict(state)
            row.update(
                {
                    "name": definition.name,
                    "level": definition.level,
                    "tags": list(definition.tags),
                    "materialized_actor_ids": self._ecology_actor_ids(monster_id=monster_id),
                    "live_units": self._live_units(monster_id),
                    "depletion_ratio": round(
                        1.0 - self._live_units(monster_id) / state.carrying_capacity,
                        6,
                    ),
                }
            )
            species[monster_id] = row
        return {
            "location_id": location_id,
            "floor_number": self.world_map.locations[location_id].floor_number,
            "safe_zone": self.world_map.locations[location_id].safe_zone,
            "danger": danger,
            "species": species,
            "background_population": self.population_location_state(location_id),
            "background_commodity_stock": dict(
                sorted(self.economy.background_commodity_stock.get(location_id, {}).items())
            ),
        }

    def monster_ecology_state(self, location_id: str | None = None) -> dict[str, Any]:
        self.assert_monster_ecology_authority()
        if location_id is not None:
            return {
                "world_now_ms": self.world.now_ms,
                "next_ecology_tick_at_ms": self.next_ecology_tick_at_ms,
                "tick_interval_ms": ECOLOGY_TICK_MS,
                "location": self.monster_ecology_location_state(location_id),
            }
        locations = sorted({state.location_id for state in self.monster_ecology.values()})
        return {
            "world_now_ms": self.world.now_ms,
            "next_ecology_tick_at_ms": self.next_ecology_tick_at_ms,
            "tick_interval_ms": ECOLOGY_TICK_MS,
            "locations": {
                location: self.monster_ecology_location_state(location)
                for location in locations
                if self.world.floors[self.world_map.locations[location].floor_number].unlocked
            },
        }

    def assert_monster_ecology_authority(self) -> None:
        if self.next_ecology_tick_at_ms <= self.world.now_ms:
            raise RuntimeError("monster ecology next tick must be in the future")
        if set(self.monster_ecology) != set(AINCRAD_MONSTERS):
            raise RuntimeError("monster ecology species registry disagrees with corpus")
        for monster_id, state in self.monster_ecology.items():
            definition = AINCRAD_MONSTERS[monster_id]
            profile = spawn_profile(definition.tags)
            if state.monster_id != monster_id or state.location_id != definition.location_id:
                raise RuntimeError(f"monster ecology identity mismatch: {monster_id}")
            if state.carrying_capacity != profile.carrying_capacity:
                raise RuntimeError(f"monster ecology capacity disagrees with spawn profile: {monster_id}")
            reserved = self._reserved_units(monster_id)
            if state.available_units + reserved > state.carrying_capacity:
                raise RuntimeError(f"monster ecology live population exceeds capacity: {monster_id}")
            if state.next_recovery_at_ms <= self.world.now_ms:
                raise RuntimeError(f"monster ecology recovery boundary is stale: {monster_id}")
        for actor in self.actors.values():
            monster_id = actor.metadata.get("ecology_monster_id")
            if not monster_id:
                continue
            if monster_id not in self.monster_ecology:
                raise RuntimeError(f"materialized monster references unknown ecology species: {monster_id}")
            if actor.metadata.get("ecology_home_location_id") != self.monster_ecology[str(monster_id)].location_id:
                raise RuntimeError("materialized ecology monster home disagrees with ecology state")
            if actor.alive and actor.location_id != self.monster_ecology[str(monster_id)].location_id:
                raise RuntimeError("living ecology monster left its authoritative ecology location")
        unknown_risk = set(self.monster_risk_debt) - set(self.population.cohorts)
        if unknown_risk:
            raise RuntimeError(f"monster ecology risk debt references unknown cohorts: {sorted(unknown_risk)}")
        if any(value < 0 for value in self.monster_risk_debt.values()):
            raise RuntimeError("monster ecology population risk debt cannot be negative")
        for row in self.monster_ecology_history:
            if int(row["at_ms"]) > self.world.now_ms:
                raise RuntimeError("monster ecology history cannot be in the future")

    def dump_monster_ecology_state(self) -> dict[str, Any]:
        self.assert_monster_ecology_authority()
        return {
            "schema": MONSTER_ECOLOGY_SCHEMA,
            "next_ecology_tick_at_ms": self.next_ecology_tick_at_ms,
            "species": {
                monster_id: asdict(state)
                for monster_id, state in self.monster_ecology.items()
            },
            "risk_debt": dict(self.monster_risk_debt),
            "history": list(self.monster_ecology_history),
        }

    def load_monster_ecology_state(self, payload: dict[str, Any]) -> None:
        if not payload:
            self._reset_monster_ecology_state()
            return
        if payload.get("schema") != MONSTER_ECOLOGY_SCHEMA:
            raise ValueError("unsupported non-empty monster ecology schema")
        species_payload = payload.get("species", {})
        if set(species_payload) != set(AINCRAD_MONSTERS):
            raise ValueError("monster ecology save species registry disagrees with current corpus")
        restored = {}
        for monster_id, row in species_payload.items():
            restored[monster_id] = MonsterSpeciesEcologyState(
                monster_id=row["monster_id"],
                location_id=row["location_id"],
                carrying_capacity=int(row["carrying_capacity"]),
                available_units=int(row["available_units"]),
                recovery_interval_ms=int(row["recovery_interval_ms"]),
                recovery_batch=int(row["recovery_batch"]),
                next_recovery_at_ms=int(row["next_recovery_at_ms"]),
                cumulative_background_kills=int(row.get("cumulative_background_kills", 0)),
                cumulative_named_kills=int(row.get("cumulative_named_kills", 0)),
                cumulative_recoveries=int(row.get("cumulative_recoveries", 0)),
                recent_kill_pressure=int(row.get("recent_kill_pressure", 0)),
                revision=int(row.get("revision", 0)),
            )
        next_tick = int(payload["next_ecology_tick_at_ms"])
        if next_tick <= self.world.now_ms:
            raise ValueError("monster ecology save next tick must be after current world time")
        self.monster_ecology = restored
        self.monster_risk_debt = {
            str(cohort_id): float(value) for cohort_id, value in payload.get("risk_debt", {}).items()
        }
        self.monster_ecology_history = list(payload.get("history", []))
        self.next_ecology_tick_at_ms = next_tick
        self.assert_monster_ecology_authority()
''',
)

write(
    "src/sao_mcp/server_ecology.py",
    '''from __future__ import annotations

import json
from dataclasses import asdict


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def register_monster_ecology_tools(mcp, runtime) -> None:
    @mcp.tool()
    def get_monster_ecology_state(location_id: str | None = None) -> str:
        """Inspect living monster density, depletion, recovery, danger and background resource supply."""
        return _json(runtime.monster_ecology_state(location_id))

    @mcp.tool()
    def get_monster_ecology_history(limit: int = 100) -> str:
        """Inspect recent monster recovery, hunting, materialization, losses and retreat events."""
        if limit < 1:
            raise ValueError("limit must be positive")
        return _json({"events": runtime.monster_ecology_history[-limit:]})

    @mcp.tool()
    def materialize_wild_monster(monster_id: str) -> str:
        """Materialize one real monster actor from the authoritative local ecology population."""
        actor = runtime.materialize_ecological_monster(monster_id)
        return _json(asdict(actor))

    @mcp.tool()
    def release_wild_monster(actor_id: str) -> str:
        """Return a living non-encounter ecological monster actor to its abstract local population."""
        runtime.release_ecological_monster(actor_id)
        return _json({"released": actor_id})
''',
)

# GameRuntime keeps transaction/loot resolution generic; ecology extends table lookup without mutating globals.
engine_path = "src/sao_mcp/runtime/engine.py"
replace_once(
    engine_path,
'''    def _grant_defeat_rewards(\n        self,\n        encounter: EncounterState,\n        target: CombatantState,\n        killer: CombatantState,\n    ) -> dict | None:\n        table_id = target.metadata.get("loot_table_id")\n        if not table_id or table_id not in CORE_LOOT_TABLES:\n            return None\n        rolled = roll_loot(CORE_LOOT_TABLES[table_id], self.rng)\n''',
'''    def loot_table(self, table_id: str):\n        return CORE_LOOT_TABLES[table_id]\n\n    def _grant_defeat_rewards(\n        self,\n        encounter: EncounterState,\n        target: CombatantState,\n        killer: CombatantState,\n    ) -> dict | None:\n        table_id = target.metadata.get("loot_table_id")\n        if not table_id:\n            return None\n        try:\n            table = self.loot_table(str(table_id))\n        except KeyError:\n            return None\n        rolled = roll_loot(table, self.rng)\n''',
)

# Economy gains a coarse anonymous commodity pool for background production such as monster drops.
economy_rules = "src/sao_mcp/rules/economy_loop.py"
replace_once(
    economy_rules,
    "    cumulative_system_restock_units: int = 0\n    cumulative_player_market_units: int = 0\n",
    "    cumulative_system_restock_units: int = 0\n    cumulative_ecology_supply_units: int = 0\n    cumulative_player_market_units: int = 0\n",
)
replace_once(
    economy_rules,
    "            self.cumulative_system_restock_units,\n            self.cumulative_player_market_units,\n",
    "            self.cumulative_system_restock_units,\n            self.cumulative_ecology_supply_units,\n            self.cumulative_player_market_units,\n",
)
replace_once(
    economy_rules,
'''    def record_player_market(self, *, units: int, gross_col: int) -> None:\n''',
'''    def record_ecology_supply(self, units: int) -> None:\n        if units <= 0:\n            raise ValueError("ecology market supply must be positive")\n        self.cumulative_ecology_supply_units += units\n        self.revision += 1\n\n    def record_player_market(self, *, units: int, gross_col: int) -> None:\n''',
)
replace_once(
    economy_rules,
    '        "cumulative_system_restock_units": region.cumulative_system_restock_units,\n        "cumulative_player_market_units": region.cumulative_player_market_units,\n',
    '        "cumulative_system_restock_units": region.cumulative_system_restock_units,\n        "cumulative_ecology_supply_units": region.cumulative_ecology_supply_units,\n        "cumulative_player_market_units": region.cumulative_player_market_units,\n',
)

property_path = "src/sao_mcp/runtime/property_economy.py"
replace_once(
    property_path,
'''        self.regional_markets: dict[str, RegionalMarketState] = {}\n        self.market_history: list[dict[str, Any]] = []\n''',
'''        self.regional_markets: dict[str, RegionalMarketState] = {}\n        self.background_commodity_stock: dict[str, dict[str, int]] = {}\n        self.market_history: list[dict[str, Any]] = []\n''',
)
replace_once(
    property_path,
'''        self.vendor_stocks = {}\n        self.regional_markets = {}\n''',
'''        self.vendor_stocks = {}\n        self.regional_markets = {}\n        self.background_commodity_stock = {}\n''',
)
replace_once(
    property_path,
'''    def vendor_quote(self, vendor_id: str, template_id: str) -> dict[str, Any]:\n''',
'''    def record_external_supply(\n        self,\n        location_id: str,\n        template_id: str,\n        units: int,\n        *,\n        source: str,\n        at_ms: int | None = None,\n    ) -> None:\n        if units <= 0:\n            raise ValueError("external market supply units must be positive")\n        if not source:\n            raise ValueError("external market supply source is required")\n        if location_id not in self.runtime.world_map.locations:\n            raise KeyError(location_id)\n        self.runtime.catalog.item(template_id)\n        stock = self.background_commodity_stock.setdefault(location_id, {})\n        stock[template_id] = stock.get(template_id, 0) + units\n        self._region(location_id).record_ecology_supply(units)\n        self._record_market(\n            "external_background_supply",\n            at_ms=at_ms,\n            location_id=location_id,\n            template_id=template_id,\n            units=units,\n            source=source,\n            stock_after=stock[template_id],\n        )\n\n    def vendor_quote(self, vendor_id: str, template_id: str) -> dict[str, Any]:\n''',
)
replace_once(
    property_path,
'''        locations = {\n            vendor.location_id for vendor in self.vendors.values()\n        } | {listing.location_id for listing in self.player_listings.values()}\n''',
'''        locations = (\n            {vendor.location_id for vendor in self.vendors.values()}\n            | {listing.location_id for listing in self.player_listings.values()}\n            | set(self.background_commodity_stock)\n        )\n''',
)
replace_once(
    property_path,
'''            demand_index, supply_index = regional_pressure(segment_totals, int(population["headcount"]))\n            region.set_pressure(demand_index, supply_index, tick_ms=tick_ms)\n\n            vendors = sorted(\n''',
'''            demand_index, supply_index = regional_pressure(segment_totals, int(population["headcount"]))\n            commodity_stock = self.background_commodity_stock.setdefault(location_id, {})\n            commodity_pressure = sum(commodity_stock.values())\n            if commodity_pressure:\n                supply_index = round(\n                    supply_index\n                    + min(1.0, commodity_pressure / max(50, int(population["headcount"]) or 1)),\n                    6,\n                )\n            region.set_pressure(demand_index, supply_index, tick_ms=tick_ms)\n\n            vendors = sorted(\n''',
)
replace_once(
    property_path,
'''            } | {\n                listing.item.template_id\n                for listing in self.player_listings.values()\n                if listing.location_id == location_id\n            }\n''',
'''            } | {\n                listing.item.template_id\n                for listing in self.player_listings.values()\n                if listing.location_id == location_id\n            } | set(commodity_stock)\n''',
)
replace_once(
    property_path,
'''            demand_remaining = {\n                template_id: max(0, units - sold_by_template.get(template_id, 0))\n                for template_id, units in demand_requested.items()\n            }\n\n            location_vendor_demand = 0\n''',
'''            demand_remaining = {\n                template_id: max(0, units - sold_by_template.get(template_id, 0))\n                for template_id, units in demand_requested.items()\n            }\n            commodity_units_by_template: dict[str, int] = {}\n            for template_id in sorted(demand_remaining):\n                available = commodity_stock.get(template_id, 0)\n                consumed = min(available, demand_remaining[template_id])\n                if consumed <= 0:\n                    continue\n                remaining_stock = available - consumed\n                if remaining_stock:\n                    commodity_stock[template_id] = remaining_stock\n                else:\n                    commodity_stock.pop(template_id, None)\n                demand_remaining[template_id] -= consumed\n                commodity_units_by_template[template_id] = consumed\n            commodity_units = sum(commodity_units_by_template.values())\n\n            location_vendor_demand = 0\n''',
)
replace_once(
    property_path,
'''            fulfilled_demand = market_units + location_vendor_demand\n''',
'''            fulfilled_demand = market_units + commodity_units + location_vendor_demand\n''',
)
replace_once(
    property_path,
'''                background_player_market_units=market_units,\n                background_player_market_col=market_col,\n                player_market_units_by_template=sold_by_template,\n''',
'''                background_player_market_units=market_units,\n                background_player_market_col=market_col,\n                player_market_units_by_template=sold_by_template,\n                background_commodity_units=commodity_units,\n                background_commodity_units_by_template=commodity_units_by_template,\n                background_commodity_stock_after=dict(sorted(commodity_stock.items())),\n''',
)
replace_once(
    property_path,
'''            "player_listings": listings,\n            "guild_headquarters": guilds,\n''',
'''            "player_listings": listings,\n            "background_commodity_stock": dict(\n                sorted(self.background_commodity_stock.get(location_id, {}).items())\n            ),\n            "guild_headquarters": guilds,\n''',
)
replace_once(
    property_path,
'''        for row in self.market_history:\n            if int(row["at_ms"]) > self.runtime.world.now_ms:\n                raise RuntimeError("economy history cannot be in the future")\n''',
'''        for location_id, stock in self.background_commodity_stock.items():\n            if location_id not in self.runtime.world_map.locations:\n                raise RuntimeError(f"background commodity stock references unknown location: {location_id}")\n            for template_id, units in stock.items():\n                self.runtime.catalog.item(template_id)\n                if units <= 0:\n                    raise RuntimeError("background commodity stock must remain positive")\n        for row in self.market_history:\n            if int(row["at_ms"]) > self.runtime.world.now_ms:\n                raise RuntimeError("economy history cannot be in the future")\n''',
)
replace_once(
    property_path,
'''                "market_history": list(self.market_history),\n''',
'''                "background_commodity_stock": {\n                    location_id: dict(stock)\n                    for location_id, stock in self.background_commodity_stock.items()\n                },\n                "market_history": list(self.market_history),\n''',
)
replace_once(
    property_path,
'''                cumulative_system_restock_units=int(row.get("cumulative_system_restock_units", 0)),\n                cumulative_player_market_units=int(row.get("cumulative_player_market_units", 0)),\n''',
'''                cumulative_system_restock_units=int(row.get("cumulative_system_restock_units", 0)),\n                cumulative_ecology_supply_units=int(row.get("cumulative_ecology_supply_units", 0)),\n                cumulative_player_market_units=int(row.get("cumulative_player_market_units", 0)),\n''',
)
replace_once(
    property_path,
'''        self.vendor_stocks = stocks\n        self.regional_markets = markets\n        self.market_history = list(payload.get("market_history", []))\n''',
'''        self.vendor_stocks = stocks\n        self.regional_markets = markets\n        self.background_commodity_stock = {\n            str(location_id): {str(template_id): int(units) for template_id, units in stock.items()}\n            for location_id, stock in payload.get("background_commodity_stock", {}).items()\n        }\n        self.market_history = list(payload.get("market_history", []))\n''',
)

# Persistence now restores the ecology top runtime and its exact coarse state.
persistence_path = "src/sao_mcp/runtime/persistence.py"
replace_once(
    persistence_path,
'''    population_dump = getattr(runtime, "dump_population_state", None)\n    world_event_dump = getattr(runtime, "dump_world_event_state", None)\n''',
'''    population_dump = getattr(runtime, "dump_population_state", None)\n    monster_ecology_dump = getattr(runtime, "dump_monster_ecology_state", None)\n    world_event_dump = getattr(runtime, "dump_world_event_state", None)\n''',
)
replace_once(
    persistence_path,
'''        "population_state": population_dump() if population_dump is not None else {},\n''',
'''        "population_state": population_dump() if population_dump is not None else {},\n        "monster_ecology_state": monster_ecology_dump() if monster_ecology_dump is not None else {},\n''',
)
replace_once(
    persistence_path,
'''        from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime\n        from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario\n\n        runtime: GameRuntime = EconomyLoopAincradRuntime()\n''',
'''        from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime\n        from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario\n\n        runtime: GameRuntime = MonsterEcologyAincradRuntime()\n''',
)
replace_once(
    persistence_path,
'''    economy.load_state(payload.get("economy_state", {}))\n\n    timeline_load = getattr(runtime, "load_timeline_state", None)\n''',
'''    economy.load_state(payload.get("economy_state", {}))\n    monster_ecology_load = getattr(runtime, "load_monster_ecology_state", None)\n    if monster_ecology_load is not None:\n        monster_ecology_load(payload.get("monster_ecology_state", {}))\n\n    timeline_load = getattr(runtime, "load_timeline_state", None)\n''',
)

# Server bootstrap advances the single-inheritance top runtime one layer and exposes ecology inspection.
bootstrap_path = "src/sao_mcp/server_bootstrap.py"
replace_once(
    bootstrap_path,
'''from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime\n''',
'''from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime\n''',
)
replace_once(
    bootstrap_path,
'''from sao_mcp.server_inventory import register_inventory_tools\nfrom sao_mcp.server_population import register_population_tools\n''',
'''from sao_mcp.server_inventory import register_inventory_tools\nfrom sao_mcp.server_ecology import register_monster_ecology_tools\nfrom sao_mcp.server_population import register_population_tools\n''',
)
replace_once(
    bootstrap_path,
'''if not isinstance(core_server.runtime, EconomyLoopAincradRuntime):\n    core_server.runtime = EconomyLoopAincradRuntime(seed=0xA1C0)\n''',
'''if not isinstance(core_server.runtime, MonsterEcologyAincradRuntime):\n    core_server.runtime = MonsterEcologyAincradRuntime(seed=0xA1C0)\n''',
)
replace_once(
    bootstrap_path,
'''register_population_tools(mcp, runtime)\nregister_gm_tools(mcp, gm_turn_executor)\n''',
'''register_population_tools(mcp, runtime)\nregister_monster_ecology_tools(mcp, runtime)\nregister_gm_tools(mcp, gm_turn_executor)\n''',
)

write(
    "tests/test_monster_ecology.py",
    '''import pytest

from sao_mcp.rules.monster_ecology import ECOLOGY_TICK_MS
from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


WEST = "floor_1_west_field"
TOWN = "floor_1_town_of_beginnings"
SCUTTLE = "floor_4_labyrinth"


def _unlock_through_floor(runtime: MonsterEcologyAincradRuntime, target_floor: int) -> None:
    for floor_number in range(1, target_floor):
        runtime.floor_boss_defeated(floor_number)
        runtime.advance_world(2 * ECOLOGY_TICK_MS)
        assert runtime.world.floors[floor_number + 1].unlocked


def test_player_arrival_materializes_wild_presence_without_manual_spawn():
    runtime = MonsterEcologyAincradRuntime(seed=701)
    player = runtime.create_character("Scout")
    assert runtime.monster_ecology_location_state(WEST)["danger"]["live_units"] > 0
    runtime.travel_actor(player.actor_id, WEST)
    state = runtime.monster_ecology_location_state(WEST)
    materialized = [
        actor_id
        for species in state["species"].values()
        for actor_id in species["materialized_actor_ids"]
    ]
    assert materialized
    assert all(runtime.actors[actor_id].alive for actor_id in materialized)
    assert all(runtime.actors[actor_id].location_id == WEST for actor_id in materialized)


def test_materialization_consumes_ecology_capacity_named_defeat_uses_corpus_loot_and_recovers():
    runtime = MonsterEcologyAincradRuntime(seed=702)
    player = runtime.create_character("Hunter")
    runtime.travel_actor(player.actor_id, WEST)
    state = runtime.monster_ecology["frenzy_boar"]
    total_before = runtime._live_units("frenzy_boar")
    boar = runtime.materialize_ecological_monster("frenzy_boar")
    assert runtime._live_units("frenzy_boar") == total_before
    boar.hp = 1
    boar.max_hp = max(boar.max_hp, 1)
    boar.evasion = 0
    player.skill_proficiencies["one_hand_sword"] = 1000
    before_col = player.col
    encounter = runtime.start_encounter([player.actor_id, boar.actor_id])
    result = runtime.attack(
        encounter.encounter_id,
        player.actor_id,
        boar.actor_id,
        defense="none",
        seed=1,
    )
    assert result.hit
    assert not boar.alive
    assert state.cumulative_named_kills == 1
    assert player.col > before_col
    depleted = runtime._live_units("frenzy_boar")
    assert depleted == total_before - 1
    runtime.advance_world(runtime.next_ecology_tick_at_ms - runtime.world.now_ms)
    assert runtime._live_units("frenzy_boar") == state.carrying_capacity
    assert state.cumulative_recoveries >= 1


def test_background_hunting_creates_real_ecology_drop_supply_for_economy():
    runtime = MonsterEcologyAincradRuntime(seed=703)
    _unlock_through_floor(runtime, 4)
    runtime.add_population_cohort(
        "f4_clearers",
        "frontline",
        120,
        SCUTTLE,
        20.0,
        "labyrinth_farming",
    )
    before = runtime.monster_ecology["scuttle_crab"].available_units
    runtime.advance_world(ECOLOGY_TICK_MS)
    after = runtime.monster_ecology["scuttle_crab"].available_units
    assert after < before
    stock = runtime.economy.background_commodity_stock[SCUTTLE]
    assert stock["great_crab_shell"] > 0
    market = runtime.aincrad_economy_state(SCUTTLE)["location"]["market"]
    assert market["cumulative_ecology_supply_units"] >= stock["great_crab_shell"]
    assert any(
        row["event"] == "background_hunt"
        and row["location_id"] == SCUTTLE
        and row["resource_drops"].get("great_crab_shell", 0) > 0
        for row in runtime.monster_ecology_history
    )


def test_monster_pressure_commits_population_losses_and_retreat_through_population_authority():
    runtime = MonsterEcologyAincradRuntime(seed=704)
    runtime.add_population_cohort(
        "field_casuals",
        "casual",
        1_000,
        WEST,
        1.0,
        "field_exploration",
    )
    runtime.advance_world(ECOLOGY_TICK_MS)
    cohort = runtime.population.cohorts["field_casuals"]
    assert cohort.headcount < 1_000
    movement = runtime.population_movement_state("field_casuals")
    assert movement is not None
    destination = runtime.world_map.locations[movement["target_location_id"]]
    assert destination.safe_zone
    assert any(
        row["event"] == "cohort_losses"
        and row["cohort_id"] == "field_casuals"
        and str(row["cause"]).startswith("monster_ecology:")
        for row in runtime.population_history
    )
    assert any(
        row["event"] == "background_population_retreat"
        and row["cohort_id"] == "field_casuals"
        for row in runtime.monster_ecology_history
    )


def test_background_commodity_supply_is_consumed_by_later_regional_demand_not_teleported():
    runtime = MonsterEcologyAincradRuntime(seed=705)
    _unlock_through_floor(runtime, 4)
    runtime.add_population_cohort(
        "f4_clearers",
        "frontline",
        140,
        SCUTTLE,
        20.0,
        "labyrinth_farming",
    )
    runtime.advance_world(ECOLOGY_TICK_MS)
    first_stock = runtime.economy.background_commodity_stock[SCUTTLE]["great_crab_shell"]
    assert first_stock > 0
    assert "great_crab_shell" not in runtime.economy.background_commodity_stock.get(TOWN, {})
    runtime.advance_world(ECOLOGY_TICK_MS)
    tick = next(
        row
        for row in reversed(runtime.economy.market_history)
        if row["event"] == "economy_tick" and row["location_id"] == SCUTTLE
    )
    assert tick["background_commodity_units"] >= 1
    assert tick["background_commodity_units_by_template"]["great_crab_shell"] >= 1


def test_monster_ecology_and_resource_stock_round_trip_exactly():
    runtime = MonsterEcologyAincradRuntime(seed=706)
    runtime.add_population_cohort("hunters", "frontline", 96, WEST, 5.0, "farming")
    runtime.advance_world(ECOLOGY_TICK_MS)
    before = runtime.monster_ecology_state(WEST)
    economy_before = runtime.aincrad_economy_state(WEST)
    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, MonsterEcologyAincradRuntime)
    assert restored.monster_ecology_state(WEST) == before
    assert restored.aincrad_economy_state(WEST) == economy_before
    assert restored.next_ecology_tick_at_ms == runtime.next_ecology_tick_at_ms


def test_release_ecological_monster_returns_one_live_unit_without_history_guessing():
    runtime = MonsterEcologyAincradRuntime(seed=707)
    before = runtime.monster_ecology["frenzy_boar"].available_units
    actor = runtime.materialize_ecological_monster("frenzy_boar")
    assert runtime.monster_ecology["frenzy_boar"].available_units == before - 1
    runtime.release_ecological_monster(actor.actor_id)
    assert actor.actor_id not in runtime.actors
    assert runtime.monster_ecology["frenzy_boar"].available_units == before
''',
)

write(
    "tests/test_monster_ecology_authority.py",
    '''from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.monster_ecology import MonsterSpeciesEcologyState
from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime
from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_monster_ecology_is_one_single_inheritance_layer_above_economy():
    assert MonsterEcologyAincradRuntime.__bases__ == (EconomyLoopAincradRuntime,)


def test_ecology_species_state_does_not_duplicate_materialized_actor_state_or_population():
    fields = set(MonsterSpeciesEcologyState.__dataclass_fields__)
    assert "reserved_units" not in fields
    assert "actor_id" not in fields
    assert "hp" not in fields
    assert "headcount" not in fields
    assert "inventory" not in fields


def test_scenarios_cannot_mutate_ecology_or_background_commodity_authorities_directly():
    forbidden = {
        "monster_ecology",
        "monster_risk_debt",
        "next_ecology_tick_at_ms",
        "advance_monster_ecology_tick",
        "materialize_ecological_monster",
        "background_commodity_stock",
        "record_external_supply",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []


def test_server_bootstrap_uses_monster_ecology_as_authoritative_top_runtime():
    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")
    assert "MonsterEcologyAincradRuntime" in source
    assert "EconomyLoopAincradRuntime(seed=0xA1C0)" not in source
    assert "register_monster_ecology_tools" in source


def test_ecology_server_exposes_inspection_and_authoritative_materialization_only():
    source = (ROOT / "src/sao_mcp/server_ecology.py").read_text(encoding="utf-8")
    assert "def get_monster_ecology_state" in source
    assert "def get_monster_ecology_history" in source
    assert "def materialize_wild_monster" in source
    assert "def release_wild_monster" in source
''',
)

# Existing bootstrap regression now locks the new top runtime while preserving economy inheritance.
server_test = "tests/test_server_bootstrap.py"
replace_once(
    server_test,
'''def test_full_server_uses_living_economy_loop_runtime():\n    from sao_mcp import server_bootstrap\n    from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime\n\n    assert isinstance(server_bootstrap.runtime, EconomyLoopAincradRuntime)\n    assert server_bootstrap.runtime.economy.next_tick_at_ms > server_bootstrap.runtime.world.now_ms\n''',
'''def test_full_server_uses_living_monster_ecology_runtime_over_economy_loop():\n    from sao_mcp import server_bootstrap\n    from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime\n    from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime\n\n    assert isinstance(server_bootstrap.runtime, MonsterEcologyAincradRuntime)\n    assert isinstance(server_bootstrap.runtime, EconomyLoopAincradRuntime)\n    assert server_bootstrap.runtime.economy.next_tick_at_ms > server_bootstrap.runtime.world.now_ms\n    assert server_bootstrap.runtime.next_ecology_tick_at_ms > server_bootstrap.runtime.world.now_ms\n''',
)
