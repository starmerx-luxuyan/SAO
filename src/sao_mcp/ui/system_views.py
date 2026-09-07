from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.corpus.recipes import WEAPON_RECIPES
from sao_mcp.rules.progression import skill_slot_count
from sao_mcp.ui.view_models import character_view


FORGE_LOCATION_IDS = {
    "floor_1_town_of_beginnings",
    "floor_48_lisbeth_smith_shop",
    "floor_55_granzam",
}


def system_menu_view(runtime, actor_id: str, encounter_id: str | None = None) -> dict[str, Any]:
    actor = runtime.actors[actor_id]
    encounter = runtime.encounters.get(encounter_id) if encounter_id else None
    character = character_view(actor, runtime.catalog, encounter)
    location = runtime.world_map.locations.get(actor.location_id or "")
    floor_number = location.floor_number if location else None
    floor_state = runtime.world.floors.get(floor_number) if floor_number else None

    neighbors: list[dict[str, Any]] = []
    for connection in runtime.world_map.adjacency.get(actor.location_id or "", []):
        destination = runtime.world_map.locations[connection.to_location_id]
        destination_floor = runtime.world.floors[destination.floor_number]
        neighbors.append(
            {
                "locationId": destination.location_id,
                "name": destination.name,
                "floor": destination.floor_number,
                "zoneKind": destination.zone_kind.value,
                "safeZone": destination.safe_zone,
                "travelMs": connection.travel_ms,
                "accessible": destination_floor.unlocked or not connection.requires_floor_unlocked,
                "provenance": asdict(destination.provenance),
            }
        )

    active_quests = runtime.quests.progress_by_actor.get(actor_id, {})
    completed = runtime.quests.completed_by_actor.get(actor_id, set())
    quest_rows: list[dict[str, Any]] = []
    for quest_id, definition in runtime.quests.definitions.items():
        progress = active_quests.get(quest_id)
        ready = False
        if progress is not None and not progress.claimed:
            ready = runtime.quests.ready_to_claim(actor, quest_id)
        quest_rows.append(
            {
                "id": quest_id,
                "definition": asdict(definition),
                "progress": asdict(progress) if progress is not None else None,
                "completed": quest_id in completed,
                "readyToClaim": ready,
            }
        )

    npc_rows = []
    for npc_id, definition in runtime.npcs.definitions.items():
        state = runtime.npcs.states[npc_id]
        if state.location_id != actor.location_id:
            continue
        npc_rows.append(
            {
                "id": npc_id,
                "name": definition.name,
                "roles": list(definition.roles),
                "relationship": state.relationship_by_actor.get(actor_id, 0),
                "questIds": list(definition.quest_ids),
                "provenance": asdict(definition.provenance),
            }
        )

    economy = getattr(runtime, "economy", None)
    vendor_rows = []
    market_rows = []
    if economy is not None:
        vendor_rows = [
            asdict(vendor)
            for vendor in economy.vendors.values()
            if vendor.location_id == actor.location_id
        ]
        for listing in economy.player_listings.values():
            if listing.location_id != actor.location_id:
                continue
            template = runtime.catalog.item(listing.item.template_id)
            market_rows.append(
                {
                    "listingId": listing.listing_id,
                    "sellerId": listing.seller_id,
                    "templateId": listing.item.template_id,
                    "name": template.name,
                    "quantity": listing.item.quantity,
                    "unitPriceCol": listing.unit_price_col,
                    "quality": listing.item.quality,
                    "makerId": listing.item.maker_id,
                    "durability": listing.item.durability,
                    "maxDurability": listing.item.max_durability,
                }
            )

    skills = []
    for skill_id, definition in runtime.catalog.skills.items():
        skills.append(
            {
                "id": skill_id,
                "name": definition.name,
                "kind": definition.kind.value,
                "description": definition.description,
                "equipped": skill_id in actor.equipped_skills,
                "proficiency": actor.skill_proficiencies.get(skill_id, 0.0),
                "prerequisites": list(definition.prerequisites),
                "provenance": asdict(definition.provenance),
            }
        )

    party = None
    if actor.party_id and actor.party_id in runtime.world.parties:
        party_state = runtime.world.parties[actor.party_id]
        party = {
            "id": party_state.party_id,
            "leaderId": party_state.leader_id,
            "memberIds": list(party_state.member_ids),
            "members": [
                {
                    "id": member_id,
                    "name": runtime.actors[member_id].name if member_id in runtime.actors else member_id,
                    "hp": runtime.actors[member_id].hp if member_id in runtime.actors else None,
                    "maxHp": runtime.actors[member_id].max_hp if member_id in runtime.actors else None,
                }
                for member_id in party_state.member_ids
            ],
        }

    return {
        "schema": "sao.ui.system.v1",
        "world": {
            "nowMs": runtime.world.now_ms,
            "unlockedFloors": [number for number, floor in runtime.world.floors.items() if floor.unlocked],
        },
        "character": character,
        "location": {
            "id": location.location_id if location else actor.location_id,
            "name": location.name if location else actor.location_id,
            "floor": floor_number,
            "zoneKind": location.zone_kind.value if location else None,
            "safeZone": location.safe_zone if location else False,
            "antiCrystal": location.anti_crystal if location else False,
            "teleportGate": location.teleport_gate if location else False,
            "floorUnlocked": floor_state.unlocked if floor_state else False,
            "mainTownGateActive": floor_state.main_town_gate_active if floor_state else False,
            "neighbors": neighbors,
            "provenance": asdict(location.provenance) if location else None,
        },
        "quests": quest_rows,
        "npcs": npc_rows,
        "vendors": vendor_rows,
        "market": market_rows,
        "forge": {
            "available": actor.location_id in FORGE_LOCATION_IDS,
            "blacksmithSkillEquipped": "blacksmithing" in actor.equipped_skills,
            "blacksmithProficiency": actor.skill_proficiencies.get("blacksmithing", 0.0),
            "recipes": [asdict(recipe) for recipe in WEAPON_RECIPES.values()],
        },
        "skillManagement": {
            "slotsUsed": len(actor.equipped_skills),
            "slotsTotal": skill_slot_count(actor.level),
            "skills": skills,
        },
        "party": party,
    }
