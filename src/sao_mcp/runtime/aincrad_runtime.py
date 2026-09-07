from __future__ import annotations

import random
import uuid
from dataclasses import asdict
from typing import Iterable

from sao_mcp.corpus.bosses import (
    CORE_BOSS_ACTIONS,
    CORE_BOSS_MINIONS,
    CORE_BOSSES,
    BossActionDefinition,
    BossDefinition,
    BossPhaseDefinition,
    apply_boss_catalog_seed,
)
from sao_mcp.domain.models import (
    CombatantState,
    CursorColor,
    DefenseMode,
    EntityKind,
    EnhancementTrack,
    ItemInstance,
    SwordSkillDefinition,
)
from sao_mcp.rules.combat import AttackResolution, resolve_physical_attack
from sao_mcp.rules.inventory import add_item, recompute_equipment_stats
from sao_mcp.runtime.engine import GameRuntime


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class AincradRuntime(GameRuntime):
    """GameRuntime plus generic multi-bar boss phases, reinforcements, telegraphs and Last Attack flow."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        apply_boss_catalog_seed(self.catalog)

    def boss_definition(self, boss: CombatantState | str) -> BossDefinition:
        actor = self.actors[boss] if isinstance(boss, str) else boss
        definition_id = actor.metadata.get("boss_definition_id")
        if not definition_id or definition_id not in CORE_BOSSES:
            raise ValueError("actor is not a registered floor boss")
        return CORE_BOSSES[str(definition_id)]

    def boss_phase(self, boss: CombatantState | str) -> BossPhaseDefinition:
        actor = self.actors[boss] if isinstance(boss, str) else boss
        definition = self.boss_definition(actor)
        phase_id = actor.metadata.get("boss_phase_id", definition.phases[0].phase_id)
        return next(phase for phase in definition.phases if phase.phase_id == phase_id)

    def boss_bar_state(self, boss: CombatantState | str) -> dict:
        actor = self.actors[boss] if isinstance(boss, str) else boss
        definition = self.boss_definition(actor)
        bar_hp = definition.hp_per_bar
        damage = max(0, actor.max_hp - actor.hp)
        bars = []
        for index in range(definition.hp_bars):
            consumed = max(0, damage - index * bar_hp)
            hp = max(0, min(bar_hp, bar_hp - consumed))
            bars.append(
                {
                    "index": index + 1,
                    "hp": hp,
                    "maxHp": bar_hp,
                    "ratio": hp / bar_hp if bar_hp else 0.0,
                    "depleted": hp <= 0,
                }
            )
        depleted = min(definition.hp_bars, damage // bar_hp if bar_hp else definition.hp_bars)
        return {
            "bossId": actor.actor_id,
            "definitionId": definition.boss_id,
            "name": actor.name,
            "floor": definition.floor_number,
            "hp": actor.hp,
            "maxHp": actor.max_hp,
            "hpBars": definition.hp_bars,
            "barHp": bar_hp,
            "depletedBars": int(depleted),
            "phase": self.boss_phase(actor).phase_id,
            "bars": bars,
            "pendingAction": actor.metadata.get("pending_boss_action"),
            "sentinelsSpawned": int(actor.metadata.get("boss_minions_spawned", 0)),
            "provenance": asdict(definition.provenance),
        }

    def _boss_item(self, actor: CombatantState, template_id: str) -> ItemInstance:
        template = self.catalog.item(template_id)
        durability = getattr(template, "base_durability", None)
        item = ItemInstance(
            instance_id=_id("bossitem"),
            template_id=template_id,
            owner_id=actor.actor_id,
            durability=durability,
            max_durability=durability,
            metadata={"boss_equipment": True},
        )
        actor.inventory[item.instance_id] = item
        return item

    def _equip_boss_phase(self, boss: CombatantState, phase: BossPhaseDefinition) -> None:
        definition = self.boss_definition(boss)
        for slot in ("weapon", "offhand"):
            old_id = boss.equipment.pop(slot, None)
            if old_id and old_id in boss.inventory:
                boss.inventory[old_id].metadata["retired_boss_equipment"] = True
        weapon = self._boss_item(boss, phase.weapon_template_id)
        boss.equipment["weapon"] = weapon.instance_id
        if phase.offhand_template_id:
            offhand = self._boss_item(boss, phase.offhand_template_id)
            boss.equipment["offhand"] = offhand.instance_id
            offhand_template = self.catalog.item(phase.offhand_template_id)
            boss.armor = definition.armor + int(getattr(offhand_template, "armor", 0))
        else:
            boss.armor = definition.armor
        weapon_template = self.catalog.weapons[phase.weapon_template_id]
        boss.skill_proficiencies[weapon_template.weapon_class.value] = max(
            boss.skill_proficiencies.get(weapon_template.weapon_class.value, 0.0),
            760.0,
        )
        boss.metadata["boss_phase_id"] = phase.phase_id

    def create_floor_boss(self, boss_definition_id: str) -> CombatantState:
        definition = CORE_BOSSES[boss_definition_id]
        actor_id = _id("boss")
        boss = CombatantState(
            actor_id=actor_id,
            name=definition.name,
            kind=EntityKind.BOSS,
            level=definition.level,
            max_hp=definition.hp_bars * definition.hp_per_bar,
            hp=definition.hp_bars * definition.hp_per_bar,
            strength=definition.strength,
            agility=definition.agility,
            armor=definition.armor,
            evasion=definition.evasion,
            cursor=CursorColor.RED,
            location_id=f"floor_{definition.floor_number}_boss_room",
            skill_proficiencies={"parry": 180.0},
            metadata={
                "boss_definition_id": definition.boss_id,
                "boss_depleted_bars": 0,
                "boss_minions_spawned": 0,
                "boss_phase_id": definition.phases[0].phase_id,
                "boss_last_attack_awarded": False,
            },
        )
        self.actors[actor_id] = boss
        self._equip_boss_phase(boss, definition.phases[0])
        return boss

    def _create_boss_minion(self, template_id: str, *, boss_id: str) -> CombatantState:
        definition = CORE_BOSS_MINIONS[template_id]
        actor_id = _id("bossminion")
        actor = CombatantState(
            actor_id=actor_id,
            name=definition.name,
            kind=EntityKind.MONSTER,
            level=definition.level,
            max_hp=definition.hp,
            hp=definition.hp,
            strength=definition.strength,
            agility=definition.agility,
            armor=definition.armor,
            evasion=definition.evasion,
            cursor=CursorColor.RED,
            location_id=self.actors[boss_id].location_id,
            skill_proficiencies={"spear": 430.0, "parry": 120.0},
            metadata={
                "boss_minion_template_id": definition.template_id,
                "boss_parent_id": boss_id,
                "no_standard_loot": True,
            },
        )
        weapon_template = self.catalog.weapons[definition.weapon_template_id]
        weapon = ItemInstance(
            instance_id=_id("bossitem"),
            template_id=weapon_template.template_id,
            owner_id=actor_id,
            durability=weapon_template.base_durability,
            max_durability=weapon_template.base_durability,
            metadata={"boss_minion_equipment": True},
        )
        actor.inventory[weapon.instance_id] = weapon
        actor.equipment["weapon"] = weapon.instance_id
        self.actors[actor_id] = actor
        return actor

    def _spawn_boss_minions(
        self,
        encounter,
        boss: CombatantState,
        count: int,
        *,
        reason: str,
        bar_depletion: int | None = None,
    ) -> list[str]:
        definition = self.boss_definition(boss)
        if not definition.initial_minion_template_id or count <= 0:
            return []
        spawned = []
        for _ in range(count):
            minion = self._create_boss_minion(definition.initial_minion_template_id, boss_id=boss.actor_id)
            encounter.participants[minion.actor_id] = minion
            spawned.append(minion.actor_id)
        boss.metadata["boss_minions_spawned"] = int(boss.metadata.get("boss_minions_spawned", 0)) + len(spawned)
        self._append(
            encounter,
            "boss_minions_spawned",
            boss.actor_id,
            None,
            minion_template_id=definition.initial_minion_template_id,
            minion_ids=spawned,
            count=len(spawned),
            reason=reason,
            bar_depletion=bar_depletion,
        )
        return spawned

    def start_floor_boss_encounter(
        self,
        player_ids: Iterable[str],
        *,
        boss_definition_id: str = "illfang_the_kobold_lord",
        enforce_location: bool = True,
    ):
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("a boss encounter needs at least one player")
        if len(players) > 48:
            raise ValueError("one Aincrad raid group cannot exceed eight six-person parties (48 players)")
        definition = CORE_BOSSES[boss_definition_id]
        boss_room = f"floor_{definition.floor_number}_boss_room"
        for actor_id in players:
            actor = self.actors[actor_id]
            if actor.kind is not EntityKind.PLAYER or not actor.alive:
                raise ValueError("boss raid participants must be living player characters")
            if enforce_location and actor.location_id != boss_room:
                raise ValueError(f"all raid participants must be at {boss_room}")
        boss = self.create_floor_boss(boss_definition_id)
        encounter = self.start_encounter(players + [boss.actor_id], zone_id=boss_room)
        self._append(
            encounter,
            "boss_encounter_started",
            boss.actor_id,
            None,
            boss_definition_id=definition.boss_id,
            hp_bars=definition.hp_bars,
            player_count=len(players),
        )
        self._append(
            encounter,
            "boss_phase_started",
            boss.actor_id,
            None,
            phase_id=definition.phases[0].phase_id,
            phase_name=definition.phases[0].name,
        )
        self._spawn_boss_minions(
            encounter,
            boss,
            definition.initial_minion_count,
            reason="encounter_start",
        )
        return encounter, boss

    def _phase_for_depleted_bars(self, definition: BossDefinition, depleted: int) -> BossPhaseDefinition:
        candidates = [phase for phase in definition.phases if depleted >= phase.activate_after_depleted_bars]
        return max(candidates, key=lambda phase: phase.activate_after_depleted_bars)

    def _process_boss_hp_transition(self, encounter, boss: CombatantState, old_hp: int) -> None:
        definition = self.boss_definition(boss)
        old_depleted = int(boss.metadata.get("boss_depleted_bars", 0))
        damage = max(0, boss.max_hp - boss.hp)
        new_depleted = min(
            definition.hp_bars,
            damage // definition.hp_per_bar if definition.hp_per_bar else definition.hp_bars,
        )
        if new_depleted <= old_depleted:
            return

        boss.metadata["boss_depleted_bars"] = int(new_depleted)
        for depleted_bar in range(old_depleted + 1, min(new_depleted, definition.hp_bars - 1) + 1):
            self._append(
                encounter,
                "boss_hp_bar_depleted",
                None,
                boss.actor_id,
                depleted_bar=depleted_bar,
                hp=boss.hp,
                hp_before=old_hp,
            )
            if depleted_bar in definition.minion_spawn_bar_depletions:
                self._spawn_boss_minions(
                    encounter,
                    boss,
                    definition.minions_per_bar_depletion,
                    reason="hp_bar_depleted",
                    bar_depletion=depleted_bar,
                )

        if boss.alive:
            desired = self._phase_for_depleted_bars(definition, int(new_depleted))
            current = self.boss_phase(boss)
            if desired.phase_id != current.phase_id:
                self._equip_boss_phase(boss, desired)
                boss.metadata.pop("pending_boss_action", None)
                self._append(
                    encounter,
                    "boss_phase_changed",
                    boss.actor_id,
                    None,
                    from_phase=current.phase_id,
                    to_phase=desired.phase_id,
                    phase_name=desired.name,
                    weapon_template_id=desired.weapon_template_id,
                )

    def _award_last_attack_bonus(self, encounter, boss: CombatantState, killer_id: str | None) -> None:
        if boss.metadata.get("boss_last_attack_awarded"):
            return
        boss.metadata["boss_last_attack_awarded"] = True
        definition = self.boss_definition(boss)
        if not killer_id or killer_id not in self.actors:
            return
        killer = self.actors[killer_id]
        if killer.kind is not EntityKind.PLAYER or not definition.last_attack_bonus_template_id:
            return
        template = self.catalog.item(definition.last_attack_bonus_template_id)
        durability = getattr(template, "base_durability", None)
        item = ItemInstance(
            instance_id=_id("item"),
            template_id=template.template_id,
            owner_id=killer.actor_id,
            durability=durability,
            max_durability=durability,
            metadata={"last_attack_bonus": True, "boss_definition_id": definition.boss_id},
        )
        add_item(killer, item, self.catalog, allow_overweight=True)
        self._append(
            encounter,
            "last_attack_bonus_awarded",
            killer.actor_id,
            boss.actor_id,
            template_id=template.template_id,
            instance_id=item.instance_id,
        )

    def _resolve_defeat(self, encounter, target: CombatantState, killer_id: str | None) -> None:
        already = bool(target.metadata.get("defeat_resolved"))
        super()._resolve_defeat(encounter, target, killer_id)
        if already or target.kind is not EntityKind.BOSS or "boss_definition_id" not in target.metadata:
            return
        definition = self.boss_definition(target)
        floor = self.world.floors[definition.floor_number]
        if not floor.floor_boss_defeated:
            self.floor_boss_defeated(definition.floor_number)
            self._append(
                encounter,
                "floor_boss_defeated",
                killer_id,
                target.actor_id,
                floor_number=definition.floor_number,
                next_floor_gate_scheduled_at_ms=self.world.floors[definition.floor_number + 1].scheduled_gate_activation_at_ms
                if definition.floor_number < 100
                else None,
            )
        self._award_last_attack_bonus(encounter, target, killer_id)

    def attack(
        self,
        encounter_id: str,
        attacker_id: str,
        target_id: str,
        *,
        sword_skill_id: str | None = None,
        defense: DefenseMode | str = DefenseMode.AUTO,
        distance_m: float = 1.0,
        seed: int | None = None,
    ) -> AttackResolution:
        encounter = self.encounters[encounter_id]
        target = encounter.participants[target_id]
        old_hp = target.hp
        result = super().attack(
            encounter_id,
            attacker_id,
            target_id,
            sword_skill_id=sword_skill_id,
            defense=defense,
            distance_m=distance_m,
            seed=seed,
        )
        if result.legal and result.hit and target.kind is EntityKind.BOSS and "boss_definition_id" in target.metadata:
            self._process_boss_hp_transition(encounter, target, old_hp)
        return result

    def _boss_action(self, boss: CombatantState, action_id: str) -> BossActionDefinition:
        phase = self.boss_phase(boss)
        if action_id not in phase.action_ids:
            raise ValueError("boss action is unavailable in the current phase")
        return CORE_BOSS_ACTIONS[action_id]

    def choose_boss_action(self, encounter_id: str, boss_id: str) -> dict:
        encounter = self.encounters[encounter_id]
        boss = encounter.participants[boss_id]
        phase = self.boss_phase(boss)
        action_id = self.rng.choice(list(phase.action_ids))
        action = CORE_BOSS_ACTIONS[action_id]
        table = encounter.threat.get(boss_id, {})
        player_ids = [
            actor_id
            for actor_id, actor in encounter.participants.items()
            if actor.kind is EntityKind.PLAYER and actor.alive
        ]
        player_ids.sort(key=lambda actor_id: table.get(actor_id, 0.0), reverse=True)
        selected = player_ids[: max(1, min(action.max_targets, len(player_ids)))]
        return {"actionId": action_id, "targetIds": selected, "phaseId": phase.phase_id}

    def telegraph_boss_action(
        self,
        encounter_id: str,
        boss_id: str,
        action_id: str,
        target_ids: Iterable[str],
    ):
        encounter = self.encounters[encounter_id]
        boss = encounter.participants[boss_id]
        if not boss.alive:
            raise ValueError("boss is defeated")
        if boss.metadata.get("pending_boss_action"):
            raise ValueError("boss already has a pending telegraphed action")
        if encounter.time_ms < boss.recovery_until_ms:
            raise ValueError("boss is still recovering")
        action = self._boss_action(boss, action_id)
        targets = list(dict.fromkeys(target_ids))
        if not targets or len(targets) > action.max_targets:
            raise ValueError("invalid target count for boss action")
        for target_id in targets:
            target = encounter.participants.get(target_id)
            if target is None or not target.alive or target.kind is not EntityKind.PLAYER:
                raise ValueError("boss actions may target living encounter players only")
        execute_at = encounter.time_ms + action.telegraph_ms
        pending = {
            "action_id": action.action_id,
            "target_ids": targets,
            "started_at_ms": encounter.time_ms,
            "execute_at_ms": execute_at,
            "phase_id": self.boss_phase(boss).phase_id,
        }
        boss.metadata["pending_boss_action"] = pending
        boss.committed_until_ms = max(boss.committed_until_ms, execute_at)
        return self._append(
            encounter,
            "boss_action_telegraphed",
            boss_id,
            None,
            action_id=action.action_id,
            action_name=action.name,
            target_ids=targets,
            execute_at_ms=execute_at,
            telegraph_ms=action.telegraph_ms,
            tags=list(action.tags),
        )

    def resolve_boss_action(
        self,
        encounter_id: str,
        boss_id: str,
        *,
        defenses: dict[str, DefenseMode | str] | None = None,
        seed: int | None = None,
    ) -> dict:
        encounter = self.encounters[encounter_id]
        boss = encounter.participants[boss_id]
        pending = boss.metadata.get("pending_boss_action")
        if not pending:
            raise ValueError("boss has no pending telegraphed action")
        action = self._boss_action(boss, str(pending["action_id"]))
        execute_at = int(pending["execute_at_ms"])
        if encounter.time_ms < execute_at:
            self._advance_encounter_to(encounter, execute_at)

        if not boss.alive:
            boss.metadata.pop("pending_boss_action", None)
            return {"resolved": False, "interrupted": True, "reason": "boss was defeated before execution"}
        if encounter.time_ms < boss.recovery_until_ms:
            boss.metadata.pop("pending_boss_action", None)
            boss.committed_until_ms = max(boss.committed_until_ms, boss.recovery_until_ms)
            self._append(
                encounter,
                "boss_action_interrupted",
                boss_id,
                None,
                action_id=action.action_id,
                reason="boss was staggered/recovering at execution time",
            )
            return {"resolved": False, "interrupted": True, "reason": "boss was staggered/recovering"}

        weapon_item, weapon = self._equipped_weapon(boss)
        skill = SwordSkillDefinition(
            skill_id=f"boss:{action.action_id}",
            name=action.name,
            weapon_class=weapon.weapon_class,
            prerequisite_proficiency=0,
            hits=(action.damage_multiplier,),
            windup_ms=0,
            active_ms=action.active_ms,
            post_motion_ms=action.recovery_ms,
            accuracy_modifier=action.accuracy_modifier,
            lunge_m=max(0.0, action.reach_m - weapon.reach_m),
            provenance=action.provenance,
        )
        local_rng = random.Random(seed) if seed is not None else self.rng
        defenses = defenses or {}
        resolutions: list[tuple[CombatantState, AttackResolution]] = []
        for target_id in list(pending["target_ids"]):
            target = encounter.participants.get(target_id)
            if target is None or not target.alive:
                continue
            resolution = resolve_physical_attack(
                boss,
                target,
                weapon_item,
                weapon,
                now_ms=encounter.time_ms,
                rng=local_rng,
                sword_skill=skill,
                defense=DefenseMode(defenses.get(target_id, DefenseMode.AUTO)),
                distance_m=min(action.reach_m, weapon.reach_m + skill.lunge_m),
            )
            resolutions.append((target, resolution))

        action_end = encounter.time_ms + action.active_ms
        recovery_end = action_end + action.recovery_ms
        boss.committed_until_ms = action_end
        boss.recovery_until_ms = recovery_end
        weapon_loss = 0
        rows = []
        for target, resolution in resolutions:
            if not resolution.legal:
                rows.append({"targetId": target.actor_id, "legal": False, "reason": resolution.reason})
                continue
            weapon_loss = max(weapon_loss, resolution.attacker_durability_loss)
            applied_stagger = max(resolution.stagger_ms, action.stagger_ms if resolution.hit else 0)
            if resolution.hit:
                target.hp = max(0, target.hp - resolution.damage)
                target.alive = target.hp > 0
                if applied_stagger:
                    target.recovery_until_ms = max(target.recovery_until_ms, encounter.time_ms + applied_stagger)
                body_id = target.equipment.get("body")
                if body_id and body_id in target.inventory:
                    body = target.inventory[body_id]
                    before = body.durability
                    if body.durability is not None:
                        body.durability = max(0, body.durability - resolution.defender_durability_pressure)
                    if before and body.durability == 0:
                        recompute_equipment_stats(target, self.catalog)
                        self._append(encounter, "equipment_broken", target.actor_id, target.actor_id, instance_id=body_id)
                encounter.last_attacker_by_target[target.actor_id] = boss.actor_id
                encounter.last_attack_time_by_target[target.actor_id] = encounter.time_ms
            rows.append(
                {
                    "targetId": target.actor_id,
                    "legal": True,
                    "hit": resolution.hit,
                    "critical": resolution.critical,
                    "guarded": resolution.guarded,
                    "parried": resolution.parried,
                    "evaded": resolution.evaded,
                    "damage": resolution.damage,
                    "staggerMs": applied_stagger,
                    "hpAfter": target.hp,
                }
            )
            if not target.alive:
                self._resolve_defeat(encounter, target, boss.actor_id)

        if weapon_item.durability is not None:
            weapon_item.durability = max(0, weapon_item.durability - weapon_loss)
        boss.metadata.pop("pending_boss_action", None)
        self._append(
            encounter,
            "boss_action_resolved",
            boss_id,
            None,
            action_id=action.action_id,
            action_name=action.name,
            targets=rows,
            recovery_end_ms=recovery_end,
        )
        self._advance_encounter_to(encounter, action_end)
        return {
            "resolved": True,
            "interrupted": False,
            "actionId": action.action_id,
            "actionName": action.name,
            "targets": rows,
            "actionEndMs": action_end,
            "recoveryEndMs": recovery_end,
        }
