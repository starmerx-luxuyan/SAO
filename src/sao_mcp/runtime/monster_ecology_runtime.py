from __future__ import annotations

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
