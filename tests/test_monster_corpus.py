from sao_mcp.corpus.canon_seed import apply_canon_seed
from sao_mcp.corpus.core import build_core_catalog
from sao_mcp.corpus.monsters import (
    AINCRAD_MONSTERS,
    AINCRAD_MONSTER_LOOT_TABLES,
    apply_aincrad_monster_drop_items,
)
from sao_mcp.corpus.world import build_world_map_catalog


def test_monster_corpus_is_playable_and_locks_known_canon_values():
    assert len(AINCRAD_MONSTERS) >= 60
    world_map = build_world_map_catalog()
    assert all(row.location_id in world_map.locations for row in AINCRAD_MONSTERS.values())

    little = AINCRAD_MONSTERS["little_nepenthes"]
    assert little.floor_number == 1
    assert little.level == 3

    lizard = AINCRAD_MONSTERS["lizardman_lord"]
    assert lizard.floor_number == 74
    assert lizard.level == 82
    reward = AINCRAD_MONSTER_LOOT_TABLES[lizard.loot_table_id]
    assert (reward.xp_min, reward.xp_max) == (8120, 8120)
    assert (reward.col_min, reward.col_max) == (1000, 1000)

    catalog = apply_aincrad_monster_drop_items(apply_canon_seed(build_core_catalog()))
    for table in AINCRAD_MONSTER_LOOT_TABLES.values():
        for entry in table.entries:
            catalog.item(entry.template_id)
