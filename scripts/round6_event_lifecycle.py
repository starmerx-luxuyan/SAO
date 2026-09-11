from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


Path("src/sao_mcp/rules/world_events.py").write_text(
'''from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class WorldEventStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    RESOLVED = "resolved"
    SKIPPED = "skipped"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


TERMINAL_WORLD_EVENT_STATUSES = frozenset(
    {
        WorldEventStatus.RESOLVED,
        WorldEventStatus.SKIPPED,
        WorldEventStatus.FAILED,
        WorldEventStatus.INTERRUPTED,
    }
)


@dataclass(slots=True, frozen=True)
class WorldEventResult:
    status: WorldEventStatus
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorldEventOccurrence:
    occurrence_id: str
    rule_id: str
    status: WorldEventStatus
    created_at_ms: int
    expected_at_ms: int | None = None
    triggered_at_ms: int | None = None
    resolved_at_ms: int | None = None
    started_early: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


class WorldEventLedger:
    """Persistent event lifecycle; executable rule callbacks stay runtime-only."""

    def __init__(self) -> None:
        self.occurrences: dict[str, WorldEventOccurrence] = {}
        self.history: list[dict[str, Any]] = []

    @staticmethod
    def _validate_id(value: str, label: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError(f"world-event {label} is required")
        return clean

    @staticmethod
    def _validate_time(value: int | None, label: str) -> None:
        if value is not None and value < 0:
            raise ValueError(f"world-event {label} cannot be negative")

    def _append_history(self, occurrence: WorldEventOccurrence, transitioned_at_ms: int) -> None:
        row = asdict(occurrence)
        row["transitioned_at_ms"] = transitioned_at_ms
        self.history.append(row)

    def plan(
        self,
        *,
        occurrence_id: str,
        rule_id: str,
        created_at_ms: int,
        expected_at_ms: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorldEventOccurrence:
        occurrence_id = self._validate_id(occurrence_id, "occurrence id")
        rule_id = self._validate_id(rule_id, "rule id")
        self._validate_time(created_at_ms, "creation time")
        self._validate_time(expected_at_ms, "expected time")
        if occurrence_id in self.occurrences:
            raise ValueError(f"world-event occurrence already exists: {occurrence_id}")
        if payload is not None and not isinstance(payload, dict):
            raise TypeError("world-event payload must be a dict")
        occurrence = WorldEventOccurrence(
            occurrence_id=occurrence_id,
            rule_id=rule_id,
            status=WorldEventStatus.PENDING,
            created_at_ms=created_at_ms,
            expected_at_ms=expected_at_ms,
            payload=dict(payload or {}),
        )
        self.occurrences[occurrence_id] = occurrence
        self._append_history(occurrence, created_at_ms)
        return occurrence

    def record_resolved(
        self,
        *,
        occurrence_id: str,
        rule_id: str,
        triggered_at_ms: int,
        resolved_at_ms: int,
        payload: dict[str, Any],
        expected_at_ms: int | None = None,
    ) -> WorldEventOccurrence:
        occurrence_id = self._validate_id(occurrence_id, "occurrence id")
        rule_id = self._validate_id(rule_id, "rule id")
        self._validate_time(triggered_at_ms, "trigger time")
        self._validate_time(resolved_at_ms, "resolution time")
        self._validate_time(expected_at_ms, "expected time")
        if occurrence_id in self.occurrences:
            raise ValueError(f"world-event occurrence already exists: {occurrence_id}")
        if resolved_at_ms < triggered_at_ms:
            raise ValueError("world-event resolution time cannot precede its trigger")
        if not isinstance(payload, dict):
            raise TypeError("world-event payload must be a dict")
        occurrence = WorldEventOccurrence(
            occurrence_id=occurrence_id,
            rule_id=rule_id,
            status=WorldEventStatus.RESOLVED,
            created_at_ms=triggered_at_ms,
            expected_at_ms=expected_at_ms,
            triggered_at_ms=triggered_at_ms,
            resolved_at_ms=resolved_at_ms,
            started_early=expected_at_ms is not None and triggered_at_ms < expected_at_ms,
            payload=dict(payload),
        )
        self.occurrences[occurrence_id] = occurrence
        self._append_history(occurrence, resolved_at_ms)
        return occurrence

    def transition(
        self,
        occurrence_id: str,
        status: WorldEventStatus,
        *,
        at_ms: int,
        triggered_at_ms: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorldEventOccurrence:
        self._validate_time(at_ms, "transition time")
        self._validate_time(triggered_at_ms, "trigger time")
        occurrence = self.occurrences[occurrence_id]
        current = occurrence.status
        allowed = {
            WorldEventStatus.PENDING: {
                WorldEventStatus.ACTIVE,
                WorldEventStatus.RESOLVED,
                WorldEventStatus.SKIPPED,
                WorldEventStatus.FAILED,
            },
            WorldEventStatus.ACTIVE: {
                WorldEventStatus.RESOLVED,
                WorldEventStatus.INTERRUPTED,
                WorldEventStatus.FAILED,
            },
        }
        if status not in allowed.get(current, set()):
            raise ValueError(f"illegal world-event transition: {current.value} -> {status.value}")
        if at_ms < occurrence.created_at_ms:
            raise ValueError("world-event transition cannot precede creation")
        if payload is not None and not isinstance(payload, dict):
            raise TypeError("world-event payload must be a dict")

        if current is WorldEventStatus.PENDING:
            if status is WorldEventStatus.ACTIVE:
                occurrence.triggered_at_ms = triggered_at_ms if triggered_at_ms is not None else at_ms
            elif status in {WorldEventStatus.RESOLVED, WorldEventStatus.FAILED}:
                occurrence.triggered_at_ms = triggered_at_ms if triggered_at_ms is not None else at_ms
                occurrence.resolved_at_ms = at_ms
            elif status is WorldEventStatus.SKIPPED:
                occurrence.resolved_at_ms = at_ms
        else:
            if occurrence.triggered_at_ms is None:
                raise RuntimeError("active world-event occurrence has no trigger time")
            occurrence.resolved_at_ms = at_ms

        if occurrence.triggered_at_ms is not None:
            if occurrence.triggered_at_ms < occurrence.created_at_ms:
                raise ValueError("world-event trigger cannot precede creation")
            if occurrence.resolved_at_ms is not None and occurrence.resolved_at_ms < occurrence.triggered_at_ms:
                raise ValueError("world-event resolution cannot precede trigger")
            occurrence.started_early = (
                occurrence.expected_at_ms is not None
                and occurrence.triggered_at_ms < occurrence.expected_at_ms
            )
        occurrence.status = status
        if payload:
            occurrence.payload.update(payload)
        self._append_history(occurrence, at_ms)
        return occurrence

    def dump_state(self) -> dict[str, Any]:
        return {
            "occurrences": {
                occurrence_id: asdict(occurrence)
                for occurrence_id, occurrence in self.occurrences.items()
            },
            "history": list(self.history),
        }

    def load_state(self, payload: dict[str, Any]) -> None:
        occurrences: dict[str, WorldEventOccurrence] = {}
        for occurrence_id, row in payload.get("occurrences", {}).items():
            status = WorldEventStatus(row["status"])
            triggered_at_ms = row.get("triggered_at_ms")
            resolved_at_ms = row.get("resolved_at_ms")
            created_at_ms = int(
                row.get(
                    "created_at_ms",
                    triggered_at_ms if triggered_at_ms is not None else resolved_at_ms,
                )
            )
            occurrence = WorldEventOccurrence(
                occurrence_id=row["occurrence_id"],
                rule_id=row["rule_id"],
                status=status,
                created_at_ms=created_at_ms,
                expected_at_ms=(
                    int(row["expected_at_ms"])
                    if row.get("expected_at_ms") is not None
                    else None
                ),
                triggered_at_ms=(int(triggered_at_ms) if triggered_at_ms is not None else None),
                resolved_at_ms=(int(resolved_at_ms) if resolved_at_ms is not None else None),
                started_early=bool(row.get("started_early", False)),
                payload=dict(row.get("payload", {})),
            )
            if occurrence.occurrence_id != occurrence_id:
                raise ValueError("world-event registry key disagrees with occurrence_id")
            if occurrence.created_at_ms < 0:
                raise ValueError("world-event save contains negative creation time")
            if occurrence.triggered_at_ms is not None and occurrence.triggered_at_ms < occurrence.created_at_ms:
                raise ValueError("world-event save trigger precedes creation")
            if occurrence.resolved_at_ms is not None:
                floor = occurrence.triggered_at_ms if occurrence.triggered_at_ms is not None else occurrence.created_at_ms
                if occurrence.resolved_at_ms < floor:
                    raise ValueError("world-event save contains reversed resolution time")
            if status is WorldEventStatus.PENDING and (
                occurrence.triggered_at_ms is not None or occurrence.resolved_at_ms is not None
            ):
                raise ValueError("pending world-event save cannot have trigger/resolution times")
            if status is WorldEventStatus.ACTIVE and (
                occurrence.triggered_at_ms is None or occurrence.resolved_at_ms is not None
            ):
                raise ValueError("active world-event save must have only a trigger time")
            if status in TERMINAL_WORLD_EVENT_STATUSES and occurrence.resolved_at_ms is None:
                raise ValueError("terminal world-event save must have a resolution time")
            occurrence.started_early = (
                occurrence.triggered_at_ms is not None
                and occurrence.expected_at_ms is not None
                and occurrence.triggered_at_ms < occurrence.expected_at_ms
            )
            occurrences[occurrence_id] = occurrence
        self.occurrences = occurrences
        self.history = list(payload.get("history", []))
''',
encoding="utf-8",
)


