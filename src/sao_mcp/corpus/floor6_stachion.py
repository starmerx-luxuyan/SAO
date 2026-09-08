from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.quests import CORE_QUESTS
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition
from sao_mcp.rules.quests import (
    QuestDefinition,
    QuestObjectiveDefinition,
    QuestObjectiveKind,
    QuestReward,
)


PROGRESSIVE_5 = "Sword Art Online Progressive Volume 5: Canon of the Golden Rule (Start)"
PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
TIMELINE_REFERENCE = "https://swordartonline.fandom.com/wiki/Sword_Art_Online_Timeline"
QUEST_ID = "curse_of_stachion"
CYLON_ID = "npc_floor6_cylon"
GOLDEN_KEY_ID = "floor6_pithagrus_golden_key"
POISON_JAR_ID = "namnepenth_poison_jar"

WITNESSES: dict[str, str] = {
    "npc_floor6_pithagrus_former_butler": "Pithagrus's Former Butler",
    "npc_floor6_pithagrus_former_servant": "Pithagrus's Former Servant",
    "npc_floor6_pithagrus_former_gardener": "Pithagrus's Former Gardener",
    "npc_floor6_pithagrus_former_cook": "Pithagrus's Former Cook",
    "npc_floor6_pithagrus_disciple_one": "Pithagrus's Former Disciple I",
    "npc_floor6_pithagrus_disciple_two": "Pithagrus's Former Disciple II",
    "npc_floor6_pithagrus_wine_merchant": "Pithagrus's Wine Merchant",
}


def _canon(notes: str, *sources: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=tuple(sources) or (PROGRESSIVE_5,), notes=notes)


def _inferred(notes: str, *sources: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=tuple(sources) or (PROGRESSIVE_5,), notes=notes)


def apply_floor6_stachion_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        GOLDEN_KEY_ID,
        ItemTemplate(
            template_id=GOLDEN_KEY_ID,
            name="Pithagrus's Golden Key",
            kind=ItemKind.QUEST,
            weight=0.08,
            stack_limit=1,
            tags=("floor_6", "curse_of_stachion", "golden_key", "pithagrus"),
            provenance=_canon(
                "Key item obtained at Pithagrus's second home in Suribus during the Curse of Stachion quest. Weight is simulation.",
                PROGRESSIVE_5,
                TIMELINE_REFERENCE,
            ),
        ),
    )
    catalog.items.setdefault(
        POISON_JAR_ID,
        ItemTemplate(
            template_id=POISON_JAR_ID,
            name="Namnepenth's Poison Jar",
            kind=ItemKind.TOOL,
            weight=0.35,
            stack_limit=1,
            tags=("floor_6", "curse_of_stachion", "paralysis_gas", "cylon", "skull_marked_jar"),
            provenance=_canon(
                "Skull-marked jar used by Cylon to release the scripted paralysis gas that incapacitates the players at Pithagrus's Suribus house. Weight is simulation.",
                PROGRESSIVE_5,
                PROGRESSIVE_6,
            ),
        ),
    )

    CORE_QUESTS.setdefault(
        QUEST_ID,
        QuestDefinition(
            quest_id=QUEST_ID,
            name="Curse of Stachion",
            floor_number=6,
            giver_id=CYLON_ID,
            turn_in_id=CYLON_ID,
            objectives=(
                QuestObjectiveDefinition(
                    "gather_old_household_testimony",
                    QuestObjectiveKind.DISCOVER,
                    "stachion_old_household_testimony",
                    required=7,
                ),
                QuestObjectiveDefinition(
                    "discover_suribus_second_home",
                    QuestObjectiveKind.DISCOVER,
                    "pithagrus_suribus_house_discovered",
                    required=1,
                ),
                QuestObjectiveDefinition(
                    "obtain_pithagrus_golden_key",
                    QuestObjectiveKind.COLLECT,
                    GOLDEN_KEY_ID,
                    required=1,
                ),
                QuestObjectiveDefinition(
                    "resolve_stachion_curse",
                    QuestObjectiveKind.DISCOVER,
                    "stachion_curse_resolved",
                    required=1,
                ),
            ),
            reward=QuestReward(),
            repeatable=False,
            provenance=_inferred(
                "The quest begins with Cylon, lord of Stachion, asking the players to find the golden cube and offer it at the traveller's grave. "
                "The first release-side investigation interviews seven former associates of Pithagrus, reveals his second home in Suribus, and leads to a golden key there. "
                "This corpus intentionally keeps the quest active after the key is obtained because the compulsory capture, Cylon-death branch and Dungeon of Trials resolution occur later.",
                PROGRESSIVE_5,
                PROGRESSIVE_6,
            ),
        ),
    )

    CORE_NPCS.setdefault(
        CYLON_ID,
        NPCDefinition(
            npc_id=CYLON_ID,
            name="Cylon",
            home_location_id="floor_6_cylon_lord_manor",
            roles=("lord_of_stachion", "quest_giver", "pithagrus_apprentice"),
            quest_ids=(QUEST_ID,),
            knowledge_tags=("curse_of_stachion", "pithagrus", "golden_cube", "traveller_grave"),
            provenance=_canon(
                "Current lord of Stachion and former apprentice of Pithagrus. He gives the Curse of Stachion quest in the release-side story.",
                PROGRESSIVE_5,
            ),
        ),
    )

    for npc_id, name in WITNESSES.items():
        CORE_NPCS.setdefault(
            npc_id,
            NPCDefinition(
                npc_id=npc_id,
                name=name,
                home_location_id="floor_6_stachion_puzzle_quarter",
                roles=("stachion_witness", "pithagrus_associate"),
                quest_ids=(),
                knowledge_tags=("pithagrus", "suribus_second_home", "curse_of_stachion"),
                provenance=_inferred(
                    "The release-side quest explicitly sends players to question Pithagrus's former butler, servant, gardener, cook, two disciples, and a visiting wine merchant. "
                    "These descriptive NPC labels avoid inventing personal names.",
                    PROGRESSIVE_5,
                ),
            ),
        )
    return catalog
