from __future__ import annotations

import uuid

from sao_mcp.corpus.floor5_shortcut import (
    AREA_BOSS_ID,
    AREA_BOSS_ROOM,
    AREA_BOSS_WEAPON_ID,
    KARLUIN_SHORTCUT_CONNECTION_ID,
    MANANARENA,
    SHORTCUT_TUNNEL,
)
from sao_mcp.corpus.loot import CORE_LOOT_TABLES
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES
from sao_mcp.domain.models import EntityKind, ItemInstance
from sao_mcp.rules.world import unlock_dynamic_world_connection


LOWER_CATACOMBS = "floor_5_karluin_catacombs_lower"
PUZZLE_PROGRESS_REQUIRED_HOURS = 24.0  # Simulation abstraction around Argo spending about a day on the puzzle.
BOSS_WEAKEN_HP_FACTOR = 0.72
BOSS_WEAKEN_ARMOR_FACTOR = 0.55
BOSS_WEAKEN_STRENGTH_FACTOR = 0.75
CLEAR_FLAG = "floor5_karluin_shortcut_area_boss_defeated"
PUZZLE_FLAG = "floor5_karluin_shortcut_puzzle_solved"


class Floor5ShortcutScenario:
    """Karluin catacomb area-boss puzzle and the shortcut to Mananarena."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        definition = AINCRAD_MONSTERS[AREA_BOSS_ID]
        CORE_LOOT_TABLES[definition.loot_table_id] = AINCRAD_MONSTER_LOOT_TABLES[
            definition.loot_table_id
        ]
        runtime.register_defeat_hook(self._on_defeat)

    def _instances(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor5_shortcut_boss_instances", {})

    def _instance(self, instance_id: str) -> dict:
        try:
            return self._instances()[instance_id]
        except KeyError as exc:
            raise KeyError(f"unknown Karluin shortcut boss instance: {instance_id}") from exc

    def _on_defeat(self, encounter, target, killer_id: str | None) -> None:
        for state in self._instances().values():
            if state["boss_id"] != target.actor_id or state["stage"] != "battle":
                continue
            state["stage"] = "cleared"
            state["cleared_at_ms"] = self.runtime.world.now_ms
            self.runtime.world.global_flags[CLEAR_FLAG] = True
            unlock_dynamic_world_connection(
                self.runtime.world,
                self.runtime.world_map,
                KARLUIN_SHORTCUT_CONNECTION_ID,
            )

    def puzzle_state(self) -> dict:
        progress = float(
            self.runtime.world.global_flags.get("floor5_karluin_shortcut_puzzle_hours", 0.0)
        )
        return {
            "progress_hours": progress,
            "required_hours": PUZZLE_PROGRESS_REQUIRED_HOURS,
            "solved": bool(self.runtime.world.global_flags.get(PUZZLE_FLAG)),
        }

    def investigate_puzzle(self, actor_id: str, *, hours: float = 1.0) -> dict:
        if hours <= 0:
            raise ValueError("investigation hours must be positive")
        actor = self.runtime.actors[actor_id]
        if actor.location_id != AREA_BOSS_ROOM:
            raise ValueError("the shortcut boss weakening puzzle is investigated in its guardian room")
        if self.runtime.world.global_flags.get(PUZZLE_FLAG):
            return self.puzzle_state()

        self.runtime.advance_world(int(round(hours * 60 * 60 * 1000)))
        progress = min(
            PUZZLE_PROGRESS_REQUIRED_HOURS,
            float(self.runtime.world.global_flags.get("floor5_karluin_shortcut_puzzle_hours", 0.0))
            + hours,
        )
        self.runtime.world.global_flags["floor5_karluin_shortcut_puzzle_hours"] = progress
        if progress >= PUZZLE_PROGRESS_REQUIRED_HOURS:
            self.runtime.world.global_flags[PUZZLE_FLAG] = True
        return self.puzzle_state()

    def start_area_boss_raid(self, player_ids: list[str]) -> dict:
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("shortcut area-boss raid needs at least one player")
        if self.runtime.world.global_flags.get(CLEAR_FLAG):
            raise ValueError("the Karluin shortcut area boss has already been defeated")
        for actor_id in players:
            actor = self.runtime.actors[actor_id]
            if (
                actor.kind is not EntityKind.PLAYER
                or not actor.alive
                or actor.location_id != AREA_BOSS_ROOM
            ):
                raise ValueError("all participants must be living players in the shortcut guardian room")

        definition = AINCRAD_MONSTERS[AREA_BOSS_ID]
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
        weapon = self.runtime.catalog.weapons[AREA_BOSS_WEAPON_ID]
        natural = ItemInstance(
            instance_id=f"shortcutboss_weapon_{uuid.uuid4().hex[:12]}",
            template_id=AREA_BOSS_WEAPON_ID,
            owner_id=boss.actor_id,
            durability=weapon.base_durability,
            max_durability=weapon.base_durability,
            metadata={"natural_attack": True, "area_boss": AREA_BOSS_ID},
        )
        boss.inventory[natural.instance_id] = natural
        boss.equipment["weapon"] = natural.instance_id
        boss.skill_proficiencies["other"] = min(1000.0, 180.0 + boss.level * 18.0)
        boss.metadata.update(
            {
                "monster_id": AREA_BOSS_ID,
                "area_boss": True,
                "monster_tags": list(definition.tags),
                "proper_name_known": False,
            }
        )

        puzzle_solved = bool(self.runtime.world.global_flags.get(PUZZLE_FLAG))
        if puzzle_solved:
            boss.max_hp = max(1, int(round(boss.max_hp * BOSS_WEAKEN_HP_FACTOR)))
            boss.hp = boss.max_hp
            boss.armor = max(0, int(round(boss.armor * BOSS_WEAKEN_ARMOR_FACTOR)))
            boss.strength = max(1, int(round(boss.strength * BOSS_WEAKEN_STRENGTH_FACTOR)))
            boss.metadata["puzzle_weakened"] = True
        else:
            boss.metadata["puzzle_weakened"] = False
            boss.metadata["resilient_unweakened"] = True

        encounter = self.runtime.start_encounter(
            players + [boss.actor_id],
            zone_id=AREA_BOSS_ROOM,
        )
        instance_id = f"shortcut5_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "encounter_id": encounter.encounter_id,
            "boss_id": boss.actor_id,
            "player_ids": players,
            "stage": "battle",
            "puzzle_weakened": puzzle_solved,
            "started_at_ms": self.runtime.world.now_ms,
            "cleared_at_ms": None,
        }
        self._instances()[instance_id] = state
        return self.status(instance_id)

    def traverse_shortcut(self, actor_id: str, destination_id: str) -> dict:
        if not self.runtime.world.global_flags.get(CLEAR_FLAG):
            raise ValueError("the Karluin-Mananarena shortcut is still blocked by the area boss")
        if destination_id not in {AREA_BOSS_ROOM, SHORTCUT_TUNNEL, MANANARENA}:
            raise ValueError("destination is not part of the Karluin-Mananarena shortcut")
        resolution = self.runtime.travel_actor(actor_id, destination_id)
        return {
            "actor_id": actor_id,
            "from_location_id": resolution.from_location_id,
            "to_location_id": resolution.to_location_id,
            "travel_ms": resolution.elapsed_ms,
            "newly_discovered": resolution.newly_discovered,
            "traversal_tags": list(resolution.traversal_tags),
            "shortcut_unlocked": True,
        }

    def status(self, instance_id: str) -> dict:
        state = self._instance(instance_id)
        boss = self.runtime.actors[state["boss_id"]]
        return {
            **state,
            "boss_name": boss.name,
            "boss_alive": boss.alive,
            "boss_hp": boss.hp,
            "boss_max_hp": boss.max_hp,
            "boss_armor": boss.armor,
            "boss_strength": boss.strength,
            "puzzle": self.puzzle_state(),
            "shortcut_unlocked": bool(self.runtime.world.global_flags.get(CLEAR_FLAG)),
            "shortcut_connection_id": KARLUIN_SHORTCUT_CONNECTION_ID,
        }


def install_floor5_shortcut_scenario(runtime) -> Floor5ShortcutScenario:
    return Floor5ShortcutScenario(runtime)