Path("src/sao_mcp/runtime/world_event_runtime.py").write_text(
'''from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any

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
''',
encoding="utf-8",
)


# Floor 4 Nocturne: turn Kysarah's interception into a planned, interruptible event.
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''from sao_mcp.rules.nightfolk import CIVIS_NOCTE, night_rank, tame_lower_level_monster\nfrom sao_mcp.rules.transport import (\n''',
    '''from sao_mcp.rules.nightfolk import CIVIS_NOCTE, night_rank, tame_lower_level_monster\nfrom sao_mcp.rules.world_events import WorldEventResult, WorldEventStatus\nfrom sao_mcp.rules.transport import (\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''KYSARAH_INTERCEPTION_TRANSFER_MS = 20 * 60_000\n''',
    '''KYSARAH_INTERCEPTION_TRANSFER_MS = 20 * 60_000\nKYSARAH_INTERCEPTION_EVENT_RULE_ID = "floor4.kysarah_interception"\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''        self.runtime = runtime\n        self.floor7_campaign = floor7_campaign\n\n    def _states(self) -> dict:\n''',
    '''        self.runtime = runtime\n        self.floor7_campaign = floor7_campaign\n        runtime.register_world_event_rule(\n            KYSARAH_INTERCEPTION_EVENT_RULE_ID,\n            self._discover_kysarah_interception_events,\n            self._resolve_kysarah_interception_event,\n        )\n        runtime.evaluate_world_events()\n\n    def _states(self) -> dict:\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''    def _state(self, instance_id: str) -> dict:\n        return self._states()[instance_id]\n\n    def _harin_state(self, harin_instance_id: str) -> dict:\n''',
    '''    def _state(self, instance_id: str) -> dict:\n        return self._states()[instance_id]\n\n    @staticmethod\n    def _kysarah_interception_event_id(instance_id: str) -> str:\n        return f"{KYSARAH_INTERCEPTION_EVENT_RULE_ID}:{instance_id}"\n\n    def _discover_kysarah_interception_events(self) -> list[str]:\n        ready: list[str] = []\n        for instance_id, state in self._states().items():\n            occurrence_id = self._kysarah_interception_event_id(instance_id)\n            occurrence = self.runtime.world_events.occurrences.get(occurrence_id)\n            if occurrence is None:\n                continue\n            if occurrence.status is WorldEventStatus.PENDING:\n                if state["stage"] != "parallel_nocturne_branches" or state["floor8_branch_stage"] != "departing_floor4":\n                    continue\n                if any(\n                    self.runtime.actors[actor_id].alive\n                    and self.runtime.actors[actor_id].location_id == "floor_4_labyrinth"\n                    for actor_id in state["floor8_actor_ids"]\n                ):\n                    ready.append(occurrence_id)\n                continue\n            if occurrence.status is not WorldEventStatus.ACTIVE:\n                continue\n            if state["floor8_branch_stage"] != "kysarah_interception":\n                continue\n            kysarah_id = state["kysarah_interception_actor_id"]\n            target_id = state["kysarah_interception_target_actor_id"]\n            if not kysarah_id or not target_id:\n                raise RuntimeError("active Kysarah interception is missing its participants")\n            kysarah = self.runtime.actors[kysarah_id]\n            target = self.runtime.actors[target_id]\n            if (\n                not kysarah.alive\n                and kysarah.metadata.get("defeat_resolved") is True\n            ) or target.metadata.get("permanent_death") is True:\n                ready.append(occurrence_id)\n        return ready\n\n    def _resolve_kysarah_interception_event(self, occurrence_id: str) -> WorldEventResult:\n        prefix = f"{KYSARAH_INTERCEPTION_EVENT_RULE_ID}:"\n        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):\n            raise RuntimeError(f"invalid Kysarah interception occurrence id: {occurrence_id}")\n        instance_id = occurrence_id[len(prefix):]\n        state = self._state(instance_id)\n        occurrence = self.runtime.world_events.occurrences[occurrence_id]\n        if occurrence.status is WorldEventStatus.PENDING:\n            candidates = [\n                actor_id\n                for actor_id in state["floor8_actor_ids"]\n                if self.runtime.actors[actor_id].alive\n                and self.runtime.actors[actor_id].location_id == "floor_4_labyrinth"\n            ]\n            if not candidates:\n                raise RuntimeError("Kysarah interception was discovered without a live responder in the Labyrinth")\n            bag_owner, _ = self._validate_inherited_keys(state)\n            if bag_owner.metadata.get("npc_definition_id") != KYSARAH_ID or not bag_owner.alive:\n                state["kysarah_interception_outcome"] = "skipped_kysarah_unavailable"\n                state["floor8_branch_stage"] = "kysarah_interception_skipped"\n                return WorldEventResult(\n                    WorldEventStatus.SKIPPED,\n                    {\n                        "instance_id": instance_id,\n                        "reason": "kysarah_unavailable_or_no_longer_holds_four_key_bag",\n                    },\n                )\n            target_id = candidates[0]\n            result = self._start_kysarah_interception(instance_id, target_id)\n            return WorldEventResult(\n                WorldEventStatus.ACTIVE,\n                {\n                    "instance_id": instance_id,\n                    "target_actor_id": target_id,\n                    "kysarah_actor_id": result["kysarah_interception_actor_id"],\n                    "encounter_id": result["kysarah_interception_encounter_id"],\n                },\n            )\n\n        if occurrence.status is not WorldEventStatus.ACTIVE:\n            raise RuntimeError("Kysarah event resolver can only advance pending or active occurrences")\n        kysarah = self.runtime.actors[state["kysarah_interception_actor_id"]]\n        target = self.runtime.actors[state["kysarah_interception_target_actor_id"]]\n        if not kysarah.alive and kysarah.metadata.get("defeat_resolved") is True:\n            state["kysarah_interception_outcome"] = "kysarah_defeated_interception_failed"\n            return WorldEventResult(\n                WorldEventStatus.FAILED,\n                {\n                    "instance_id": instance_id,\n                    "reason": "kysarah_defeated_by_responder",\n                    "target_actor_id": target.actor_id,\n                },\n            )\n        if target.metadata.get("permanent_death") is True:\n            encounter = self.runtime.encounters[state["kysarah_interception_encounter_id"]]\n            encounter.threat.clear()\n            success_route = exit_encounter_via_travel(\n                self.runtime,\n                encounter.encounter_id,\n                [kysarah.actor_id],\n                KYSARAH_TRANSFER_ROOM,\n            )\n            state["kysarah_interception_outcome"] = "kysarah_interception_succeeded"\n            state["kysarah_success_route"] = group_travel_record(success_route)\n            state["floor8_branch_stage"] = "kysarah_interception_player_defeated"\n            return WorldEventResult(\n                WorldEventStatus.RESOLVED,\n                {\n                    "instance_id": instance_id,\n                    "outcome": "interception_succeeded_after_responder_permanent_death",\n                    "target_actor_id": target.actor_id,\n                },\n            )\n        raise RuntimeError("active Kysarah event was rediscovered without a terminal condition")\n\n    def _harin_state(self, harin_instance_id: str) -> dict:\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''            "kysarah_interception_actor_id": None,\n            "kysarah_interception_encounter_id": None,\n            "kysarah_interception_outcome": None,\n            "kysarah_interception_transport": None,\n''',
    '''            "kysarah_interception_event_id": None,\n            "kysarah_interception_actor_id": None,\n            "kysarah_interception_target_actor_id": None,\n            "kysarah_interception_encounter_id": None,\n            "kysarah_interception_outcome": None,\n            "kysarah_interception_transport": None,\n            "kysarah_success_route": None,\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''        state["response_split_assigned_at_ms"] = self.runtime.world.now_ms\n        state["stage"] = "parallel_nocturne_branches"\n        return self.status(instance_id)\n''',
    '''        state["response_split_assigned_at_ms"] = self.runtime.world.now_ms\n        state["stage"] = "parallel_nocturne_branches"\n        occurrence_id = self._kysarah_interception_event_id(instance_id)\n        state["kysarah_interception_event_id"] = occurrence_id\n        self.runtime.plan_world_event(\n            occurrence_id,\n            KYSARAH_INTERCEPTION_EVENT_RULE_ID,\n            payload={"instance_id": instance_id, "floor8_actor_ids": list(floor8_ids)},\n        )\n        if floor8_ids:\n            self.runtime.evaluate_world_events()\n        else:\n            self.runtime.skip_world_event(\n                occurrence_id,\n                payload={"reason": "no_floor8_responder"},\n            )\n        return self.status(instance_id)\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''    def trigger_kysarah_interception(self, instance_id: str, actor_id: str) -> dict:\n''',
    '''    def _start_kysarah_interception(self, instance_id: str, actor_id: str) -> dict:\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''        state["kysarah_interception_transport"] = authorized_transport_record(transfer)\n        state["kysarah_interception_actor_id"] = bag_owner.actor_id\n        state["kysarah_interception_encounter_id"] = encounter.encounter_id\n''',
    '''        state["kysarah_interception_transport"] = authorized_transport_record(transfer)\n        state["kysarah_interception_actor_id"] = bag_owner.actor_id\n        state["kysarah_interception_target_actor_id"] = actor_id\n        state["kysarah_interception_encounter_id"] = encounter.encounter_id\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''        state["kysarah_requested_item_template_id"] = ICHTHYOID_TUBER_ID\n        state["floor8_branch_stage"] = "kysarah_truce_resolved"\n        return self.status(instance_id)\n''',
    '''        state["kysarah_requested_item_template_id"] = ICHTHYOID_TUBER_ID\n        state["floor8_branch_stage"] = "kysarah_truce_resolved"\n        self.runtime.interrupt_world_event(\n            state["kysarah_interception_event_id"],\n            payload={\n                "reason": "falhari_truce",\n                "truce_actor_id": actor_id,\n                "requested_item_template_id": ICHTHYOID_TUBER_ID,\n            },\n        )\n        return self.status(instance_id)\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''        kysarah_state = None\n        if state["kysarah_interception_actor_id"] is not None:\n''',
    '''        event_id = state.get("kysarah_interception_event_id")\n        event_state = (\n            self.runtime.world_event_state(event_id)\n            if event_id is not None and event_id in self.runtime.world_events.occurrences\n            else None\n        )\n        kysarah_state = None\n        if state["kysarah_interception_actor_id"] is not None:\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''            "kysarah": kysarah_state,\n            "five_key_assets_intact": True,\n''',
    '''            "kysarah": kysarah_state,\n            "kysarah_interception_event": event_state,\n            "five_key_assets_intact": True,\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor4_nocturne.py",
    '''    return Floor4NocturneScenario(runtime, floor7_campaign)\n''',
    '''    service = runtime.install_world_event_service(\n        "floor4.nocturne", lambda: Floor4NocturneScenario(runtime, floor7_campaign)\n    )\n    if not isinstance(service, Floor4NocturneScenario):\n        raise RuntimeError("floor4.nocturne service registry contains the wrong service type")\n    if service.floor7_campaign is not floor7_campaign:\n        raise RuntimeError("floor4.nocturne service is already bound to a different Floor 7 campaign service")\n    return service\n''',
)

