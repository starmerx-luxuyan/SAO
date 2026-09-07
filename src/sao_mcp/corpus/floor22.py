from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.world import LocationDefinition, TravelConnection, WorldMapCatalog
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind, ZoneKind
from sao_mcp.rules.npcs import NPCDefinition, NPCState
from sao_mcp.rules.quests import (
    QuestDefinition,
    QuestObjectiveDefinition,
    QuestObjectiveKind,
    QuestReward,
)


QUEST_ID = "witch_of_the_west_and_three_treasures"
TOTO_ID = "npc_floor22_toto"
FOREST_SITE = "floor_22_forest_house_site"
QUEST_AREA = "floor_22_witch_quest_area"
WITCH_CASTLE = "floor_22_witch_castle"


def apply_floor22_catalog_seed(catalog: Catalog) -> None:
    items = {
        "scarecrow_stolen_brain": ItemTemplate(
            "scarecrow_stolen_brain",
            "Scarecrow's Stolen Brain",
            ItemKind.QUEST,
            weight=0.2,
            stack_limit=1,
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=("Sword Art Online: The Day Before",),
                notes="Optional Witch of the West quest treasure.",
            ),
        ),
        "tin_stolen_heart": ItemTemplate(
            "tin_stolen_heart",
            "Tin's Stolen Heart Gem",
            ItemKind.QUEST,
            weight=0.2,
            stack_limit=1,
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=("Sword Art Online: The Day Before",),
                notes="Optional Witch of the West quest treasure.",
            ),
        ),
        "lion_stolen_courage": ItemTemplate(
            "lion_stolen_courage",
            "Lion's Stolen Golden Mane",
            ItemKind.QUEST,
            weight=0.2,
            stack_limit=1,
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=("Sword Art Online: The Day Before",),
                notes="Optional Witch of the West quest treasure representing Lion's courage.",
            ),
        ),
        "witch_castle_key": ItemTemplate(
            "witch_castle_key",
            "Witch Castle Small-Door Key",
            ItemKind.QUEST,
            weight=0.05,
            stack_limit=1,
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=("Sword Art Online: The Day Before",),
                notes="Dropped by one of the four Werepanthers after entering the Witch's castle grounds.",
            ),
        ),
    }
    for key, value in items.items():
        catalog.items.setdefault(key, value)


def apply_floor22_world_seed(world_map: WorldMapCatalog) -> None:
    if FOREST_SITE in world_map.locations:
        return
    canon = Provenance(
        ProvenanceKind.CANON_INFERRED,
        sources=("Sword Art Online: The Day Before",),
    )
    world_map.locations[FOREST_SITE] = LocationDefinition(
        FOREST_SITE,
        22,
        "Forest House K4 Site",
        ZoneKind.FIELD,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 1, Chapter 17", "Sword Art Online: The Day Before"),
            notes="Detached log-house site in the southwestern forest of Floor 22.",
        ),
    )
    world_map.locations[QUEST_AREA] = LocationDefinition(
        QUEST_AREA,
        22,
        "Witch of the West Isolated Quest Area",
        ZoneKind.DUNGEON,
        anti_crystal=True,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online: The Day Before",),
            notes="Northwestern cliff-sealed quest area reached through the airborne Log House, not by ordinary walking.",
        ),
    )
    world_map.locations[WITCH_CASTLE] = LocationDefinition(
        WITCH_CASTLE,
        22,
        "Witch's Castle",
        ZoneKind.DUNGEON,
        anti_crystal=True,
        provenance=canon,
    )
    edge = TravelConnection(
        "floor_22_coral",
        FOREST_SITE,
        20 * 60_000,
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=("Sword Art Online: The Day Before",),
            notes="The home is described as roughly a twenty-minute trip from the nearest Teleport Gate.",
        ),
    )
    world_map.connections = tuple(world_map.connections) + (edge,)
    world_map.adjacency.setdefault("floor_22_coral", []).append(edge)
    world_map.adjacency.setdefault(FOREST_SITE, []).append(
        TravelConnection(FOREST_SITE, "floor_22_coral", edge.travel_ms, True, True, edge.provenance)
    )
    quest_edge = TravelConnection(
        QUEST_AREA,
        WITCH_CASTLE,
        12 * 60_000,
        provenance=Provenance(
            ProvenanceKind.SIMULATION,
            notes="In-quest travel time between the isolated landing area and castle is runtime calibration.",
        ),
    )
    world_map.connections = tuple(world_map.connections) + (quest_edge,)
    world_map.adjacency.setdefault(QUEST_AREA, []).append(quest_edge)
    world_map.adjacency.setdefault(WITCH_CASTLE, []).append(
        TravelConnection(WITCH_CASTLE, QUEST_AREA, quest_edge.travel_ms, True, True, quest_edge.provenance)
    )


def floor22_quest_definition() -> QuestDefinition:
    return QuestDefinition(
        quest_id=QUEST_ID,
        name="Witch of the West and the Three Treasures",
        floor_number=22,
        giver_id=TOTO_ID,
        turn_in_id=TOTO_ID,
        objectives=(
            QuestObjectiveDefinition(
                "recover_scarecrow_brain",
                QuestObjectiveKind.COLLECT,
                "scarecrow_stolen_brain",
                1,
                False,
                False,
            ),
            QuestObjectiveDefinition(
                "recover_tin_heart",
                QuestObjectiveKind.COLLECT,
                "tin_stolen_heart",
                1,
                False,
                False,
            ),
            QuestObjectiveDefinition(
                "recover_lion_courage",
                QuestObjectiveKind.COLLECT,
                "lion_stolen_courage",
                1,
                False,
                False,
            ),
            QuestObjectiveDefinition(
                "defeat_witch",
                QuestObjectiveKind.KILL,
                "witch_of_the_west",
                1,
                False,
                True,
            ),
        ),
        reward=QuestReward(),
        repeatable=False,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online: The Day Before",),
            notes=(
                "Toto triggers the Floor 22 collection/kill quest. The three treasures are optional; "
                "defeating the Witch completes the required objective and unlocks purchase of Forest House K4."
            ),
        ),
    )


def floor22_toto_definition() -> NPCDefinition:
    return NPCDefinition(
        npc_id=TOTO_ID,
        name="Toto",
        home_location_id=FOREST_SITE,
        roles=("quest_giver", "quest_key_npc", "companion"),
        quest_ids=(QUEST_ID,),
        knowledge_tags=("forest_house_k4", "witch_quest", "dorothy"),
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online: The Day Before",),
            notes="Dorothy's dog and the quest-starting key NPC.",
        ),
    )


def install_floor22_npc(runtime) -> None:
    definition = floor22_toto_definition()
    runtime.npcs.definitions[definition.npc_id] = definition
    runtime.npcs.states.setdefault(definition.npc_id, NPCState(definition.npc_id, definition.home_location_id))
