from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from sao_mcp.domain.models import CombatEvent, CombatantState, EncounterState, WorldState
from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.runtime.engine import GameRuntime


SAVE_SCHEMA = "sao.aincrad.save.v1"
ACTORS_ADAPTER = TypeAdapter(dict[str, CombatantState])
WORLD_ADAPTER = TypeAdapter(WorldState)
EVENTS_ADAPTER = TypeAdapter(list[CombatEvent])


def _tuplify(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tuplify(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuplify(item) for key, item in value.items()}
    return value


def export_runtime(runtime: GameRuntime) -> str:
    encounters: dict[str, dict[str, Any]] = {}
    for encounter_id, encounter in runtime.encounters.items():
        encounters[encounter_id] = {
            "encounter_id": encounter.encounter_id,
            "participant_ids": list(encounter.participants),
            "zone_id": encounter.zone_id,
            "time_ms": encounter.time_ms,
            "safe_zone": encounter.safe_zone,
            "anti_crystal": encounter.anti_crystal,
            "threat": encounter.threat,
            "last_attacker_by_target": encounter.last_attacker_by_target,
            "last_attack_time_by_target": encounter.last_attack_time_by_target,
            "events": EVENTS_ADAPTER.dump_python(encounter.events, mode="json"),
        }

    economy = getattr(runtime, "economy", None)
    payload = {
        "schema": SAVE_SCHEMA,
        "world": WORLD_ADAPTER.dump_python(runtime.world, mode="json"),
        "actors": ACTORS_ADAPTER.dump_python(runtime.actors, mode="json"),
        "encounters": encounters,
        "rng_state": runtime.rng.getstate(),
        "quest_state": runtime.quests.dump_state(),
        "npc_state": runtime.npcs.dump_state(),
        "economy_state": economy.dump_state() if economy is not None else {},
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def import_runtime(payload_json: str, *, into: GameRuntime | None = None) -> GameRuntime:
    payload = json.loads(payload_json)
    if payload.get("schema") != SAVE_SCHEMA:
        raise ValueError(f"unsupported save schema: {payload.get('schema')!r}")

    if into is None:
        # Local import avoids an import cycle: AincradRuntime subclasses GameRuntime and is the
        # feature-complete default for saves, while callers can still supply a custom GameRuntime.
        from sao_mcp.runtime.aincrad_runtime import AincradRuntime

        runtime: GameRuntime = AincradRuntime()
    else:
        runtime = into
    runtime.world = WORLD_ADAPTER.validate_python(payload["world"])
    runtime.actors = ACTORS_ADAPTER.validate_python(payload["actors"])
    runtime.encounters = {}
    for encounter_id, value in payload.get("encounters", {}).items():
        participant_ids = value["participant_ids"]
        missing = [actor_id for actor_id in participant_ids if actor_id not in runtime.actors]
        if missing:
            raise ValueError(f"save references missing actors: {missing}")
        runtime.encounters[encounter_id] = EncounterState(
            encounter_id=value["encounter_id"],
            participants={actor_id: runtime.actors[actor_id] for actor_id in participant_ids},
            zone_id=value["zone_id"],
            time_ms=int(value.get("time_ms", 0)),
            safe_zone=bool(value.get("safe_zone", False)),
            anti_crystal=bool(value.get("anti_crystal", False)),
            threat={
                target_id: {actor_id: float(threat) for actor_id, threat in table.items()}
                for target_id, table in value.get("threat", {}).items()
            },
            last_attacker_by_target=dict(value.get("last_attacker_by_target", {})),
            last_attack_time_by_target={
                target_id: int(time_ms)
                for target_id, time_ms in value.get("last_attack_time_by_target", {}).items()
            },
            events=EVENTS_ADAPTER.validate_python(value.get("events", [])),
        )

    if "rng_state" in payload:
        runtime.rng.setstate(_tuplify(payload["rng_state"]))
    runtime.quests.load_state(payload.get("quest_state", {}))
    runtime.npcs.load_state(payload.get("npc_state", {}))
    economy = getattr(runtime, "economy", None)
    if economy is None:
        economy = EconomyRuntime()
        runtime.economy = economy
    economy.load_state(payload.get("economy_state", {}))
    return runtime
