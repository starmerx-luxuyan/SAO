from __future__ import annotations

from sao_mcp.domain.models import EntityKind, ZoneKind
from sao_mcp.rules.communications import CommunicationsRuntime, MessageChannel
from sao_mcp.rules.state_authority import authoritative_guild_id
from sao_mcp.runtime.property_runtime import PropertyFamilyAincradRuntime


class CommunicatingAincradRuntime(PropertyFamilyAincradRuntime):
    """Property/family runtime plus persistent, knowledge-bounded Aincrad short messages."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.communications = CommunicationsRuntime()

    def _location_floor(self, location_id: str | None) -> int | None:
        if not location_id:
            return None
        location = self.world_map.locations.get(location_id)
        return location.floor_number if location else None

    def _in_dungeon(self, actor_id: str) -> bool:
        actor = self.actors[actor_id]
        if not actor.location_id or actor.location_id not in self.world_map.locations:
            return False
        return self.world_map.locations[actor.location_id].zone_kind in {
            ZoneKind.DUNGEON,
            ZoneKind.LABYRINTH,
            ZoneKind.BOSS_ROOM,
        }

    def _validate_identity_meeting(self, observer_id: str, target_id: str):
        observer = self.actors[observer_id]
        target = self.actors[target_id]
        if observer.kind is not EntityKind.PLAYER or target.kind is not EntityKind.PLAYER:
            raise ValueError("identity registration is for player characters")
        if observer_id == target_id:
            return {"observerId": observer_id, "targetId": target_id, "known": True}
        colocated = bool(observer.location_id and observer.location_id == target.location_id)
        shared_encounter = any(
            observer_id in encounter.participants and target_id in encounter.participants
            for encounter in self.encounters.values()
        )
        if not colocated and not shared_encounter:
            raise ValueError("player identity cannot be learned without an actual meeting")
        return observer, target

    def _player_identity_known(self, observer_id: str, target_id: str) -> bool:
        return target_id in set(self.actors[observer_id].metadata.get("known_player_ids", ()))

    def learn_player_identity(self, observer_id: str, target_id: str) -> dict:
        observer, target = self._validate_identity_meeting(observer_id, target_id)
        known = set(observer.metadata.get("known_player_ids", ()))
        known.add(target_id)
        observer.metadata["known_player_ids"] = sorted(known)
        return {
            "observerId": observer_id,
            "targetId": target_id,
            "known": True,
            "name": target.name,
        }

    def _message_channel(self, sender_id: str, target_id: str) -> MessageChannel:
        sender = self.actors[sender_id]
        target = self.actors[target_id]
        marriage = self.relationships.marriage_for(sender_id)
        if marriage and target_id in marriage.partner_ids:
            return MessageChannel.SPOUSE
        if self.relationships.are_friends(sender_id, target_id):
            return MessageChannel.FRIEND
        sender_guild = authoritative_guild_id(self, sender_id)
        target_guild = authoritative_guild_id(self, target_id)
        if sender_guild is not None and sender_guild == target_guild:
            return MessageChannel.GUILD
        return MessageChannel.STRANGER_INSTANT

    def send_short_message(self, sender_id: str, target_id: str, text: str):
        sender = self.actors[sender_id]
        target = self.actors[target_id]
        if sender.kind is not EntityKind.PLAYER or target.kind is not EntityKind.PLAYER:
            raise ValueError("short messages are between player characters")
        if sender.metadata.get("permanent_death") or not sender.alive:
            raise ValueError("defeated players cannot send messages")
        if target.metadata.get("permanent_death"):
            raise ValueError("fallen player contact is disabled")
        if self._in_dungeon(target_id):
            raise ValueError("messages cannot be delivered to a player currently in a dungeon")

        channel = self._message_channel(sender_id, target_id)
        confirmation = True
        if channel is MessageChannel.GUILD and self._in_dungeon(sender_id):
            raise ValueError("guild short messages are unavailable from within a dungeon")
        if channel is MessageChannel.STRANGER_INSTANT:
            if not self._player_identity_known(sender_id, target_id):
                raise ValueError("stranger instant message requires the sender to know the recipient identity")
            sender_floor = self._location_floor(sender.location_id)
            target_floor = self._location_floor(target.location_id)
            if sender_floor is None or sender_floor != target_floor:
                raise ValueError("stranger instant messages require both players on the same floor")
            confirmation = False

        message = self.communications.send(
            sender,
            target,
            channel,
            text,
            now_ms=self.world.now_ms,
            delivery_confirmation_visible=confirmation,
        )
        return message

    def read_message(self, actor_id: str, message_id: str):
        return self.communications.mark_read(actor_id, message_id, now_ms=self.world.now_ms)

    def message_inbox(self, actor_id: str, *, unread_only: bool = False):
        return self.communications.inbox(actor_id, unread_only=unread_only)

    def message_outbox(self, actor_id: str):
        return self.communications.outbox(actor_id)

    def dump_communications_state(self) -> dict:
        return self.communications.dump_state()

    def load_communications_state(self, payload: dict) -> None:
        self.communications.load_state(payload)
