from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.corpus.loot import CORE_LOOT_TABLES
from sao_mcp.corpus.monsters import (
    AINCRAD_MONSTERS,
    AINCRAD_MONSTER_LOOT_TABLES,
    apply_aincrad_monster_drop_items,
)
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_adventure_tools(mcp, runtime) -> None:
    # Monster content plugs into the existing item/loot/combat path. No separate monster runtime exists.
    apply_aincrad_monster_drop_items(runtime.catalog)
    CORE_LOOT_TABLES.update(AINCRAD_MONSTER_LOOT_TABLES)

    def _spawn_catalog_monster(monster_id: str, *, level_override: int | None = None):
        definition = AINCRAD_MONSTERS[monster_id]
        monster = runtime._create_monster(
            name=definition.name,
            level=definition.level if level_override is None else level_override,
            location_id=definition.location_id,
            hp_factor=definition.hp_factor,
            loot_table_id=definition.loot_table_id,
            quest_kill_id=definition.quest_kill_id,
        )
        monster.metadata.update(
            {
                "monster_id": definition.monster_id,
                "monster_tags": list(definition.tags),
                "monster_floor": definition.floor_number,
                "monster_provenance": definition.provenance.kind.value,
            }
        )
        return monster

    @mcp.tool()
    def list_locations(floor_number: int, actor_id: str | None = None) -> str:
        """List locations on one Aincrad floor with discovery and gate state."""
        if floor_number not in runtime.world.floors:
            raise ValueError("floor_number must be 1..100")
        floor = runtime.world.floors[floor_number]
        entries = []
        for location in runtime.world_map.locations.values():
            if location.floor_number != floor_number:
                continue
            entries.append(
                {
                    "id": location.location_id,
                    "name": location.name,
                    "zoneKind": location.zone_kind.value,
                    "safeZone": location.safe_zone,
                    "antiCrystal": location.anti_crystal,
                    "teleportGate": location.teleport_gate,
                    "discovered": location.location_id in floor.discovered_locations,
                    "provenance": asdict(location.provenance),
                }
            )
        current = runtime.actors[actor_id].location_id if actor_id else None
        return _json(
            {
                "floor": floor_number,
                "unlocked": floor.unlocked,
                "mainTownGateActive": floor.main_town_gate_active,
                "actorLocationId": current,
                "locations": entries,
            }
        )

    @mcp.tool()
    def list_monsters(floor_number: int | None = None) -> str:
        """List playable Aincrad monster identities, levels, habitats and provenance."""
        if floor_number is not None and floor_number not in runtime.world.floors:
            raise ValueError("floor_number must be 1..100")
        rows = []
        for definition in AINCRAD_MONSTERS.values():
            if floor_number is not None and definition.floor_number != floor_number:
                continue
            rows.append(
                {
                    "id": definition.monster_id,
                    "name": definition.name,
                    "floor": definition.floor_number,
                    "level": definition.level,
                    "locationId": definition.location_id,
                    "hpFactor": definition.hp_factor,
                    "tags": list(definition.tags),
                    "provenance": asdict(definition.provenance),
                }
            )
        return _json({"count": len(rows), "monsters": rows})

    @mcp.tool()
    def create_monster_encounter(actor_id: str, monster_id: str) -> str:
        """Spawn one catalogued Aincrad monster in its habitat and start a normal encounter."""
        definition = AINCRAD_MONSTERS[monster_id]
        actor = runtime.actors[actor_id]
        if actor.location_id != definition.location_id:
            raise ValueError(
                f"{definition.name} encounter requires actor at {definition.location_id}"
            )
        monster = _spawn_catalog_monster(monster_id)
        encounter = runtime.start_encounter(
            [actor_id, monster.actor_id],
            zone_id=definition.location_id,
        )
        return _json(
            {
                "encounterId": encounter.encounter_id,
                "playerId": actor_id,
                "monsterId": monster.actor_id,
                "monsterTemplateId": monster_id,
                "name": monster.name,
                "level": monster.level,
                "maxHp": monster.max_hp,
                "locationId": definition.location_id,
            }
        )

    @mcp.tool()
    def travel_to(actor_id: str, destination_id: str) -> str:
        """Travel along one connected world-map edge and advance persistent world time."""
        return _json(asdict(runtime.travel_actor(actor_id, destination_id)))

    @mcp.tool()
    def teleport_to(
        actor_id: str,
        crystal_instance_id: str,
        destination_id: str,
        encounter_id: str | None = None,
    ) -> str:
        """Consume a Teleport Crystal and move to an active teleport gate."""
        return _json(
            asdict(
                runtime.teleport_actor(
                    actor_id,
                    crystal_instance_id,
                    destination_id,
                    encounter_id=encounter_id,
                )
            )
        )

    @mcp.tool()
    def interact_npc(actor_id: str, npc_id: str) -> str:
        """Interact with a colocated NPC and return roles, knowledge tags and available quests."""
        return _json(asdict(runtime.interact_npc(actor_id, npc_id)))

    @mcp.tool()
    def list_npcs(location_id: str | None = None) -> str:
        """List known persistent NPCs, optionally restricted to one location."""
        rows = []
        for npc_id, definition in runtime.npcs.definitions.items():
            resolved_location_id = runtime.npc_location_id(npc_id)
            if location_id is not None and resolved_location_id != location_id:
                continue
            rows.append(
                {
                    "id": npc_id,
                    "name": definition.name,
                    "locationId": resolved_location_id,
                    "roles": list(definition.roles),
                    "questIds": list(definition.quest_ids),
                    "provenance": asdict(definition.provenance),
                }
            )
        return _json({"npcs": rows})

    @mcp.tool()
    def list_quests(actor_id: str) -> str:
        """List quest definitions plus this actor's active/completed progress."""
        actor = runtime.actors[actor_id]
        active = runtime.quests.progress_by_actor.get(actor_id, {})
        completed = runtime.quests.completed_by_actor.get(actor_id, set())
        rows = []
        for quest_id, definition in runtime.quests.definitions.items():
            progress = active.get(quest_id)
            ready = False
            if progress is not None and not progress.claimed:
                ready = runtime.quests.ready_to_claim(actor, quest_id)
            rows.append(
                {
                    "definition": asdict(definition),
                    "progress": asdict(progress) if progress is not None else None,
                    "completed": quest_id in completed,
                    "readyToClaim": ready,
                    "globalAcceptBlockUntilMs": runtime.quests.global_accept_block_until_ms.get(quest_id, 0),
                }
            )
        return _json({"actorId": actor_id, "quests": rows})

    @mcp.tool()
    def accept_quest(actor_id: str, quest_id: str) -> str:
        """Accept a quest from its colocated quest giver, enforcing prerequisites and cooldowns."""
        return _json(asdict(runtime.accept_quest(actor_id, quest_id)))

    @mcp.tool()
    def claim_quest(actor_id: str, quest_id: str) -> str:
        """Turn in a completed quest to the designated NPC and grant authoritative rewards."""
        return _json(asdict(runtime.claim_quest(actor_id, quest_id)))

    @mcp.tool()
    def create_little_nepenthes_encounter(
        actor_id: str,
        flowerhead: bool = False,
        monster_level: int = 3,
    ) -> str:
        """Create a Floor-1 Little Nepenthes encounter for quest/adventure play."""
        actor = runtime.actors[actor_id]
        if actor.location_id != "floor_1_west_field":
            raise ValueError("Little Nepenthes encounter requires the Floor 1 west field")
        if flowerhead:
            monster = runtime.create_little_nepenthes(flowerhead=True, level=monster_level)
        else:
            monster = _spawn_catalog_monster("little_nepenthes", level_override=monster_level)
        encounter = runtime.start_encounter(
            [actor_id, monster.actor_id],
            zone_id="floor_1_west_field",
        )
        return _json(
            {
                "encounterId": encounter.encounter_id,
                "playerId": actor_id,
                "monsterId": monster.actor_id,
                "flowerhead": flowerhead,
            }
        )

    @mcp.tool()
    def advance_encounter_time(encounter_id: str, elapsed_ms: int) -> str:
        """Advance encounter time to process regeneration, damage-over-time and recovery states."""
        encounter = runtime.advance_encounter(encounter_id, elapsed_ms)
        return _json(
            {
                "encounterId": encounter.encounter_id,
                "timeMs": encounter.time_ms,
                "participants": {
                    actor_id: {"hp": actor.hp, "alive": actor.alive}
                    for actor_id, actor in encounter.participants.items()
                },
            }
        )

    @mcp.tool()
    def export_save_json() -> str:
        """Export the complete deterministic Aincrad runtime save as JSON."""
        return export_runtime(runtime)

    @mcp.tool()
    def import_save_json(save_json: str) -> str:
        """Load a previously exported sao.aincrad.save.v1 payload into this runtime."""
        import_runtime(save_json, into=runtime)
        return _json(
            {
                "ok": True,
                "actors": len(runtime.actors),
                "encounters": len(runtime.encounters),
                "worldTimeMs": runtime.world.now_ms,
            }
        )
