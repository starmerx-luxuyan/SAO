from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


Path("src/sao_mcp/rules/knowledge.py").write_text(
'''from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EpistemicBasis(StrEnum):
    OBSERVED = "observed"
    REPORTED = "reported"
    INFERRED = "inferred"


@dataclass(slots=True, frozen=True)
class KnowledgeEvent:
    event_id: str
    knower_id: str
    fact_id: str
    value: Any
    basis: EpistemicBasis
    source_id: str | None
    learned_at_ms: int
    confidence: float
    expires_at_ms: int | None
    learned_location_id: str | None
    evidence_event_ids: tuple[str, ...] = ()
    supersedes_event_id: str | None = None
    transmission_depth: int = 0

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("knowledge event_id must be non-empty")
        if not self.knower_id:
            raise ValueError("knowledge knower_id must be non-empty")
        if not self.fact_id:
            raise ValueError("knowledge fact_id must be non-empty")
        if self.learned_at_ms < 0:
            raise ValueError("knowledge learned_at_ms cannot be negative")
        if not 0.0 < self.confidence <= 1.0:
            raise ValueError("knowledge confidence must be in (0, 1]")
        if self.expires_at_ms is not None and self.expires_at_ms <= self.learned_at_ms:
            raise ValueError("knowledge expiry must be after learning time")
        if self.transmission_depth < 0:
            raise ValueError("knowledge transmission_depth cannot be negative")
        if len(set(self.evidence_event_ids)) != len(self.evidence_event_ids):
            raise ValueError("knowledge evidence_event_ids must be unique")

    def stale_at(self, now_ms: int) -> bool:
        if now_ms < 0:
            raise ValueError("knowledge staleness time cannot be negative")
        return self.expires_at_ms is not None and now_ms >= self.expires_at_ms
''',
encoding="utf-8",
)


Path("src/sao_mcp/runtime/knowledge_runtime.py").write_text(
'''from __future__ import annotations

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

    def learn_player_identity(self, observer_id: str, target_id: str) -> dict:
        result = super().learn_player_identity(observer_id, target_id)
        location_id = self._knowledge_entity_location_id(observer_id)
        if location_id is None:
            raise RuntimeError("identity observation completed without a settled observation location")
        self.record_observation(
            observer_id,
            f"player_identity:{target_id}",
            self.actors[target_id].name,
            observation_location_id=location_id,
            source_id=target_id,
        )
        return result

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
''',
encoding="utf-8",
)


replace_once(
    "src/sao_mcp/rules/npc_actor_core.py",
    '''    decision_basis_fact_ids: tuple[str, ...] = ()\n    decision_relation_actor_ids: tuple[str, ...] = ()\n''',
    '''    decision_basis_fact_ids: tuple[str, ...] = ()\n    decision_basis_event_ids: tuple[str, ...] = ()\n    decision_relation_actor_ids: tuple[str, ...] = ()\n''',
)
replace_once(
    "src/sao_mcp/rules/npc_actor_core.py",
    '''            self.short_term_plan = []\n            self.plan_cursor = 0\n            self.revision += 1\n        self.last_decision_at_ms = decided_at_ms\n''',
    '''            self.short_term_plan = []\n            self.plan_cursor = 0\n            self.decision_basis_event_ids = ()\n            self.revision += 1\n        self.last_decision_at_ms = decided_at_ms\n''',
)
replace_once(
    "src/sao_mcp/rules/npc_actor_core.py",
    '''        self.decision_relation_actor_ids = (\n            (goal.relationship_actor_id,)\n            if goal is not None and goal.relationship_actor_id is not None\n            else ()\n        )\n\n    def clear_current_goal(self) -> None:\n''',
    '''        self.decision_relation_actor_ids = (\n            (goal.relationship_actor_id,)\n            if goal is not None and goal.relationship_actor_id is not None\n            else ()\n        )\n\n    def set_decision_basis_events(self, event_ids: tuple[str, ...]) -> None:\n        if self.decision_basis_event_ids != event_ids:\n            self.decision_basis_event_ids = event_ids\n            self.revision += 1\n\n    def clear_current_goal(self) -> None:\n''',
)
replace_once(
    "src/sao_mcp/rules/npc_actor_core.py",
    '''        self.decision_basis_fact_ids = ()\n        self.decision_relation_actor_ids = ()\n''',
    '''        self.decision_basis_fact_ids = ()\n        self.decision_basis_event_ids = ()\n        self.decision_relation_actor_ids = ()\n''',
)

replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    'NPC_AUTONOMY_SCHEMA = "npc-autonomy.v2"',
    'NPC_AUTONOMY_SCHEMA = "npc-autonomy.v3"',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''        for npc_id in self.npcs.definitions:\n            self._ensure_actor_core(npc_id)\n        self.register_world_advance_hook(self._resolve_due_npc_activities)\n''',
    '''        for npc_id in self.npcs.definitions:\n            self._ensure_actor_core(npc_id)\n        self.register_world_advance_hook(self._resolve_due_npc_activities)\n        self.register_knowledge_update_hook(self._on_knowledge_update)\n''',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''    def _evaluate_npc_decision(self, npc_id: str, decision_at_ms: int) -> None:\n        agenda = self._agenda(npc_id)\n''',
    '''    def _on_knowledge_update(self, event) -> None:\n        if event.knower_id not in self.npcs.definitions:\n            return\n        agenda = self._agenda(event.knower_id)\n        if not agenda.active:\n            self._evaluate_npc_decision(event.knower_id, self.world.now_ms)\n\n    def _evaluate_npc_decision(self, npc_id: str, decision_at_ms: int) -> None:\n        agenda = self._agenda(npc_id)\n''',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''        previous_id = core.current_goal_id\n        core.select_goal(selected_id, decided_at_ms=decision_at_ms)\n        if selected is None:\n            return\n''',
    '''        previous_id = core.current_goal_id\n        core.select_goal(selected_id, decided_at_ms=decision_at_ms)\n        if selected is None:\n            core.set_decision_basis_events(())\n            return\n        if selected.required_fact_id is not None:\n            decision_belief = self.belief(npc_id, selected.required_fact_id)\n            if decision_belief is None:\n                raise RuntimeError("eligible NPC goal lost its decision belief before selection")\n            core.set_decision_basis_events((decision_belief.event_id,))\n        else:\n            core.set_decision_basis_events(())\n''',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''        beliefs = {\n            fact_id: (\n                asdict(belief) if (belief := self.belief(npc_id, fact_id)) is not None else None\n            )\n            for fact_id in core.decision_basis_fact_ids\n        }\n''',
    '''        decision_events = {\n            event_id: self.knowledge_event_state(event_id)\n            for event_id in core.decision_basis_event_ids\n        }\n        beliefs = {\n            row["fact_id"]: row\n            for row in decision_events.values()\n        }\n''',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''            "decision_basis_fact_ids": list(core.decision_basis_fact_ids),\n            "decision_relation_actor_ids": list(core.decision_relation_actor_ids),\n            "decision_beliefs": beliefs,\n''',
    '''            "decision_basis_fact_ids": list(core.decision_basis_fact_ids),\n            "decision_basis_event_ids": list(core.decision_basis_event_ids),\n            "decision_relation_actor_ids": list(core.decision_relation_actor_ids),\n            "decision_beliefs": beliefs,\n            "decision_evidence": decision_events,\n''',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''            if core.plan_cursor < 0 or core.plan_cursor > len(core.short_term_plan):\n                raise RuntimeError(f"NPC {npc_id} actor-core plan cursor is invalid")\n            for goal in core.long_term_goals.values():\n''',
    '''            if core.plan_cursor < 0 or core.plan_cursor > len(core.short_term_plan):\n                raise RuntimeError(f"NPC {npc_id} actor-core plan cursor is invalid")\n            for event_id in core.decision_basis_event_ids:\n                event = self.knowledge_event(event_id)\n                if event.knower_id != npc_id:\n                    raise RuntimeError(f"NPC {npc_id} decision evidence belongs to another knower")\n                if event.fact_id not in core.decision_basis_fact_ids:\n                    raise RuntimeError(f"NPC {npc_id} decision evidence disagrees with decision fact IDs")\n            for goal in core.long_term_goals.values():\n''',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''        if schema != NPC_AUTONOMY_SCHEMA:\n            if payload.get("agendas"):\n                raise ValueError(\n                    "legacy NPC autonomy state mixes goals into agenda activities and cannot be migrated exactly"\n                )\n''',
    '''        if schema != NPC_AUTONOMY_SCHEMA:\n            if payload.get("actor_cores") or payload.get("agendas"):\n                raise ValueError(\n                    "legacy NPC autonomy state lacks exact knowledge-event decision provenance and cannot be migrated"\n                )\n''',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''                decision_basis_fact_ids=tuple(row.get("decision_basis_fact_ids", ())),\n                decision_relation_actor_ids=tuple(row.get("decision_relation_actor_ids", ())),\n''',
    '''                decision_basis_fact_ids=tuple(row.get("decision_basis_fact_ids", ())),\n                decision_basis_event_ids=tuple(row.get("decision_basis_event_ids", ())),\n                decision_relation_actor_ids=tuple(row.get("decision_relation_actor_ids", ())),\n''',
)

replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''    "observe_fact": (\n        frozenset({"entity_id", "fact_id", "value"}),\n        frozenset({"source_id"}),\n    ),\n    "infer_fact": (\n        frozenset({"entity_id", "fact_id", "value"}),\n        frozenset({"source_id"}),\n    ),\n''',
    '''    "observe_fact": (\n        frozenset({"entity_id", "fact_id", "value", "observation_location_id"}),\n        frozenset({"source_id", "confidence", "expires_after_ms"}),\n    ),\n    "infer_fact": (\n        frozenset({"entity_id", "fact_id", "value", "evidence_fact_ids"}),\n        frozenset({"source_id", "confidence"}),\n    ),\n''',
)
replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''            if op == "assign_guild_goal":\n                member_ids = action["assigned_member_ids"]\n''',
    '''            if op == "infer_fact":\n                evidence_fact_ids = action["evidence_fact_ids"]\n                if not isinstance(evidence_fact_ids, list) or not evidence_fact_ids or any(\n                    not isinstance(fact_id, str) or not fact_id for fact_id in evidence_fact_ids\n                ):\n                    raise ValueError(\n                        f"GM turn action {index} (infer_fact) evidence_fact_ids must be a non-empty string list"\n                    )\n            if op == "assign_guild_goal":\n                member_ids = action["assigned_member_ids"]\n''',
)
replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''        if op == "observe_fact":\n            return runtime.record_observation(\n                action["entity_id"],\n                action["fact_id"],\n                action["value"],\n                source_id=action.get("source_id"),\n            )\n        if op == "infer_fact":\n            return runtime.record_inference(\n                action["entity_id"],\n                action["fact_id"],\n                action["value"],\n                source_id=action.get("source_id"),\n            )\n''',
    '''        if op == "observe_fact":\n            return runtime.record_observation(\n                action["entity_id"],\n                action["fact_id"],\n                action["value"],\n                observation_location_id=action["observation_location_id"],\n                source_id=action.get("source_id"),\n                confidence=float(action.get("confidence", 1.0)),\n                expires_after_ms=(\n                    int(action["expires_after_ms"])\n                    if action.get("expires_after_ms") is not None\n                    else None\n                ),\n            )\n        if op == "infer_fact":\n            return runtime.record_inference(\n                action["entity_id"],\n                action["fact_id"],\n                action["value"],\n                evidence_fact_ids=action["evidence_fact_ids"],\n                source_id=action.get("source_id"),\n                confidence=(\n                    float(action["confidence"])\n                    if action.get("confidence") is not None\n                    else None\n                ),\n            )\n''',
)

replace_once(
    "src/sao_mcp/server_gm.py",
    '''    def get_entity_knowledge_history(entity_id: str) -> str:\n        """Inspect the entity's full dynamic knowledge history, preserving rumors, mistakes and corrections."""\n        knower_id = gm_turn_executor.runtime._knowledge_owner_id(entity_id)\n        rows = [\n            event\n            for event in gm_turn_executor.runtime.knowledge_events\n            if event.knower_id == knower_id\n        ]\n        return _json({"knower_id": knower_id, "events": rows})\n\n''',
    '''    def get_entity_knowledge_history(entity_id: str) -> str:\n        """Inspect full belief history with confidence, expiry, evidence and correction provenance."""\n        runtime = gm_turn_executor.runtime\n        return _json({\n            "knower_id": runtime._knowledge_owner_id(entity_id),\n            "events": runtime.knowledge_history(entity_id),\n        })\n\n    @mcp.tool()\n    def get_knowledge_event_chain(event_id: str) -> str:\n        """Trace one belief event back through the exact observations/reports/inferences that support it."""\n        return _json({"events": gm_turn_executor.runtime.knowledge_event_chain(event_id)})\n\n''',
)

Path("tests/test_knowledge_runtime.py").write_text(
'''import pytest

