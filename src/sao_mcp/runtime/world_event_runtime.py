from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any

from sao_mcp.rules.world_events import WorldEventLedger, WorldEventOccurrence
from sao_mcp.runtime.knowledge_runtime import KnowledgeAincradRuntime


WorldAdvanceHook = Callable[[int, int], None]
WorldEventDiscover = Callable[[], Iterable[str]]
WorldEventResolver = Callable[[str], dict[str, Any] | None]


@dataclass(slots=True, frozen=True)
class WorldEventRule:
    rule_id: str
    discover: WorldEventDiscover
    resolve: WorldEventResolver


class WorldEventAincradRuntime(KnowledgeAincradRuntime):
    """Knowledge-aware runtime with persistent conditional world-event resolution."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.world_advance_hooks: list[WorldAdvanceHook] = []
        self.world_event_rules: dict[str, WorldEventRule] = {}
        self.world_event_services: dict[str, object] = {}
        self.world_events = WorldEventLedger()
        self._evaluating_world_events = False

    def register_world_advance_hook(self, hook: WorldAdvanceHook) -> None:
        self.world_advance_hooks.append(hook)

    def install_world_event_service(self, service_id: str, factory: Callable[[], object]) -> object:
        clean_service_id = service_id.strip()
        if not clean_service_id:
            raise ValueError("world-event service id is required")
        existing = self.world_event_services.get(clean_service_id)
        if existing is not None:
            return existing
        service = factory()
        self.world_event_services[clean_service_id] = service
        return service

    def register_world_event_rule(
        self,
        rule_id: str,
        discover: WorldEventDiscover,
        resolve: WorldEventResolver,
    ) -> None:
        clean_rule_id = rule_id.strip()
        if not clean_rule_id:
            raise ValueError("world-event rule id is required")
        if clean_rule_id in self.world_event_rules:
            raise ValueError(f"world-event rule is already registered: {clean_rule_id}")
        self.world_event_rules[clean_rule_id] = WorldEventRule(clean_rule_id, discover, resolve)

    def evaluate_world_events(self) -> list[WorldEventOccurrence]:
        """Resolve every newly-satisfied occurrence, including chains created by earlier resolutions."""

        if self._evaluating_world_events:
            return []
        self._evaluating_world_events = True
        resolved: list[WorldEventOccurrence] = []
        try:
            while True:
                candidate: tuple[WorldEventRule, str] | None = None
                for rule in self.world_event_rules.values():
                    occurrence_ids = tuple(rule.discover())
                    if len(set(occurrence_ids)) != len(occurrence_ids):
                        raise RuntimeError(f"world-event rule {rule.rule_id} emitted duplicate occurrence ids")
                    for occurrence_id in occurrence_ids:
                        if not isinstance(occurrence_id, str) or not occurrence_id.strip():
                            raise RuntimeError(f"world-event rule {rule.rule_id} emitted an invalid occurrence id")
                        existing = self.world_events.occurrences.get(occurrence_id)
                        if existing is not None:
                            if existing.rule_id != rule.rule_id:
                                raise RuntimeError(
                                    f"world-event occurrence id collision: {occurrence_id} belongs to {existing.rule_id}, "
                                    f"not {rule.rule_id}"
                                )
                            continue
                        candidate = (rule, occurrence_id)
                        break
                    if candidate is not None:
                        break
                if candidate is None:
                    break

                rule, occurrence_id = candidate
                triggered_at_ms = self.world.now_ms
                payload = rule.resolve(occurrence_id)
                if payload is None:
                    payload = {}
                occurrence = self.world_events.record_resolved(
                    occurrence_id=occurrence_id,
                    rule_id=rule.rule_id,
                    triggered_at_ms=triggered_at_ms,
                    resolved_at_ms=self.world.now_ms,
                    payload=payload,
                )
                resolved.append(occurrence)
            return resolved
        finally:
            self._evaluating_world_events = False

    def world_event_state(self, occurrence_id: str | None = None) -> dict[str, Any]:
        if occurrence_id is None:
            return {
                "registered_rule_ids": list(self.world_event_rules),
                "occurrences": {
                    key: asdict(value)
                    for key, value in self.world_events.occurrences.items()
                },
            }
        occurrence = self.world_events.occurrences[occurrence_id]
        return asdict(occurrence)

    def world_event_history(self, rule_id: str | None = None) -> list[dict[str, Any]]:
        rows = self.world_events.history
        if rule_id is not None:
            rows = [row for row in rows if row["rule_id"] == rule_id]
        return list(rows)

    def dump_world_event_state(self) -> dict[str, Any]:
        return self.world_events.dump_state()

    def load_world_event_state(self, payload: dict[str, Any]) -> None:
        self.world_events.load_state(payload)

    def _emit_world_advance(self, before_ms: int) -> None:
        after_ms = self.world.now_ms
        if after_ms == before_ms:
            return
        for hook in tuple(self.world_advance_hooks):
            hook(before_ms, after_ms)
        self.evaluate_world_events()

    def advance_world(self, elapsed_ms: int) -> list[int]:
        before_ms = self.world.now_ms
        activated = super().advance_world(elapsed_ms)
        self._emit_world_advance(before_ms)
        return activated

    def _resolve_defeat(self, encounter, target, killer_id: str | None) -> None:
        super()._resolve_defeat(encounter, target, killer_id)
        self.evaluate_world_events()

    def travel_actor(self, actor_id: str, destination_id: str):
        # GameRuntime.travel_actor delegates to the data-only travel rule, which advances
        # WorldState directly. Emit the same authoritative time event after that commit.
        before_ms = self.world.now_ms
        resolution = super().travel_actor(actor_id, destination_id)
        self._emit_world_advance(before_ms)
        return resolution
