from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from sao_mcp.domain.models import CombatEvent, CombatantState, EncounterState, WorldState
from sao_mcp.rules.spatial import default_formation
from sao_mcp.runtime.engine import GameRuntime


SAVE_SCHEMA_V1 = "sao.aincrad.save.v1"
SAVE_SCHEMA = "sao.aincrad.save.v2"
ACTORS_ADAPTER = TypeAdapter(dict[str, CombatantState])
WORLD_ADAPTER = TypeAdapter(WorldState)
EVENTS_ADAPTER = TypeAdapter(list[CombatEvent])


def _tuplify(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tuplify(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuplify(item) for key, item in value.items()}
    return value


def _upgrade_payload(payload: dict[str, Any]) -> dict[str, Any]:
    schema = payload.get("schema")
    if schema == SAVE_SCHEMA:
        return payload
    if schema == SAVE_SCHEMA_V1:
        if payload.get("encounters"):
            raise ValueError(
                "sao.aincrad.save.v1 encounters cannot be migrated exactly because v1 did not record encounter world-time anchors"
            )
        upgraded = dict(payload)
        upgraded["schema"] = SAVE_SCHEMA
        return upgraded
    raise ValueError(f"unsupported save schema: {schema!r}")


def export_runtime(runtime: GameRuntime) -> str:
    encounters: dict[str, dict[str, Any]] = {}
    for encounter_id, encounter in runtime.encounters.items():
        absolute_encounter_ms = runtime.encounter_world_time_ms(encounter_id)
        if runtime.world.now_ms < absolute_encounter_ms:
            raise RuntimeError(
                f"world clock precedes encounter {encounter_id}: {runtime.world.now_ms} < {absolute_encounter_ms}"
            )
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
            "positions": {
                actor_id: [float(position[0]), float(position[1])]
                for actor_id, position in encounter.positions.items()
            },
            "arena_radius_m": encounter.arena_radius_m,
        }

    economy = getattr(runtime, "economy", None)
    timeline_dump = getattr(runtime, "dump_timeline_state", None)
    duel_dump = getattr(runtime, "dump_duel_state", None)
    relationship_dump = getattr(runtime, "dump_relationship_state", None)
    family_dump = getattr(runtime, "dump_family_state", None)
    communications_dump = getattr(runtime, "dump_communications_state", None)
    knowledge_dump = getattr(runtime, "dump_knowledge_state", None)
    npc_autonomy_dump = getattr(runtime, "dump_npc_autonomy_state", None)
    housing_dump = getattr(runtime, "dump_housing_state", None)
    payload = {
        "schema": SAVE_SCHEMA,
        "world": WORLD_ADAPTER.dump_python(runtime.world, mode="json"),
        "actors": ACTORS_ADAPTER.dump_python(runtime.actors, mode="json"),
        "encounters": encounters,
        "rng_state": runtime.rng.getstate(),
        "quest_state": runtime.quests.dump_state(),
        "npc_state": runtime.npcs.dump_state(),
        "economy_state": economy.dump_state() if economy is not None else {},
        "timeline_state": timeline_dump() if timeline_dump is not None else {},
        "duel_state": duel_dump() if duel_dump is not None else {},
        "relationship_state": relationship_dump() if relationship_dump is not None else {},
        "family_state": family_dump() if family_dump is not None else {},
        "communications_state": communications_dump() if communications_dump is not None else {},
        "knowledge_state": knowledge_dump() if knowledge_dump is not None else {},
        "npc_autonomy_state": npc_autonomy_dump() if npc_autonomy_dump is not None else {},
        "housing_state": housing_dump() if housing_dump is not None else {},
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def import_runtime(payload_json: str, *, into: GameRuntime | None = None) -> GameRuntime:
    payload = _upgrade_payload(json.loads(payload_json))

    if into is None:
        from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
        from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario

        runtime: GameRuntime = HousingAincradRuntime()
        install_floor22_witch_scenario(runtime)
    else:
        runtime = into
    runtime.world = WORLD_ADAPTER.validate_python(payload["world"])

    from sao_mcp.rules.world import restore_dynamic_world_connections

    restore_dynamic_world_connections(runtime.world, runtime.world_map)
    runtime.actors = ACTORS_ADAPTER.validate_python(payload["actors"])
    runtime.encounters = {}
    for encounter_id, value in payload.get("encounters", {}).items():
        participant_ids = value["participant_ids"]
        missing = [actor_id for actor_id in participant_ids if actor_id not in runtime.actors]
        if missing:
            raise ValueError(f"save references missing actors: {missing}")
        positions = {
            actor_id: (float(position[0]), float(position[1]))
            for actor_id, position in value.get("positions", {}).items()
            if actor_id in participant_ids and len(position) == 2
        }
        encounter = EncounterState(
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
            positions=positions,
            arena_radius_m=float(value.get("arena_radius_m", 30.0)),
        )
        default_formation(encounter)
        runtime.encounters[encounter_id] = encounter
        absolute_encounter_ms = runtime.encounter_world_time_ms(encounter_id)
        if runtime.world.now_ms < absolute_encounter_ms:
            raise ValueError(
                f"save world clock precedes encounter {encounter_id}: {runtime.world.now_ms} < {absolute_encounter_ms}"
            )

    if "rng_state" in payload:
        runtime.rng.setstate(_tuplify(payload["rng_state"]))
    runtime.quests.load_state(payload.get("quest_state", {}))
    runtime.npcs.load_state(payload.get("npc_state", {}))

    knowledge_load = getattr(runtime, "load_knowledge_state", None)
    if knowledge_load is not None:
        knowledge_load(payload.get("knowledge_state", {}))
    autonomy_load = getattr(runtime, "load_npc_autonomy_state", None)
    if autonomy_load is not None:
        autonomy_load(payload.get("npc_autonomy_state", {}))

    from sao_mcp.runtime.property_economy import make_runtime_economy

    economy = make_runtime_economy(runtime)
    runtime.economy = economy
    economy.load_state(payload.get("economy_state", {}))

    timeline_load = getattr(runtime, "load_timeline_state", None)
    if timeline_load is not None:
        timeline_load(payload.get("timeline_state", {}))
    duel_load = getattr(runtime, "load_duel_state", None)
    if duel_load is not None:
        duel_load(payload.get("duel_state", {}))
    relationship_load = getattr(runtime, "load_relationship_state", None)
    if relationship_load is not None:
        relationship_load(payload.get("relationship_state", {}))
    family_load = getattr(runtime, "load_family_state", None)
    if family_load is not None:
        family_load(payload.get("family_state", {}))
    communications_load = getattr(runtime, "load_communications_state", None)
    if communications_load is not None:
        communications_load(payload.get("communications_state", {}))
    housing_load = getattr(runtime, "load_housing_state", None)
    if housing_load is not None:
        housing_load(payload.get("housing_state", {}))
    if hasattr(runtime, "relationships"):
        from sao_mcp.runtime.community_hooks import attach_community_economy

        attach_community_economy(runtime, economy)
    return runtime
