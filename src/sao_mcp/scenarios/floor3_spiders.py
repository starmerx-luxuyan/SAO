from __future__ import annotations

import uuid

from sao_mcp.corpus.floor3 import FANG_ID, NEPHILA_ID, QUEST_ID, SCOUT_EMBLEM_ID
from sao_mcp.corpus.loot import CORE_LOOT_TABLES
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES
from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.quests import QuestObjectiveKind


NEST_ID = "floor_3_queen_spider_nest"


class Floor3SpiderScenario:
    """Small content script for the Dark-Elf-path Vanquishing the Spiders quest."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        CORE_LOOT_TABLES[AINCRAD_MONSTERS[NEPHILA_ID].loot_table_id] = AINCRAD_MONSTER_LOOT_TABLES[
            AINCRAD_MONSTERS[NEPHILA_ID].loot_table_id
        ]

    def _active_progress(self, actor_id: str):
        progress = self.runtime.quests.progress_by_actor.get(actor_id, {}).get(QUEST_ID)
        if progress is None or progress.claimed:
            raise ValueError("Vanquishing the Spiders must be active")
        return progress

    def search_dead_scout(self, actor_id: str) -> ItemInstance:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        if actor.location_id != NEST_ID:
            raise ValueError("the dead Dark Elf scout is inside the Queen Spider's Nest")
        existing = next(
            (item for item in actor.inventory.values() if item.template_id == SCOUT_EMBLEM_ID),
            None,
        )
        if existing is not None:
            return existing
        item = ItemInstance(
            instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
            template_id=SCOUT_EMBLEM_ID,
            owner_id=actor_id,
            quantity=1,
        )
        add_item(actor, item, self.runtime.catalog, allow_overweight=True)
        self.runtime.quests.record_event(
            actor_id,
            kind=QuestObjectiveKind.COLLECT,
            target_id=SCOUT_EMBLEM_ID,
        )
        return item

    def create_nephila_encounter(self, actor_id: str):
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        if actor.location_id != NEST_ID:
            raise ValueError("Nephila Regina is encountered inside the Queen Spider's Nest")
        definition = AINCRAD_MONSTERS[NEPHILA_ID]
        monster = self.runtime._create_monster(
            name=definition.name,
            level=definition.level,
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
            }
        )
        encounter = self.runtime.start_encounter(
            [actor_id, monster.actor_id],
            zone_id=NEST_ID,
        )
        return encounter, monster


def install_floor3_spider_scenario(runtime) -> Floor3SpiderScenario:
    # Corpus is installed during normal catalog seeding. This installer only binds the playable script.
    if QUEST_ID not in runtime.quests.definitions:
        raise RuntimeError("Floor 3 spider corpus was not loaded")
    if NEPHILA_ID not in AINCRAD_MONSTERS:
        raise RuntimeError("Nephila Regina corpus was not loaded")
    if FANG_ID not in runtime.catalog.items or SCOUT_EMBLEM_ID not in runtime.catalog.items:
        raise RuntimeError("Floor 3 quest items were not loaded")
    return Floor3SpiderScenario(runtime)
