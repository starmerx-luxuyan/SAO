from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.rules.knowledge import EpistemicBasis, KnowledgeEvent
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.runtime.communications_runtime import CommunicatingAincradRuntime


class KnowledgeAincradRuntime(CommunicatingAincradRuntime):
    """Communicating runtime with persistent beliefs and authoritative meeting boundaries."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.knowledge_events: list[KnowledgeEvent] = []

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

    def record_knowledge(
        self,
        entity_id: str,
        fact_id: str,
        value: Any,
        *,
        basis: EpistemicBasis | str,
        source_id: str | None = None,
    ) -> KnowledgeEvent:
        if not fact_id:
            raise ValueError("fact_id must be non-empty")
        if not self._knowledge_entity_alive(entity_id):
            raise ValueError("defeated materialized entities cannot acquire new knowledge")
        knower_id = self._knowledge_owner_id(entity_id)
        resolved_source = self._knowledge_owner_id(source_id) if source_id is not None and (
            source_id in self.actors or source_id in self.npcs.definitions
        ) else source_id
        event = KnowledgeEvent(
            knower_id=knower_id,
            fact_id=fact_id,
            value=value,
            basis=EpistemicBasis(basis),
            source_id=resolved_source,
            learned_at_ms=self.world.now_ms,
        )
        self.knowledge_events.append(event)
        return event

    def record_observation(
        self,
        entity_id: str,
        fact_id: str,
        value: Any,
        *,
        source_id: str | None = None,
    ) -> KnowledgeEvent:
        return self.record_knowledge(
            entity_id,
            fact_id,
            value,
            basis=EpistemicBasis.OBSERVED,
            source_id=source_id,
        )

    def record_inference(
        self,
        entity_id: str,
        fact_id: str,
        value: Any,
        *,
        source_id: str | None = None,
    ) -> KnowledgeEvent:
        return self.record_knowledge(
            entity_id,
            fact_id,
            value,
            basis=EpistemicBasis.INFERRED,
            source_id=source_id,
        )

    def share_known_fact(self, sender_id: str, recipient_id: str, fact_id: str) -> KnowledgeEvent:
        belief = self.belief(sender_id, fact_id)
        if belief is None:
            raise ValueError("sender does not know the requested fact")
        if not self._knowledge_entity_alive(sender_id) or not self._knowledge_entity_alive(recipient_id):
            raise ValueError("knowledge cannot be shared by or with a defeated materialized entity")
        sender_location = self._knowledge_entity_location_id(sender_id)
        recipient_location = self._knowledge_entity_location_id(recipient_id)
        if sender_location is None or sender_location != recipient_location:
            raise ValueError("knowledge sharing requires an actual colocated conversation")
        return self.record_knowledge(
            recipient_id,
            fact_id,
            belief.value,
            basis=EpistemicBasis.REPORTED,
            source_id=sender_id,
        )

    def belief(self, entity_id: str, fact_id: str) -> KnowledgeEvent | None:
        knower_id = self._knowledge_owner_id(entity_id)
        for event in reversed(self.knowledge_events):
            if event.knower_id == knower_id and event.fact_id == fact_id:
                return event
        return None

    def knowledge_state(self, entity_id: str) -> dict:
        knower_id = self._knowledge_owner_id(entity_id)
        current: dict[str, KnowledgeEvent] = {}
        for event in self.knowledge_events:
            if event.knower_id == knower_id:
                current[event.fact_id] = event
        return {
            "knower_id": knower_id,
            "facts": {
                fact_id: asdict(event)
                for fact_id, event in sorted(current.items())
            },
        }

    def learn_player_identity(self, observer_id: str, target_id: str) -> dict:
        result = super().learn_player_identity(observer_id, target_id)
        self.record_observation(
            observer_id,
            f"player_identity:{target_id}",
            self.actors[target_id].name,
            source_id=target_id,
        )
        return result

    def dump_knowledge_state(self) -> dict:
        return {
            "events": [asdict(event) for event in self.knowledge_events],
        }

    def load_knowledge_state(self, payload: dict) -> None:
        events: list[KnowledgeEvent] = []
        for row in payload.get("events", []):
            knower_id = row["knower_id"]
            if knower_id not in self.actors and knower_id not in self.npcs.definitions:
                raise ValueError(f"knowledge save references unknown knower: {knower_id}")
            learned_at_ms = int(row["learned_at_ms"])
            if learned_at_ms > self.world.now_ms:
                raise ValueError(f"knowledge event occurs after current world time: {knower_id}/{row['fact_id']}")
            events.append(
                KnowledgeEvent(
                    knower_id=knower_id,
                    fact_id=row["fact_id"],
                    value=row["value"],
                    basis=EpistemicBasis(row["basis"]),
                    source_id=row.get("source_id"),
                    learned_at_ms=learned_at_ms,
                )
            )
        self.knowledge_events = events
