from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.rules.knowledge import EpistemicBasis, KnowledgeEvent
from sao_mcp.runtime.communications_runtime import CommunicatingAincradRuntime


class KnowledgeAincradRuntime(CommunicatingAincradRuntime):
    """Communicating runtime with persistent per-entity beliefs derived from knowledge history."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.knowledge_events: list[KnowledgeEvent] = []

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
        self.knowledge_events = [
            KnowledgeEvent(
                knower_id=row["knower_id"],
                fact_id=row["fact_id"],
                value=row["value"],
                basis=EpistemicBasis(row["basis"]),
                source_id=row.get("source_id"),
                learned_at_ms=int(row["learned_at_ms"]),
            )
            for row in payload.get("events", [])
        ]
