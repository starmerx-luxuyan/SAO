from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6_ambush import GAS_MASK_ID, IRON_KEY_ID, JOE_DAGGER_ID, MORTE_HATCHET_ID
from sao_mcp.corpus.floor6_stachion import CYLON_ID, GOLDEN_KEY_ID, POISON_JAR_ID, QUEST_ID, WITNESSES
from sao_mcp.corpus.floor6_world import STACHION_POST_AMBUSH_CONNECTION_ID
from sao_mcp.domain.models import (
    CombatantState,
    CursorColor,
    EntityKind,
    ItemInstance,
    StatusEffectState,
    StatusType,
)
from sao_mcp.rules.group_travel import exit_encounter_via_travel, group_travel_record
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.state_authority import locate_runtime_item
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.transport import authorized_boarding, authorized_transport_record
from sao_mcp.rules.world import unlock_dynamic_world_connection


STACHION = "floor_6_stachion"
PUZZLE_QUARTER = "floor_6_stachion_puzzle_quarter"
CYLON_MANOR = "floor_6_cylon_lord_manor"
TRAVELLER_GRAVE = "floor_6_traveller_grave"
SURIBUS = "floor_6_suribus"
PITHAGRUS_HOUSE = "floor_6_pithagrus_suribus_house"
CYLON_TRANSPORT = "floor_6_cylon_transport_carriage"
FIELD = "floor_6_field"
HOUSE_SEARCH_MS = 75 * 60_000
TRANSPORT_TO_AMBUSH_MS = 18 * 60_000
SCRIPTED_PARALYSIS_MS = 2 * 60 * 60_000
POST_CYLON_DEATH_PARALYSIS_MS = 90_000
AMBUSH_RETREAT_HP_RATIO = 0.25  # Simulation threshold; canon only establishes that the pair eventually retreat.