from sao_mcp.rules.knowledge import EpistemicBasis
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


AGIL = "pc_agil"
AGIL_SHOP = "floor_50_agil_shop"
ALGADE = "floor_50_algade"
TOWN = "floor_1_town_of_beginnings"


def test_beliefs_preserve_rumor_correction_chain_and_survive_save_load():
    runtime = HousingAincradRuntime(seed=107)
    scout = runtime.create_character("Scout", level=10)
    listener = runtime.create_character("Listener", level=10)
    scout.location_id = TOWN
    listener.location_id = TOWN

    fact_id = "floor1_boss_room:door_trapped"
    rumor_fact = "rumor:floor1_boss_room_door_trapped"
    rumor = runtime.record_observation(
        scout.actor_id,
        rumor_fact,
        True,
        observation_location_id=TOWN,
        source_id="field_rumor",
        confidence=0.60,
    )
    inferred = runtime.record_inference(
        scout.actor_id,
        fact_id,
        True,
        evidence_fact_ids=[rumor_fact],
        source_id="scout_reasoning",
    )
    assert inferred.basis is EpistemicBasis.INFERRED
    assert inferred.evidence_event_ids == (rumor.event_id,)
    assert inferred.confidence == pytest.approx(0.48)

    reported = runtime.share_known_fact(scout.actor_id, listener.actor_id, fact_id)
    assert reported.basis is EpistemicBasis.REPORTED
    assert reported.value is True
    assert reported.source_id == scout.actor_id
    assert reported.evidence_event_ids == (inferred.event_id,)
    assert reported.transmission_depth == 1
    assert reported.confidence == pytest.approx(inferred.confidence * 0.85)

    runtime.advance_world(1_000)
    corrected = runtime.record_observation(
        scout.actor_id,
        fact_id,
        False,
        observation_location_id=TOWN,
        source_id="direct_inspection",
    )
    assert corrected.supersedes_event_id == inferred.event_id
    assert runtime.belief(scout.actor_id, fact_id).value is False
    assert runtime.belief(listener.actor_id, fact_id).value is True

    second_report = runtime.share_known_fact(scout.actor_id, listener.actor_id, fact_id)
    assert second_report.supersedes_event_id == reported.event_id
    current = runtime.knowledge_state(listener.actor_id)
    assert current["facts"][fact_id]["value"] is False
    assert current["facts"][fact_id]["basis"] is EpistemicBasis.REPORTED
    chain = runtime.knowledge_event_chain(second_report.event_id)
    assert [row["event_id"] for row in chain] == [corrected.event_id, second_report.event_id]

    restored = import_runtime(export_runtime(runtime))
    restored_belief = restored.belief(listener.actor_id, fact_id)
    assert restored_belief is not None
    assert restored_belief.value is False
    assert restored_belief.event_id == second_report.event_id
    restored_history = restored.knowledge_history(listener.actor_id, fact_id)
    assert [row["value"] for row in restored_history] == [True, False]
    assert restored_history[-1]["supersedes_event_id"] == reported.event_id


