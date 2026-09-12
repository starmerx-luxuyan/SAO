from __future__ import annotations

import random
import uuid
from dataclasses import asdict, replace

from sao_mcp.domain.models import DefenseMode, EntityKind
from sao_mcp.rules.combat import DEFAULT_TUNING, AttackResolution, effective_attack_speed_ms, resolve_physical_attack
from sao_mcp.rules.inventory import recompute_equipment_stats
from sao_mcp.rules.progression import gain_skill_proficiency
from sao_mcp.rules.progression_effects import (
    normal_attack_modifiers,
    refresh_weapon_enhancement_caps,
    weapon_proficiency_key,
    weapon_proficiency_value,
)
from sao_mcp.rules.social import apply_unlawful_hostile_action
from sao_mcp.rules.spatial import earliest_pending_execution_ms
from sao_mcp.rules.timeline import QueuedPlayerAttack
from sao_mcp.runtime.raid_spatial_runtime import RaidSpatialAincradRuntime


class TimelineRaidAincradRuntime(RaidSpatialAincradRuntime):
    """Raid/spatial runtime with persistent player actions ordered against Boss telegraphs."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.queued_player_attacks: dict[str, list[QueuedPlayerAttack]] = {}
        self._timeline_sequence = 0

    def _queue(self, encounter_id: str) -> list[QueuedPlayerAttack]:
        return self.queued_player_attacks.setdefault(encounter_id, [])

    def _attack_timing(self, attacker_id: str, sword_skill_id: str | None) -> tuple[int, int]:
        attacker = self.actors[attacker_id]
        weapon_item, weapon = self._equipped_weapon(attacker)
        if sword_skill_id:
            skill = self.catalog.sword_skills[sword_skill_id]
            return max(1, skill.windup_ms + skill.active_ms), max(0, skill.post_motion_ms)
        _, recovery_multiplier = normal_attack_modifiers(attacker, weapon.weapon_class)
        return (
            effective_attack_speed_ms(weapon, weapon_item),
            int(round(DEFAULT_TUNING.base_normal_post_motion_ms * recovery_multiplier)),
        )

    def _validate_queue_attack(
        self,
        encounter_id: str,
        attacker_id: str,
        target_id: str,
        sword_skill_id: str | None,
    ) -> tuple[float, int]:
        encounter = self.encounters[encounter_id]
        if attacker_id not in encounter.participants or target_id not in encounter.participants:
            raise ValueError("attacker and target must both be in the encounter")
        attacker = encounter.participants[attacker_id]
        target = encounter.participants[target_id]
        if not attacker.alive:
            raise ValueError("attacker is defeated")
        if not target.alive:
            raise ValueError("target is defeated")
        if attacker_id == target_id:
            raise ValueError("self-targeted physical attack is unsupported")
        if encounter.time_ms < attacker.committed_until_ms or encounter.time_ms < attacker.recovery_until_ms:
            raise ValueError("attacker is still committed or recovering")
        if any(row.attacker_id == attacker_id for row in self._queue(encounter_id)):
            raise ValueError("attacker already has a queued timeline action")

        weapon_item, weapon = self._equipped_weapon(attacker)
        if weapon_item.broken:
            raise ValueError("equipped weapon is broken")
        if attacker.level < weapon.required_level or attacker.strength < weapon.required_strength:
            raise ValueError("weapon requirements are not met")
        skill = self.catalog.sword_skills.get(sword_skill_id) if sword_skill_id else None
        if sword_skill_id and skill is None:
            raise KeyError(sword_skill_id)
        if skill is not None:
            if skill.weapon_class is not weapon.weapon_class:
                raise ValueError("Sword Skill is incompatible with the equipped weapon")
            proficiency = weapon_proficiency_value(attacker, weapon.weapon_class, sword_skill=skill)
            if proficiency < skill.prerequisite_proficiency:
                raise ValueError("Sword Skill proficiency prerequisite is not met")
        distance = self.encounter_distance(encounter_id, attacker_id, target_id)
        reach = weapon.reach_m + (skill.lunge_m if skill else 0.0)
        if distance > reach:
            raise ValueError(f"target is outside attack reach ({distance:.2f} m > {reach:.2f} m)")
        duration, _ = self._attack_timing(attacker_id, sword_skill_id)
        return distance, duration

    def queue_player_attack(
        self,
        encounter_id: str,
        attacker_id: str,
        target_id: str,
        *,
        sword_skill_id: str | None = None,
        defense: DefenseMode | str = DefenseMode.AUTO,
        seed: int | None = None,
    ) -> QueuedPlayerAttack:
        encounter = self.encounters[encounter_id]
        deadline = earliest_pending_execution_ms(encounter)
        if deadline is not None and deadline <= encounter.time_ms:
            raise ValueError("a pending Boss telegraph is already due and must resolve first")
        distance, duration = self._validate_queue_attack(encounter_id, attacker_id, target_id, sword_skill_id)
        self._timeline_sequence += 1
        action = QueuedPlayerAttack(
            action_id=f"timeline_{uuid.uuid4().hex[:12]}",
            encounter_id=encounter_id,
            attacker_id=attacker_id,
            target_id=target_id,
            sword_skill_id=sword_skill_id,
            defense=DefenseMode(defense).value,
            started_at_ms=encounter.time_ms,
            impact_at_ms=encounter.time_ms + duration,
            seed=int(seed if seed is not None else self.rng.randrange(0, 2**63)),
            start_distance_m=distance,
            sequence=self._timeline_sequence,
        )
        self._queue(encounter_id).append(action)
        attacker = encounter.participants[attacker_id]
        attacker.committed_until_ms = action.impact_at_ms
        attacker.metadata["timeline_action_id"] = action.action_id
        self._append(
            encounter,
            "timeline_attack_started",
            attacker_id,
            target_id,
            action_id=action.action_id,
            sword_skill=sword_skill_id,
            impact_at_ms=action.impact_at_ms,
            start_distance_m=round(distance, 4),
        )
        return action

    def attack_or_queue_authoritative(
        self,
        encounter_id: str,
        attacker_id: str,
        target_id: str,
        *,
        sword_skill_id: str | None = None,
        defense: DefenseMode | str = DefenseMode.AUTO,
        seed: int | None = None,
    ) -> dict:
        encounter = self.encounters[encounter_id]
        distance, duration = self._validate_queue_attack(encounter_id, attacker_id, target_id, sword_skill_id)
        deadline = earliest_pending_execution_ms(encounter)
        if deadline is not None and deadline <= encounter.time_ms:
            return {
                "queued": False,
                "resolution": AttackResolution(False, reason="a pending Boss telegraph is due and must resolve first"),
                "distance": distance,
            }
        if deadline is not None and encounter.time_ms + duration > deadline:
            action = self.queue_player_attack(
                encounter_id,
                attacker_id,
                target_id,
                sword_skill_id=sword_skill_id,
                defense=defense,
                seed=seed,
            )
            return {"queued": True, "action": action, "distance": distance}
        resolution, distance = super().attack_authoritative(
            encounter_id,
            attacker_id,
            target_id,
            sword_skill_id=sword_skill_id,
            defense=defense,
            seed=seed,
        )
        return {"queued": False, "resolution": resolution, "distance": distance}

    def _interrupt_actor_actions(self, encounter_id: str, actor_id: str, reason: str) -> int:
        interrupted = 0
        for action in self._queue(encounter_id):
            if action.attacker_id == actor_id and action.interrupted_reason is None:
                action.interrupted_reason = reason
                interrupted += 1
        return interrupted

    def _remove_action(self, encounter_id: str, action: QueuedPlayerAttack) -> None:
        queue = self._queue(encounter_id)
        if action in queue:
            queue.remove(action)
        actor = self.actors.get(action.attacker_id)
        if actor and actor.metadata.get("timeline_action_id") == action.action_id:
            actor.metadata.pop("timeline_action_id", None)

    def _resolve_queued_attack(self, action: QueuedPlayerAttack) -> dict:
        encounter = self.encounters[action.encounter_id]
        attacker = encounter.participants.get(action.attacker_id)
        target = encounter.participants.get(action.target_id)
        if attacker is None or target is None:
            self._remove_action(action.encounter_id, action)
            return {"event": "player_attack", "resolved": False, "actionId": action.action_id, "reason": "actor left encounter"}
        if action.interrupted_reason or not attacker.alive:
            reason = action.interrupted_reason or "attacker was defeated"
            attacker.committed_until_ms = min(attacker.committed_until_ms, encounter.time_ms)
            self._append(encounter, "timeline_attack_interrupted", attacker.actor_id, target.actor_id, action_id=action.action_id, reason=reason)
            self._remove_action(action.encounter_id, action)
            return {"event": "player_attack", "resolved": False, "interrupted": True, "actionId": action.action_id, "reason": reason}
        if not target.alive:
            attacker.committed_until_ms = encounter.time_ms
            self._append(encounter, "timeline_attack_cancelled", attacker.actor_id, target.actor_id, action_id=action.action_id, reason="target was defeated before impact")
            self._remove_action(action.encounter_id, action)
            return {"event": "player_attack", "resolved": False, "actionId": action.action_id, "reason": "target was defeated before impact"}

        old_hp = target.hp
        weapon_item, weapon = self._equipped_weapon(attacker)
        skill = self.catalog.sword_skills.get(action.sword_skill_id) if action.sword_skill_id else None
        distance = self.encounter_distance(action.encounter_id, attacker.actor_id, target.actor_id)
        raw = resolve_physical_attack(
            attacker,
            target,
            weapon_item,
            weapon,
            now_ms=encounter.time_ms,
            rng=random.Random(action.seed),
            sword_skill=skill,
            defense=DefenseMode(action.defense),
            distance_m=distance,
        )
        _, post_motion = self._attack_timing(attacker.actor_id, action.sword_skill_id)
        resolution = replace(
            raw,
            action_end_ms=encounter.time_ms,
            recovery_end_ms=encounter.time_ms + post_motion,
        )
        attacker.committed_until_ms = encounter.time_ms
        attacker.recovery_until_ms = resolution.recovery_end_ms

        if not resolution.legal:
            self._append(
                encounter,
                "timeline_attack_whiffed",
                attacker.actor_id,
                target.actor_id,
                action_id=action.action_id,
                reason=resolution.reason,
                impact_distance_m=round(distance, 4),
            )
            self._remove_action(action.encounter_id, action)
            return {
                "event": "player_attack",
                "resolved": True,
                "actionId": action.action_id,
                "resolution": asdict(resolution),
                "impactDistanceM": distance,
            }

        apply_unlawful_hostile_action(attacker, target, safe_zone=encounter.safe_zone)
        before_weapon = weapon_item.durability
        if weapon_item.durability is not None:
            weapon_item.durability = max(0, weapon_item.durability - resolution.attacker_durability_loss)

        if resolution.hit:
            target.hp = max(0, target.hp - resolution.damage)
            target.alive = target.hp > 0
            if resolution.stagger_ms:
                target.recovery_until_ms = max(target.recovery_until_ms, encounter.time_ms + resolution.stagger_ms)
            body_id = target.equipment.get("body")
            if body_id and body_id in target.inventory:
                body = target.inventory[body_id]
                before_body = body.durability
                if body.durability is not None:
                    body.durability = max(0, body.durability - resolution.defender_durability_pressure)
                if before_body and body.durability == 0:
                    recompute_equipment_stats(target, self.catalog)
                    self._append(encounter, "equipment_broken", target.actor_id, target.actor_id, instance_id=body_id)
            if target.kind in (EntityKind.MONSTER, EntityKind.BOSS):
                table = encounter.threat.setdefault(target.actor_id, {})
                table[attacker.actor_id] = table.get(attacker.actor_id, 0.0) + resolution.threat_generated
            encounter.last_attacker_by_target[target.actor_id] = attacker.actor_id
            encounter.last_attack_time_by_target[target.actor_id] = encounter.time_ms
            proficiency_key = weapon_proficiency_key(attacker, weapon.weapon_class, sword_skill=skill)
            gain_skill_proficiency(attacker, proficiency_key, 2.4 if action.sword_skill_id else 1.0, catalog=self.catalog)
            refresh_weapon_enhancement_caps(attacker, self.catalog)

        self._append(
            encounter,
            "timeline_attack_resolved",
            attacker.actor_id,
            target.actor_id,
            action_id=action.action_id,
            hit=resolution.hit,
            critical=resolution.critical,
            parried=resolution.parried,
            guarded=resolution.guarded,
            evaded=resolution.evaded,
            damage=resolution.damage,
            sword_skill=action.sword_skill_id,
            impact_distance_m=round(distance, 4),
            weapon_durability=weapon_item.durability,
        )
        if before_weapon and weapon_item.durability == 0:
            self._append(encounter, "equipment_broken", attacker.actor_id, attacker.actor_id, instance_id=weapon_item.instance_id)
        if resolution.hit and target.kind is EntityKind.BOSS and "boss_definition_id" in target.metadata:
            self._process_boss_hp_transition(encounter, target, old_hp)
        if not target.alive:
            self._resolve_defeat(encounter, target, attacker.actor_id)
        self._remove_action(action.encounter_id, action)
        return {
            "event": "player_attack",
            "resolved": True,
            "actionId": action.action_id,
            "resolution": asdict(resolution),
            "impactDistanceM": distance,
            "targetHp": target.hp,
        }

    def _pending_boss_events(self, encounter_id: str) -> list[tuple[int, str]]:
        encounter = self.encounters[encounter_id]
        rows: list[tuple[int, str]] = []
        for actor in encounter.participants.values():
            pending = actor.metadata.get("pending_boss_action")
            if actor.kind is EntityKind.BOSS and pending and "execute_at_ms" in pending:
                rows.append((int(pending["execute_at_ms"]), actor.actor_id))
        return rows

    def process_next_timeline_event(self, encounter_id: str) -> dict:
        encounter = self.encounters[encounter_id]
        queued = sorted(self._queue(encounter_id), key=lambda row: (row.impact_at_ms, row.sequence))
        boss_events = sorted(self._pending_boss_events(encounter_id))
        next_player = queued[0] if queued else None
        next_boss = boss_events[0] if boss_events else None
        if next_player is None and next_boss is None:
            return {"processed": False, "reason": "timeline has no pending events", "timeMs": encounter.time_ms}

        player_time = next_player.impact_at_ms if next_player else 2**63 - 1
        boss_time = next_boss[0] if next_boss else 2**63 - 1
        if boss_time <= player_time:
            if encounter.time_ms < boss_time:
                self._advance_encounter_to(encounter, boss_time)
            boss_id = next_boss[1]
            result = super().resolve_boss_action(encounter_id, boss_id)
            for row in result.get("targets", ()):
                if row.get("hit") and row.get("targetId"):
                    self._interrupt_actor_actions(
                        encounter_id,
                        str(row["targetId"]),
                        f"Boss action {result.get('actionId', 'unknown')} connected during action wind-up",
                    )
            return {"processed": True, "event": "boss_action", "bossId": boss_id, "result": result, "timeMs": encounter.time_ms}

        if encounter.time_ms < next_player.impact_at_ms:
            self._advance_encounter_to(encounter, next_player.impact_at_ms)
        result = self._resolve_queued_attack(next_player)
        return {"processed": True, **result, "timeMs": encounter.time_ms}

    def timeline_state(self, encounter_id: str) -> dict:
        encounter = self.encounters[encounter_id]
        return {
            "encounterId": encounter_id,
            "timeMs": encounter.time_ms,
            "queuedPlayerAttacks": [row.dump() for row in sorted(self._queue(encounter_id), key=lambda x: (x.impact_at_ms, x.sequence))],
            "bossEvents": [
                {"executeAtMs": when, "bossId": boss_id}
                for when, boss_id in sorted(self._pending_boss_events(encounter_id))
            ],
        }

    def dump_timeline_state(self) -> dict:
        return {
            "sequence": self._timeline_sequence,
            "queued_player_attacks": {
                encounter_id: [row.dump() for row in rows]
                for encounter_id, rows in self.queued_player_attacks.items()
                if rows
            },
        }

    def load_timeline_state(self, payload: dict) -> None:
        self._timeline_sequence = int(payload.get("sequence", 0))
        self.queued_player_attacks = {
            encounter_id: [QueuedPlayerAttack.load(row) for row in rows]
            for encounter_id, rows in payload.get("queued_player_attacks", {}).items()
        }