class Floor6StachionScenario:
    """Curse of Stachion through Cylon's death and the handoff back to ordinary world/PvP rules."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor6_stachion_quest_states", {})

    def _state(self, actor_id: str) -> dict:
        try:
            return self._states()[actor_id]
        except KeyError as exc:
            raise ValueError("Curse of Stachion has not been started") from exc

    def _active_progress(self, actor_id: str):
        progress = self.runtime.quests.progress_by_actor.get(actor_id, {}).get(QUEST_ID)
        if progress is None or progress.claimed:
            raise ValueError("Curse of Stachion must be active")
        return progress

    def start_quest(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != CYLON_MANOR:
            raise ValueError("Curse of Stachion begins with Cylon at the Stachion lord's manor")
        self.runtime.accept_quest(actor_id, QUEST_ID)
        self._states().setdefault(
            actor_id,
            {
                "actor_id": actor_id,
                "stage": "interview_old_associates",
                "started_at_ms": self.runtime.world.now_ms,
                "witnesses_interviewed": [],
                "suribus_house_revealed_at_ms": None,
                "golden_key_obtained_at_ms": None,
                "capture_event_started": False,
                "captured_at_ms": None,
                "capture_boarding": None,
                "cylon_actor_id": None,
                "transport_encounter_id": None,
                "confiscated_key_instance_id": None,
                "ambush_site_reached_at_ms": None,
                "post_ambush_routes_unlocked_at_ms": None,
                "morte_actor_id": None,
                "joe_actor_id": None,
                "ground_cache_actor_id": None,
                "cylon_killed_at_ms": None,
                "poison_cloud_active": False,
                "ambushers_retreated_at_ms": None,
                "ambusher_retreat_route": None,
                "ground_loot_recovered_at_ms": None,
                "recovered_instance_ids": [],
            },
        )
        return self.status(actor_id)

    def interview_witness(self, actor_id: str, witness_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        state = self._state(actor_id)
        if actor.location_id != PUZZLE_QUARTER:
            raise ValueError("Pithagrus's former associates are interviewed in Stachion's puzzle-heavy town area")
        if witness_id not in WITNESSES:
            raise KeyError(witness_id)
        self.runtime.interact_npc(actor_id, witness_id)
        interviewed = state["witnesses_interviewed"]
        if witness_id not in interviewed:
            interviewed.append(witness_id)
            self.runtime.quests.record_event(
                actor_id, kind=QuestObjectiveKind.DISCOVER, target_id="stachion_old_household_testimony"
            )
        if len(interviewed) == len(WITNESSES) and state["suribus_house_revealed_at_ms"] is None:
            state["stage"] = "travel_to_suribus_second_home"
            state["suribus_house_revealed_at_ms"] = self.runtime.world.now_ms
            self.runtime.quests.record_event(
                actor_id, kind=QuestObjectiveKind.DISCOVER, target_id="pithagrus_suribus_house_discovered"
            )
        return self.status(actor_id)

    def search_pithagrus_house(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        state = self._state(actor_id)
        if actor.location_id != PITHAGRUS_HOUSE:
            raise ValueError("the golden key is found at Pithagrus's second home in Suribus")
        if len(state["witnesses_interviewed"]) < len(WITNESSES):
            raise ValueError("the Stachion interviews have not yet revealed Pithagrus's Suribus house")
        existing = next((item for item in actor.inventory.values() if item.template_id == GOLDEN_KEY_ID), None)
        if existing is None:
            self.runtime.advance_world(HOUSE_SEARCH_MS)
            existing = ItemInstance(
                instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
                template_id=GOLDEN_KEY_ID,
                owner_id=actor_id,
            )
            add_item(actor, existing, self.runtime.catalog, allow_overweight=True)
            self.runtime.quests.record_event(actor_id, kind=QuestObjectiveKind.COLLECT, target_id=GOLDEN_KEY_ID)
            state["golden_key_obtained_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "golden_key_obtained_capture_pending"
        return self.status(actor_id)

    def _create_cylon_actor(self) -> CombatantState:
        actor_id = f"questnpc_cylon_{uuid.uuid4().hex[:12]}"
        cylon = CombatantState(
            actor_id=actor_id,
            name="Cylon",
            kind=EntityKind.NPC,
            level=18,
            max_hp=2800,
            hp=2800,
            strength=32,
            agility=28,
            armor=85,
            evasion=5,
            cursor=CursorColor.YELLOW,
            location_id=PITHAGRUS_HOUSE,
            metadata={"npc_definition_id": CYLON_ID, "quest_id": QUEST_ID, "combat_stats_provenance": "simulation"},
        )
        for template_id, metadata in (
            (POISON_JAR_ID, {"scripted_capture_tool": True}),
            (IRON_KEY_ID, {"cylon_quest_valuable": True}),
            (GAS_MASK_ID, {"paralysis_gas_protection": True}),
        ):
            item = ItemInstance(
                instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
                template_id=template_id,
                owner_id=actor_id,
                metadata=metadata,
            )
            cylon.inventory[item.instance_id] = item
        self.runtime.actors[actor_id] = cylon
        return cylon

    def trigger_cylon_capture(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        state = self._state(actor_id)
        if actor.location_id != PITHAGRUS_HOUSE:
            raise ValueError("Cylon's scripted capture triggers as the player attempts to leave the Suribus house")
        if state["stage"] != "golden_key_obtained_capture_pending":
            raise ValueError("the golden key must be obtained before Cylon's capture event")
        key = next((item for item in actor.inventory.values() if item.template_id == GOLDEN_KEY_ID), None)
        if key is None:
            raise ValueError("the player no longer carries Pithagrus's golden key")
        cylon = self._create_cylon_actor()
        actor.inventory.pop(key.instance_id)
        key.owner_id = cylon.actor_id
        key.metadata["confiscated_by_cylon"] = True
        cylon.inventory[key.instance_id] = key
        actor.statuses = [status for status in actor.statuses if status.stack_key != "scripted_cylon_paralysis"]
        actor.statuses.append(
            StatusEffectState(
                effect_id=f"cylon_paralysis:{actor_id}:{self.runtime.world.now_ms}",
                status_type=StatusType.PARALYSIS,
                source_id=cylon.actor_id,
                remaining_ms=SCRIPTED_PARALYSIS_MS,
                magnitude=1.0,
                tick_interval_ms=SCRIPTED_PARALYSIS_MS,
                until_next_tick_ms=SCRIPTED_PARALYSIS_MS,
                stack_key="scripted_cylon_paralysis",
                tags=("scripted", "curse_of_stachion", "namnepenth_poison_gas", "full_body"),
            )
        )
        actor.metadata["scripted_capture"] = "cylon_transport"
        boarding = authorized_boarding(
            self.runtime,
            transport_id=f"cylon_carriage_boarding:{actor_id}",
            actor_ids=[actor_id, cylon.actor_id],
            from_location_id=PITHAGRUS_HOUSE,
            transport_location_id=CYLON_TRANSPORT,
            transport_tags=("cylon_capture", "carriage"),
        )
        encounter = self.runtime.start_encounter([actor_id, cylon.actor_id], zone_id=CYLON_TRANSPORT, safe_zone=False)
        self.runtime._append(
            encounter,
            "cylon_scripted_capture",
            cylon.actor_id,
            actor_id,
            poison_jar_template_id=POISON_JAR_ID,
            confiscated_key_instance_id=key.instance_id,
            boarding_transport_id=boarding.transport_id,
        )
        state.update(
            stage="captured_transport_to_stachion",
            capture_event_started=True,
            captured_at_ms=self.runtime.world.now_ms,
            capture_boarding=authorized_transport_record(boarding),
            cylon_actor_id=cylon.actor_id,
            transport_encounter_id=encounter.encounter_id,
            confiscated_key_instance_id=key.instance_id,
        )
        return self.status(actor_id)

    def advance_transport_to_ambush_site(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state["stage"] != "captured_transport_to_stachion":
            raise ValueError("Cylon's carriage transport is not currently active")
        encounter_id = state["transport_encounter_id"]
        self.runtime.advance_encounter(encounter_id, TRANSPORT_TO_AMBUSH_MS)
        unlock_dynamic_world_connection(
            self.runtime.world,
            self.runtime.world_map,
            STACHION_POST_AMBUSH_CONNECTION_ID,
        )
        state["stage"] = "morte_joe_ambush_pending"
        state["ambush_site_reached_at_ms"] = self.runtime.world.now_ms
        state["post_ambush_routes_unlocked_at_ms"] = self.runtime.world.now_ms
        self.runtime._append(
            self.runtime.encounters[encounter_id], "transport_reaches_ambush_site", state["cylon_actor_id"], actor_id
        )
        return self.status(actor_id)

    def _create_hostile_player(
        self,
        name: str,
        weapon_template_id: str,
        *,
        level: int,
        strength: int,
        agility: int,
    ) -> CombatantState:
        actor_id = f"namedplayer_{name.lower()}_{uuid.uuid4().hex[:10]}"
        weapon_template = self.runtime.catalog.weapons[weapon_template_id]
        player = CombatantState(
            actor_id=actor_id,
            name=name,
            kind=EntityKind.PLAYER,
            level=level,
            max_hp=5200 + level * 100,
            hp=5200 + level * 100,
            strength=strength,
            agility=agility,
            armor=145,
            evasion=12,
            cursor=CursorColor.GREEN,
            location_id=CYLON_TRANSPORT,
            skill_proficiencies={weapon_template.weapon_class.value: 620.0, "parry": 420.0},
            metadata={"named_player_npc": True, "hostile_scene_actor": True, "combat_stats_provenance": "simulation"},
        )
        weapon = ItemInstance(
            instance_id=f"weapon_{uuid.uuid4().hex[:12]}",
            template_id=weapon_template_id,
            owner_id=actor_id,
            durability=weapon_template.base_durability,
            max_durability=weapon_template.base_durability,
        )
        player.inventory[weapon.instance_id] = weapon
        player.equipment["weapon"] = weapon.instance_id
        if name == "Morte" and "anneal_blade" in self.runtime.catalog.weapons:
            alt = self.runtime.catalog.weapons["anneal_blade"]
            alt_item = ItemInstance(
                instance_id=f"weapon_{uuid.uuid4().hex[:12]}",
                template_id="anneal_blade",
                owner_id=actor_id,
                durability=alt.base_durability,
                max_durability=alt.base_durability,
                metadata={"quick_change_alternate": True},
            )
            player.inventory[alt_item.instance_id] = alt_item
        self.runtime.actors[actor_id] = player
        return player

    def _drop_cylon_inventory(self, cylon: CombatantState) -> CombatantState:
        cache_id = f"groundloot_cylon_{uuid.uuid4().hex[:10]}"
        cache = CombatantState(
            actor_id=cache_id,
            name="Cylon's Dropped Valuables",
            kind=EntityKind.NPC,
            level=1,
            max_hp=1,
            hp=1,
            strength=1,
            agility=1,
            cursor=CursorColor.YELLOW,
            location_id=CYLON_TRANSPORT,
            metadata={"ground_loot_cache": True, "noncombatant": True, "source_actor_id": cylon.actor_id},
        )
        for instance_id, item in list(cylon.inventory.items()):
            cylon.inventory.pop(instance_id)
            item.owner_id = None
            item.metadata["ground_drop_reason"] = "Cylon killed in Morte/Joe carriage ambush"
            cache.inventory[instance_id] = item
        self.runtime.actors[cache_id] = cache
        return cache

    def trigger_morte_joe_ambush(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state["stage"] != "morte_joe_ambush_pending":
            raise ValueError("the carriage has not reached the Morte/Joe ambush point")
        encounter = self.runtime.encounters[state["transport_encounter_id"]]
        cylon = self.runtime.actors[state["cylon_actor_id"]]
        morte = self._create_hostile_player("Morte", MORTE_HATCHET_ID, level=24, strength=52, agility=47)
        joe = self._create_hostile_player("Joe", JOE_DAGGER_ID, level=22, strength=38, agility=56)
        encounter.participants[morte.actor_id] = morte
        encounter.participants[joe.actor_id] = joe
        player_position = encounter.positions.get(actor_id, (-1.15, 0.0))
        encounter.positions[morte.actor_id] = (player_position[0] + 3.0, player_position[1] + 1.2)
        encounter.positions[joe.actor_id] = (player_position[0] + 3.2, player_position[1] - 1.2)
        self.runtime._append(encounter, "morte_joe_ambush", morte.actor_id, cylon.actor_id, joe_actor_id=joe.actor_id)
        cylon.hp = 0
        cylon.alive = False
        self.runtime._resolve_defeat(encounter, cylon, morte.actor_id)
        cache = self._drop_cylon_inventory(cylon)
        for status in self.runtime.actors[actor_id].statuses:
            if status.stack_key == "scripted_cylon_paralysis":
                status.remaining_ms = min(status.remaining_ms, POST_CYLON_DEATH_PARALYSIS_MS)
                status.until_next_tick_ms = min(status.until_next_tick_ms, status.remaining_ms)
        state.update(
            stage="ambush_cylon_dead",
            morte_actor_id=morte.actor_id,
            joe_actor_id=joe.actor_id,
            ground_cache_actor_id=cache.actor_id,
            cylon_killed_at_ms=self.runtime.world.now_ms,
        )
        return self.status(actor_id)

    def topple_poison_jar(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state["stage"] != "ambush_cylon_dead":
            raise ValueError("the poison jar can be used after Cylon has been killed and his valuables spill onto the road")
        actor = self.runtime.actors[actor_id]
        if not any(status.status_type is StatusType.PARALYSIS for status in actor.statuses):
            raise ValueError("this scene action represents blowing the jar over while still paralysed")
        cache = self.runtime.actors[state["ground_cache_actor_id"]]
        jar = next((item for item in cache.inventory.values() if item.template_id == POISON_JAR_ID), None)
        if jar is None:
            raise ValueError("Namnepenth's Poison Jar is not among Cylon's ground loot")
        jar.metadata["toppled"] = True
        jar.metadata["paralysis_cloud_active"] = True
        for hostile_id in (state["morte_actor_id"], state["joe_actor_id"]):
            self.runtime.actors[hostile_id].metadata["avoiding_paralysis_cloud"] = True
        state["poison_cloud_active"] = True
        state["stage"] = "poison_cloud_deployed"
        self.runtime._append(
            self.runtime.encounters[state["transport_encounter_id"]],
            "poison_jar_toppled_by_breath",
            actor_id,
            None,
            poison_jar_instance_id=jar.instance_id,
        )
        return self.status(actor_id)

    def advance_to_paralysis_release(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state["stage"] != "poison_cloud_deployed":
            raise ValueError("the poison-cloud diversion has not been created")
        actor = self.runtime.actors[actor_id]
        remaining = max(
            (status.remaining_ms for status in actor.statuses if status.stack_key == "scripted_cylon_paralysis"),
            default=0,
        )
        if remaining:
            self.runtime.advance_encounter(state["transport_encounter_id"], remaining)
        actor.metadata.pop("scripted_capture", None)
        state["stage"] = "morte_joe_pvp_active"
        return self.status(actor_id)

    def _ambusher_ids(self, state: dict) -> tuple[str, ...]:
        return tuple(
            hostile_id
            for hostile_id in (state.get("morte_actor_id"), state.get("joe_actor_id"))
            if hostile_id
        )

    def _ambushers_neutralized(self, state: dict) -> bool:
        encounter = self.runtime.encounters[state["transport_encounter_id"]]
        for hostile_id in self._ambusher_ids(state):
            hostile = self.runtime.actors[hostile_id]
            if hostile.alive and not hostile.metadata.get("retreated") and hostile_id in encounter.participants:
                return False
        return True

    def resolve_ambusher_retreat(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state["stage"] != "morte_joe_pvp_active":
            raise ValueError("Morte/Joe retreat can only resolve after the paralysis handoff to ordinary PvP")
        encounter = self.runtime.encounters[state["transport_encounter_id"]]
        hostiles = [self.runtime.actors[hostile_id] for hostile_id in self._ambusher_ids(state)]
        trigger = any(not hostile.alive for hostile in hostiles) or any(
            hostile.alive and hostile.max_hp > 0 and hostile.hp / hostile.max_hp <= AMBUSH_RETREAT_HP_RATIO
            for hostile in hostiles
        )
        if not trigger:
            raise ValueError("the ambushers have not yet reached the simulation retreat condition")

        retreating = [hostile for hostile in hostiles if hostile.alive and not hostile.metadata.get("retreated")]
        route = None
        if retreating:
            movement = exit_encounter_via_travel(
                self.runtime,
                encounter.encounter_id,
                [hostile.actor_id for hostile in retreating],
                FIELD,
            )
            route = group_travel_record(movement)
        retreated_ids: list[str] = []
        for hostile in retreating:
            hostile.metadata["retreated"] = True
            hostile.metadata["retreated_from_floor6_ambush_at_ms"] = self.runtime.world.now_ms
            retreated_ids.append(hostile.actor_id)
            self.runtime._append(
                encounter,
                "ambusher_retreated",
                hostile.actor_id,
                actor_id,
                hp=hostile.hp,
                max_hp=hostile.max_hp,
                retreat_threshold_ratio=AMBUSH_RETREAT_HP_RATIO,
                destination_id=FIELD,
            )

        if not self._ambushers_neutralized(state):
            raise RuntimeError("ambush retreat did not clear every living hostile")
        state["stage"] = "ambushers_neutralized_ground_loot"
        state["ambushers_retreated_at_ms"] = self.runtime.world.now_ms
        state["ambusher_retreat_ids"] = retreated_ids
        state["ambusher_retreat_route"] = route
        return self.status(actor_id)

    def recover_cylon_ground_loot(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state["stage"] == "morte_joe_pvp_active" and self._ambushers_neutralized(state):
            state["stage"] = "ambushers_neutralized_ground_loot"
        if state["stage"] != "ambushers_neutralized_ground_loot":
            raise ValueError("Cylon's valuables cannot be recovered while a living ambusher still controls the road")
        actor = self.runtime.actors[actor_id]
        cache = self.runtime.actors[state["ground_cache_actor_id"]]
        recovered: list[str] = []
        for instance_id, item in list(cache.inventory.items()):
            cache.inventory.pop(instance_id)
            item.metadata.pop("ground_drop_reason", None)
            add_item(actor, item, self.runtime.catalog, allow_overweight=True)
            recovered.append(instance_id)
        cache.metadata["emptied"] = True
        cache.metadata["recovered_by_actor_id"] = actor_id
        state["stage"] = "post_ambush_loot_recovered"
        state["ground_loot_recovered_at_ms"] = self.runtime.world.now_ms
        state["recovered_instance_ids"] = recovered
        self.runtime._append(
            self.runtime.encounters[state["transport_encounter_id"]],
            "cylon_ground_loot_recovered",
            actor_id,
            None,
            recovered_instance_ids=recovered,
        )
        return {
            "recovered_instance_ids": recovered,
            "state": self.status(actor_id),
        }

    def status(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        actor = self.runtime.actors[actor_id]
        progress = self.runtime.quests.progress_by_actor.get(actor_id, {}).get(QUEST_ID)
        player_key = next((item for item in actor.inventory.values() if item.template_id == GOLDEN_KEY_ID), None)
        key_owner_id = player_key.owner_id if player_key else None
        key_instance_id = state.get("confiscated_key_instance_id")
        if key_instance_id:
            located = locate_runtime_item(self.runtime, key_instance_id)
            if located is not None:
                key = located.item
                if key.template_id != GOLDEN_KEY_ID:
                    raise RuntimeError("Stachion confiscated golden-key instance ID points to the wrong item template")
                key_owner_id = located.sole_actor_id
            else:
                key_owner_id = None
        ground_items: list[dict] = []
        cache_id = state.get("ground_cache_actor_id")
        if cache_id in self.runtime.actors:
            cache = self.runtime.actors[cache_id]
            for item in cache.inventory.values():
                ground_items.append({"instance_id": item.instance_id, "template_id": item.template_id, "owner_id": item.owner_id})
        paralysed = any(status.status_type is StatusType.PARALYSIS and status.remaining_ms > 0 for status in actor.statuses)
        ambushers_neutralized = False
        if state.get("transport_encounter_id") in self.runtime.encounters and self._ambusher_ids(state):
            ambushers_neutralized = self._ambushers_neutralized(state)
        return {
            **state,
            "witness_count": len(state["witnesses_interviewed"]),
            "witness_total": len(WITNESSES),
            "has_golden_key": player_key is not None,
            "golden_key_owner_id": key_owner_id,
            "paralysed": paralysed,
            "ambushers_neutralized": ambushers_neutralized,
            "ground_items": sorted(ground_items, key=lambda row: (row["template_id"], row["instance_id"])),
            "quest_progress": dict(progress.counters) if progress else None,
            "ready_to_claim": self.runtime.quests.ready_to_claim(actor, QUEST_ID) if progress else False,
            "next_canon_stage": (
                "Morte and Joe ambush Cylon's carriage" if state["stage"] == "morte_joe_ambush_pending"
                else "blow over Namnepenth's Poison Jar while paralysed" if state["stage"] == "ambush_cylon_dead"
                else "wait for scripted paralysis to expire, then fight or escape" if state["stage"] == "poison_cloud_deployed"
                else "recover Cylon's dropped keys and tools" if state["stage"] == "ambushers_neutralized_ground_loot"
                else "compulsory Cylon capture event" if state["stage"] == "golden_key_obtained_capture_pending"
                else None
            ),
        }


def install_floor6_stachion_scenario(runtime) -> Floor6StachionScenario:
    if QUEST_ID not in runtime.quests.definitions or CYLON_ID not in runtime.npcs.definitions:
        raise RuntimeError("Curse of Stachion quest/NPC corpus was not loaded")
    required_items = {GOLDEN_KEY_ID, POISON_JAR_ID, IRON_KEY_ID, GAS_MASK_ID}
    if any(template_id not in runtime.catalog.items for template_id in required_items):
        raise RuntimeError("Floor 6 Stachion quest-item corpus was not loaded")
    if MORTE_HATCHET_ID not in runtime.catalog.weapons or JOE_DAGGER_ID not in runtime.catalog.weapons:
        raise RuntimeError("Floor 6 ambush weapon corpus was not loaded")
    return Floor6StachionScenario(runtime)
