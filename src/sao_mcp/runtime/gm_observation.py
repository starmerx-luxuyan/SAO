from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.state_authority import authoritative_guild_id


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
            viewpoints[observer_id] = {
                "observer": self._self_actor(observer_id),
                "location": self._location(observer_id),
                "visible_entities": self._visible_entities(observer_id),
                "knowledge": self.runtime.knowledge_state(observer_id),
                "quest_log": self._quest_log(observer_id),
                "guild": self._guild(observer_id),
                "relationships": self._relationships(observer_id),
                "messages": self._messages(observer_id),
                "encounters": self._encounters(
                    observer_id,
                    allowed_encounter_ids=allowed_encounters,
                    event_offsets=event_offsets,
                ),
            }
        return {
            "world_now_ms": self.runtime.world.now_ms,
            "observer_actor_ids": list(observer_ids),
            "viewpoints": viewpoints,
        }
