from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.corpus.bosses import CORE_BOSS_ACTIONS, CORE_BOSSES
from sao_mcp.domain.models import DefenseMode, EntityKind
from sao_mcp.rules.raids import (
    RAID_ROLES,
    assign_raid_role,
    boss_raid_status,
    retreat_from_boss_room,
    set_party_rotation,
)


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_boss_tools(mcp, runtime) -> None:
    @mcp.tool()
    def list_floor_bosses(floor_number: int | None = None) -> str:
        """List implemented floor-boss definitions with explicit canon/simulation provenance."""
        rows = []
        for definition in CORE_BOSSES.values():
            if floor_number is not None and definition.floor_number != floor_number:
                continue
            rows.append(asdict(definition))
        return _json({"bosses": rows})

    @mcp.tool()
    def inspect_boss_action(action_id: str) -> str:
        """Inspect one boss action's telegraph, reach, target cap and provenance."""
        return _json(asdict(CORE_BOSS_ACTIONS[action_id]))

    def _start_boss(player_ids: list[str], boss_definition_id: str, enforce_location: bool) -> str:
        if boss_definition_id not in CORE_BOSSES:
            raise KeyError(boss_definition_id)
        if boss_definition_id == "asterius_the_taurus_king":
            raise ValueError("Floor 2 Asterius uses the dedicated Taurus raid sequence")
        encounter, boss = runtime.start_floor_boss_encounter(
            player_ids,
            boss_definition_id=boss_definition_id,
            enforce_location=enforce_location,
        )
        minions = [
            actor_id
            for actor_id, actor in encounter.participants.items()
            if actor.metadata.get("boss_parent_id") == boss.actor_id
        ]
        return _json(
            {
                "encounterId": encounter.encounter_id,
                "bossId": boss.actor_id,
                "boss": runtime.boss_bar_state(boss),
                "openingMinionIds": minions,
                "playerIds": player_ids,
                "zoneId": encounter.zone_id,
                "raidStatus": boss_raid_status(runtime, encounter.encounter_id),
            }
        )

    @mcp.tool()
    def start_floor_boss_raid(
        player_ids: list[str],
        boss_definition_id: str,
        enforce_location: bool = True,
    ) -> str:
        """Start any implemented ordinary Floor Boss raid. Floor 2 uses its dedicated Taurus sequence."""
        return _start_boss(player_ids, boss_definition_id, enforce_location)

    @mcp.tool()
    def start_floor_1_illfang_raid(
        player_ids: list[str],
        enforce_location: bool = True,
    ) -> str:
        """Start the Floor-1 Illfang raid; retained as a convenient compatibility entry point."""
        return _start_boss(player_ids, "illfang_the_kobold_lord", enforce_location)

    @mcp.tool()
    def get_boss_state(encounter_id: str, boss_id: str | None = None) -> str:
        """Return segmented HP bars, phase and pending telegraph for an encounter boss."""
        encounter = runtime.encounters[encounter_id]
        if boss_id is None:
            candidates = [
                actor.actor_id
                for actor in encounter.participants.values()
                if actor.kind is EntityKind.BOSS and actor.alive
            ]
            if not candidates:
                candidates = [
                    actor.actor_id
                    for actor in encounter.participants.values()
                    if actor.kind is EntityKind.BOSS
                ]
            if not candidates:
                raise ValueError("encounter has no registered boss")
            boss_id = candidates[0]
        return _json(runtime.boss_bar_state(boss_id))

    @mcp.tool()
    def get_boss_raid_status(encounter_id: str) -> str:
        """Return raid casualties, wipe state, retreat capabilities, threat leader and command assignments."""
        return _json(boss_raid_status(runtime, encounter_id))

    @mcp.tool()
    def assign_boss_raid_role(encounter_id: str, actor_id: str, role: str) -> str:
        """Assign a tactical raid role: tank, attacker, support or minion_control."""
        encounter = runtime.encounters[encounter_id]
        actor = encounter.participants.get(actor_id)
        if actor is None or actor.kind is not EntityKind.PLAYER:
            raise ValueError("raid role requires a participating player")
        if role not in RAID_ROLES:
            raise ValueError(f"unknown raid role: {role}")
        return _json(assign_raid_role(runtime.world, encounter_id, actor_id, role))

    @mcp.tool()
    def set_boss_party_rotation(encounter_id: str, party_ids: list[str]) -> str:
        """Set an ordered party rotation plan for tank/attack/potion-cycle coordination."""
        encounter = runtime.encounters[encounter_id]
        encounter_party_ids = {
            actor.party_id
            for actor in encounter.participants.values()
            if actor.kind is EntityKind.PLAYER and actor.party_id
        }
        if any(party_id not in encounter_party_ids for party_id in party_ids):
            raise ValueError("party rotation contains a party absent from this encounter")
        return _json(set_party_rotation(runtime.world, encounter_id, party_ids))

    @mcp.tool()
    def retreat_from_floor_boss(
        encounter_id: str,
        actor_id: str,
        method: str = "door",
        teleport_crystal_instance_id: str | None = None,
        teleport_destination_id: str | None = None,
    ) -> str:
        """Retreat through the boss-room entrance or by Teleport Crystal when the room permits it."""
        return _json(
            asdict(
                retreat_from_boss_room(
                    runtime,
                    encounter_id,
                    actor_id,
                    method=method,
                    teleport_crystal_instance_id=teleport_crystal_instance_id,
                    teleport_destination_id=teleport_destination_id,
                )
            )
        )

    @mcp.tool()
    def choose_boss_action(encounter_id: str, boss_id: str) -> str:
        """Choose an available action and legal targets from current phase/threat state without executing it."""
        return _json(runtime.choose_boss_action(encounter_id, boss_id))

    @mcp.tool()
    def telegraph_boss_action(
        encounter_id: str,
        boss_id: str,
        action_id: str,
        target_ids: list[str],
    ) -> str:
        """Open a visible boss telegraph window before damage is resolved."""
        event = runtime.telegraph_boss_action(encounter_id, boss_id, action_id, target_ids)
        return _json(asdict(event))

    @mcp.tool()
    def resolve_boss_action(
        encounter_id: str,
        boss_id: str,
        defenses: dict[str, str] | None = None,
        seed: int | None = None,
    ) -> str:
        """Resolve the pending boss telegraph after players have had a reaction window."""
        normalized = {
            actor_id: DefenseMode(mode)
            for actor_id, mode in (defenses or {}).items()
        }
        return _json(
            runtime.resolve_boss_action(
                encounter_id,
                boss_id,
                defenses=normalized,
                seed=seed,
            )
        )

    @mcp.tool()
    def list_live_boss_minions(encounter_id: str, boss_id: str) -> str:
        """List currently alive/dead boss-linked minions for raid target assignment."""
        encounter = runtime.encounters[encounter_id]
        rows = [
            {
                "id": actor.actor_id,
                "name": actor.name,
                "hp": actor.hp,
                "maxHp": actor.max_hp,
                "alive": actor.alive,
                "templateId": actor.metadata.get("boss_minion_template_id"),
            }
            for actor in encounter.participants.values()
            if actor.metadata.get("boss_parent_id") == boss_id
        ]
        return _json({"bossId": boss_id, "minions": rows})
