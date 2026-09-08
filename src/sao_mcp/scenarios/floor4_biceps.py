from __future__ import annotations

import uuid

from sao_mcp.corpus.floor4_fieldboss import (
    BICEPS_ID,
    BICEPS_WEAPON_ID,
    CALDERA_LAKE,
)
from sao_mcp.corpus.loot import CORE_LOOT_TABLES
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES
from sao_mcp.domain.models import ItemInstance


CLEAR_FLAG = "floor4_biceps_archelon_defeated"
RAM_ACTION_MS = 900


class Floor4BicepsScenario:
    """The Floor 4 Caldera Lake Field Boss and its south-route unlock."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        definition = AINCRAD_MONSTERS[BICEPS_ID]
        CORE_LOOT_TABLES[definition.loot_table_id] = AINCRAD_MONSTER_LOOT_TABLES[
            definition.loot_table_id
        ]

    def _instances(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor4_biceps_instances", {})

    def _instance(self, instance_id: str) -> dict:
        try:
            return self._instances()[instance_id]
        except KeyError as exc:
            raise KeyError(f"unknown Biceps Archelon instance: {instance_id}") from exc

    def start_raid(self, player_ids: list[str]) -> dict:
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("Biceps Archelon raid needs at least one player")
        if self.runtime.world.global_flags.get(CLEAR_FLAG):
            raise ValueError("Biceps Archelon has already been defeated")
        capacity = 0
        for actor_id in players:
            actor = self.runtime.actors[actor_id]
            if not actor.alive or actor.location_id != CALDERA_LAKE:
                raise ValueError("all participants must be living players at Caldera Lake")
            gondola = actor.metadata.get("floor4_gondola")
            if gondola:
                capacity += int(gondola.get("passenger_seats", 0)) + int(gondola.get("gondolier_seat", 1))
        if capacity < len(players):
            raise ValueError("the raid needs enough player-gondola capacity for all participants")

        definition = AINCRAD_MONSTERS[BICEPS_ID]
        boss = self.runtime._create_monster(
            name=definition.name,
            level=definition.level,
            location_id=definition.location_id,
            hp_factor=definition.hp_factor,
            loot_table_id=definition.loot_table_id,
            quest_kill_id=definition.quest_kill_id,
        )
        old_weapon_id = boss.equipment.get("weapon")
        if old_weapon_id:
            boss.inventory.pop(old_weapon_id, None)
        weapon = self.runtime.catalog.weapons[BICEPS_WEAPON_ID]
        natural = ItemInstance(
            instance_id=f"fieldboss_weapon_{uuid.uuid4().hex[:12]}",
            template_id=BICEPS_WEAPON_ID,
            owner_id=boss.actor_id,
            durability=weapon.base_durability,
            max_durability=weapon.base_durability,
            metadata={"natural_attack": True, "field_boss": BICEPS_ID},
        )
        boss.inventory[natural.instance_id] = natural
        boss.equipment["weapon"] = natural.instance_id
        boss.metadata.update(
            {
                "monster_id": BICEPS_ID,
                "field_boss": True,
                "field_boss_hp_bars": 2,
                "length_m": 20.0,
                "valid_weak_points": ["left_head", "right_head", "abdomen"],
                "shell_side_nearly_invulnerable": True,
                "dangerous_charge": True,
                "spin_threshold_ratio": 0.10,
                "spin_preparation_defense_up": True,
            }
        )
        encounter = self.runtime.start_encounter(
            players + [boss.actor_id],
            zone_id=CALDERA_LAKE,
        )
        instance_id = f"biceps4_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "encounter_id": encounter.encounter_id,
            "boss_id": boss.actor_id,
            "player_ids": players,
            "stage": "battle",
            "started_at_ms": self.runtime.world.now_ms,
            "cleared_at_ms": None,
            "last_attack_player_id": None,
        }
        self._instances()[instance_id] = state
        return self.status(instance_id)

    def _sync_clear(self, state: dict) -> None:
        boss = self.runtime.actors[state["boss_id"]]
        if boss.alive or state["stage"] == "cleared":
            return
        encounter = self.runtime.encounters[state["encounter_id"]]
        killer_id = None
        for event in reversed(encounter.events):
            if event.event_type == "defeated" and event.target_id == boss.actor_id:
                killer_id = event.actor_id
                break
        state["stage"] = "cleared"
        state["cleared_at_ms"] = self.runtime.world.now_ms
        state["last_attack_player_id"] = killer_id
        self.runtime.world.global_flags[CLEAR_FLAG] = True

    def ram_abdomen(self, instance_id: str, actor_id: str) -> dict:
        state = self._instance(instance_id)
        encounter = self.runtime.encounters[state["encounter_id"]]
        boss = self.runtime.actors[state["boss_id"]]
        actor = self.runtime.actors[actor_id]
        if actor_id not in encounter.participants or not actor.alive:
            raise ValueError("ram attacker must be a living raid participant")
        gondola = actor.metadata.get("floor4_gondola")
        if not gondola or not gondola.get("ram_installed"):
            raise ValueError("a gondola with the Fire-Bear ram is required")
        if not boss.alive:
            self._sync_clear(state)
            return self.status(instance_id)
        if boss.hp / boss.max_hp > 0.10:
            raise ValueError("the abdomen ram finisher is available during Biceps's sub-10% spin preparation")

        damage = max(1, int(round(boss.max_hp * 0.12)))
        boss.hp = max(0, boss.hp - damage)
        boss.alive = boss.hp > 0
        self.runtime._append(
            encounter,
            "biceps_abdomen_ram",
            actor_id,
            boss.actor_id,
            damage=damage,
            weak_point="abdomen",
            gondola_id=gondola.get("gondola_id"),
        )
        self.runtime.advance_encounter(encounter.encounter_id, RAM_ACTION_MS)
        if not boss.alive:
            self.runtime._resolve_defeat(encounter, boss, actor_id)
        self._sync_clear(state)
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._instance(instance_id)
        self._sync_clear(state)
        boss = self.runtime.actors[state["boss_id"]]
        bar_hp = boss.max_hp / 2
        remaining = boss.hp
        bars = []
        for index in range(2):
            low = index * bar_hp
            hp = max(0.0, min(bar_hp, remaining - low))
            bars.append({"index": index + 1, "hp": hp, "max_hp": bar_hp})
        ratio = boss.hp / boss.max_hp if boss.max_hp else 0.0
        return {
            **state,
            "boss_name": boss.name,
            "hp": boss.hp,
            "max_hp": boss.max_hp,
            "hp_bars": bars,
            "hp_ratio": ratio,
            "spin_preparing": bool(boss.alive and ratio <= 0.10),
            "weak_points": list(boss.metadata.get("valid_weak_points", ())),
            "shell_side_nearly_invulnerable": True,
            "south_route_unlocked": bool(self.runtime.world.global_flags.get(CLEAR_FLAG)),
        }


def install_floor4_biceps_scenario(runtime) -> Floor4BicepsScenario:
    return Floor4BicepsScenario(runtime)
