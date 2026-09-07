from __future__ import annotations

from sao_mcp.rules.loot import LootEntry, LootTable


# These are playable simulation tables. They are not presented as official SAO drop rates.
CORE_LOOT_TABLES: dict[str, LootTable] = {
    "floor1_frenzy_boar": LootTable(
        table_id="floor1_frenzy_boar",
        col_min=8,
        col_max=18,
        xp_min=18,
        xp_max=30,
        entries=(
            LootEntry("boar_hide", 0.82, 1, 2),
            LootEntry("red_jewel_fragment", 0.06, 1, 1),
        ),
        provenance="simulation",
    ),
    "floor1_field_wolf": LootTable(
        table_id="floor1_field_wolf",
        col_min=11,
        col_max=22,
        xp_min=22,
        xp_max=34,
        entries=(LootEntry("red_jewel_fragment", 0.08, 1, 1),),
        provenance="simulation",
    ),
    "floor1_mining_node": LootTable(
        table_id="floor1_mining_node",
        entries=(
            LootEntry("iron_ore", 1.0, 1, 3),
            LootEntry("red_jewel_fragment", 0.04, 1, 1),
        ),
        provenance="simulation",
    ),
}
