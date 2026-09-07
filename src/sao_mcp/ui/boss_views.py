from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.corpus.bosses import CORE_BOSS_ACTIONS
from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.spatial import actor_collision_radius_m, distance_between_points


def boss_raid_view(runtime, encounter_id: str, boss_id: str | None = None) -> dict[str, Any]:
    encounter = runtime.encounters[encounter_id]
    if boss_id is None:
        bosses = [
            actor
            for actor in encounter.participants.values()
            if actor.kind is EntityKind.BOSS
        ]
        if not bosses:
            raise ValueError("encounter has no boss")
        boss = bosses[0]
    else:
        boss = encounter.participants[boss_id]
    state = runtime.boss_bar_state(boss)
    definition = runtime.boss_definition(boss)
    phase = runtime.boss_phase(boss)

    pending = boss.metadata.get("pending_boss_action")
    pending_view = None
    if pending:
        action = CORE_BOSS_ACTIONS[str(pending["action_id"])]
        pending_view = {
            "actionId": action.action_id,
            "name": action.name,
            "targetIds": list(pending["target_ids"]),
            "initialTargetIds": list(pending.get("initial_target_ids", pending["target_ids"])),
            "startedAtMs": int(pending["started_at_ms"]),
            "executeAtMs": int(pending["execute_at_ms"]),
            "remainingMs": max(0, int(pending["execute_at_ms"]) - encounter.time_ms),
            "telegraphMs": action.telegraph_ms,
            "tags": list(action.tags),
            "spatialMode": pending.get("spatial_mode", "locked_targets"),
            "areaCenter": pending.get("area_center"),
            "areaRadiusM": pending.get("area_radius_m"),
        }

    def in_current_danger(actor) -> bool:
        if not pending or actor.actor_id not in encounter.positions:
            return False
        if pending.get("spatial_mode") == "locked_radius":
            center = pending.get("area_center")
            radius = pending.get("area_radius_m")
            if not center or radius is None:
                return False
            point = encounter.positions[actor.actor_id]
            return (
                distance_between_points((float(center[0]), float(center[1])), point)
                - actor_collision_radius_m(actor)
                <= float(radius)
            )
        return actor.actor_id in pending.get("target_ids", ())

    threat = encounter.threat.get(boss.actor_id, {})
    players = []
    for actor in encounter.participants.values():
        if actor.kind is not EntityKind.PLAYER:
            continue
        position = encounter.positions.get(actor.actor_id)
        players.append(
            {
                "id": actor.actor_id,
                "name": actor.name,
                "level": actor.level,
                "hp": actor.hp,
                "maxHp": actor.max_hp,
                "hpRatio": actor.hp / actor.max_hp if actor.max_hp else 0.0,
                "alive": actor.alive,
                "partyId": actor.party_id,
                "threat": round(threat.get(actor.actor_id, 0.0), 3),
                "recoveryRemainingMs": max(0, actor.recovery_until_ms - encounter.time_ms),
                "targeted": bool(pending and actor.actor_id in pending.get("initial_target_ids", pending["target_ids"])),
                "inDangerZone": in_current_danger(actor),
                "position": list(position) if position else None,
                "collisionRadiusM": actor_collision_radius_m(actor),
            }
        )
    players.sort(key=lambda row: row["threat"], reverse=True)

    minions = []
    for actor in encounter.participants.values():
        if actor.metadata.get("boss_parent_id") != boss.actor_id:
            continue
        position = encounter.positions.get(actor.actor_id)
        minions.append(
            {
                "id": actor.actor_id,
                "name": actor.name,
                "hp": actor.hp,
                "maxHp": actor.max_hp,
                "hpRatio": actor.hp / actor.max_hp if actor.max_hp else 0.0,
                "alive": actor.alive,
                "templateId": actor.metadata.get("boss_minion_template_id"),
                "spawnOrdinal": actor.metadata.get("boss_spawn_ordinal"),
                "position": list(position) if position else None,
                "collisionRadiusM": actor_collision_radius_m(actor),
            }
        )

    boss_position = encounter.positions.get(boss.actor_id)
    spatial = {
        "arenaRadiusM": encounter.arena_radius_m,
        "boss": {
            "id": boss.actor_id,
            "position": list(boss_position) if boss_position else None,
            "collisionRadiusM": actor_collision_radius_m(boss),
        },
        "telegraph": {
            "mode": pending_view["spatialMode"] if pending_view else None,
            "center": pending_view["areaCenter"] if pending_view else None,
            "radiusM": pending_view["areaRadiusM"] if pending_view else None,
        },
    }

    available_actions = [asdict(CORE_BOSS_ACTIONS[action_id]) for action_id in phase.action_ids]
    return {
        "schema": "sao.ui.boss_raid.v2",
        "encounter": {
            "id": encounter.encounter_id,
            "timeMs": encounter.time_ms,
            "zoneId": encounter.zone_id,
            "safeZone": encounter.safe_zone,
            "antiCrystal": encounter.anti_crystal,
        },
        "boss": {
            **state,
            "alive": boss.alive,
            "level": boss.level,
            "phaseName": phase.name,
            "phaseProvenance": asdict(phase.provenance),
            "availableActions": available_actions,
        },
        "telegraph": pending_view,
        "spatial": spatial,
        "players": players,
        "minions": minions,
        "events": [asdict(event) for event in encounter.events[-18:]],
        "raid": {
            "playerCount": len(players),
            "livingPlayers": sum(1 for row in players if row["alive"]),
            "livingMinions": sum(1 for row in minions if row["alive"]),
            "totalMinionsSpawned": state["sentinelsSpawned"],
            "playersInDangerZone": sum(1 for row in players if row["alive"] and row["inDangerZone"]),
        },
        "provenance": asdict(definition.provenance),
    }
