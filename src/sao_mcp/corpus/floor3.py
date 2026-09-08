from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES, MonsterDefinition
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind
from sao_mcp.rules.loot import LootEntry, LootTable
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition
from sao_mcp.rules.quests import (
    CORE_QUESTS if False else QuestDefinition,  # type: ignore[comparison-overlap]
)
from sao_mcp.corpus.quests import CORE_QUESTS
from sao_mcp.rules.quests import QuestObjectiveDefinition, QuestObjectiveKind, QuestReward


PROGRESSIVE_2 = "Sword Art Online Progressive Volume 2: Concerto of Black and White"
QUEST_ID = "vanquishing_the_spiders"
COMMANDER_ID = "npc_floor3_dark_elf_commander"
SCOUT_EMBLEM_ID = "dark_elf_scout_leaf_emblem"
FANG_ID = "queen_spider_poison_fang"
NEPHILA_ID = "nephila_regina"


def _canon(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(PROGRESSIVE_2,), notes=notes)


def apply_floor3_spider_corpus(catalog: Catalog) -> Catalog:
    """Install the Dark-Elf-path Vanquishing the Spiders quest slice and its required content."""
    catalog.items.setdefault(
        SCOUT_EMBLEM_ID,
        ItemTemplate(
            SCOUT_EMBLEM_ID,
            "Dark Elf Scout Leaf Emblem",
            ItemKind.QUEST,
            weight=0.05,
            stack_limit=1,
            tags=("floor_3", "elf_war", "vanquishing_the_spiders"),
            provenance=_canon("Leaf-design emblem recovered from the dead Dark Elf scout in the Queen Spider's Nest."),
        ),
    )
    catalog.items.setdefault(
        FANG_ID,
        ItemTemplate(
            FANG_ID,
            "Queen Spider's Poison Fang",
            ItemKind.QUEST,
            weight=0.3,
            stack_limit=1,
            tags=("floor_3", "elf_war", "nephila_regina_drop"),
            provenance=_canon("Quest item dropped by Nephila Regina and returned to the Dark Elf commander."),
        ),
    )

    AINCRAD_MONSTERS.setdefault(
        NEPHILA_ID,
        MonsterDefinition(
            monster_id=NEPHILA_ID,
            name="Nephila Regina",
            floor_number=3,
            level=9,
            location_id="floor_3_queen_spider_nest",
            hp_factor=4.2,
            quest_kill_id=NEPHILA_ID,
            loot_table_id="aincrad_nephila_regina",
            tags=("spider", "dungeon_boss", "flag_mob", "elf_war"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_2,),
                notes=(
                    "Nephila Regina is the Queen Spider's Nest dungeon boss and Flag Mob for Vanquishing the Spiders. "
                    "Level and HP factor are simulation calibration."
                ),
            ),
        ),
    )
    AINCRAD_MONSTER_LOOT_TABLES.setdefault(
        "aincrad_nephila_regina",
        LootTable(
            table_id="aincrad_nephila_regina",
            col_min=95,
            col_max=145,
            xp_min=420,
            xp_max=560,
            entries=(LootEntry(FANG_ID, 1.0),),
            provenance="canon_poison_fang_drop_plus_simulation_col_xp",
        ),
    )

    CORE_QUESTS.setdefault(
        QUEST_ID,
        QuestDefinition(
            quest_id=QUEST_ID,
            name="Vanquishing the Spiders",
            floor_number=3,
            giver_id=COMMANDER_ID,
            turn_in_id=COMMANDER_ID,
            objectives=(
                QuestObjectiveDefinition(
                    "recover_scout_emblem",
                    QuestObjectiveKind.COLLECT,
                    SCOUT_EMBLEM_ID,
                    required=1,
                    consume_on_turn_in=True,
                ),
                QuestObjectiveDefinition(
                    "defeat_nephila_regina",
                    QuestObjectiveKind.KILL,
                    NEPHILA_ID,
                    required=1,
                ),
                QuestObjectiveDefinition(
                    "recover_queen_spider_fang",
                    QuestObjectiveKind.COLLECT,
                    FANG_ID,
                    required=1,
                    consume_on_turn_in=True,
                ),
            ),
            reward=QuestReward(col=260, xp=420),
            repeatable=False,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_2,),
                notes=(
                    "Dark-Elf-path Elf War chapter. Canon requires finding the dead scout's leaf emblem, "
                    "then killing Nephila Regina and returning its poison fang. The runtime combines the two turn-ins "
                    "into one persistent quest; Col/XP reward values are simulation."
                ),
            ),
        ),
    )

    CORE_NPCS.setdefault(
        COMMANDER_ID,
        NPCDefinition(
            npc_id=COMMANDER_ID,
            name="Dark Elf Commander",
            home_location_id="floor_3_dark_elf_base",
            roles=("dark_elf", "commander", "quest_giver", "elf_war"),
            quest_ids=(QUEST_ID,),
            knowledge_tags=("queen_spider_nest", "nephila_regina", "elf_war", "jade_key"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_2,),
                notes="The Dark Elf commander assigns the spider-extermination chapter; generic display name avoids inventing a personal name.",
            ),
        ),
    )
    return catalog
