from __future__ import annotations

import random
import uuid
from dataclasses import asdict

from sao_mcp.corpus.core import Catalog, build_core_catalog
from sao_mcp.domain.models import (
    CombatEvent,
    CombatantState,
    CursorColor,
    DefenseMode,
    EncounterState,
    EnhancementTrack,
    EntityKind,
    ItemInstance,
    PartyState,
    RaidState,
)
from sao_mcp.rules.combat import AttackResolution, resolve_physical_attack
from sao_mcp.rules.crafting import EnhancementResolution, attempt_enhancement
from sao_mcp.rules.items import ConsumableResolution, tick_statuses, use_consumable
from sao_mcp.rules.progression import default_max_hp, gain_skill_proficiency
from sao_mcp.rules.social import add_party_member, add_raid_party, apply_unlawful_hostile_action
from sao_mcp.rules.world import advance_world_time, defeat_floor_boss, make_aincrad_world


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class GameRuntime:
    """Authoritative in-memory Aincrad runtime. Persistence is layered separately."""

    def __init__(self, *, seed: int | None = None, catalog: Catalog | None = None) -> None:
        self.catalog = catalog or build_core_catalog()
        self.world = make_aincrad_world()
        self.actors: dict[str, CombatantState] = {}
        self.encounters: dict[str, EncounterState] = {}
        self.rng = random.Random(seed)

    def create_character(self, name: str, *, level: int = 1) -> CombatantState:
        if not name.strip():
            raise ValueError("name is required")
        if level < 1:
            raise ValueError("level must be >= 1")
        strength = 10 + (level - 1) * 2
        agility = 10 + (level - 1) * 2
        actor_id = _id("pc")
        hp = default_max_hp(level, strength, agility)
        actor = CombatantState(
            actor_id=actor_id,
            name=name.strip(),
            kind=EntityKind.PLAYER,
            level=level,
            max_hp=hp,
            hp=hp,
            strength=strength,
            agility=agility,
            location_id="floor_1_town_of_beginnings",
            equipped_skills=["one_hand_sword", "searching"],
            skill_proficiencies={"one_hand_sword": 0.0, "searching": 0.0, "parry": 0.0},
        )
        starter = self.catalog.weapons["starter_one_hand_sword"]
        sword = ItemInstance(
            instance_id=_id("item"),
            template_id=starter.template_id,
            owner_id=actor_id,
            durability=starter.base_durability,
            max_durability=starter.base_durability,
            max_enhancement_attempts=5,
        )
        potion = ItemInstance(
            instance_id=_id("item"),
            template_id="healing_potion_basic",
            owner_id=actor_id,
            quantity=3,
        )
        actor.inventory[sword.instance_id] = sword
        actor.inventory[potion.instance_id] = potion
        actor.equipment["weapon"] = sword.instance_id
        self.actors[actor_id] = actor
        return actor

    def create_training_monster(self, name: str = "Frenzy Boar", *, level: int = 1) -> CombatantState:
        actor_id = _id("mob")
        strength = 9 + level * 2
        agility = 8 + level * 2
        hp = int(default_max_hp(level, strength, agility) * 0.72)
        actor = CombatantState(
            actor_id=actor_id,
            name=name,
            kind=EntityKind.MONSTER,
            level=level,
            max_hp=hp,
            hp=hp,
            strength=strength,
            agility=agility,
            armor=20 + level * 3,
            evasion=level,
            cursor=CursorColor.RED,
            location_id="floor_1_west_field",
            skill_proficiencies={"one_hand_sword": min(1000.0, 80.0 + level * 5)},
        )
        natural = self.catalog.weapons["starter_one_hand_sword"]
        attack = ItemInstance(
            instance_id=_id("natural"),
            template_id=natural.template_id,
            owner_id=actor_id,
            durability=10_000,
            max_durability=10_000,
            max_enhancement_attempts=0,
            metadata={"natural_attack": True},
        )
        actor.inventory[attack.instance_id] = attack
        actor.equipment["weapon"] = attack.instance_id
        self.actors[actor_id] = actor
        return actor

    def start_encounter(
        self,
        actor_ids: list[str],
        *,
        zone_id: str = "floor_1_west_field",
        safe_zone: bool = False,
        anti_crystal: bool = False,
    ) -> EncounterState:
        if len(set(actor_ids)) < 2:
            raise ValueError("an encounter needs at least two distinct participants")
        missing = [actor_id for actor_id in actor_ids if actor_id not in self.actors]
        if missing:
            raise KeyError(f"unknown actors: {missing}")
        encounter = EncounterState(
            encounter_id=_id("enc"),
            participants={actor_id: self.actors[actor_id] for actor_id in actor_ids},
            zone_id=zone_id,
            safe_zone=safe_zone,
            anti_crystal=anti_crystal,
        )
        self.encounters[encounter.encounter_id] = encounter
        return encounter

    def _equipped_weapon(self, actor: CombatantState) -> tuple[ItemInstance, object]:
        instance_id = actor.equipment.get("weapon")
        if not instance_id:
            raise ValueError("actor has no equipped weapon")
        instance = actor.inventory[instance_id]
        return instance, self.catalog.weapons[instance.template_id]

    def _append(self, encounter: EncounterState, event_type: str, actor_id: str | None, target_id: str | None, **payload) -> CombatEvent:
        event = CombatEvent(encounter.time_ms, event_type, actor_id, target_id, payload)
        encounter.events.append(event)
        return event

    def _advance_encounter_to(self, encounter: EncounterState, new_time_ms: int) -> None:
        if new_time_ms <= encounter.time_ms:
            return
        elapsed = new_time_ms - encounter.time_ms
        encounter.time_ms = new_time_ms
        for actor in encounter.participants.values():
            changes = tick_statuses(actor, elapsed)
            for status_type, delta in changes:
                self._append(encounter, "status_tick", actor.actor_id, actor.actor_id, status=status_type.value, hp_delta=delta)
            if not actor.alive:
                self._append(encounter, "defeated", None, actor.actor_id)

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
        attacker = encounter.participants[attacker_id]
        target = encounter.participants[target_id]
        if encounter.safe_zone:
            result = AttackResolution(False, reason="hostile damage is blocked in this protected area")
            self._append(encounter, "attack_blocked", attacker_id, target_id, reason=result.reason)
            return result

        weapon_item, weapon = self._equipped_weapon(attacker)
        skill = self.catalog.sword_skills.get(sword_skill_id) if sword_skill_id else None
        local_rng = random.Random(seed) if seed is not None else self.rng
        mode = DefenseMode(defense)
        result = resolve_physical_attack(
            attacker,
            target,
            weapon_item,
            weapon,
            now_ms=encounter.time_ms,
            rng=local_rng,
            sword_skill=skill,
            defense=mode,
            distance_m=distance_m,
        )
        if not result.legal:
            self._append(encounter, "attack_illegal", attacker_id, target_id, reason=result.reason)
            return result

        # Crime state is a consequence of a legal hostile action, including a miss,
        # not of merely submitting an invalid/out-of-range attack request.
        apply_unlawful_hostile_action(attacker, target, safe_zone=encounter.safe_zone)

        attacker.committed_until_ms = result.action_end_ms
        attacker.recovery_until_ms = result.recovery_end_ms
        if weapon_item.durability is not None:
            weapon_item.durability = max(0, weapon_item.durability - result.attacker_durability_loss)

        if result.hit:
            target.hp = max(0, target.hp - result.damage)
            target.alive = target.hp > 0
            if result.stagger_ms:
                target.recovery_until_ms = max(target.recovery_until_ms, encounter.time_ms + result.stagger_ms)
            body_id = target.equipment.get("body")
            if body_id and body_id in target.inventory:
                body = target.inventory[body_id]
                if body.durability is not None:
                    body.durability = max(0, body.durability - result.defender_durability_pressure)
            if target.kind in (EntityKind.MONSTER, EntityKind.BOSS):
                target_threat = encounter.threat.setdefault(target_id, {})
                target_threat[attacker_id] = target_threat.get(attacker_id, 0.0) + result.threat_generated
            encounter.last_attacker_by_target[target_id] = attacker_id
            encounter.last_attack_time_by_target[target_id] = encounter.time_ms
            gain_skill_proficiency(attacker, weapon.weapon_class.value, 2.4 if sword_skill_id else 1.0)

        self._append(
            encounter,
            "attack",
            attacker_id,
            target_id,
            hit=result.hit,
            critical=result.critical,
            parried=result.parried,
            guarded=result.guarded,
            evaded=result.evaded,
            damage=result.damage,
            sword_skill=sword_skill_id,
            weapon_durability=weapon_item.durability,
        )
        self._advance_encounter_to(encounter, result.action_end_ms)
        if not target.alive:
            self._append(encounter, "defeated", attacker_id, target_id)
        return result

    def switch(self, encounter_id: str, outgoing_id: str, incoming_id: str, target_id: str) -> CombatEvent:
        encounter = self.encounters[encounter_id]
        outgoing = encounter.participants[outgoing_id]
        incoming = encounter.participants[incoming_id]
        target = encounter.participants[target_id]
        if not outgoing.party_id or outgoing.party_id != incoming.party_id:
            raise ValueError("Switch requires coordinated members of the same party")
        if target.kind not in (EntityKind.MONSTER, EntityKind.BOSS):
            raise ValueError("default Switch handling is for monster targets")
        if encounter.last_attacker_by_target.get(target_id) != outgoing_id:
            raise ValueError("outgoing member has not created the current opening")
        last = encounter.last_attack_time_by_target.get(target_id, -10_000)
        if encounter.time_ms - last > 1_800:
            raise ValueError("the Switch opening has expired")

        target.ai_reaction_until_ms = max(target.ai_reaction_until_ms, encounter.time_ms + 650)
        table = encounter.threat.setdefault(target_id, {})
        transferable = table.get(outgoing_id, 0.0) * 0.35
        table[outgoing_id] = max(0.0, table.get(outgoing_id, 0.0) - transferable)
        table[incoming_id] = table.get(incoming_id, 0.0) + transferable
        return self._append(
            encounter,
            "switch",
            outgoing_id,
            target_id,
            incoming_id=incoming_id,
            ai_reaction_until_ms=target.ai_reaction_until_ms,
            transferred_threat=round(transferable, 3),
        )

    def monster_target(self, encounter_id: str, monster_id: str) -> str | None:
        encounter = self.encounters[encounter_id]
        monster = encounter.participants[monster_id]
        if monster.kind not in (EntityKind.MONSTER, EntityKind.BOSS):
            raise ValueError("actor is not a monster")
        table = encounter.threat.get(monster_id, {})
        legal = {
            actor_id: threat
            for actor_id, threat in table.items()
            if actor_id in encounter.participants and encounter.participants[actor_id].alive
        }
        if legal:
            return max(legal, key=legal.get)
        candidates = [a.actor_id for a in encounter.participants.values() if a.alive and a.kind is EntityKind.PLAYER]
        return candidates[0] if candidates else None

    def use_inventory_item(self, actor_id: str, instance_id: str, *, encounter_id: str | None = None) -> ConsumableResolution:
        actor = self.actors[actor_id]
        item = actor.inventory[instance_id]
        template = self.catalog.consumables[item.template_id]
        encounter = self.encounters.get(encounter_id) if encounter_id else None
        now = encounter.time_ms if encounter else self.world.now_ms
        result = use_consumable(actor, item, template, now_ms=now, anti_crystal=bool(encounter and encounter.anti_crystal))
        if result.consumed and item.quantity <= 0:
            actor.inventory.pop(instance_id, None)
        if encounter:
            self._append(encounter, "use_item", actor_id, actor_id, template_id=template.template_id, consumed=result.consumed, reason=result.reason)
        return result

    def enhance_item(
        self,
        actor_id: str,
        instance_id: str,
        track: EnhancementTrack | str,
        *,
        smith_proficiency: float,
        material_quality: float = 1.0,
        item_difficulty: float = 1.0,
        seed: int | None = None,
        allow_destructive_overcap: bool = False,
    ) -> EnhancementResolution:
        actor = self.actors[actor_id]
        item = actor.inventory[instance_id]
        local_rng = random.Random(seed) if seed is not None else self.rng
        return attempt_enhancement(
            item,
            EnhancementTrack(track),
            smith_proficiency=smith_proficiency,
            material_quality=material_quality,
            item_difficulty=item_difficulty,
            rng=local_rng,
            allow_destructive_overcap=allow_destructive_overcap,
        )

    def create_party(self, leader_id: str) -> PartyState:
        if leader_id not in self.actors:
            raise KeyError(leader_id)
        party = PartyState(_id("party"), leader_id, [leader_id])
        self.world.parties[party.party_id] = party
        self.actors[leader_id].party_id = party.party_id
        return party

    def join_party(self, party_id: str, actor_id: str) -> PartyState:
        party = self.world.parties[party_id]
        add_party_member(party, actor_id)
        self.actors[actor_id].party_id = party_id
        return party

    def create_raid(self, leader_id: str, party_id: str) -> RaidState:
        raid = RaidState(_id("raid"), leader_id, [party_id])
        self.world.raids[raid.raid_id] = raid
        return raid

    def join_raid(self, raid_id: str, party_id: str) -> RaidState:
        raid = self.world.raids[raid_id]
        add_raid_party(raid, party_id)
        return raid

    def floor_boss_defeated(self, floor_number: int) -> None:
        defeat_floor_boss(self.world, floor_number)

    def advance_world(self, elapsed_ms: int) -> list[int]:
        return advance_world_time(self.world, elapsed_ms)

    def actor_snapshot(self, actor_id: str) -> dict:
        return asdict(self.actors[actor_id])
