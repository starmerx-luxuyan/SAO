from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any

from sao_mcp.rules.canonical_timeline import (
    CanonicalTimelineLedger,
    canonical_timeline_profile_catalog,
)
from sao_mcp.rules.world_events import (
    TERMINAL_WORLD_EVENT_STATUSES,
    WorldEventLedger,
    WorldEventOccurrence,
    WorldEventResult,
    WorldEventStatus,
)
from sao_mcp.runtime.knowledge_runtime import KnowledgeAincradRuntime


WorldAdvanceHook = Callable[[int, int], None]
WorldEventDiscover = Callable[[], Iterable[str]]
WorldEventResolver = Callable[[str], WorldEventResult | dict[str, Any] | None]


@dataclass(slots=True, frozen=True)
class WorldEventRule:
    rule_id: str
    discover: WorldEventDiscover
    resolve: WorldEventResolver


class WorldEventAincradRuntime(KnowledgeAincradRuntime):
    """Knowledge-aware runtime with persistent state-driven world-event lifecycles."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.world_advance_hooks: list[WorldAdvanceHook] = []
        self.world_event_rules: dict[str, WorldEventRule] = {}
        self.world_event_services: dict[str, object] = {}
        self.world_events = WorldEventLedger()
        self.canonical_timeline = CanonicalTimelineLedger()
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

    def canonical_timeline_profiles(self) -> list[dict[str, Any]]:
        return canonical_timeline_profile_catalog()

    def select_canonical_timeline_profile(
        self,
        profile_id: str | None,
        *,
        anchor_world_ms: int = 0,
    ) -> dict[str, Any]:
        self.canonical_timeline.select_profile(profile_id, anchor_world_ms=anchor_world_ms)
        self.canonical_timeline.reconcile_floor_bosses(self.world)
        return self.canonical_timeline_state()

    def canonical_timeline_state(self) -> dict[str, Any]:
        return self.canonical_timeline.state(now_ms=self.world.now_ms)

    def dump_canonical_timeline_state(self) -> dict[str, Any]:
        return self.canonical_timeline.dump_state()

    def load_canonical_timeline_state(self, payload: dict[str, Any]) -> None:
        self.canonical_timeline.load_state(payload)
        self.canonical_timeline.reconcile_floor_bosses(self.world)

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

    def plan_world_event(
        self,
        occurrence_id: str,
        rule_id: str,
        *,
        expected_at_ms: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorldEventOccurrence:
        if rule_id not in self.world_event_rules:
            raise KeyError(f"world-event rule is not registered: {rule_id}")
        return self.world_events.plan(
            occurrence_id=occurrence_id,
            rule_id=rule_id,
            created_at_ms=self.world.now_ms,
            expected_at_ms=expected_at_ms,
            payload=payload,
        )

    def plan_canonical_world_event(
        self,
        occurrence_id: str,
        rule_id: str,
        canonical_seed_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> WorldEventOccurrence:
        reserved = {"canonical_profile_id", "canonical_seed_id", "canonical_expected_window_end_ms"}
        supplied = set((payload or {}).keys())
        conflict = sorted(reserved & supplied)
        if conflict:
            raise ValueError(f"canonical event payload cannot override reserved keys: {conflict}")
        profile = self.canonical_timeline.profile
        expected_at_ms = None
        expected_end_ms = None
        if profile is not None:
            expected_at_ms, expected_end_ms = self.canonical_timeline.expected_window(canonical_seed_id)
        merged = dict(payload or {})
        merged.update(
            {
                "canonical_profile_id": profile.profile_id if profile is not None else None,
                "canonical_seed_id": canonical_seed_id,
                "canonical_expected_window_end_ms": expected_end_ms,
            }
        )
        return self.plan_world_event(
            occurrence_id,
            rule_id,
            expected_at_ms=expected_at_ms,
            payload=merged,
        )

    def transition_world_event(
        self,
        occurrence_id: str,
        status: WorldEventStatus,
        *,
        payload: dict[str, Any] | None = None,
        triggered_at_ms: int | None = None,
    ) -> WorldEventOccurrence:
        return self.world_events.transition(
            occurrence_id,
            status,
            at_ms=self.world.now_ms,
            triggered_at_ms=triggered_at_ms,
            payload=payload,
        )

    def skip_world_event(self, occurrence_id: str, *, payload: dict[str, Any] | None = None) -> WorldEventOccurrence:
        return self.transition_world_event(occurrence_id, WorldEventStatus.SKIPPED, payload=payload)

    def fail_world_event(self, occurrence_id: str, *, payload: dict[str, Any] | None = None) -> WorldEventOccurrence:
        return self.transition_world_event(occurrence_id, WorldEventStatus.FAILED, payload=payload)

    def interrupt_world_event(self, occurrence_id: str, *, payload: dict[str, Any] | None = None) -> WorldEventOccurrence:
        return self.transition_world_event(occurrence_id, WorldEventStatus.INTERRUPTED, payload=payload)

    def resolve_world_event(self, occurrence_id: str, *, payload: dict[str, Any] | None = None) -> WorldEventOccurrence:
        return self.transition_world_event(occurrence_id, WorldEventStatus.RESOLVED, payload=payload)

    @staticmethod
    def _normalize_world_event_result(value: WorldEventResult | dict[str, Any] | None) -> WorldEventResult:
        if isinstance(value, WorldEventResult):
            if value.status is WorldEventStatus.PENDING:
                raise RuntimeError("world-event resolver cannot return pending")
            return value
        if value is None:
            return WorldEventResult(WorldEventStatus.RESOLVED, {})
        if not isinstance(value, dict):
            raise TypeError("world-event resolver must return WorldEventResult, dict, or None")
        return WorldEventResult(WorldEventStatus.RESOLVED, value)

    def evaluate_world_events(self) -> list[WorldEventOccurrence]:
        """Advance every discoverable occurrence until no rule can make another lifecycle transition."""

        if self._evaluating_world_events:
            return []
        self._evaluating_world_events = True
        transitioned: list[WorldEventOccurrence] = []
        try:
            while True:
                candidate: tuple[WorldEventRule, str, WorldEventOccurrence | None] | None = None
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
                            if existing.status in TERMINAL_WORLD_EVENT_STATUSES:
                                continue
                        candidate = (rule, occurrence_id, existing)
                        break
                    if candidate is not None:
                        break
                if candidate is None:
                    break

                rule, occurrence_id, existing = candidate
                started_at_ms = self.world.now_ms
                result = self._normalize_world_event_result(rule.resolve(occurrence_id))
                if existing is None:
                    if result.status is WorldEventStatus.RESOLVED:
                        occurrence = self.world_events.record_resolved(
                            occurrence_id=occurrence_id,
                            rule_id=rule.rule_id,
                            triggered_at_ms=started_at_ms,
                            resolved_at_ms=self.world.now_ms,
                            payload=result.payload,
                        )
                    else:
                        self.world_events.plan(
                            occurrence_id=occurrence_id,
                            rule_id=rule.rule_id,
                            created_at_ms=started_at_ms,
                        )
                        occurrence = self.world_events.transition(
                            occurrence_id,
                            result.status,
                            at_ms=(started_at_ms if result.status is WorldEventStatus.ACTIVE else self.world.now_ms),
                            triggered_at_ms=(
                                started_at_ms
                                if result.status in {WorldEventStatus.ACTIVE, WorldEventStatus.FAILED}
                                else None
                            ),
                            payload=result.payload,
                        )
                else:
                    if existing.status is WorldEventStatus.ACTIVE and result.status is WorldEventStatus.ACTIVE:
                        raise RuntimeError(f"active world-event resolver made no transition: {occurrence_id}")
                    occurrence = self.world_events.transition(
                        occurrence_id,
                        result.status,
                        at_ms=(started_at_ms if result.status is WorldEventStatus.ACTIVE else self.world.now_ms),
                        triggered_at_ms=(
                            started_at_ms
                            if existing.status is WorldEventStatus.PENDING
                            and result.status in {
                                WorldEventStatus.ACTIVE,
                                WorldEventStatus.RESOLVED,
                                WorldEventStatus.FAILED,
                            }
                            else None
                        ),
                        payload=result.payload,
                    )
                transitioned.append(occurrence)
            return transitioned
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

    def floor_boss_defeated(self, floor_number: int) -> None:
        already_defeated = self.world.floors[floor_number].floor_boss_defeated
        super().floor_boss_defeated(floor_number)
        if already_defeated:
            return
        seed = self.canonical_timeline.seed_for_floor_boss(floor_number)
        if seed is None:
            return
        actual_at_ms = self.world.floors[floor_number].floor_boss_defeated_at_ms
        if actual_at_ms is None:
            raise RuntimeError("floor-boss defeat committed without an authoritative timestamp")
        self.canonical_timeline.observe(
            seed.seed_id,
            actual_at_ms=int(actual_at_ms),
            details={"floor_number": floor_number},
        )

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

    def _finalize_expired_deaths(self, encounter) -> None:
        super()._finalize_expired_deaths(encounter)
        self.evaluate_world_events()

    def travel_actor(self, actor_id: str, destination_id: str):
        # GameRuntime.travel_actor delegates to the data-only travel rule, which advances
        # WorldState directly. Emit the same authoritative time event after that commit.
        before_ms = self.world.now_ms
        resolution = super().travel_actor(actor_id, destination_id)
        self._emit_world_advance(before_ms)
        return resolution