# The interception is now world-driven; only player decisions remain MCP actions.
replace_once(
    "src/sao_mcp/server_floor4_nocturne.py",
    '''    @mcp.tool()\n    def trigger_progressive9_kysarah_interception(instance_id: str, actor_id: str) -> str:\n        """When an assigned Floor 8 responder physically enters the Floor 4 Labyrinth, reuse the real Kysarah four-key-bag holder and start an ordinary encounter."""\n        return _json(nocturne.trigger_kysarah_interception(instance_id, actor_id))\n\n''',
    "",
)

# Core lifecycle tests: early activation, interruption, skip, and persistence of active state.
replace_once(
    "tests/test_world_event_runtime.py",
    '''from sao_mcp.runtime.housing_runtime import HousingAincradRuntime\nfrom sao_mcp.runtime.persistence import export_runtime, import_runtime\n''',
    '''import pytest\n\nfrom sao_mcp.rules.world_events import WorldEventResult, WorldEventStatus\nfrom sao_mcp.runtime.housing_runtime import HousingAincradRuntime\nfrom sao_mcp.runtime.persistence import export_runtime, import_runtime\n''',
)
with Path("tests/test_world_event_runtime.py").open("a", encoding="utf-8") as handle:
    handle.write(
'''\n\ndef test_planned_event_can_start_early_then_be_interrupted_and_persist():\n    runtime = HousingAincradRuntime(seed=803)\n    runtime.register_world_event_rule(\n        "test.interruptible",\n        lambda: ["test:interruptible:1"],\n        lambda occurrence_id: WorldEventResult(\n            WorldEventStatus.ACTIVE,\n            {"occurrence_id": occurrence_id, "phase": "started"},\n        ),\n    )\n    runtime.plan_world_event(\n        "test:interruptible:1",\n        "test.interruptible",\n        expected_at_ms=1_000,\n        payload={"seed": "planned"},\n    )\n\n    transitioned = runtime.evaluate_world_events()\n    assert [row.status for row in transitioned] == [WorldEventStatus.ACTIVE]\n    active = runtime.world_event_state("test:interruptible:1")\n    assert active["status"] == "active"\n    assert active["triggered_at_ms"] == 0\n    assert active["expected_at_ms"] == 1_000\n    assert active["started_early"] is True\n    assert active["payload"] == {\n        "seed": "planned",\n        "occurrence_id": "test:interruptible:1",\n        "phase": "started",\n    }\n\n    restored = import_runtime(export_runtime(runtime))\n    persisted = restored.world_event_state("test:interruptible:1")\n    assert persisted["status"] == "active"\n    assert persisted["started_early"] is True\n    restored.interrupt_world_event(\n        "test:interruptible:1",\n        payload={"reason": "player_changed_the_situation"},\n    )\n    interrupted = restored.world_event_state("test:interruptible:1")\n    assert interrupted["status"] == "interrupted"\n    assert interrupted["resolved_at_ms"] == restored.world.now_ms\n    assert interrupted["payload"]["reason"] == "player_changed_the_situation"\n    assert [row["status"] for row in restored.world_event_history("test.interruptible")] == [\n        "pending",\n        "active",\n        "interrupted",\n    ]\n\n    with pytest.raises(ValueError, match="illegal world-event transition"):\n        restored.resolve_world_event("test:interruptible:1")\n\n\ndef test_planned_event_can_be_skipped_before_it_starts():\n    runtime = HousingAincradRuntime(seed=804)\n    runtime.register_world_event_rule("test.skip", lambda: [], lambda occurrence_id: {})\n    runtime.plan_world_event("test:skip:1", "test.skip")\n    runtime.skip_world_event("test:skip:1", payload={"reason": "precondition_removed"})\n    skipped = runtime.world_event_state("test:skip:1")\n    assert skipped["status"] == "skipped"\n    assert skipped["triggered_at_ms"] is None\n    assert skipped["resolved_at_ms"] == runtime.world.now_ms\n''')

