from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.social_communication import (
    ARGO_REPORT_DELAY_MS,
    GUILD_NOTICE_DELAY_MS,
    LOCAL_RUMOR_DELAY_MS,
    MAX_AUTONOMOUS_RUMOR_DEPTH,
    SOCIAL_TICK_MS,
    TERMINAL_NOTICE_TTL_MS,
    SocialDeliveryChannel,
    SocialDeliveryState,
    SocialDeliveryStatus,
)
from sao_mcp.rules.state_authority import authoritative_guild_id
from sao_mcp.runtime.quest_ecology_runtime import QuestEcologyAincradRuntime


SOCIAL_COMMUNICATION_SCHEMA = "social-communication.v1"
ARGO_NPC_ID = "pc_argo"
PUBLIC_FACT_PREFIXES = ("quest_contract:",)


class SocialCommunicationAincradRuntime(QuestEcologyAincradRuntime):
    """Knowledge-backed delayed notices, local rumor diffusion and broker reports."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        if ARGO_NPC_ID not in self.npcs.definitions:
            raise RuntimeError("social communication runtime requires the canonical Argo NPC seed")
        self.social_deliveries: dict[str, SocialDeliveryState] = {}
        self.social_history: list[dict[str, Any]] = []
        self.social_delivery_sequence = 0
        self.next_social_tick_at_ms = self.world.now_ms + SOCIAL_TICK_MS
        self.social_knowledge_cursor = self.knowledge_event_count()
        self.social_quest_cursor = len(self.quest_ecology_history)
        self.argo_subscribers: set[str] = set()
        self.argo_publishable_event_ids: set[str] = set()
        self.register_world_advance_hook(self._resolve_due_social_communication)

    def _record_social(self, event: str, *, at_ms: int | None = None, **fields: Any) -> None:
        self.social_history.append(
            {"event": event, **fields, "at_ms": self.world.now_ms if at_ms is None else int(at_ms)}
        )

    def _next_social_delivery_id(self) -> str:
        self.social_delivery_sequence += 1
        return f"social_{self.social_delivery_sequence:08d}"

    def _social_entity_ids_at(self, location_id: str) -> list[str]:
        owners: dict[str, str] = {}
        for actor_id, actor in self.actors.items():
            if not actor.alive or actor.location_id != location_id:
                continue
            owner_id = self._knowledge_owner_id(actor_id)
            owners[owner_id] = owner_id
        for npc_id in self.npcs.definitions:
            if not self._knowledge_entity_alive(npc_id):
                continue
            if self._knowledge_entity_location_id(npc_id) == location_id:
                owners[npc_id] = npc_id
        return sorted(owners)

    @staticmethod
    def _public_fact(fact_id: str) -> bool:
        return fact_id.startswith(PUBLIC_FACT_PREFIXES)

    def _delivery_key_exists(
        self, channel: SocialDeliveryChannel, source_event_id: str, recipient_id: str
    ) -> bool:
        return any(
            row.channel is channel
            and row.source_event_id == source_event_id
            and row.recipient_id == recipient_id
            for row in self.social_deliveries.values()
        )

    def _schedule_social_delivery(
        self,
        *,
        channel: SocialDeliveryChannel,
        sender_id: str,
        recipient_id: str,
        source_event_id: str,
        delay_ms: int,
        confidence_factor: float,
        scope_id: str | None = None,
    ) -> SocialDeliveryState | None:
        if delay_ms <= 0:
            raise ValueError("social delivery delay must be positive")
        source_event = self.knowledge_event(source_event_id)
        if source_event.knower_id != self._knowledge_owner_id(sender_id):
            raise ValueError("social delivery source event does not belong to sender")
        if source_event.stale_at(self.world.now_ms):
            return None
        recipient_owner = self._knowledge_owner_id(recipient_id)
        if recipient_owner == source_event.knower_id:
            return None
        current = self.belief(recipient_id, source_event.fact_id)
        if current is not None and current.value == source_event.value:
            return None
        if self._delivery_key_exists(channel, source_event_id, recipient_owner):
            return None
        delivery = SocialDeliveryState(
            delivery_id=self._next_social_delivery_id(),
            channel=channel,
            sender_id=source_event.knower_id,
            recipient_id=recipient_owner,
            source_event_id=source_event.event_id,
            fact_id=source_event.fact_id,
            created_at_ms=self.world.now_ms,
            due_at_ms=self.world.now_ms + delay_ms,
            confidence_factor=confidence_factor,
            scope_id=scope_id,
        )
        self.social_deliveries[delivery.delivery_id] = delivery
        self._record_social(
            "delivery_scheduled",
            delivery_id=delivery.delivery_id,
            channel=channel.value,
            sender_id=delivery.sender_id,
            recipient_id=delivery.recipient_id,
            source_event_id=source_event.event_id,
            fact_id=source_event.fact_id,
            due_at_ms=delivery.due_at_ms,
            scope_id=scope_id,
        )
        return delivery

    def _fail_delivery(self, delivery: SocialDeliveryState, reason: str, at_ms: int) -> None:
        delivery.fail(reason=reason, at_ms=at_ms)
        self._record_social(
            "delivery_failed",
            at_ms=at_ms,
            delivery_id=delivery.delivery_id,
            channel=delivery.channel.value,
            recipient_id=delivery.recipient_id,
            fact_id=delivery.fact_id,
            reason=reason,
        )

    def _deliver_social_fact(self, delivery: SocialDeliveryState, at_ms: int) -> None:
        if not self._knowledge_entity_alive(delivery.recipient_id):
            self._fail_delivery(delivery, "recipient_unavailable", at_ms)
            return
        source_event = self.knowledge_event(delivery.source_event_id)
        if source_event.stale_at(at_ms):
            self._fail_delivery(delivery, "source_fact_stale", at_ms)
            return
        if source_event.knower_id != self._knowledge_owner_id(delivery.sender_id):
            raise RuntimeError("social delivery reporter/source authority changed")
        if delivery.channel is SocialDeliveryChannel.LOCAL_RUMOR:
            sender_location = self._knowledge_entity_location_id(delivery.sender_id)
            recipient_location = self._knowledge_entity_location_id(delivery.recipient_id)
            if sender_location is None or sender_location != recipient_location:
                self._fail_delivery(delivery, "rumor_participants_no_longer_colocated", at_ms)
                return
        elif delivery.channel is SocialDeliveryChannel.GUILD_NOTICE:
            guild = self.relationships.guilds.get(str(delivery.scope_id))
            if guild is None or delivery.recipient_id not in guild.member_ids:
                self._fail_delivery(delivery, "recipient_left_guild", at_ms)
                return
            if delivery.recipient_id in self.actors and self._in_dungeon(delivery.recipient_id):
                self._fail_delivery(delivery, "guild_notice_blocked_by_dungeon", at_ms)
                return
        elif delivery.channel is SocialDeliveryChannel.ARGO_INTELLIGENCE:
            if delivery.recipient_id not in self.argo_subscribers:
                self._fail_delivery(delivery, "argo_subscription_inactive", at_ms)
                return
            if delivery.recipient_id in self.actors and self._in_dungeon(delivery.recipient_id):
                self._fail_delivery(delivery, "argo_report_blocked_by_dungeon", at_ms)
                return
        received = self.receive_reported_fact(
            delivery.recipient_id,
            reporter_id=delivery.sender_id,
            source_event_id=delivery.source_event_id,
            confidence_factor=delivery.confidence_factor,
            learned_location_id=self._knowledge_entity_location_id(delivery.recipient_id),
        )
        delivery.deliver(received_event_id=received.event_id, at_ms=at_ms)
        self._record_social(
            "delivery_completed",
            at_ms=at_ms,
            delivery_id=delivery.delivery_id,
            channel=delivery.channel.value,
            sender_id=delivery.sender_id,
            recipient_id=delivery.recipient_id,
            source_event_id=delivery.source_event_id,
            received_event_id=received.event_id,
            fact_id=delivery.fact_id,
        )

    def _deliver_due_social_facts(self, at_ms: int) -> None:
        due = sorted(
            (row for row in self.social_deliveries.values() if row.pending and row.due_at_ms <= at_ms),
            key=lambda row: (row.due_at_ms, row.delivery_id),
        )
        for delivery in due:
            if delivery.due_at_ms != at_ms:
                raise RuntimeError("social delivery boundary was skipped by world scheduler")
            self._deliver_social_fact(delivery, at_ms)

    def _contract_fact_id(self, contract_id: str) -> str:
        return f"quest_contract:{contract_id}"

    def _contract_fact_value(self, contract_id: str) -> dict[str, Any]:
        contract = self.quest_contracts[contract_id]
        occurrence = self.world_events.occurrences[contract.occurrence_id]
        return {
            "contract_id": contract.contract_id,
            "status": occurrence.status.value,
            "source_kind": contract.source_kind.value,
            "source_location_id": contract.source_location_id,
            "posting_location_id": contract.posting_location_id,
            "target_id": contract.target_id,
            "required": contract.required,
            "expires_at_ms": contract.expires_at_ms,
            "winner_kind": contract.winner_kind,
            "winner_ids": list(contract.winner_ids),
            "winner_ref_id": contract.winner_ref_id,
        }

    def _observe_contract_board_for_entity(self, contract_id: str, entity_id: str) -> None:
        contract = self.quest_contracts[contract_id]
        if self._knowledge_entity_location_id(entity_id) != contract.posting_location_id:
            return
        value = self._contract_fact_value(contract_id)
        fact_id = self._contract_fact_id(contract_id)
        current = self.belief(entity_id, fact_id)
        if current is not None and current.value == value:
            return
        occurrence = self.world_events.occurrences[contract.occurrence_id]
        expires_after_ms = None
        if occurrence.status.value == "active":
            remaining = contract.expires_at_ms - self.world.now_ms
            if remaining <= 0:
                return
            expires_after_ms = remaining
        else:
            expires_after_ms = TERMINAL_NOTICE_TTL_MS
        event = self.record_observation(
            entity_id,
            fact_id,
            value,
            observation_location_id=contract.posting_location_id,
            source_id=f"quest_board:{contract.posting_location_id}",
            expires_after_ms=expires_after_ms,
        )
        self._record_social(
            "quest_board_observed",
            contract_id=contract_id,
            entity_id=self._knowledge_owner_id(entity_id),
            knowledge_event_id=event.event_id,
            status=occurrence.status.value,
            location_id=contract.posting_location_id,
        )

    def _observe_contract_board(self, contract_id: str) -> None:
        contract = self.quest_contracts[contract_id]
        for entity_id in self._social_entity_ids_at(contract.posting_location_id):
            self._observe_contract_board_for_entity(contract_id, entity_id)

    def _observe_active_boards_for_entity(self, entity_id: str) -> None:
        location_id = self._knowledge_entity_location_id(entity_id)
        if location_id is None:
            return
        for contract_id, contract in sorted(self.quest_contracts.items()):
            occurrence = self.world_events.occurrences[contract.occurrence_id]
            if occurrence.status.value != "active" or contract.posting_location_id != location_id:
                continue
            self._observe_contract_board_for_entity(contract_id, entity_id)

    def _observe_all_active_boards(self) -> None:
        for contract_id, contract in sorted(self.quest_contracts.items()):
            occurrence = self.world_events.occurrences[contract.occurrence_id]
            if occurrence.status.value == "active":
                self._observe_contract_board(contract_id)

    def _process_quest_notice_changes(self) -> None:
        rows = self.quest_ecology_history[self.social_quest_cursor :]
        contract_events = {
            "contract_published",
            "contract_resolved",
            "contract_expired",
            "contract_interrupted",
        }
        for row in rows:
            if row.get("event") not in contract_events:
                continue
            contract_id = str(row["contract_id"])
            if contract_id in self.quest_contracts:
                self._observe_contract_board(contract_id)
        self.social_quest_cursor = len(self.quest_ecology_history)

    def _spread_public_event_locally(self, source_event) -> None:
        if source_event.transmission_depth >= MAX_AUTONOMOUS_RUMOR_DEPTH:
            return
        location_id = self._knowledge_entity_location_id(source_event.knower_id)
        if location_id is None:
            return
        for recipient_id in self._social_entity_ids_at(location_id):
            self._schedule_social_delivery(
                channel=SocialDeliveryChannel.LOCAL_RUMOR,
                sender_id=source_event.knower_id,
                recipient_id=recipient_id,
                source_event_id=source_event.event_id,
                delay_ms=LOCAL_RUMOR_DELAY_MS,
                confidence_factor=0.68,
                scope_id=location_id,
            )

    def _schedule_argo_reports(self, source_event) -> None:
        for actor_id in sorted(self.argo_subscribers):
            self._schedule_social_delivery(
                channel=SocialDeliveryChannel.ARGO_INTELLIGENCE,
                sender_id=ARGO_NPC_ID,
                recipient_id=actor_id,
                source_event_id=source_event.event_id,
                delay_ms=ARGO_REPORT_DELAY_MS,
                confidence_factor=0.93,
                scope_id="argo_brokerage",
            )

    def _process_new_social_knowledge(self) -> None:
        rows = self.knowledge_events_since(self.social_knowledge_cursor)
        for event in rows:
            is_public = self._public_fact(event.fact_id)
            if is_public:
                self._spread_public_event_locally(event)
            if event.knower_id == ARGO_NPC_ID and (
                is_public or event.event_id in self.argo_publishable_event_ids
            ):
                self._schedule_argo_reports(event)
        self.social_knowledge_cursor = self.knowledge_event_count()

    def advance_social_communication_tick(self, tick_ms: int) -> None:
        if tick_ms != self.next_social_tick_at_ms:
            raise RuntimeError(
                f"social tick must resolve at its scheduled boundary: {tick_ms} != {self.next_social_tick_at_ms}"
            )
        if self.world.now_ms != tick_ms:
            raise RuntimeError("social tick must resolve at authoritative current world time")
        self._process_quest_notice_changes()
        self._observe_all_active_boards()
        self._process_new_social_knowledge()
        self.next_social_tick_at_ms += SOCIAL_TICK_MS
        self.assert_social_communication_authority()

    def _resolve_due_social_communication(self, before_ms: int, after_ms: int) -> None:
        self._deliver_due_social_facts(after_ms)
        if self.next_social_tick_at_ms == after_ms:
            self.advance_social_communication_tick(after_ms)
        elif self.next_social_tick_at_ms < after_ms:
            raise RuntimeError("social communication tick boundary was skipped by world scheduler")

    def _next_scheduler_boundary(self, target_ms: int) -> int:
        boundary = super()._next_scheduler_boundary(target_ms)
        now = self.world.now_ms
        if now < self.next_social_tick_at_ms <= target_ms:
            boundary = min(boundary, self.next_social_tick_at_ms)
        due = [
            row.due_at_ms
            for row in self.social_deliveries.values()
            if row.pending and now < row.due_at_ms <= target_ms
        ]
        return min([boundary, *due]) if due else boundary

    def travel_actor(self, actor_id: str, destination_id: str):
        result = super().travel_actor(actor_id, destination_id)
        actor = self.actors[actor_id]
        if actor.kind is EntityKind.PLAYER and actor.alive and actor.location_id is not None:
            self._observe_active_boards_for_entity(actor_id)
        return result

    def post_guild_fact_notice(self, sender_id: str, guild_id: str, fact_id: str) -> list[SocialDeliveryState]:
        guild = self.relationships.guilds[guild_id]
        if authoritative_guild_id(self, sender_id) != guild_id:
            raise ValueError("guild notice sender is not an authoritative guild member")
        if sender_id != guild.leader_id and sender_id not in guild.manager_ids:
            raise ValueError("guild notice requires leader or manager permission")
        source_event = self.belief(sender_id, fact_id)
        if source_event is None:
            raise ValueError("guild notice sender does not know a current version of the requested fact")
        rows = []
        for actor_id in sorted(guild.member_ids):
            if actor_id == sender_id:
                continue
            delivery = self._schedule_social_delivery(
                channel=SocialDeliveryChannel.GUILD_NOTICE,
                sender_id=sender_id,
                recipient_id=actor_id,
                source_event_id=source_event.event_id,
                delay_ms=GUILD_NOTICE_DELAY_MS,
                confidence_factor=0.90,
                scope_id=guild_id,
            )
            if delivery is not None:
                rows.append(delivery)
        self._record_social(
            "guild_notice_posted",
            sender_id=sender_id,
            guild_id=guild_id,
            fact_id=fact_id,
            source_event_id=source_event.event_id,
            delivery_ids=[row.delivery_id for row in rows],
        )
        return rows

    def spread_local_rumor(self, sender_id: str, fact_id: str) -> list[SocialDeliveryState]:
        source_event = self.belief(sender_id, fact_id)
        if source_event is None:
            raise ValueError("rumor sender does not know a current version of the requested fact")
        location_id = self._knowledge_entity_location_id(sender_id)
        if location_id is None:
            raise ValueError("local rumor requires a settled sender")
        rows = []
        for recipient_id in self._social_entity_ids_at(location_id):
            delivery = self._schedule_social_delivery(
                channel=SocialDeliveryChannel.LOCAL_RUMOR,
                sender_id=sender_id,
                recipient_id=recipient_id,
                source_event_id=source_event.event_id,
                delay_ms=LOCAL_RUMOR_DELAY_MS,
                confidence_factor=0.68,
                scope_id=location_id,
            )
            if delivery is not None:
                rows.append(delivery)
        self._record_social(
            "local_rumor_started",
            sender_id=self._knowledge_owner_id(sender_id),
            fact_id=fact_id,
            source_event_id=source_event.event_id,
            location_id=location_id,
            delivery_ids=[row.delivery_id for row in rows],
        )
        return rows

    def subscribe_argo_intelligence(self, actor_id: str) -> dict[str, Any]:
        actor = self.actors[actor_id]
        if actor.kind is not EntityKind.PLAYER or not actor.alive:
            raise ValueError("Argo intelligence subscription requires a living player")
        argo_location = self._knowledge_entity_location_id(ARGO_NPC_ID)
        if actor.location_id != argo_location:
            raise ValueError("Argo intelligence subscription requires an actual meeting with Argo")
        self.argo_subscribers.add(actor_id)
        self._record_social("argo_subscription_started", actor_id=actor_id, location_id=argo_location)
        return {"actor_id": actor_id, "subscribed": True, "argo_location_id": argo_location}

    def unsubscribe_argo_intelligence(self, actor_id: str) -> dict[str, Any]:
        self.argo_subscribers.discard(actor_id)
        self._record_social("argo_subscription_ended", actor_id=actor_id)
        return {"actor_id": actor_id, "subscribed": False}

    def brief_argo(self, sender_id: str, fact_id: str):
        if self._knowledge_entity_location_id(sender_id) != self._knowledge_entity_location_id(ARGO_NPC_ID):
            raise ValueError("briefing Argo requires an actual colocated conversation")
        event = self.share_known_fact(sender_id, ARGO_NPC_ID, fact_id)
        self.argo_publishable_event_ids.add(event.event_id)
        self._record_social(
            "argo_briefed",
            sender_id=self._knowledge_owner_id(sender_id),
            fact_id=fact_id,
            argo_event_id=event.event_id,
        )
        return event

    def social_delivery_state(self, delivery_id: str) -> dict[str, Any]:
        return asdict(self.social_deliveries[delivery_id])

    def social_communication_state(self) -> dict[str, Any]:
        self.assert_social_communication_authority()
        return {
            "world_now_ms": self.world.now_ms,
            "next_social_tick_at_ms": self.next_social_tick_at_ms,
            "knowledge_cursor": self.social_knowledge_cursor,
            "quest_cursor": self.social_quest_cursor,
            "argo_subscribers": sorted(self.argo_subscribers),
            "deliveries": {
                key: asdict(value) for key, value in sorted(self.social_deliveries.items())
            },
        }

    def assert_social_communication_authority(self) -> None:
        if self.next_social_tick_at_ms <= self.world.now_ms:
            raise RuntimeError("social communication next tick must be in the future")
        if not 0 <= self.social_knowledge_cursor <= self.knowledge_event_count():
            raise RuntimeError("social communication knowledge cursor is invalid")
        if not 0 <= self.social_quest_cursor <= len(self.quest_ecology_history):
            raise RuntimeError("social communication quest cursor is invalid")
        for actor_id in self.argo_subscribers:
            actor = self.actors.get(actor_id)
            if actor is None or actor.kind is not EntityKind.PLAYER:
                raise RuntimeError("Argo subscriber is not a current player actor")
        for event_id in self.argo_publishable_event_ids:
            event = self._knowledge_event_index.get(event_id)
            if event is None or event.knower_id != ARGO_NPC_ID:
                raise RuntimeError("Argo publishable event lacks authoritative Argo knowledge")
        seen = set()
        for delivery_id, delivery in self.social_deliveries.items():
            if delivery.delivery_id != delivery_id:
                raise RuntimeError("social delivery registry key/id mismatch")
            source = self._knowledge_event_index.get(delivery.source_event_id)
            if source is None or source.fact_id != delivery.fact_id:
                raise RuntimeError("social delivery source fact disagrees with Knowledge authority")
            if source.knower_id != self._knowledge_owner_id(delivery.sender_id):
                raise RuntimeError("social delivery sender does not own its source KnowledgeEvent")
            key = (delivery.channel.value, delivery.source_event_id, delivery.recipient_id)
            if key in seen:
                raise RuntimeError("duplicate social delivery for one source event and recipient")
            seen.add(key)
            if delivery.pending and delivery.due_at_ms <= self.world.now_ms:
                raise RuntimeError("pending social delivery crossed its due boundary")
            if delivery.status is SocialDeliveryStatus.DELIVERED:
                received = self._knowledge_event_index.get(str(delivery.received_event_id))
                if received is None or delivery.source_event_id not in received.evidence_event_ids:
                    raise RuntimeError("delivered social fact lacks exact Knowledge evidence chain")
                if received.knower_id != self._knowledge_owner_id(delivery.recipient_id):
                    raise RuntimeError("delivered social fact went to the wrong Knowledge owner")
        for row in self.social_history:
            if int(row["at_ms"]) > self.world.now_ms:
                raise RuntimeError("social communication history cannot be in the future")

    def dump_social_communication_state(self) -> dict[str, Any]:
        self.assert_social_communication_authority()
        return {
            "schema": SOCIAL_COMMUNICATION_SCHEMA,
            "sequence": self.social_delivery_sequence,
            "next_tick_at_ms": self.next_social_tick_at_ms,
            "knowledge_cursor": self.social_knowledge_cursor,
            "quest_cursor": self.social_quest_cursor,
            "argo_subscribers": sorted(self.argo_subscribers),
            "argo_publishable_event_ids": sorted(self.argo_publishable_event_ids),
            "deliveries": {key: asdict(value) for key, value in self.social_deliveries.items()},
            "history": list(self.social_history),
        }

    def load_social_communication_state(self, payload: dict[str, Any]) -> None:
        if not payload:
            self.social_deliveries = {}
            self.social_history = []
            self.social_delivery_sequence = 0
            self.next_social_tick_at_ms = self.world.now_ms + SOCIAL_TICK_MS
            self.social_knowledge_cursor = self.knowledge_event_count()
            self.social_quest_cursor = len(self.quest_ecology_history)
            self.argo_subscribers = set()
            self.argo_publishable_event_ids = set()
            return
        if payload.get("schema") != SOCIAL_COMMUNICATION_SCHEMA:
            raise ValueError("unsupported non-empty social communication schema")
        restored = {}
        for delivery_id, row in payload.get("deliveries", {}).items():
            delivery = SocialDeliveryState(
                delivery_id=row["delivery_id"],
                channel=SocialDeliveryChannel(row["channel"]),
                sender_id=row["sender_id"],
                recipient_id=row["recipient_id"],
                source_event_id=row["source_event_id"],
                fact_id=row["fact_id"],
                created_at_ms=int(row["created_at_ms"]),
                due_at_ms=int(row["due_at_ms"]),
                confidence_factor=float(row["confidence_factor"]),
                scope_id=row.get("scope_id"),
                status=SocialDeliveryStatus(row.get("status", "pending")),
                delivered_at_ms=(int(row["delivered_at_ms"]) if row.get("delivered_at_ms") is not None else None),
                received_event_id=row.get("received_event_id"),
                failure_reason=row.get("failure_reason"),
            )
            if delivery.delivery_id != delivery_id:
                raise ValueError("social communication save delivery key/id mismatch")
            restored[delivery_id] = delivery
        self.social_deliveries = restored
        self.social_history = list(payload.get("history", []))
        self.social_delivery_sequence = int(payload.get("sequence", 0))
        self.next_social_tick_at_ms = int(payload["next_tick_at_ms"])
        self.social_knowledge_cursor = int(payload.get("knowledge_cursor", 0))
        self.social_quest_cursor = int(payload.get("quest_cursor", 0))
        self.argo_subscribers = set(payload.get("argo_subscribers", []))
        self.argo_publishable_event_ids = set(payload.get("argo_publishable_event_ids", []))
        if self.next_social_tick_at_ms <= self.world.now_ms:
            raise ValueError("social communication save next tick must be after current world time")
        self.assert_social_communication_authority()
