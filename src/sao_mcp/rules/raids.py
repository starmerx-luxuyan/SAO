from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import CombatantState, EntityKind, EncounterState, WorldState
from sao_mcp.rules.group_travel import exit_encounter_via_travel


RAID_ROLE_TANK = "tank"
RAID_ROLE_ATTACKER = "attacker"
RAID_ROLE_SUPPORT = "support"
RAID_ROLE_MINION_CONTROL = "minion_control"
RAID_ROLES = {
    RAID_ROLE_TANK,
    RAID_ROLE_ATTACKER,
    RAID_ROLE_SUPPORT,
    RAID_ROLE_MINION_CONTROL,
}


@dataclass(slots=True, frozen=True)
class BossRetreatResolution:
    actor_id: str
    encounter_id: str
    method: str
    destination_id: str
    remaining_players: int
    boss_reset: bool


def _boss(encounter: EncounterState) -> CombatantState:
    bosses = [actor for actor in encounter.participants.values() if actor.kind is EntityKind.BOSS]
    if not bosses:
        raise ValueError("encounter has no floor boss")
    return bosses[0]


def raid_command_state(world: WorldState, encounter_id: str) -> dict:
    all_states = world.global_flags.setdefault("raid_command_states", {})
    return all_states.setdefault(
        encounter_id,
        {
            "roles": {},
            "party_rotation": [],
            "notes": [],
        },
    )


def assign_raid_role(world: WorldState, encounter_id: str, actor_id: str, role: str) -> dict:
    if role not in RAID_ROLES:
        raise ValueError(f"role must be one of {sorted(RAID_ROLES)}")
    state = raid_command_state(world, encounter_id)
    state["roles"][actor_id] = role
    return state


def set_party_rotation(world: WorldState, encounter_id: str, party_ids: list[str]) -> dict:
    if len(set(party_ids)) != len(party_ids):
        raise ValueError("party rotation contains duplicates")
    state = raid_command_state(world, encounter_id)
    state["party_rotation"] = list(party_ids)
    return state


def boss_raid_status(runtime, encounter_id: str) -> dict:
    encounter = runtime.encounters[encounter_id]
    boss = _boss(encounter)
    players = [actor for actor in encounter.participants.values() if actor.kind is EntityKind.PLAYER]
    living = [actor for actor in players if actor.alive]
    dead = [actor for actor in players if not actor.alive]
    party_ids = sorted({actor.party_id for actor in players if actor.party_id})
    command = raid_command_state(runtime.world, encounter_id)
    threat = encounter.threat.get(boss.actor_id, {})
    threat_leader = None
    if threat:
        candidates = {
            actor_id: value
            for actor_id, value in threat.items()
            if actor_id in encounter.participants and encounter.participants[actor_id].alive
        }
        if candidates:
            threat_leader = max(candidates, key=candidates.get)
    return {
        "encounterId": encounter_id,
        "bossId": boss.actor_id,
        "bossAlive": boss.alive,
        "playerCount": len(players),
        "livingPlayers": len(living),
        "deadPlayers": len(dead),
        "wipe": bool(players) and not living and boss.alive,
        "partyIds": party_ids,
        "threatLeaderId": threat_leader,
        "canUseTeleportCrystal": not encounter.anti_crystal,
        "doorLocked": bool(boss.metadata.get("boss_room_door_locked", False)),
        "retreatPossible": not bool(boss.metadata.get("boss_room_door_locked", False)) or not encounter.anti_crystal,
        "command": command,
    }


def _reset_boss_after_disengage(runtime, encounter: EncounterState, boss: CombatantState) -> None:
    definition = runtime.boss_definition(boss)
    boss.hp = boss.max_hp
    boss.alive = True
    boss.recovery_until_ms = 0
    boss.committed_until_ms = 0
    boss.ai_reaction_until_ms = 0
    boss.metadata["boss_depleted_bars"] = 0
    boss.metadata["boss_minions_spawned"] = 0
    boss.metadata.pop("pending_boss_action", None)
    boss.metadata["boss_encounter_disengaged"] = True
    runtime._equip_boss_phase(boss, definition.phases[0])
    encounter.threat.clear()
    encounter.last_attacker_by_target.clear()
    encounter.last_attack_time_by_target.clear()
    for actor_id, actor in list(encounter.participants.items()):
        if actor.metadata.get("boss_parent_id") == boss.actor_id:
            encounter.participants.pop(actor_id, None)
    runtime._append(
        encounter,
        "boss_disengaged_reset",
        boss.actor_id,
        None,
        hp=boss.hp,
        phase_id=definition.phases[0].phase_id,
        reason="all_players_left_boss_room",
    )


def _finalize_retreat(runtime, encounter: EncounterState, boss: CombatantState) -> tuple[int, bool]:
    remaining = sum(
        1
        for actor in encounter.participants.values()
        if actor.kind is EntityKind.PLAYER and actor.alive
    )
    reset = remaining == 0 and boss.alive
    if reset:
        _reset_boss_after_disengage(runtime, encounter, boss)
    return remaining, reset


def retreat_from_boss_room(
    runtime,
    encounter_id: str,
    actor_id: str,
    *,
    method: str = "door",
    teleport_crystal_instance_id: str | None = None,
    teleport_destination_id: str | None = None,
) -> BossRetreatResolution:
    encounter = runtime.encounters[encounter_id]
    boss = _boss(encounter)
    actor = encounter.participants.get(actor_id)
    if actor is None or actor.kind is not EntityKind.PLAYER:
        raise ValueError("retreating actor must be a player in this boss encounter")
    if not actor.alive:
        raise ValueError("defeated players cannot retreat")

    if method == "door":
        if boss.metadata.get("boss_room_door_locked"):
            raise ValueError("boss-room entrance is locked")
        floor = runtime.boss_definition(boss).floor_number
        destination_id = f"floor_{floor}_labyrinth"
        if destination_id not in runtime.world_map.locations:
            raise ValueError("boss room has no mapped labyrinth retreat destination")
        resolution = exit_encounter_via_travel(runtime, encounter_id, [actor_id], destination_id)
        runtime._append(
            encounter,
            "boss_room_retreat",
            actor_id,
            None,
            method="door",
            destination_id=destination_id,
            elapsed_ms=resolution.elapsed_ms,
            traversal_tags=list(resolution.traversal_tags),
        )
    elif method == "teleport":
        if encounter.anti_crystal:
            raise ValueError("Teleport Crystals are disabled by this Anti-Crystal Area")
        if not teleport_crystal_instance_id or not teleport_destination_id:
            raise ValueError("teleport retreat requires a crystal instance and active-gate destination")
        runtime.teleport_actor(
            actor_id,
            teleport_crystal_instance_id,
            teleport_destination_id,
            encounter_id=encounter_id,
        )
        destination_id = teleport_destination_id
    else:
        raise ValueError("method must be 'door' or 'teleport'")

    remaining, reset = _finalize_retreat(runtime, encounter, boss)
    return BossRetreatResolution(
        actor_id=actor_id,
        encounter_id=encounter_id,
        method=method,
        destination_id=destination_id,
        remaining_players=remaining,
        boss_reset=reset,
    )
