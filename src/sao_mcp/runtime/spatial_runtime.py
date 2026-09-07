from __future__ import annotations

import math
from dataclasses import asdict

from sao_mcp.domain.models import DefenseMode, EntityKind
from sao_mcp.rules.spatial import (
    MovementResolution,
    actor_distance,
    default_formation,
    earliest_pending_execution_ms,
    movement_duration_ms,
    movement_speed_mps,
    validate_destination,
    validate_movement_ready,
)
from sao_mcp.runtime.aincrad_runtime import AincradRuntime


class SpatialAincradRuntime(AincradRuntime):
    """Aincrad runtime whose formal combat actions derive range from authoritative 2-D positions."""

    def start_encounter(self, actor_ids, *, zone_id="floor_1_west_field", safe_zone=None, anti_crystal=None):
        encounter = super().start_encounter(
            actor_ids,
            zone_id=zone_id,
            safe_zone=safe_zone,
            anti_crystal=anti_crystal,
        )
        encounter.arena_radius_m = 22.0 if zone_id.endswith("boss_room") else 30.0
        default_formation(encounter)
        return encounter

    def _spawn_boss_minions(self, encounter, boss, count, *, reason, bar_depletion=None):
        spawned = super()._spawn_boss_minions(
            encounter,
            boss,
            count,
            reason=reason,
            bar_depletion=bar_depletion,
        )
        if not spawned:
            return spawned
        boss_position = encounter.positions.get(boss.actor_id, (0.0, 0.0))
        base_angle = 0.9 + int(boss.metadata.get("boss_minions_spawned", 0)) * 0.37
        for index, actor_id in enumerate(spawned):
            angle = base_angle + index * (2 * math.pi / max(3, len(spawned)))
            encounter.positions[actor_id] = (
                round(boss_position[0] + math.cos(angle) * 2.2, 4),
                round(boss_position[1] + math.sin(angle) * 2.2, 4),
            )
        return spawned

    def encounter_distance(self, encounter_id: str, actor_id: str, target_id: str) -> float:
        return actor_distance(self.encounters[encounter_id], actor_id, target_id)

    def move_encounter_actor(
        self,
        encounter_id: str,
        actor_id: str,
        x: float,
        y: float,
    ) -> MovementResolution:
        encounter = self.encounters[encounter_id]
        if actor_id not in encounter.participants:
            raise ValueError("actor is not in this encounter")
        actor = encounter.participants[actor_id]
        if actor_id not in encounter.positions:
            default_formation(encounter)
        validate_movement_ready(actor, now_ms=encounter.time_ms)
        destination = (float(x), float(y))
        validate_destination(encounter, destination)
        origin = encounter.positions[actor_id]
        distance = actor_distance_between(origin, destination)
        elapsed = movement_duration_ms(actor, distance)
        deadline = earliest_pending_execution_ms(encounter)
        finish_at = encounter.time_ms + elapsed
        if deadline is not None:
            if deadline <= encounter.time_ms:
                raise ValueError("a pending boss telegraph is due and must resolve before movement")
            if finish_at > deadline:
                remaining_ms = max(0, deadline - encounter.time_ms)
                max_distance = movement_speed_mps(actor) * remaining_ms / 1000.0
                raise ValueError(
                    f"movement would finish after a pending boss telegraph resolves; "
                    f"remaining window permits about {max_distance:.2f} m"
                )
        if elapsed == 0:
            return MovementResolution(actor_id, origin, destination, 0.0, movement_speed_mps(actor), 0, True)

        actor.committed_until_ms = finish_at
        self._append(
            encounter,
            "movement_started",
            actor_id,
            actor_id,
            from_position=list(origin),
            to_position=list(destination),
            distance_m=round(distance, 4),
            speed_mps=round(movement_speed_mps(actor), 4),
            finish_at_ms=finish_at,
        )
        self._advance_encounter_to(encounter, finish_at)
        if not actor.alive:
            self._append(
                encounter,
                "movement_interrupted",
                actor_id,
                actor_id,
                reason="actor was defeated before movement completed",
            )
            return MovementResolution(
                actor_id,
                origin,
                origin,
                distance,
                movement_speed_mps(actor),
                elapsed,
                False,
                "actor was defeated before movement completed",
            )
        encounter.positions[actor_id] = destination
        self._append(
            encounter,
            "movement_completed",
            actor_id,
            actor_id,
            position=list(destination),
        )
        return MovementResolution(
            actor_id,
            origin,
            destination,
            distance,
            movement_speed_mps(actor),
            elapsed,
            True,
        )

    def attack_authoritative(
        self,
        encounter_id: str,
        attacker_id: str,
        target_id: str,
        *,
        sword_skill_id: str | None = None,
        defense: DefenseMode | str = DefenseMode.AUTO,
        seed: int | None = None,
    ):
        distance = self.encounter_distance(encounter_id, attacker_id, target_id)
        result = self.attack(
            encounter_id,
            attacker_id,
            target_id,
            sword_skill_id=sword_skill_id,
            defense=defense,
            distance_m=distance,
            seed=seed,
        )
        return result, distance

    def choose_boss_action(self, encounter_id: str, boss_id: str) -> dict:
        encounter = self.encounters[encounter_id]
        boss = encounter.participants[boss_id]
        phase = self.boss_phase(boss)
        players = [
            actor
            for actor in encounter.participants.values()
            if actor.kind is EntityKind.PLAYER and actor.alive and actor.actor_id in encounter.positions
        ]
        if not players:
            return {"actionId": None, "targetIds": [], "phaseId": phase.phase_id, "reason": "no living players"}
        threat = encounter.threat.get(boss_id, {})
        candidates = []
        for action_id in phase.action_ids:
            action = self._boss_action(boss, action_id)
            eligible = [
                actor for actor in players
                if self.encounter_distance(encounter_id, boss_id, actor.actor_id) <= action.reach_m
            ]
            if eligible:
                candidates.append((action, eligible))
        if not candidates:
            nearest = min(
                players,
                key=lambda actor: self.encounter_distance(encounter_id, boss_id, actor.actor_id),
            )
            return {
                "actionId": None,
                "targetIds": [],
                "phaseId": phase.phase_id,
                "approachTargetId": nearest.actor_id,
                "distanceM": round(self.encounter_distance(encounter_id, boss_id, nearest.actor_id), 4),
                "reason": "no player is inside the reach of any current boss action",
            }
        action, eligible = self.rng.choice(candidates)
        eligible.sort(key=lambda actor: threat.get(actor.actor_id, 0.0), reverse=True)
        selected = [actor.actor_id for actor in eligible[: max(1, min(action.max_targets, len(eligible)))]]
        return {
            "actionId": action.action_id,
            "targetIds": selected,
            "phaseId": phase.phase_id,
            "distancesM": {
                actor_id: round(self.encounter_distance(encounter_id, boss_id, actor_id), 4)
                for actor_id in selected
            },
        }

    def telegraph_boss_action(self, encounter_id: str, boss_id: str, action_id: str, target_ids):
        encounter = self.encounters[encounter_id]
        boss = encounter.participants[boss_id]
        action = self._boss_action(boss, action_id)
        for target_id in target_ids:
            if self.encounter_distance(encounter_id, boss_id, target_id) > action.reach_m:
                raise ValueError("boss cannot telegraph this action against a target outside its current reach")
        return super().telegraph_boss_action(encounter_id, boss_id, action_id, target_ids)

    def resolve_boss_action(self, encounter_id: str, boss_id: str, *, defenses=None, seed=None) -> dict:
        encounter = self.encounters[encounter_id]
        boss = encounter.participants[boss_id]
        pending = boss.metadata.get("pending_boss_action")
        if not pending:
            raise ValueError("boss has no pending telegraphed action")
        action = self._boss_action(boss, str(pending["action_id"]))
        original_targets = list(pending["target_ids"])
        in_range = []
        escaped = []
        for target_id in original_targets:
            target = encounter.participants.get(target_id)
            if target is None or not target.alive or target_id not in encounter.positions:
                continue
            distance = self.encounter_distance(encounter_id, boss_id, target_id)
            if distance <= action.reach_m:
                in_range.append(target_id)
            else:
                escaped.append((target_id, distance))
        pending["target_ids"] = in_range
        result = super().resolve_boss_action(
            encounter_id,
            boss_id,
            defenses=defenses,
            seed=seed,
        )
        escaped_rows = [
            {
                "targetId": target_id,
                "legal": False,
                "hit": False,
                "spatiallyEscaped": True,
                "distanceM": round(distance, 4),
                "reason": "target moved outside the telegraphed action reach before execution",
            }
            for target_id, distance in escaped
        ]
        if result.get("resolved"):
            result["targets"] = escaped_rows + list(result.get("targets", []))
            result["spatialEscapes"] = len(escaped_rows)
        return result

    def spatial_state(self, encounter_id: str) -> dict:
        encounter = self.encounters[encounter_id]
        rows = []
        for actor_id, position in encounter.positions.items():
            actor = encounter.participants.get(actor_id)
            if actor is None:
                continue
            rows.append(
                {
                    "actorId": actor_id,
                    "name": actor.name,
                    "kind": actor.kind.value,
                    "alive": actor.alive,
                    "x": position[0],
                    "y": position[1],
                    "movementSpeedMps": round(movement_speed_mps(actor), 4),
                }
            )
        return {
            "encounterId": encounter_id,
            "timeMs": encounter.time_ms,
            "arenaRadiusM": encounter.arena_radius_m,
            "actors": rows,
        }


def actor_distance_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])
