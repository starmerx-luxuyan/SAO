from __future__ import annotations

import random
import uuid
from dataclasses import asdict

from sao_mcp.corpus.core import Catalog, build_core_catalog
from sao_mcp.corpus.loot import CORE_LOOT_TABLES
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
from sao_mcp.rules.inventory import (
    EquipmentChange,
    RepairResolution,
    equip,
    recompute_equipment_stats,
    repair_item,
    transfer_item,
    unequip,
)
from sao_mcp.rules.items import ConsumableResolution, tick_statuses, use_consumable
from sao_mcp.rules.loot import GrantedLoot, LootRoll, grant_loot, roll_loot
from sao_mcp.rules.progression import (
    default_max_hp,
    experience_to_reach_level,
    gain_skill_proficiency,
)
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

    def create_character(
        self,
        name: str,
        *,
        level: int = 1,
        starter_weapon_id: str = "starter_one_hand_sword",
    ) -> CombatantState:
        if not name.strip():
            raise ValueError("name is required")
        if level < 1:
            raise ValueError("level must be >= 1")
        if starter_weapon_id not in self.catalog.weapons:
            raise KeyError(starter_weapon_id)

        strength = 10 + (level - 1) * 2
        agility = 10 + (level - 1) * 2
        actor_id = _id("pc")
        hp = default_max_hp(level, strength, agility)
        weapon_template = self.catalog.weapons[starter_weapon_id]
        weapon_skill_id = weapon_template.weapon_class.value
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
            equipped_skills=[weapon_skill_id, "searching"],
            skill_proficiencies={weapon_skill_id: 0.0, "searching": 0.0, "parry": 0.0},
            metadata={"experience": experience_to_reach_level(level)},
        )

        weapon = ItemInstance(
            instance_id=_id("item"),
            template_id=weapon_template.template_id,
            owner_id=actor_id,
            durability=weapon_template.base_durability,
            max_durability=weapon_template.base_durability,
            max_enhancement_attempts=5,
        )
        coat_template = self.catalog.armors["starter_leather_coat"]
        coat = ItemInstance(
            instance_id=_id("item"),
            template_id=coat_template.template_id,
            owner_id=actor_id,
            durability=coat_template.base_durability,
            max_durability=coat_template.base_durability,
        )
        potion = ItemInstance(
            instance_id=_id("item"),
            template_id="healing_potion_basic",
            owner_id=actor_id,
            quantity=3,
        )
        actor.inventory[weapon.instance_id] = weapon
        actor.inventory[coat.instance_id] = coat
        actor.inventory[potion.instance_id] = potion
        equip(actor, weapon.instance_id, self.catalog)
        equip(actor, coat.instance_id, self.catalog)
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
            metadata={"loot_table_id": "floor1_frenzy_boar"},
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

    def _append(
        self,
        encounter: EncounterState,
        event_type: str,
        actor_id: str | None,
        target_id: str | None,
        **payload,
    ) -> CombatEvent:
        event = CombatEvent(encounter.time_ms, event_type, actor_id, target_id, payload)
        encounter.events.append(event)
        return event

    def _reward_recipients(self, encounter: EncounterState, killer: CombatantState) -> list[CombatantState]:
        if not killer.party_id:
            return [killer]
        members = [
            actor
            for actor in encounter.participants.values()
            if actor.kind is EntityKind.PLAYER and actor.party_id == killer.party_id and actor.alive
        ]
        return members or [killer]

    def _grant_defeat_rewards(
        self,
        encounter: EncounterState,
        target: CombatantState,
        killer: CombatantState,
    ) -> dict | None:
        table_id = target.metadata.get("loot_table_id")
        if not table_id or table_id not in CORE_LOOT_TABLES:
            return None
        rolled = roll_loot(CORE_LOOT_TABLES[table_id], self.rng)
        recipients = self._reward_recipients(encounter, killer)
        count = max(1, len(recipients))
        details: list[dict] = []
        for index, recipient in enumerate(recipients):
            # Simulation policy: Col/XP are party-shared, item drops go to the killer.
            col_share = rolled.col // count + (rolled.col % count if index == 0 else 0)
            xp_share = rolled.xp // count + (rolled.xp % count if index == 0 else 0)
            share = LootRoll(
                rolled.table_id,
                col_share,
                xp_share,
                rolled.drops if recipient.actor_id == killer.actor_id else (),
            )
            granted: GrantedLoot = grant_loot(recipient, share, self.catalog, allow_overweight=True)
            details.append(
                {
                    "actor_id": recipient.actor_id,
                    "col": granted.col,
                    "xp": granted.experience.amount,
                    "new_level": granted.experience.new_level,
                    "items": list(granted.item_instance_ids),
                }
            )
        payload = {
            "table_id": rolled.table_id,
            "policy": "party_share_col_xp_killer_owns_items_v1",
            "drops": [asdict(drop) for drop in rolled.drops],
            "recipients": details,
        }
        self._append(encounter, "loot_awarded", killer.actor_id, target.actor_id, **payload)
        return payload

    def _resolve_defeat(
        self,
        encounter: EncounterState,
        target: CombatantState,
        killer_id: str | None,
    ) -> None:
        if target.metadata.get("defeat_resolved"):
            return
        target.metadata["defeat_resolved"] = True
        self._append(encounter, "defeated", killer_id, target.actor_id)
        if target.kind not in (EntityKind.MONSTER, EntityKind.BOSS) or not killer_id:
            return
        killer = encounter.participants.get(killer_id)
        if killer is None or killer.kind is not EntityKind.PLAYER:
            return
        self._grant_defeat_rewards(encounter, target, killer)

    def _advance_encounter_to(self, encounter: EncounterState, new_time_ms: int) -> None:
        if new_time_ms <= encounter.time_ms:
            return
        elapsed = new_time_ms - encounter.time_ms
        encounter.time_ms = new_time_ms
        for actor in encounter.participants.values():
            was_alive = actor.alive
            changes = tick_statuses(actor, elapsed)
            for status_type, delta in changes:
                self._append(
                    encounter,
                    "status_tick",
                    actor.actor_id,
                    actor.actor_id,
                    status=status_type.value,
                    hp_delta=delta,
                )
            if was_alive and not actor.alive:
                self._resolve_defeat(
                    encounter,
                    actor,
                    encounter.last_attacker_by_target.get(actor.actor_id),
                )

    def advance_encounter(self, encounter_id: str, elapsed_ms: int) -> EncounterState:
        if elapsed_ms < 0:
            raise ValueError("elapsed_ms must be >= 0")
        encounter = self.encounters[encounter_id]
        self._advance_encounter_to(encounter, encounter.time_ms + elapsed_ms)
        return encounter

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

        apply_unlawful_hostile_action(attacker, target, safe_zone=encounter.safe_zone)
        attacker.committed_until_ms = result.action_end_ms
        attacker.recovery_until_ms = result.recovery_end_ms
        weapon_before = weapon_item.durability
        if weapon_item.durability is not None:
            weapon_item.durability = max(0, weapon_item.durability - result.attacker_durability_loss)

        if result.hit:
            target.hp = max(0, target.hp - result.damage)
            target.alive = target.hp > 0
            if result.stagger_ms:
                target.recovery_until_ms = max(
                    target.recovery_until_ms,
                    encounter.time_ms + result.stagger_ms,
                )
            body_id = target.equipment.get("body")
            if body_id and body_id in target.inventory:
                body = target.inventory[body_id]
                body_before = body.durability
                if body.durability is not None:
                    body.durability = max(0, body.durability - result.defender_durability_pressure)
                if body_before and body.durability == 0:
                    recompute_equipment_stats(target, self.catalog)
                    self._append(encounter, "equipment_broken", target_id, target_id, instance_id=body_id)
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
        if weapon_before and weapon_item.durability == 0:
            self._append(encounter, "equipment_broken", attacker_id, attacker_id, instance_id=weapon_item.instance_id)
        self._advance_encounter_to(encounter, result.action_end_ms)
        if not target.alive:
            self._resolve_defeat(encounter, target, attacker_id)
        return result

    def switch(
        self,
        encounter_id: str,
        outgoing_id: str,
        incoming_id: str,
        target_id: str,
    ) -> CombatEvent:
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
        candidates = [
            a.actor_id
            for a in encounter.participants.values()
            if a.alive and a.kind is EntityKind.PLAYER
        ]
        return candidates[0] if candidates else None

    def use_inventory_item(
        self,
        actor_id: str,
        instance_id: str,
        *,
        encounter_id: str | None = None,
    ) -> ConsumableResolution:
        actor = self.actors[actor_id]
        item = actor.inventory[instance_id]
        template = self.catalog.consumables[item.template_id]
        encounter = self.encounters.get(encounter_id) if encounter_id else None
        now = encounter.time_ms if encounter else self.world.now_ms
        result = use_consumable(
            actor,
            item,
            template,
            now_ms=now,
            anti_crystal=bool(encounter and encounter.anti_crystal),
        )
        if result.consumed and item.quantity <= 0:
            actor.inventory.pop(instance_id, None)
        if encounter:
            self._append(
                encounter,
                "use_item",
                actor_id,
                actor_id,
                template_id=template.template_id,
                consumed=result.consumed,
                reason=result.reason,
            )
        return result

    def equip_item(self, actor_id: str, instance_id: str) -> EquipmentChange:
        return equip(self.actors[actor_id], instance_id, self.catalog)

    def unequip_item(self, actor_id: str, slot: str) -> EquipmentChange:
        return unequip(self.actors[actor_id], slot, self.catalog)

    def transfer_inventory_item(
        self,
        source_id: str,
        destination_id: str,
        instance_id: str,
        *,
        quantity: int | None = None,
    ) -> ItemInstance:
        return transfer_item(
            self.actors[source_id],
            self.actors[destination_id],
            instance_id,
            self.catalog,
            quantity=quantity,
        )

    def repair_inventory_item(
        self,
        actor_id: str,
        instance_id: str,
        *,
        smith_proficiency: float,
        pay_from_actor: bool = True,
    ) -> RepairResolution:
        return repair_item(
            self.actors[actor_id],
            instance_id,
            self.catalog,
            smith_proficiency=smith_proficiency,
            pay_from_actor=pay_from_actor,
        )

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
