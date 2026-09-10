from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {text.count(old)}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


Path("src/sao_mcp/rules/world_events.py").write_text(
    '''from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class WorldEventStatus(StrEnum):
    RESOLVED = "resolved"


@dataclass(slots=True)
class WorldEventOccurrence:
    occurrence_id: str
    rule_id: str
    status: WorldEventStatus
    triggered_at_ms: int
    resolved_at_ms: int
    payload: dict[str, Any] = field(default_factory=dict)


class WorldEventLedger:
    """Persistent outcomes for world events; executable rule callbacks stay runtime-only."""

    def __init__(self) -> None:
        self.occurrences: dict[str, WorldEventOccurrence] = {}
        self.history: list[dict[str, Any]] = []

    def record_resolved(
        self,
        *,
        occurrence_id: str,
        rule_id: str,
        triggered_at_ms: int,
        resolved_at_ms: int,
        payload: dict[str, Any],
    ) -> WorldEventOccurrence:
        if not occurrence_id or not rule_id:
            raise ValueError("world-event occurrence and rule ids are required")
        if occurrence_id in self.occurrences:
            raise ValueError(f"world-event occurrence already exists: {occurrence_id}")
        if triggered_at_ms < 0 or resolved_at_ms < triggered_at_ms:
            raise ValueError("world-event resolution time cannot precede its trigger")
        if not isinstance(payload, dict):
            raise TypeError("world-event payload must be a dict")
        occurrence = WorldEventOccurrence(
            occurrence_id=occurrence_id,
            rule_id=rule_id,
            status=WorldEventStatus.RESOLVED,
            triggered_at_ms=triggered_at_ms,
            resolved_at_ms=resolved_at_ms,
            payload=dict(payload),
        )
        self.occurrences[occurrence_id] = occurrence
        self.history.append(asdict(occurrence))
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
            occurrence = WorldEventOccurrence(
                occurrence_id=row["occurrence_id"],
                rule_id=row["rule_id"],
                status=WorldEventStatus(row["status"]),
                triggered_at_ms=int(row["triggered_at_ms"]),
                resolved_at_ms=int(row["resolved_at_ms"]),
                payload=dict(row.get("payload", {})),
            )
            if occurrence.occurrence_id != occurrence_id:
                raise ValueError("world-event registry key disagrees with occurrence_id")
            if occurrence.resolved_at_ms < occurrence.triggered_at_ms:
                raise ValueError("world-event save contains reversed trigger/resolution time")
            occurrences[occurrence_id] = occurrence
        history = list(payload.get("history", []))
        self.occurrences = occurrences
        self.history = history
''',
    encoding="utf-8",
)

Path("src/sao_mcp/runtime/world_event_runtime.py").write_text(
    '''from __future__ import annotations

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
        self.world_events = WorldEventLedger()
        self._evaluating_world_events = False

    def register_world_advance_hook(self, hook: WorldAdvanceHook) -> None:
        self.world_advance_hooks.append(hook)

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

replace_once(
    "src/sao_mcp/runtime/persistence.py",
    '''    population_dump = getattr(runtime, "dump_population_state", None)\n    payload = {\n''',
    '''    population_dump = getattr(runtime, "dump_population_state", None)\n    world_event_dump = getattr(runtime, "dump_world_event_state", None)\n    payload = {\n''',
)
replace_once(
    "src/sao_mcp/runtime/persistence.py",
    '''        "legal_state": runtime.legal.dump_state(),\n        "economy_state": economy.dump_state() if economy is not None else {},\n''',
    '''        "legal_state": runtime.legal.dump_state(),\n        "world_event_state": world_event_dump() if world_event_dump is not None else {},\n        "economy_state": economy.dump_state() if economy is not None else {},\n''',
)
replace_once(
    "src/sao_mcp/runtime/persistence.py",
    '''    runtime.npcs.load_state(payload.get("npc_state", {}))\n    runtime.legal.load_state(payload.get("legal_state", {}))\n\n    population_load = getattr(runtime, "load_population_state", None)\n''',
    '''    runtime.npcs.load_state(payload.get("npc_state", {}))\n    runtime.legal.load_state(payload.get("legal_state", {}))\n    world_event_load = getattr(runtime, "load_world_event_state", None)\n    if world_event_load is not None:\n        world_event_load(payload.get("world_event_state", {}))\n\n    population_load = getattr(runtime, "load_population_state", None)\n''',
)

replace_once(
    "src/sao_mcp/server_gm.py",
    '''        return _json({"knower_id": knower_id, "events": rows})\n''',
    '''        return _json({"knower_id": knower_id, "events": rows})\n\n    @mcp.tool()\n    def get_world_event_state(occurrence_id: str | None = None) -> str:\n        """Inspect registered event rules and already-resolved persistent world-event occurrences."""\n        return _json(gm_turn_executor.runtime.world_event_state(occurrence_id))\n\n    @mcp.tool()\n    def get_world_event_history(rule_id: str | None = None) -> str:\n        """Inspect resolved world-event history, optionally filtered by one rule id."""\n        return _json({"events": gm_turn_executor.runtime.world_event_history(rule_id)})\n''',
)

Path("tests/test_world_event_runtime.py").write_text(
    '''from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def test_world_event_rules_resolve_once_and_chain_in_one_evaluation():
    runtime = HousingAincradRuntime(seed=801)
    flags = {"first": False, "second": False}

    def discover_first():
        return ["test:first"] if flags["first"] else []

    def resolve_first(occurrence_id: str):
        assert occurrence_id == "test:first"
        flags["second"] = True
        return {"kind": "first"}

    def discover_second():
        return ["test:second"] if flags["second"] else []

    runtime.register_world_event_rule("test.first", discover_first, resolve_first)
    runtime.register_world_event_rule(
        "test.second",
        discover_second,
        lambda occurrence_id: {"kind": "second", "occurrence_id": occurrence_id},
    )

    runtime.advance_world(10)
    assert runtime.world_event_history() == []

    flags["first"] = True
    resolved = runtime.evaluate_world_events()
    assert [row.occurrence_id for row in resolved] == ["test:first", "test:second"]
    assert [row.rule_id for row in resolved] == ["test.first", "test.second"]
    assert len(runtime.world_event_history()) == 2

    runtime.advance_world(100)
    assert len(runtime.world_event_history()) == 2


def test_world_event_occurrences_persist_but_executable_rules_do_not():
    runtime = HousingAincradRuntime(seed=802)
    runtime.register_world_event_rule(
        "test.persist",
        lambda: ["test:persist:1"],
        lambda occurrence_id: {"occurrence_id": occurrence_id, "value": 7},
    )
    runtime.evaluate_world_events()

    restored = import_runtime(export_runtime(runtime))
    persisted = restored.world_event_state("test:persist:1")
    assert persisted["rule_id"] == "test.persist"
    assert persisted["status"] == "resolved"
    assert persisted["payload"]["value"] == 7
    assert restored.world_event_state()["registered_rule_ids"] == []

    fired = []
    restored.register_world_event_rule(
        "test.persist",
        lambda: ["test:persist:1"],
        lambda occurrence_id: fired.append(occurrence_id) or {},
    )
    restored.evaluate_world_events()
    assert fired == []
    assert len(restored.world_event_history("test.persist")) == 1
''',
    encoding="utf-8",
)
