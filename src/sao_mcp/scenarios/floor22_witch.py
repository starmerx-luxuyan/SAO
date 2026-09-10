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
from sao_mcp.rules.group_travel import group_travel_record, travel_together
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.transport import (
    authorized_transport,
    authorized_transport_record,
    authorized_transport_within_window,
)


LOG_HOUSE_FLIGHT_MS = 15 * 60_000
WITCH_RETURN_EVENT_RULE_ID = "floor22.witch_return"


class Floor22WitchScenario:
    """Playable Floor 22 Witch quest composed on top of the ordinary Aincrad runtime."""

    scenario_id = "floor22_witch"

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        apply_floor22_catalog_seed(runtime.catalog)
        apply_floor22_world_seed(runtime.world_map)
        runtime.quests.definitions.setdefault(QUEST_ID, floor22_quest_definition())
        install_floor22_npc(runtime)
        runtime.register_world_event_rule(
            WITCH_RETURN_EVENT_RULE_ID,
            self._discover_witch_return_events,
            self._resolve_witch_return_event,
        )
        runtime.evaluate_world_events()

    def instances(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor22_witch_instances", {})

    def instance(self, instance_id: str) -> dict:
        try:
            return self.instances()[instance_id]
        except KeyError as exc:
            raise KeyError(f"unknown Floor 22 Witch quest instance: {instance_id}") from exc

    def start(self, player_ids: list[str]) -> dict:
        runtime = self.runtime
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("quest instance needs at least one player")
        if not runtime.world.floors[22].unlocked:
            raise ValueError("Floor 22 is not unlocked")
        for actor_id in players:
            actor = runtime.actors[actor_id]
            if actor.kind is not EntityKind.PLAYER or not actor.alive:
                raise ValueError("quest participants must be living players")
            if actor.location_id != FOREST_SITE:
                raise ValueError(f"all quest participants must be at {FOREST_SITE}")
            runtime.quests.accept(actor_id, QUEST_ID, now_ms=runtime.world.now_ms)

        instance_id = f"witch22_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "player_ids": players,
            "stage": "isolated_area",
            "optional_treasures": [],
            "werepanther_ids": [],
            "werepanther_encounter_id": None,
            "witch_id": None,
            "witch_encounter_id": None,
            "key_instance_id": None,
            "started_at_ms": runtime.world.now_ms,
            "outbound_transport": None,
            "castle_route": [],
            "return_transport": None,
            "toto_return_transport": None,
            "completed_at_ms": None,
        }
        self.instances()[instance_id] = state
        flight = authorized_transport(
            runtime,
            transport_id=f"{instance_id}:log_house_outbound",
            actor_ids=players,
            npc_ids=[TOTO_ID],
            carrier_actor_id=None,
            from_location_id=FOREST_SITE,
            to_location_id=QUEST_AREA,
            elapsed_ms=LOG_HOUSE_FLIGHT_MS,
            transport_tags=("flying_log_house", "floor22_witch_quest"),
        )
        state["outbound_transport"] = authorized_transport_record(flight)
        for actor_id in players:
            runtime.actors[actor_id].metadata["floor22_witch_instance_id"] = instance_id
        return dict(state)

    def collect_optional_treasure(self, actor_id: str, template_id: str) -> ItemInstance:
        allowed = {
            "scarecrow_stolen_brain",
            "tin_stolen_heart",
            "lion_stolen_courage",
        }
        if template_id not in allowed:
            raise ValueError("item is not one of the three optional Witch quest treasures")
        runtime = self.runtime
        actor = runtime.actors[actor_id]
        instance_id = actor.metadata.get("floor22_witch_instance_id")
        if not instance_id:
            raise ValueError("actor is not inside the Floor 22 Witch quest")
        state = self.instance(str(instance_id))
        if state["stage"] != "isolated_area" or actor.location_id != QUEST_AREA:
            raise ValueError("optional treasures are collected in the isolated quest area before entering the castle")
        if template_id in state["optional_treasures"]:
            raise ValueError("this optional treasure has already been recovered for the instance")
        item = ItemInstance(
            instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
            template_id=template_id,
            owner_id=actor_id,
            quantity=1,
        )
        add_item(actor, item, runtime.catalog, allow_overweight=True)
        state["optional_treasures"].append(template_id)
        for player_id in state["player_ids"]:
            runtime.quests.record_event(
                player_id,
                kind=QuestObjectiveKind.COLLECT,
                target_id=template_id,
            )
        return item

    def enter_castle(self, instance_id: str):
        runtime = self.runtime
        state = self.instance(instance_id)
        if state["stage"] != "isolated_area":
            raise ValueError("quest instance is not ready to enter the Witch's castle")
        player_ids = [actor_id for actor_id in state["player_ids"] if runtime.actors[actor_id].alive]
        if not player_ids:
            raise ValueError("quest instance has no living players")
        for actor_id in player_ids:
            if runtime.actors[actor_id].location_id != QUEST_AREA:
                raise ValueError("all living quest participants must regroup in the isolated quest area")
        route = travel_together(runtime, player_ids, WITCH_CASTLE)
        state["castle_route"] = [group_travel_record(route)]
        players = [runtime.actors[actor_id] for actor_id in player_ids]
        werepanthers = []
        for index in range(4):
            mob = runtime._create_monster(
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
        encounter = runtime.start_encounter(
            [actor.actor_id for actor in players] + [mob.actor_id for mob in werepanthers],
            zone_id=WITCH_CASTLE,
            anti_crystal=True,
        )
        state["werepanther_ids"] = [mob.actor_id for mob in werepanthers]
        state["werepanther_encounter_id"] = encounter.encounter_id
        state["stage"] = "werepanthers"
        return encounter

    def _defeat_killer(self, encounter_id: str | None, target_id: str) -> str | None:
        if not encounter_id:
            return None
        encounter = self.runtime.encounters.get(encounter_id)
        if encounter is None:
            return None
        for event in reversed(encounter.events):
            if event.event_type == "defeated" and event.target_id == target_id:
                return event.actor_id
        return None

    def _ensure_castle_key(self, state: dict) -> ItemInstance:
        runtime = self.runtime
        living_players = [
            runtime.actors[actor_id]
            for actor_id in state["player_ids"]
            if actor_id in runtime.actors and runtime.actors[actor_id].alive
        ]
        for actor in living_players:
            for item in actor.inventory.values():
                if item.template_id == "witch_castle_key":
                    state["key_instance_id"] = item.instance_id
                    return item

        key_holder = next(
            (
                runtime.actors[actor_id]
                for actor_id in state["werepanther_ids"]
                if actor_id in runtime.actors and runtime.actors[actor_id].metadata.get("floor22_key_holder")
            ),
            None,
        )
        if key_holder is None or key_holder.alive:
            raise ValueError("the Werepanther holding the Witch Castle key has not been defeated")
        recipient_id = self._defeat_killer(state.get("werepanther_encounter_id"), key_holder.actor_id)
        if recipient_id not in state["player_ids"] or recipient_id not in runtime.actors or not runtime.actors[recipient_id].alive:
            if not living_players:
                raise ValueError("quest instance has no living player able to receive the castle key")
            recipient_id = living_players[0].actor_id
        recipient = runtime.actors[recipient_id]
        key = ItemInstance(
            instance_id=f"questkey_{uuid.uuid4().hex[:12]}",
            template_id="witch_castle_key",
            owner_id=recipient_id,
            quantity=1,
        )
        add_item(recipient, key, runtime.catalog, allow_overweight=True)
        state["key_instance_id"] = key.instance_id
        encounter = runtime.encounters.get(state.get("werepanther_encounter_id"))
        if encounter is not None:
            runtime._append(
                encounter,
                "witch_castle_key_dropped",
                key_holder.actor_id,
                recipient_id,
                instance_id=state["instance_id"],
            )
        return key

    def start_confrontation(self, instance_id: str, *, accept_soup: bool = False):
        runtime = self.runtime
        state = self.instance(instance_id)
        if state["stage"] != "werepanthers":
            raise ValueError("Witch confrontation is not yet available")
        living_panthers = [
            actor_id
            for actor_id in state["werepanther_ids"]
            if actor_id in runtime.actors and runtime.actors[actor_id].alive
        ]
        if living_panthers:
            raise ValueError("the four Werepanthers must be defeated before reaching the Witch")
        self._ensure_castle_key(state)
        players = [
            runtime.actors[actor_id]
            for actor_id in state["player_ids"]
            if actor_id in runtime.actors and runtime.actors[actor_id].alive
        ]
        if not players:
            raise ValueError("quest instance has no living players")
        witch = runtime._create_monster(
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
        encounter = runtime.start_encounter(
            [actor.actor_id for actor in players] + [witch.actor_id],
            zone_id=WITCH_CASTLE,
            anti_crystal=True,
        )
        if not accept_soup:
            courage_recovered = "lion_stolen_courage" in state["optional_treasures"]
            duration = 1_500 if courage_recovered else 5_000
            for actor in players:
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
            runtime._append(
                encounter,
                "witch_soup_paralysis",
                witch.actor_id,
                None,
                duration_ms=duration,
                lion_courage_recovered=courage_recovered,
                provenance="forced paralysis is canon; duration is simulation",
            )
        state["witch_id"] = witch.actor_id
        state["witch_encounter_id"] = encounter.encounter_id
        state["stage"] = "witch_battle"
        return encounter, witch

    def _sync_witch_defeat(self, state: dict) -> None:
        if state["stage"] != "witch_battle":
            return
        witch_id = state.get("witch_id")
        witch = self.runtime.actors.get(witch_id) if witch_id else None
        if witch is None or witch.alive:
            return
        for player_id in state["player_ids"]:
            if player_id in self.runtime.actors:
                self.runtime.quests.record_event(
                    player_id,
                    kind=QuestObjectiveKind.KILL,
                    target_id="witch_of_the_west",
                )
        state["stage"] = "witch_defeated"
        encounter = self.runtime.encounters.get(state.get("witch_encounter_id"))
        if encounter is not None:
            killer_id = self._defeat_killer(encounter.encounter_id, witch.actor_id)
            self.runtime._append(
                encounter,
                "witch_of_the_west_defeated",
                killer_id,
                witch.actor_id,
                toto_present=True,
            )

    @staticmethod
    def _witch_return_instance_id(occurrence_id: str) -> str:
        prefix = f"{WITCH_RETURN_EVENT_RULE_ID}:"
        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):
            raise RuntimeError(f"invalid Witch return occurrence id: {occurrence_id}")
        return occurrence_id[len(prefix):]

    def _discover_witch_return_events(self) -> list[str]:
        states = self.runtime.world.global_flags.get("floor22_witch_instances", {})
        ready: list[str] = []
        for instance_id, state in states.items():
            if state["stage"] not in {"witch_battle", "witch_defeated"}:
                continue
            witch_id = state.get("witch_id")
            witch = self.runtime.actors.get(witch_id) if witch_id else None
            if (
                witch is None
                or witch.alive
                or witch.metadata.get("defeat_resolved") is not True
            ):
                continue
            returning_ids = [
                actor_id for actor_id in state["player_ids"]
                if actor_id in self.runtime.actors and self.runtime.actors[actor_id].alive
            ]
            if not returning_ids:
                continue
            if any(self.runtime.actors[actor_id].location_id != WITCH_CASTLE for actor_id in returning_ids):
                raise RuntimeError("Witch return candidates are no longer colocated at the Witch Castle")
            ready.append(f"{WITCH_RETURN_EVENT_RULE_ID}:{instance_id}")
        return ready

    def _resolve_witch_return_event(self, occurrence_id: str) -> dict:
        instance_id = self._witch_return_instance_id(occurrence_id)
        state = self.instance(instance_id)
        self._sync_witch_defeat(state)
        result = self._finish_return(instance_id)
        return {
            "instance_id": instance_id,
            "completed_player_ids": list(result["completedPlayerIds"]),
            "stage": result["stage"],
        }

    def _finish_return(self, instance_id: str) -> dict:
        runtime = self.runtime
        state = self.instance(instance_id)
        if state["stage"] != "witch_defeated":
            raise ValueError("the Witch must be defeated before the Log House can return")
        returning_ids = [
            actor_id for actor_id in state["player_ids"]
            if actor_id in runtime.actors and runtime.actors[actor_id].alive
        ]
        if not returning_ids:
            raise ValueError("the Witch quest has no living player to return")
        encounter = runtime.encounters.get(state.get("witch_encounter_id"))
        if encounter is not None and encounter.active:
            active_returners = [actor_id for actor_id in returning_ids if actor_id in encounter.participants]
            if active_returners:
                runtime.remove_encounter_participants(
                    encounter.encounter_id,
                    active_returners,
                    reason="witch_defeated_log_house_return",
                )

        return_started_at_ms = runtime.world.now_ms
        return_flight = authorized_transport(
            runtime,
            transport_id=f"{instance_id}:log_house_return",
            actor_ids=returning_ids,
            carrier_actor_id=None,
            from_location_id=WITCH_CASTLE,
            to_location_id=FOREST_SITE,
            elapsed_ms=LOG_HOUSE_FLIGHT_MS,
            transport_tags=("flying_log_house", "floor22_witch_quest", "return"),
        )
        toto_return = authorized_transport_within_window(
            runtime,
            transport_id=f"{instance_id}:toto_return",
            actor_ids=(),
            npc_ids=[TOTO_ID],
            carrier_actor_id=None,
            from_location_id=QUEST_AREA,
            to_location_id=FOREST_SITE,
            elapsed_ms=LOG_HOUSE_FLIGHT_MS,
            started_at_ms=return_started_at_ms,
            completed_at_ms=runtime.world.now_ms,
            transport_tags=("flying_log_house", "floor22_witch_quest", "return"),
        )
        state["return_transport"] = authorized_transport_record(return_flight)
        state["toto_return_transport"] = authorized_transport_record(toto_return)

        completed = []
        for actor_id in returning_ids:
            actor = runtime.actors[actor_id]
            actor.metadata.pop("floor22_witch_instance_id", None)
            if runtime.quests.ready_to_claim(actor, QUEST_ID):
                runtime.quests.claim(actor, QUEST_ID, runtime.catalog, now_ms=runtime.world.now_ms)
                completed.append(actor_id)
        state["stage"] = "completed"
        state["completed_at_ms"] = runtime.world.now_ms
        return {"instanceId": instance_id, "completedPlayerIds": completed, "stage": "completed"}


def install_floor22_witch_scenario(runtime) -> Floor22WitchScenario:
    scenarios = getattr(runtime, "scenarios", None)
    if scenarios is None:
        scenarios = {}
        runtime.scenarios = scenarios
    existing = scenarios.get(Floor22WitchScenario.scenario_id)
    if isinstance(existing, Floor22WitchScenario):
        return existing
    scenario = Floor22WitchScenario(runtime)
    scenarios[scenario.scenario_id] = scenario
    return scenario