def test_direct_observation_requires_actual_location_and_inference_requires_known_evidence():
    runtime = HousingAincradRuntime(seed=108)
    runtime.world.floors[50].unlocked = True

    with pytest.raises(ValueError, match="observation_location_id"):
        runtime.record_observation(
            AGIL,
            "algade_market:ore_shortage",
            True,
            observation_location_id=ALGADE,
        )

    clue = runtime.record_observation(
        AGIL,
        "market_talk:ore_shortage_claim",
        True,
        observation_location_id=AGIL_SHOP,
        confidence=0.7,
    )
    with pytest.raises(ValueError, match="at least one evidence"):
        runtime.record_inference(AGIL, "algade_market:ore_shortage", True, evidence_fact_ids=[])
    with pytest.raises(ValueError, match="unknown or stale"):
        runtime.record_inference(
            AGIL,
            "algade_market:ore_shortage",
            True,
            evidence_fact_ids=["missing:evidence"],
        )
    inferred = runtime.record_inference(
        AGIL,
        "algade_market:ore_shortage",
        True,
        evidence_fact_ids=[clue.fact_id],
    )
    assert inferred.confidence == pytest.approx(0.56)


def test_stale_belief_disappears_from_current_state_and_stops_driving_npc_goal():
    runtime = HousingAincradRuntime(seed=109)
    npc_id = "npc_tutorial_instructor"
    fact_id = "field_orientation:route_open"
    runtime.set_npc_goal(
        npc_id,
        "use_verified_route",
        TOWN,
        required_fact_id=fact_id,
        required_fact_value=True,
    )
    assert runtime.npc_actor_core_state(npc_id)["current_goal_id"] is None

    observed = runtime.record_observation(
        npc_id,
        fact_id,
        True,
        observation_location_id=TOWN,
        expires_after_ms=100,
    )
    selected = runtime.npc_actor_core_state(npc_id)
    assert selected["current_goal_id"] == "use_verified_route"
    assert selected["decision_basis_event_ids"] == [observed.event_id]
    assert selected["decision_evidence"][observed.event_id]["stale"] is False

    runtime.advance_world(100)
    assert runtime.belief(npc_id, fact_id) is None
    state = runtime.knowledge_state(npc_id)
    assert fact_id not in state["facts"]
    assert state["stale_facts"][fact_id]["event_id"] == observed.event_id
    assert runtime.npc_actor_core_state(npc_id)["current_goal_id"] is None


def test_named_npc_epistemic_identity_survives_materialization_and_travel_blocks_reporting():
    runtime = HousingAincradRuntime(seed=110)
    runtime.world.floors[50].unlocked = True
    listener = runtime.create_character("Customer", level=10)
    listener.location_id = AGIL_SHOP

    clue = runtime.record_observation(
        AGIL,
        "market_talk:ore_shortage_claim",
        True,
        observation_location_id=AGIL_SHOP,
        source_id="market_talk",
        confidence=0.7,
    )
    fact_id = "algade_market:ore_shortage"
    runtime.record_inference(
        AGIL,
        fact_id,
        True,
        evidence_fact_ids=[clue.fact_id],
        source_id="merchant_judgment",
    )
    assert runtime.belief(AGIL, fact_id).knower_id == AGIL

    agil_actor = runtime.create_character("Agil", level=30)
    agil_actor.metadata["npc_definition_id"] = AGIL
    agil_actor.location_id = AGIL_SHOP

    assert runtime.belief(agil_actor.actor_id, fact_id).knower_id == AGIL
    first_report = runtime.share_known_fact(AGIL, listener.actor_id, fact_id)
    assert first_report.source_id == AGIL

    runtime.set_npc_goal(AGIL, "visit_algade_market", ALGADE)
    assert runtime.npc_location_id(AGIL) is None
    with pytest.raises(ValueError, match="colocated conversation"):
        runtime.share_known_fact(AGIL, listener.actor_id, fact_id)

    runtime.advance_world(2 * 60_000)
    assert runtime.npc_location_id(AGIL) == ALGADE
    assert agil_actor.location_id == ALGADE
    assert runtime.npc_agenda_state(AGIL)["goal_reached"] is True
    assert runtime.belief(agil_actor.actor_id, fact_id).value is True

    agil_actor.hp = 0
    agil_actor.alive = False
    with pytest.raises(ValueError, match="cannot acquire new knowledge"):
        runtime.record_observation(
            AGIL,
            "algade_market:new_fact",
            True,
            observation_location_id=ALGADE,
        )
