from __future__ import annotations

import uuid

from sao_mcp.corpus.floor22 import (
    FOREST_SITE,
    QUEST_AREA,
    QUEST_ID,
    TOTO_ID,
    WITCH_CASTLE,
    apply_floor22_catalog_seed,
    apply_floor22_world_seed,
    floor22_quest_definition,
    install_floor22_npc,
)
from sao_mcp.domain.models import EntityKind, ItemInstance, StatusEffectState, StatusType
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


class Floor22QuestAincradRuntime(HousingAincradRuntime):
    """Full housing runtime plus the canonical Forest House K4 unlock scenario."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        apply_floor22_catalog_seed(self.catalog)
        apply_floor22_world_seed(self.world_map)
        self.quests.definitions.setdefault(QUEST_ID, floor22_quest_definition())
        install_floor22_npc(self)

    def _instances(self) -> dict:
        return self.world.global_flags.setdefault("floor22_witch_instances", {})

    def _instance(self, instance_id: str) -> dict:
        try:
            return self._instances()[instance_id]
        except KeyError as exc:
            raise KeyError(f"unknown Floor 22 Witch quest instance: {instance_id}") from exc

    def start_witch_quest(self, player_ids: list[str]) -> dict:
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("quest instance needs at least one player")
        if not self.world.floors[22].unlocked:
            raise ValueError("Floor 22 is not unlocked")
        for actor_id in players:
            actor = self.actors[actor_id]
            if actor.kind is not EntityKind.PLAYER or not actor.alive:
                raise ValueError("quest participants must be living players")
            if actor.location_id != FOREST_SITE:
                raise ValueError(f"all quest participants must be at {FOREST_SITE}")
            self.quests.accept(actor_id, QUEST_ID, now_ms=self.world.now_ms)

        instance_id = f"witch22_{uuid.uuid4().hex[:12]}"
        instance = {
            "instance_id": instance_id,
            "player_ids": players,
            "stage": "isolated_area",
            "optional_treasures": [],
            "werepanther_ids": [],
            "witch_id": None,
            "key_instance_id": None,
            "started_at_ms": self.world.now_ms,
            "completed_at_ms": None,
        }
        self._instances()[instance_id] = instance
        # The Log House + Toto transition is a scripted quest transfer, not an ordinary walking edge.
        self.world.now_ms += 15 * 60_000
        for actor_id in players:
            actor = self.actors[actor_id]
            actor.location_id = QUEST_AREA
            actor.metadata["floor22_witch_instance_id"] = instance_id
            self.world.floors[22].discovered_locations.add(QUEST_AREA)
        self.npcs.states[TOTO_ID].location_id = QUEST_AREA
        return dict(instance)

    def collect_witch_optional_treasure(self, actor_id: str, template_id: str) -> ItemInstance:
        allowed = {
            "scarecrow_stolen_brain",
            "tin_stolen_heart",
            "lion_stolen_courage",
        }
        if template_id not in allowed:
            raise ValueError("item is not one of the three optional Witch quest treasures")
        actor = self.actors[actor_id]
        instance_id = actor.metadata.get("floor22_witch_instance_id")
        if not instance_id:
            raise ValueError("actor is not inside the Floor 22 Witch quest")
        instance = self._instance(str(instance_id))
        if instance["stage"] != "isolated_area" or actor.location_id != QUEST_AREA:
            raise ValueError("optional treasures are collected in the isolated quest area before entering the castle")
        if template_id in instance["optional_treasures"]:
            raise ValueError("this optional treasure has already been recovered for the instance")
        item = ItemInstance(
            instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
            template_id=template_id,
            owner_id=actor_id,
            quantity=1,
        )
        add_item(actor, item, self.catalog, allow_overweight=True)
        instance["optional_treasures"].append(template_id)
        for player_id in instance["player_ids"]:
            self.quests.record_event(
                player_id,
                kind=QuestObjectiveKind.COLLECT,
                target_id=template_id,
            )
        return item

    def enter_witch_castle(self, instance_id: str):
        instance = self._instance(instance_id)
        if instance["stage"] != "isolated_area":
            raise ValueError("quest instance is not ready to enter the Witch's castle")
        players = [self.actors[actor_id] for actor_id in instance["player_ids"] if self.actors[actor_id].alive]
        if not players:
            raise ValueError("quest instance has no living players")
        for actor in players:
            if actor.location_id != QUEST_AREA:
                raise ValueError("all living quest participants must regroup in the isolated quest area")
            actor.location_id = WITCH_CASTLE
        self.world.now_ms += 12 * 60_000
        werepanthers = []
        for index in range(4):
            mob = self._create_monster(
                name="Werepanther",
                level=25,
                location_id=WITCH_CASTLE,
                hp_factor=1.05,
                loot_table_id="",
                quest_kill_id="witch_castle_werepanther",
            )
            mob.metadata["floor22_witch_instance_id"] = instance_id
            mob.metadata["floor22_key_holder"] = index == 0
            werepanthers.append(mob)
        encounter = self.start_encounter(
            [actor.actor_id for actor in players] + [mob.actor_id for mob in werepanthers],
            zone_id=WITCH_CASTLE,
            anti_crystal=True,
        )
        instance["werepanther_ids"] = [mob.actor_id for mob in werepanthers]
        instance["stage"] = "werepanthers"
        return encounter

    def start_witch_confrontation(self, instance_id: str, *, accept_soup: bool = False):
        instance = self._instance(instance_id)
        if instance["stage"] != "werepanthers":
            raise ValueError("Witch confrontation is not yet available")
        living_panthers = [
            actor_id for actor_id in instance["werepanther_ids"]
            if actor_id in self.actors and self.actors[actor_id].alive
        ]
        if living_panthers:
            raise ValueError("the four Werepanthers must be defeated before reaching the Witch")
        holders = [
            self.actors[actor_id]
            for actor_id in instance["player_ids"]
            if actor_id in self.actors and self.actors[actor_id].alive
        ]
        has_key = any(
            item.template_id == "witch_castle_key"
            for actor in holders
            for item in actor.inventory.values()
        )
        if not has_key:
            raise ValueError("the Witch Castle key is required to reach the inner room")
        witch = self._create_monster(
            name="Witch of the West",
            level=28,
            location_id=WITCH_CASTLE,
            hp_factor=3.4,
            loot_table_id="",
            quest_kill_id="witch_of_the_west",
        )
        witch.metadata["floor22_witch_instance_id"] = instance_id
        witch.metadata["floor22_witch_boss"] = True
        witch.metadata["toto_present"] = True
        encounter = self.start_encounter(
            [actor.actor_id for actor in holders] + [witch.actor_id],
            zone_id=WITCH_CASTLE,
            anti_crystal=True,
        )
        if not accept_soup:
            courage_recovered = "lion_stolen_courage" in instance["optional_treasures"]
            duration = 1_500 if courage_recovered else 5_000
            for actor in holders:
                actor.statuses.append(
                    StatusEffectState(
                        effect_id=f"witch_paralysis_{uuid.uuid4().hex[:10]}",
                        status_type=StatusType.PARALYSIS,
                        source_id=witch.actor_id,
                        remaining_ms=duration,
                        magnitude=1.0,
                        tick_interval_ms=duration,
                        until_next_tick_ms=duration,
                        tags=("floor22_witch_script", "lion_roar_releases"),
                    )
                )
            self._append(
                encounter,
                "witch_soup_paralysis",
                witch.actor_id,
                None,
                duration_ms=duration,
                lion_courage_recovered=courage_recovered,
                provenance="forced paralysis is canon; duration is simulation",
            )
        instance["witch_id"] = witch.actor_id
        instance["stage"] = "witch_battle"
        return encounter, witch

    def _grant_castle_key(self, killer_id: str, instance: dict) -> None:
        killer = self.actors[killer_id]
        if any(item.template_id == "witch_castle_key" for item in killer.inventory.values()):
            return
        key = ItemInstance(
            instance_id=f"questkey_{uuid.uuid4().hex[:12]}",
            template_id="witch_castle_key",
            owner_id=killer_id,
            quantity=1,
        )
        add_item(killer, key, self.catalog, allow_overweight=True)
        instance["key_instance_id"] = key.instance_id

    def _resolve_defeat(self, encounter, target, killer_id):
        already = bool(target.metadata.get("defeat_resolved"))
        super()._resolve_defeat(encounter, target, killer_id)
        if already:
            return
        instance_id = target.metadata.get("floor22_witch_instance_id")
        if not instance_id or instance_id not in self._instances():
            return
        instance = self._instance(str(instance_id))
        if target.metadata.get("floor22_key_holder") and killer_id in self.actors:
            self._grant_castle_key(killer_id, instance)
            self._append(
                encounter,
                "witch_castle_key_dropped",
                target.actor_id,
                killer_id,
                instance_id=instance_id,
            )
        if target.metadata.get("floor22_witch_boss"):
            for player_id in instance["player_ids"]:
                if player_id in self.actors:
                    self.quests.record_event(
                        player_id,
                        kind=QuestObjectiveKind.KILL,
                        target_id="witch_of_the_west",
                    )
            instance["stage"] = "witch_defeated"
            self._append(
                encounter,
                "witch_of_the_west_defeated",
                killer_id,
                target.actor_id,
                toto_present=True,
            )

    def return_from_witch_quest(self, instance_id: str) -> dict:
        instance = self._instance(instance_id)
        if instance["stage"] != "witch_defeated":
            raise ValueError("the Witch must be defeated before the Log House can return")
        completed = []
        for actor_id in instance["player_ids"]:
            actor = self.actors[actor_id]
            actor.location_id = FOREST_SITE
            actor.metadata.pop("floor22_witch_instance_id", None)
            if self.quests.ready_to_claim(actor, QUEST_ID):
                self.quests.claim(actor, QUEST_ID, self.catalog, now_ms=self.world.now_ms)
                completed.append(actor_id)
        self.npcs.states[TOTO_ID].location_id = FOREST_SITE
        self.world.now_ms += 15 * 60_000
        instance["stage"] = "completed"
        instance["completed_at_ms"] = self.world.now_ms
        return {"instanceId": instance_id, "completedPlayerIds": completed, "stage": "completed"}
