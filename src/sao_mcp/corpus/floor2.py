from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.quests import CORE_QUESTS
from sao_mcp.domain.models import Provenance, ProvenanceKind
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition
from sao_mcp.rules.quests import (
    QuestDefinition,
    QuestObjectiveDefinition,
    QuestObjectiveKind,
    QuestReward,
)


PROGRESSIVE_1 = "Sword Art Online Progressive Volume 1: Interlude - The Reason for the Whiskers"
QUEST_REFERENCE = "https://swordartonline.fandom.com/wiki/Martial_Arts_quest"
QUEST_ID = "floor2_martial_arts_rock_trial"
MASTER_ID = "npc_floor2_martial_arts_master"
ROCK_SPLIT_TARGET = "floor2_martial_arts_rock_split"


def apply_floor2_martial_arts_corpus(catalog: Catalog) -> Catalog:
    CORE_QUESTS.setdefault(
        QUEST_ID,
        QuestDefinition(
            quest_id=QUEST_ID,
            name="Martial Arts Rock Trial",
            floor_number=2,
            giver_id=MASTER_ID,
            turn_in_id=MASTER_ID,
            objectives=(
                QuestObjectiveDefinition(
                    "split_nearly_unbreakable_rock",
                    QuestObjectiveKind.DISCOVER,
                    ROCK_SPLIT_TARGET,
                    required=1,
                ),
            ),
            reward=QuestReward(),
            repeatable=False,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_1, QUEST_REFERENCE),
                notes=(
                    "The quest is unnamed in canon. The player must split an approximately two-metre-high, "
                    "1.5-metre-wide rock that is almost as tough as an Immortal Object using only their palms. "
                    "Completion grants the Martial Arts Extra Skill. Runtime practice/progress numbers are simulation."
                ),
            ),
        ),
    )
    CORE_NPCS.setdefault(
        MASTER_ID,
        NPCDefinition(
            npc_id=MASTER_ID,
            name="Martial Arts Master",
            home_location_id="floor_2_martial_arts_hut",
            roles=("quest_giver", "extra_skill_master", "martial_arts"),
            quest_ids=(QUEST_ID,),
            knowledge_tags=("martial_arts", "rock_trial", "whisker_paint"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_1, QUEST_REFERENCE),
                notes="The quest NPC lives in a hut near the summit of a high mountain at Floor 2's southern edge; no personal name is supplied here.",
            ),
        ),
    )
    return catalog
