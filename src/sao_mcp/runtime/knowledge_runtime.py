from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import Any

from sao_mcp.rules.knowledge import EpistemicBasis, KnowledgeEvent
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.runtime.communications_runtime import CommunicatingAincradRuntime


KNOWLEDGE_SCHEMA = "knowledge.v2"
REPORT_CONFIDENCE_FACTOR = 0.85
INFERENCE_CONFIDENCE_FACTOR = 0.80
KnowledgeUpdateHook = Callable[[KnowledgeEvent], None]


class KnowledgeAincradRuntime(CommunicatingAincradRuntime):
    """Persistent entity beliefs with causal evidence, staleness and location-bounded observation."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.knowledge_events: list[KnowledgeEvent] = []
        self._knowledge_event_index: dict[str, KnowledgeEvent] = {}
        self._knowledge_sequence = 0
        self.knowledge_update_hooks: list[KnowledgeUpdateHook] = []

    def register_knowledge_update_hook(self, hook: KnowledgeUpdateHook) -> None:
        self.knowledge_update_hooks.append(hook)

    def _materialized_npc_actor(self, npc_id: str):
        matches = [
            actor
            for actor in self.actors.values()
            if actor.metadata.get("npc_definition_id") == npc_id
        ]
        if len(matches) > 1:
            raise RuntimeError(f"multiple materialized actors exist for NPC {npc_id}")
        return matches[0] if matches else None

    def npc_location_id(self, npc_id: str) -> str:
        if npc_id not in self.npcs.states:
            raise KeyError(npc_id)
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is None:
            return self.npcs.states[npc_id].location_id
        if materialized.location_id is None:
            raise RuntimeError(f"materialized NPC {npc_id} has no settled world location")
        return materialized.location_id

    def interact_npc(self, actor_id: str, npc_id: str):
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is not None and not materialized.alive:
            raise ValueError("materialized NPC is not alive for interaction")
        actor = self.actors[actor_id]
        interaction = self.npcs.interact_at(
            actor_id,
            npc_id,
            actor_location_id=actor.location_id,
            npc_location_id=self.npc_location_id(npc_id),
            now_ms=self.world.now_ms,
            quests=self.quests,
        )
        self.quests.record_event(
            actor_id,
            kind=QuestObjectiveKind.TALK,
            target_id=npc_id,
        )
        return interaction

    def claim_quest(self, actor_id: str, quest_id: str):
        actor = self.actors[actor_id]
        definition = self.quests.definitions[quest_id]
        materialized = self._materialized_npc_actor(definition.turn_in_id)
        if materialized is not None and not materialized.alive:
            raise ValueError("materialized quest turn-in NPC is not alive")
        if actor.location_id != self.npc_location_id(definition.turn_in_id):
            raise ValueError("quest must be turned in to the designated NPC")
        return self.quests.claim(actor, quest_id, self.catalog, now_ms=self.world.now_ms)

    def _knowledge_owner_id(self, entity_id: str) -> str:
        if entity_id in self.actors:
            definition_id = self.actors[entity_id].metadata.get("npc_definition_id")
            if definition_id is not None:
                if not isinstance(definition_id, str) or definition_id not in self.npcs.definitions:
                    raise RuntimeError(f"actor {entity_id} references invalid NPC definition {definition_id!r}")
                return definition_id
            return entity_id
        if entity_id in self.npcs.definitions:
            return entity_id
        raise KeyError(entity_id)

    def _knowledge_entity_location_id(self, entity_id: str) -> str | None:
        if entity_id in self.actors:
            return self.actors[entity_id].location_id
        if entity_id in self.npcs.definitions:
            return self.npc_location_id(entity_id)
        raise KeyError(entity_id)

    def _knowledge_entity_alive(self, entity_id: str) -> bool:
        if entity_id in self.actors:
            return self.actors[entity_id].alive
        if entity_id in self.npcs.definitions:
            materialized = self._materialized_npc_actor(entity_id)
            return materialized.alive if materialized is not None else True
        raise KeyError(entity_id)

    def _resolve_source_id(self, source_id: str | None) -> str | None:
        if source_id is None:
            return None
        if source_id in self.actors or source_id in self.npcs.definitions:
            return self._knowledge_owner_id(source_id)
        return source_id

    @staticmethod
    def _validate_confidence(confidence: float) -> float:
        value = float(confidence)
        if not 0.0 < value <= 1.0:
            raise ValueError("knowledge confidence must be in (0, 1]")
        return value

    def _next_knowledge_event_id(self) -> str:
        self._knowledge_sequence += 1
        return f"knowledge_{self._knowledge_sequence:08d}"

    def _latest_event(self, knower_id: str, fact_id: str) -> KnowledgeEvent | None:
        for event in reversed(self.knowledge_events):
            if event.knower_id == knower_id and event.fact_id == fact_id:
                return event
        return None

    def knowledge_event(self, event_id: str) -> KnowledgeEvent:
        return self._knowledge_event_index[event_id]

    def knowledge_event_count(self) -> int:
        return len(self.knowledge_events)

    def knowledge_events_since(self, offset: int) -> tuple[KnowledgeEvent, ...]:
        if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= len(self.knowledge_events):
            raise ValueError("knowledge event offset is outside the authoritative event log")
        return tuple(self.knowledge_events[offset:])

    def _event_view(self, event: KnowledgeEvent) -> dict[str, Any]:
        row = asdict(event)
        row["age_ms"] = self.world.now_ms - event.learned_at_ms
        row["stale"] = event.stale_at(self.world.now_ms)
        return row

    def knowledge_event_state(self, event_id: str) -> dict[str, Any]:
        return self._event_view(self.knowledge_event(event_id))

    def _record_knowledge_event(
        self,
        entity_id: str,
        fact_id: str,
        value: Any,
        *,
        basis: EpistemicBasis,
        source_id: str | None,
        confidence: float,
        expires_at_ms: int | None,
        learned_location_id: str | None,
        evidence_event_ids: Sequence[str] = (),
        transmission_depth: int = 0,
    ) -> KnowledgeEvent:
        if not fact_id:
            raise ValueError("fact_id must be non-empty")
        if not self._knowledge_entity_alive(entity_id):
            raise ValueError("defeated materialized entities cannot acquire new knowledge")
        confidence = self._validate_confidence(confidence)
        if expires_at_ms is not None and expires_at_ms <= self.world.now_ms:
            raise ValueError("knowledge expiry must be in the future")
        evidence_ids = tuple(evidence_event_ids)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("knowledge evidence event IDs must be unique")
        for evidence_id in evidence_ids:
            if evidence_id not in self._knowledge_event_index:
                raise KeyError(f"unknown knowledge evidence event: {evidence_id}")
        if learned_location_id is not None and learned_location_id not in self.world_map.locations:
            raise KeyError(learned_location_id)

        knower_id = self._knowledge_owner_id(entity_id)
        previous = self._latest_event(knower_id, fact_id)
        event = KnowledgeEvent(
            event_id=self._next_knowledge_event_id(),
            knower_id=knower_id,
            fact_id=fact_id,
            value=value,
            basis=basis,
            source_id=self._resolve_source_id(source_id),
            learned_at_ms=self.world.now_ms,
            confidence=confidence,
            expires_at_ms=expires_at_ms,
            learned_location_id=learned_location_id,
            evidence_event_ids=evidence_ids,
            supersedes_event_id=previous.event_id if previous is not None else None,
            transmission_depth=transmission_depth,
        )
        self.knowledge_events.append(event)
        self._knowledge_event_index[event.event_id] = event
        for hook in tuple(self.knowledge_update_hooks):
            hook(event)
        return event

    def record_observation(
        self,
        entity_id: str,
        fact_id: str,
        value: Any,
        *,
        observation_location_id: str,
        source_id: str | None = None,
        confidence: float = 1.0,
        expires_after_ms: int | None = None,
    ) -> KnowledgeEvent:
        if observation_location_id not in self.world_map.locations:
            raise KeyError(observation_location_id)
        actual_location = self._knowledge_entity_location_id(entity_id)
        if actual_location is None or actual_location != observation_location_id:
            raise ValueError("direct observation requires the knower to be at observation_location_id")
        if source_id is not None and (source_id in self.actors or source_id in self.npcs.definitions):
            source_location = self._knowledge_entity_location_id(source_id)
            if source_location != observation_location_id:
                raise ValueError("observed entity source must be colocated with the knower")
        expires_at_ms = None
        if expires_after_ms is not None:
            if not isinstance(expires_after_ms, int) or isinstance(expires_after_ms, bool) or expires_after_ms <= 0:
                raise ValueError("expires_after_ms must be a positive integer")
            expires_at_ms = self.world.now_ms + expires_after_ms
        return self._record_knowledge_event(
            entity_id,
            fact_id,
            value,
            basis=EpistemicBasis.OBSERVED,
            source_id=source_id,
            confidence=confidence,
            expires_at_ms=expires_at_ms,
            learned_location_id=observation_location_id,
        )

    def record_inference(
        self,
        entity_id: str,
        fact_id: str,
        value: Any,
        *,
        evidence_fact_ids: Sequence[str],
        source_id: str | None = None,
        confidence: float | None = None,
    ) -> KnowledgeEvent:
        if not evidence_fact_ids:
            raise ValueError("inference requires at least one evidence fact")
        if len(set(evidence_fact_ids)) != len(tuple(evidence_fact_ids)):
            raise ValueError("inference evidence_fact_ids must be unique")
        evidence: list[KnowledgeEvent] = []
        for evidence_fact_id in evidence_fact_ids:
            belief = self.belief(entity_id, evidence_fact_id)
            if belief is None:
                raise ValueError(f"inference evidence is unknown or stale: {evidence_fact_id}")
            evidence.append(belief)
        confidence_ceiling = min(event.confidence for event in evidence)
        resolved_confidence = (
            confidence_ceiling * INFERENCE_CONFIDENCE_FACTOR
            if confidence is None
            else self._validate_confidence(confidence)
        )
        if resolved_confidence > confidence_ceiling:
            raise ValueError("inference confidence cannot exceed its least-confident evidence")
        expiries = [event.expires_at_ms for event in evidence if event.expires_at_ms is not None]
        expires_at_ms = min(expiries) if expiries else None
        return self._record_knowledge_event(
            entity_id,
            fact_id,
            value,
            basis=EpistemicBasis.INFERRED,
            source_id=source_id,
            confidence=resolved_confidence,
            expires_at_ms=expires_at_ms,
            learned_location_id=self._knowledge_entity_location_id(entity_id),
            evidence_event_ids=[event.event_id for event in evidence],
            transmission_depth=max(event.transmission_depth for event in evidence),
        )

    def receive_reported_fact(
        self,
        recipient_id: str,
        *,
        reporter_id: str,
        source_event_id: str,
        confidence_factor: float,
        learned_location_id: str | None = None,
    ) -> KnowledgeEvent:
        source_event = self.knowledge_event(source_event_id)
        reporter_owner = self._knowledge_owner_id(reporter_id)
        if source_event.knower_id != reporter_owner:
            raise ValueError("reported fact source event does not belong to the reporter")
        if source_event.stale_at(self.world.now_ms):
            raise ValueError("reported fact source event is stale")
        factor = float(confidence_factor)
        if not 0.0 < factor <= 1.0:
            raise ValueError("reported fact confidence factor must be in (0, 1]")
        if learned_location_id is None:
            learned_location_id = self._knowledge_entity_location_id(recipient_id)
        return self._record_knowledge_event(
            recipient_id,
            source_event.fact_id,
            source_event.value,
            basis=EpistemicBasis.REPORTED,
            source_id=reporter_id,
            confidence=source_event.confidence * factor,
            expires_at_ms=source_event.expires_at_ms,
            learned_location_id=learned_location_id,
            evidence_event_ids=(source_event.event_id,),
            transmission_depth=source_event.transmission_depth + 1,
        )

    def send_known_fact_message(
        self, sender_id: str, target_id: str, fact_id: str, text: str
    ):
        source_event = self.belief(sender_id, fact_id)
        if source_event is None:
            raise ValueError("sender does not know a current version of the requested fact")
        message = self.send_short_message(sender_id, target_id, text)
        self.communications.attach_fact(message.message_id, fact_id, source_event.event_id)
        return message

    def read_message(self, actor_id: str, message_id: str):
        message = super().read_message(actor_id, message_id)
        if (
            message.attached_fact_id
            and message.source_knowledge_event_id
            and message.received_knowledge_event_id is None
        ):
            source_event = self.knowledge_event(message.source_knowledge_event_id)
            if not source_event.stale_at(self.world.now_ms):
                factor = 0.80 if message.channel.value == "stranger_instant" else REPORT_CONFIDENCE_FACTOR
                received = self.receive_reported_fact(
                    actor_id,
                    reporter_id=message.sender_id,
                    source_event_id=source_event.event_id,
                    confidence_factor=factor,
                    learned_location_id=self._knowledge_entity_location_id(actor_id),
                )
                self.communications.mark_fact_received(message.message_id, received.event_id)
        return message

    def share_known_fact(self, sender_id: str, recipient_id: str, fact_id: str) -> KnowledgeEvent:
        source_belief = self.belief(sender_id, fact_id)
        if source_belief is None:
            raise ValueError("sender does not know a current version of the requested fact")
        if not self._knowledge_entity_alive(sender_id) or not self._knowledge_entity_alive(recipient_id):
            raise ValueError("knowledge cannot be shared by or with a defeated materialized entity")
        sender_location = self._knowledge_entity_location_id(sender_id)
        recipient_location = self._knowledge_entity_location_id(recipient_id)
        if sender_location is None or sender_location != recipient_location:
            raise ValueError("knowledge sharing requires an actual colocated conversation")
        return self._record_knowledge_event(
            recipient_id,
            fact_id,
            source_belief.value,
            basis=EpistemicBasis.REPORTED,
            source_id=sender_id,
            confidence=source_belief.confidence * REPORT_CONFIDENCE_FACTOR,
            expires_at_ms=source_belief.expires_at_ms,
            learned_location_id=sender_location,
            evidence_event_ids=(source_belief.event_id,),
            transmission_depth=source_belief.transmission_depth + 1,
        )

    def belief(self, entity_id: str, fact_id: str) -> KnowledgeEvent | None:
        knower_id = self._knowledge_owner_id(entity_id)
        latest = self._latest_event(knower_id, fact_id)
        if latest is None or latest.stale_at(self.world.now_ms):
            return None
        return latest

    def knowledge_history(self, entity_id: str, fact_id: str | None = None) -> list[dict[str, Any]]:
        knower_id = self._knowledge_owner_id(entity_id)
        return [
            self._event_view(event)
            for event in self.knowledge_events
            if event.knower_id == knower_id and (fact_id is None or event.fact_id == fact_id)
        ]

    def knowledge_event_chain(self, event_id: str) -> list[dict[str, Any]]:
        ordered: list[KnowledgeEvent] = []
        visited: set[str] = set()

        def visit(current_id: str) -> None:
            if current_id in visited:
                return
            visited.add(current_id)
            event = self.knowledge_event(current_id)
            for evidence_id in event.evidence_event_ids:
                visit(evidence_id)
            ordered.append(event)

        visit(event_id)
        return [self._event_view(event) for event in ordered]

    def knowledge_state(self, entity_id: str) -> dict:
        knower_id = self._knowledge_owner_id(entity_id)
        latest: dict[str, KnowledgeEvent] = {}
        for event in self.knowledge_events:
            if event.knower_id == knower_id:
                latest[event.fact_id] = event
        current = {
            fact_id: event
            for fact_id, event in latest.items()
            if not event.stale_at(self.world.now_ms)
        }
        stale = {
            fact_id: event
            for fact_id, event in latest.items()
            if event.stale_at(self.world.now_ms)
        }
        return {
            "knower_id": knower_id,
            "facts": {
                fact_id: self._event_view(event)
                for fact_id, event in sorted(current.items())
            },
            "stale_facts": {
                fact_id: self._event_view(event)
                for fact_id, event in sorted(stale.items())
            },
        }

    def _player_identity_known(self, observer_id: str, target_id: str) -> bool:
        return self.belief(observer_id, f"player_identity:{target_id}") is not None

    def learn_player_identity(self, observer_id: str, target_id: str) -> dict:
        observer, target = self._validate_identity_meeting(observer_id, target_id)
        location_id = self._knowledge_entity_location_id(observer_id)
        if location_id is None:
            raise RuntimeError("identity observation completed without a settled observation location")
        self.record_observation(
            observer_id,
            f"player_identity:{target_id}",
            target.name,
            observation_location_id=location_id,
            source_id=target_id,
        )
        return {"observerId": observer_id, "targetId": target_id, "known": True, "name": target.name}

    def dump_knowledge_state(self) -> dict:
        return {
            "schema": KNOWLEDGE_SCHEMA,
            "sequence": self._knowledge_sequence,
            "events": [asdict(event) for event in self.knowledge_events],
        }

    def load_knowledge_state(self, payload: dict) -> None:
        if not payload:
            self.knowledge_events = []
            self._knowledge_event_index = {}
            self._knowledge_sequence = 0
            return
        schema = payload.get("schema")
        if schema != KNOWLEDGE_SCHEMA:
            if payload.get("events"):
                raise ValueError("legacy knowledge state lacks exact causal provenance and cannot be migrated")
            self.knowledge_events = []
            self._knowledge_event_index = {}
            self._knowledge_sequence = 0
            return

        sequence = int(payload.get("sequence", 0))
        if sequence < 0:
            raise ValueError("knowledge sequence cannot be negative")
        events: list[KnowledgeEvent] = []
        index: dict[str, KnowledgeEvent] = {}
        max_sequence = 0
        for row in payload.get("events", []):
            knower_id = row["knower_id"]
            if knower_id not in self.actors and knower_id not in self.npcs.definitions:
                raise ValueError(f"knowledge save references unknown knower: {knower_id}")
            learned_at_ms = int(row["learned_at_ms"])
            if learned_at_ms > self.world.now_ms:
                raise ValueError(f"knowledge event occurs after current world time: {knower_id}/{row['fact_id']}")
            event_id = row["event_id"]
            if event_id in index:
                raise ValueError(f"duplicate knowledge event id: {event_id}")
            if not event_id.startswith("knowledge_"):
                raise ValueError(f"invalid knowledge event id: {event_id}")
            try:
                event_sequence = int(event_id.removeprefix("knowledge_"))
            except ValueError as exc:
                raise ValueError(f"invalid knowledge event id: {event_id}") from exc
            max_sequence = max(max_sequence, event_sequence)
            evidence_ids = tuple(row.get("evidence_event_ids", ()))
            if any(evidence_id not in index for evidence_id in evidence_ids):
                raise ValueError(f"knowledge event {event_id} references future or missing evidence")
            supersedes_event_id = row.get("supersedes_event_id")
            if supersedes_event_id is not None and supersedes_event_id not in index:
                raise ValueError(f"knowledge event {event_id} supersedes a missing/future event")
            event = KnowledgeEvent(
                event_id=event_id,
                knower_id=knower_id,
                fact_id=row["fact_id"],
                value=row["value"],
                basis=EpistemicBasis(row["basis"]),
                source_id=row.get("source_id"),
                learned_at_ms=learned_at_ms,
                confidence=float(row["confidence"]),
                expires_at_ms=(int(row["expires_at_ms"]) if row.get("expires_at_ms") is not None else None),
                learned_location_id=row.get("learned_location_id"),
                evidence_event_ids=evidence_ids,
                supersedes_event_id=supersedes_event_id,
                transmission_depth=int(row.get("transmission_depth", 0)),
            )
            if event.learned_location_id is not None and event.learned_location_id not in self.world_map.locations:
                raise ValueError(f"knowledge event {event_id} references unknown learned location")
            if event.supersedes_event_id is not None:
                previous = index[event.supersedes_event_id]
                if previous.knower_id != event.knower_id or previous.fact_id != event.fact_id:
                    raise ValueError(f"knowledge correction chain crosses knower/fact boundary: {event_id}")
            events.append(event)
            index[event_id] = event
        if sequence < max_sequence:
            raise ValueError("knowledge sequence precedes persisted event ids")
        self.knowledge_events = events
        self._knowledge_event_index = index
        self._knowledge_sequence = sequence