''',
encoding="utf-8",
)

replace_once(
    "tests/test_npc_autonomy.py",
    '''    runtime.record_observation(AGIL, fact_id, True, source_id="verified_route_report")\n''',
    '''    observed = runtime.record_observation(\n        AGIL,\n        fact_id,\n        True,\n        observation_location_id=AGIL_SHOP,\n        source_id="verified_route_report",\n    )\n''',
)
replace_once(
    "tests/test_npc_autonomy.py",
    '''    assert selected["decision_basis_fact_ids"] == [fact_id]\n    assert selected["decision_beliefs"][fact_id]["value"] is True\n''',
    '''    assert selected["decision_basis_fact_ids"] == [fact_id]\n    assert selected["decision_basis_event_ids"] == [observed.event_id]\n    assert selected["decision_beliefs"][fact_id]["event_id"] == observed.event_id\n    assert selected["decision_beliefs"][fact_id]["value"] is True\n''',
)
replace_once(
    "tests/test_npc_autonomy.py",
    '''    runtime.record_inference(AGIL, unavailable_fact, True, source_id="market_rumor")\n''',
    '''    rumor = runtime.record_observation(\n        AGIL,\n        "market_rumor:shop_unavailable",\n        True,\n        observation_location_id=ALGADE,\n        source_id="market_rumor",\n        confidence=0.6,\n    )\n    runtime.record_inference(\n        AGIL,\n        unavailable_fact,\n        True,\n        evidence_fact_ids=[rumor.fact_id],\n        source_id="merchant_judgment",\n    )\n''',
)
replace_once(
    "tests/test_npc_autonomy.py",
    '''    runtime.record_observation(AGIL, unavailable_fact, False, source_id="verified_shop_status")\n''',
    '''    runtime.record_observation(\n        AGIL,\n        unavailable_fact,\n        False,\n        observation_location_id=ALGADE,\n        source_id="verified_shop_status",\n    )\n''',
)

Path("tests/test_knowledge_authority_source.py").write_text(
'''import ast
from pathlib import Path

from sao_mcp.rules.knowledge import KnowledgeEvent
from sao_mcp.rules.npc_actor_core import NPCActorCoreState
from sao_mcp.runtime.gm_turn import GMTurnExecutor


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src/sao_mcp"


def test_knowledge_events_have_causal_and_temporal_provenance_fields():
    fields = set(KnowledgeEvent.__dataclass_fields__)
    assert {
        "event_id",
        "confidence",
        "expires_at_ms",
        "learned_location_id",
        "evidence_event_ids",
        "supersedes_event_id",
        "transmission_depth",
    } <= fields


def test_actor_core_persists_exact_knowledge_event_used_for_decision():
    fields = set(NPCActorCoreState.__dataclass_fields__)
    assert "decision_basis_event_ids" in fields


def test_gm_observation_and_inference_contracts_require_epistemic_evidence():
    contract = GMTurnExecutor.supported_actions()
    assert set(contract["observe_fact"]["required"]) == {
        "entity_id",
        "fact_id",
        "value",
        "observation_location_id",
    }
    assert set(contract["infer_fact"]["required"]) == {
        "entity_id",
        "fact_id",
        "value",
        "evidence_fact_ids",
    }


def test_no_source_module_outside_knowledge_runtime_reads_or_mutates_raw_knowledge_event_ledger():
    violations = []
    authority = SOURCE_ROOT / "runtime/knowledge_runtime.py"
    for path in SOURCE_ROOT.rglob("*.py"):
        if path == authority:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "knowledge_events":
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert violations == []
''',
encoding="utf-8",
)