# Authority gate: Kysarah interception is no longer a manual transition/tool.
replace_once(
    "tests/test_world_event_authority.py",
    '''    ("floor4_nocturne.py", "trigger_kysarah_interception"),\n''',
    "",
)
replace_once(
    "tests/test_world_event_authority.py",
    '''        "finish_floor22_witch_quest_return",\n''',
    '''        "finish_floor22_witch_quest_return",\n        "trigger_progressive9_kysarah_interception",\n''',
)

# Progressive 9 live tests now observe automatic activation and real terminal outcomes.
replace_once(
    "tests/test_floor8_emergency.py",
    '''from sao_mcp.scenarios.floor4_nocturne import install_floor4_nocturne_scenario\n''',
    '''from sao_mcp.scenarios.floor4_nocturne import (\n    KYSARAH_INTERCEPTION_EVENT_RULE_ID,\n    install_floor4_nocturne_scenario,\n)\n''',
)
replace_once(
    "tests/test_floor8_emergency.py",
    '''    _move_to_floor4_labyrinth(runtime, a)\n    intercepted = nocturne.trigger_kysarah_interception(instance_id, a.actor_id)\n    encounter_id = intercepted["kysarah_interception_encounter_id"]\n''',
    '''    event_id = f"{KYSARAH_INTERCEPTION_EVENT_RULE_ID}:{instance_id}"\n    assert runtime.world_event_state(event_id)["status"] == "pending"\n    _move_to_floor4_labyrinth(runtime, a)\n    intercepted = nocturne.status(instance_id)\n    assert runtime.world_event_state(event_id)["status"] == "active"\n    encounter_id = intercepted["kysarah_interception_encounter_id"]\n''',
)
replace_once(
    "tests/test_floor8_emergency.py",
    '''    truce = nocturne.resolve_kysarah_falhari_truce(instance_id, a.actor_id)\n    assert truce["kysarah_interception_outcome"] == "falhari_truce"\n''',
    '''    truce = nocturne.resolve_kysarah_falhari_truce(instance_id, a.actor_id)\n    assert truce["kysarah_interception_outcome"] == "falhari_truce"\n    assert runtime.world_event_state(event_id)["status"] == "interrupted"\n    assert runtime.world_event_state(event_id)["payload"]["reason"] == "falhari_truce"\n''',
)
replace_once(
    "tests/test_floor8_emergency.py",
    '''    assert restored_nocturne.status(instance_id)["kysarah_interception_outcome"] == "falhari_truce"\n''',
    '''    assert restored_nocturne.status(instance_id)["kysarah_interception_outcome"] == "falhari_truce"\n    assert restored.world_event_state(event_id)["status"] == "interrupted"\n''',
)
replace_once(
    "tests/test_floor8_emergency.py",
    '''    state = nocturne._state(instance_id)\n    state["stage"] = "parallel_nocturne_branches"\n    state["floor8_actor_ids"] = [a.actor_id]\n    state["hideout_actor_ids"] = [b.actor_id]\n    state["floor8_branch_stage"] = "departing_floor4"\n    state["hideout_branch_stage"] = "on_lake"\n\n    _move_to_floor4_labyrinth(runtime, a)\n    intercepted = nocturne.trigger_kysarah_interception(instance_id, a.actor_id)\n    encounter = runtime.encounters[intercepted["kysarah_interception_encounter_id"]]\n''',
    '''    state = nocturne._state(instance_id)\n    state["stage"] = "floor8_emergency_received"\n    nocturne.assign_floor8_emergency_split(instance_id, [a.actor_id], [b.actor_id])\n    event_id = f"{KYSARAH_INTERCEPTION_EVENT_RULE_ID}:{instance_id}"\n\n    _move_to_floor4_labyrinth(runtime, a)\n    intercepted = nocturne.status(instance_id)\n    assert runtime.world_event_state(event_id)["status"] == "active"\n    encounter = runtime.encounters[intercepted["kysarah_interception_encounter_id"]]\n''',
)
replace_once(
    "tests/test_floor8_emergency.py",
    '''    runtime._resolve_defeat(encounter, kysarah, a.actor_id)\n\n    recovered = nocturne.claim_four_key_bag_after_kysarah_defeat(instance_id, a.actor_id)\n''',
    '''    runtime._resolve_defeat(encounter, kysarah, a.actor_id)\n    failed = runtime.world_event_state(event_id)\n    assert failed["status"] == "failed"\n    assert failed["payload"]["reason"] == "kysarah_defeated_by_responder"\n\n    recovered = nocturne.claim_four_key_bag_after_kysarah_defeat(instance_id, a.actor_id)\n''',
)
with Path("tests/test_floor8_emergency.py").open("a", encoding="utf-8") as handle:
    handle.write(
'''\n\ndef test_kysarah_interception_is_skipped_when_no_floor8_responder_exists():\n    runtime, campaign, nocturne, instance_id, a, b, kizmel, kysarah, bag, fallen, ruby = _setup_branch_state()\n    state = nocturne._state(instance_id)\n    state["stage"] = "floor8_emergency_received"\n\n    split = nocturne.assign_floor8_emergency_split(instance_id, [], [a.actor_id, b.actor_id])\n    event_id = f"{KYSARAH_INTERCEPTION_EVENT_RULE_ID}:{instance_id}"\n    skipped = runtime.world_event_state(event_id)\n    assert split["floor8_branch_stage"] == "no_responder"\n    assert skipped["status"] == "skipped"\n    assert skipped["triggered_at_ms"] is None\n    assert skipped["payload"]["reason"] == "no_floor8_responder"\n''')
