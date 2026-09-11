from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.access import require_location_access
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.state_authority import authoritative_guild_id
from sao_mcp.rules.travel import AUTONOMOUS_TRAVEL_RESTRICTION_KEY


VISIBLE_COMBAT_EVENT_PAYLOAD_KEYS = frozenset({
    "hit",
    "critical",
    "parried",
    "guarded",
    "evaded",
    "damage",
    "sword_skill",
    "reason",
    "template_id",
    "consumed",
    "status",
    "status_type",
    "incoming_id",
    "destination_id",
    "actor_ids",
})


class GMObservationGate:
    """Project only state observable from explicitly named player viewpoints.

    The gate is stateless. It never owns world, actor, quest, guild or knowledge state; all rows are
    derived from the authoritative runtime at read time. Hidden actor-core plans, world-event
    occurrences, canonical expectations, threat tables and other omniscient runtime internals have
    no projection here.
    """

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def validate_observer_actor_ids(self, observer_actor_ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        if not isinstance(observer_actor_ids, (list, tuple)) or not observer_actor_ids:
            raise ValueError("GM observation requires at least one explicit player viewpoint")
        if any(not isinstance(actor_id, str) or not actor_id for actor_id in observer_actor_ids):
            raise ValueError("GM observation viewpoint IDs must be non-empty strings")
        ids = tuple(observer_actor_ids)
        if len(set(ids)) != len(ids):
            raise ValueError("GM observation viewpoint IDs must be unique")
        for actor_id in ids:
            actor = self.runtime.actors.get(actor_id)
            if actor is None:
                raise KeyError(actor_id)
            if actor.kind is not EntityKind.PLAYER:
                raise ValueError("GM observation viewpoints must be player actors")
        return ids

    def current_observer_encounter_ids(self, observer_actor_ids: tuple[str, ...]) -> set[str]:
        observer_set = set(observer_actor_ids)
        return {
            encounter_id
            for encounter_id, encounter in self.runtime.encounters.items()
            if observer_set.intersection(encounter.participants)
        }

    def _self_actor(self, actor_id: str) -> dict[str, Any]:
        actor = self.runtime.actors[actor_id]
        return {
            "actor_id": actor.actor_id,
            "name": actor.name,
            "kind": actor.kind.value,
            "level": actor.level,
            "hp": actor.hp,
            "max_hp": actor.max_hp,
            "alive": actor.alive,
            "location_id": actor.location_id,
            "cursor": actor.cursor.value,
            "col": actor.col,
            "equipment": dict(actor.equipment),
            "inventory": [
                {
                    "instance_id": item.instance_id,
                    "template_id": item.template_id,
                    "quantity": item.quantity,
                    "durability": item.durability,
                    "max_durability": item.max_durability,
                }
                for item in sorted(actor.inventory.values(), key=lambda row: row.instance_id)
            ],
            "statuses": [
                {
                    "status_type": status.status_type.value,
                    "remaining_ms": status.remaining_ms,
                }
                for status in actor.statuses
                if status.remaining_ms > 0
            ],
            "committed_until_ms": actor.committed_until_ms,
            "recovery_until_ms": actor.recovery_until_ms,
        }

    def _location(self, actor_id: str) -> dict[str, Any] | None:
        location_id = self.runtime.actors[actor_id].location_id
        if location_id is None:
            return None
        location = self.runtime.world_map.locations[location_id]
        return {
            "location_id": location.location_id,
            "name": location.name,
            "floor_number": location.floor_number,
            "zone_kind": location.zone_kind.value,
            "safe_zone": location.safe_zone,
            "anti_crystal": location.anti_crystal,
            "teleport_gate": location.teleport_gate,
        }

    def _player_name_known(self, observer_id: str, target_id: str) -> bool:
        if observer_id == target_id:
            return True
        belief = self.runtime.belief(observer_id, f"player_identity:{target_id}")
        return belief is not None

    def _active_encounter_with(self, observer_id: str, target_id: str) -> bool:
        return any(
            encounter.active
            and observer_id in encounter.participants
            and target_id in encounter.participants
            for encounter in self.runtime.encounters.values()
        )

    def _visible_entities(self, observer_id: str) -> list[dict[str, Any]]:
        actor = self.runtime.actors[observer_id]
        if actor.location_id is None:
            return []
        location_id = actor.location_id
        rows: list[dict[str, Any]] = []
        unknown_player_index = 0
        materialized_npc_ids: set[str] = set()

        for target in sorted(self.runtime.actors.values(), key=lambda row: row.actor_id):
            if target.actor_id == observer_id or target.location_id != location_id or not target.alive:
                continue
            if target.kind is EntityKind.PLAYER:
                known = self._player_name_known(observer_id, target.actor_id)
                if known:
                    rows.append({
                        "actor_id": target.actor_id,
                        "display_name": target.name,
                        "kind": target.kind.value,
                        "cursor": target.cursor.value,
                    })
                else:
                    unknown_player_index += 1
                    rows.append({
                        "scene_ref": f"unknown_player_{unknown_player_index}",
                        "display_name": "Unknown Player",
                        "kind": target.kind.value,
                        "cursor": target.cursor.value,
                    })
                continue

            npc_id = target.metadata.get("npc_definition_id")
            if isinstance(npc_id, str) and npc_id in self.runtime.npcs.definitions:
                materialized_npc_ids.add(npc_id)
                rows.append({
                    "npc_id": npc_id,
                    "display_name": self.runtime.npcs.definitions[npc_id].name,
                    "kind": "npc",
                    "cursor": target.cursor.value,
                })
                continue

            if self._active_encounter_with(observer_id, target.actor_id):
                rows.append({
                    "actor_id": target.actor_id,
                    "display_name": target.name,
                    "kind": target.kind.value,
                    "cursor": target.cursor.value,
                })

        for npc_id, definition in sorted(self.runtime.npcs.definitions.items()):
            if npc_id in materialized_npc_ids:
                continue
            if self.runtime.npc_location_id(npc_id) != location_id:
                continue
            rows.append({
                "npc_id": npc_id,
                "display_name": definition.name,
                "kind": "npc",
            })
        return rows

    def _participant(self, observer_id: str, participant) -> dict[str, Any]:
        if participant.kind is EntityKind.PLAYER and participant.actor_id != observer_id:
            display_name = (
                participant.name
                if self._player_name_known(observer_id, participant.actor_id)
                else "Unknown Player"
            )
        else:
            display_name = participant.name
        return {
            "actor_id": participant.actor_id,
            "display_name": display_name,
            "kind": participant.kind.value,
            "hp": participant.hp,
            "max_hp": participant.max_hp,
            "alive": participant.alive,
            "cursor": participant.cursor.value,
            "statuses": [
                status.status_type.value
                for status in participant.statuses
                if status.remaining_ms > 0
            ],
        }

    @staticmethod
    def _event(event) -> dict[str, Any]:
        payload = {
            key: value
            for key, value in event.payload.items()
            if key in VISIBLE_COMBAT_EVENT_PAYLOAD_KEYS
        }
        return {
            "time_ms": event.time_ms,
            "event_type": event.event_type,
            "actor_id": event.actor_id,
            "target_id": event.target_id,
            "payload": payload,
        }

    def _encounters(
        self,
        observer_id: str,
        *,
        allowed_encounter_ids: set[str],
        event_offsets: dict[str, int] | None,
    ) -> dict[str, Any]:
        rows: dict[str, Any] = {}
        for encounter_id in sorted(allowed_encounter_ids):
            encounter = self.runtime.encounters.get(encounter_id)
            if encounter is None or observer_id not in encounter.participants:
                continue
            row = {
                "encounter_id": encounter_id,
                "zone_id": encounter.zone_id,
                "time_ms": encounter.time_ms,
                "active": encounter.active,
                "participants": {
                    actor_id: self._participant(observer_id, participant)
                    for actor_id, participant in encounter.participants.items()
                },
            }
            if event_offsets is not None:
                start = event_offsets.get(encounter_id, len(encounter.events))
                row["recent_events"] = [
                    self._event(event) for event in encounter.events[start:]
                ]
            rows[encounter_id] = row
        return rows

    def _quest_log(self, observer_id: str) -> dict[str, Any]:
        active = self.runtime.quests.progress_by_actor.get(observer_id, {})
        completed = self.runtime.quests.completed_by_actor.get(observer_id, set())
        return {
            "active": {quest_id: asdict(progress) for quest_id, progress in sorted(active.items())},
            "completed_quest_ids": sorted(completed),
        }

    def _guild(self, observer_id: str) -> dict[str, Any] | None:
        guild_id = authoritative_guild_id(self.runtime, observer_id)
        if guild_id is None:
            return None
        guild = self.runtime.relationships.guilds[guild_id]
        return {
            "guild_id": guild.guild_id,
            "name": guild.name,
            "leader_id": guild.leader_id,
            "member_ids": list(guild.member_ids),
            "manager_ids": list(guild.manager_ids),
            "emblem": guild.emblem,
            "headquarters_location_id": guild.headquarters_location_id,
        }

    def _relationships(self, observer_id: str) -> dict[str, Any]:
        marriage = self.runtime.relationships.marriage_for(observer_id)
        return {
            "friend_ids": sorted(self.runtime.relationships.friends.get(observer_id, set())),
            "spouse_id": (
                next((actor_id for actor_id in marriage.partner_ids if actor_id != observer_id), None)
                if marriage is not None
                else None
            ),
        }

    def _travel_options(self, observer_id: str) -> list[dict[str, Any]]:
        actor = self.runtime.actors[observer_id]
        if not actor.alive or actor.location_id is None:
            return []
        if actor.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:
            return []
        if any(
            encounter.active and observer_id in encounter.participants
            for encounter in self.runtime.encounters.values()
        ):
            return []
        rows = []
        for edge in self.runtime.world_map.adjacency.get(actor.location_id, ()):
            destination = self.runtime.world_map.locations[edge.to_location_id]
            floor = self.runtime.world.floors[destination.floor_number]
            if edge.requires_floor_unlocked and not floor.unlocked:
                continue
            try:
                require_location_access(actor, destination.location_id)
            except ValueError:
                continue
            rows.append({
                "destination_id": destination.location_id,
                "name": destination.name,
                "travel_ms": edge.travel_ms,
                "traversal_tags": list(edge.traversal_tags),
            })
        return sorted(rows, key=lambda row: (row["travel_ms"], row["destination_id"]))

    def _teleport_options(self, observer_id: str) -> tuple[list[str], list[dict[str, Any]]]:
        actor = self.runtime.actors[observer_id]
        crystals = sorted(
            item.instance_id
            for item in actor.inventory.values()
            if item.template_id == "teleport_crystal" and item.quantity > 0
        )
        if not crystals or not actor.alive or actor.location_id is None:
            return crystals, []
        if actor.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:
            return crystals, []
        rows = []
        for destination in self.runtime.world_map.locations.values():
            if not destination.teleport_gate:
                continue
            floor = self.runtime.world.floors[destination.floor_number]
            if not floor.unlocked or not floor.main_town_gate_active:
                continue
            try:
                require_location_access(actor, destination.location_id)
            except ValueError:
                continue
            rows.append({
                "destination_id": destination.location_id,
                "name": destination.name,
                "floor_number": destination.floor_number,
            })
        return crystals, sorted(rows, key=lambda row: (row["floor_number"], row["destination_id"]))

    def _available_quest_ids(self, observer_id: str, local_npc_ids: set[str]) -> list[str]:
        active = self.runtime.quests.progress_by_actor.get(observer_id, {})
        completed = self.runtime.quests.completed_by_actor.get(observer_id, set())
        rows = []
        for quest_id, definition in self.runtime.quests.definitions.items():
            if definition.giver_id not in local_npc_ids:
                continue
            progress = active.get(quest_id)
            if progress is not None and not progress.claimed and not progress.terminated:
                continue
            if quest_id in completed and not definition.repeatable:
                continue
            if self.runtime.world.now_ms < self.runtime.quests.global_accept_block_until_ms.get(quest_id, 0):
                continue
            if any(required not in completed for required in definition.prerequisites):
                continue
            rows.append(quest_id)
        return sorted(rows)

    def _claimable_quest_ids(self, observer_id: str, local_npc_ids: set[str]) -> list[str]:
        actor = self.runtime.actors[observer_id]
        rows = []
        for quest_id, progress in self.runtime.quests.progress_by_actor.get(observer_id, {}).items():
            if progress.claimed or progress.terminated:
                continue
            definition = self.runtime.quests.definitions[quest_id]
            if definition.turn_in_id not in local_npc_ids:
                continue
            ready = True
            for objective in definition.objectives:
                if not objective.required_for_completion:
                    continue
                if objective.kind is QuestObjectiveKind.COLLECT:
                    current = sum(
                        item.quantity
                        for item in actor.inventory.values()
                        if item.template_id == objective.target_id
                    )
                else:
                    current = progress.counters.get(objective.objective_id, 0)
                if current < objective.required:
                    ready = False
                    break
            if ready:
                rows.append(quest_id)
        return sorted(rows)

    def _capabilities(self, observer_id: str, visible_entities: list[dict[str, Any]], encounters: dict[str, Any]) -> dict[str, Any]:
        actor = self.runtime.actors[observer_id]
        local_npc_ids = {
            row["npc_id"]
            for row in visible_entities
            if isinstance(row, dict) and isinstance(row.get("npc_id"), str)
        }
        crystals, teleport_options = self._teleport_options(observer_id)
        knowledge = self.runtime.knowledge_state(observer_id)
        return {
            "travel_options": self._travel_options(observer_id),
            "teleport_crystal_instance_ids": crystals,
            "teleport_options": teleport_options,
            "interactable_npc_ids": sorted(local_npc_ids),
            "inventory_instance_ids": sorted(actor.inventory),
            "equipped_slots": sorted(actor.equipment),
            "knowledge_fact_ids": sorted(knowledge.get("facts", {})),
            "available_quest_ids": self._available_quest_ids(observer_id, local_npc_ids),
            "claimable_quest_ids": self._claimable_quest_ids(observer_id, local_npc_ids),
            "encounter_ids": sorted(encounters),
        }

    def _messages(self, observer_id: str) -> list[dict[str, Any]]:
        if not hasattr(self.runtime, "message_inbox"):
            return []
        rows = []
        for message in self.runtime.message_inbox(observer_id):
            row = {
                "message_id": message.message_id,
                "sender_id": message.sender_id,
                "channel": message.channel.value,
                "sent_at_ms": message.sent_at_ms,
                "read_at_ms": message.read_at_ms,
                "unread": message.read_at_ms is None,
            }
            if message.read_at_ms is not None:
                row["text"] = message.text
            rows.append(row)
        return rows

    def observe(
        self,
        observer_actor_ids: list[str] | tuple[str, ...],
        *,
        event_offsets: dict[str, int] | None = None,
        additional_encounter_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        observer_ids = self.validate_observer_actor_ids(observer_actor_ids)
        current_encounters = self.current_observer_encounter_ids(observer_ids)
        allowed_encounters = set(current_encounters)
        if additional_encounter_ids:
            allowed_encounters.update(additional_encounter_ids)
        viewpoints = {}
        for observer_id in observer_ids:
            visible_entities = self._visible_entities(observer_id)
            encounters = self._encounters(
                observer_id,
                allowed_encounter_ids=allowed_encounters,
                event_offsets=event_offsets,
            )
            viewpoints[observer_id] = {
                "observer": self._self_actor(observer_id),
                "location": self._location(observer_id),
                "visible_entities": visible_entities,
                "knowledge": self.runtime.knowledge_state(observer_id),
                "quest_log": self._quest_log(observer_id),
                "guild": self._guild(observer_id),
                "relationships": self._relationships(observer_id),
                "messages": self._messages(observer_id),
                "encounters": encounters,
                "capabilities": self._capabilities(observer_id, visible_entities, encounters),
            }
        return {
            "world_now_ms": self.runtime.world.now_ms,
            "observer_actor_ids": list(observer_ids),
            "viewpoints": viewpoints,
        }
