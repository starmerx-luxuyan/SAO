from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES, MonsterDefinition
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind
from sao_mcp.rules.loot import LootTable


PROGRESSIVE_4 = "Sword Art Online Progressive Volume 4: Scherzo of Deep Night"
KARLUIN_REFERENCE = "https://swordartonline.fandom.com/wiki/Karluin"
ITEM_REFERENCE = "https://swordartonline.fandom.com/wiki/Items"
STATUS_REFERENCE = "https://swordartonline.fandom.com/wiki/Status_Effect"
SHREWMAN_REFERENCE = "https://swordartonline.fandom.com/wiki/Sly_Shrewman"

BLUE_BLUEBERRY_TART = "blue_blueberry_tart"
RING_OF_LUMINESCENCE = "ring_of_luminescence"
KARLUIN_RELIC_COIN = "karluin_relic_coin"
KARLUIN_RELIC_GEM = "karluin_relic_gem"
MOURNFUL_WRAITH = "mournful_wraith"
SLY_SHREWMAN = "sly_shrewman"


def _canon(notes: str, *sources: str) -> Provenance:
    return Provenance(
        ProvenanceKind.CANON,
        sources=tuple(sources) or (PROGRESSIVE_4,),
        notes=notes,
    )


def apply_floor5_karluin_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        BLUE_BLUEBERRY_TART,
        ItemTemplate(
            template_id=BLUE_BLUEBERRY_TART,
            name="Blue-Blueberry Tart",
            kind=ItemKind.FOOD,
            weight=0.2,
            stack_limit=1,
            tags=("floor_5", "karluin", "blink_and_brink", "relic_finding_bonus", "one_hour"),
            provenance=_canon(
                "Limited-supply dessert sold at BLINK & BRINK. Eating it grants Relic Finding Bonus for one hour; runtime price is intentionally unspecified.",
                PROGRESSIVE_4,
                ITEM_REFERENCE,
                STATUS_REFERENCE,
            ),
        ),
    )
    catalog.items.setdefault(
        RING_OF_LUMINESCENCE,
        ItemTemplate(
            template_id=RING_OF_LUMINESCENCE,
            name="Ring of Luminescence",
            kind=ItemKind.MISC,
            weight=0.05,
            stack_limit=1,
            tags=("accessory", "ring", "relic", "floor_5", "karluin", "candlelight", "breath_activated"),
            provenance=_canon(
                "Relic ring found in a temple in Karluin. It shines when breathed on.",
                PROGRESSIVE_4,
                ITEM_REFERENCE,
            ),
        ),
    )
    catalog.items.setdefault(
        KARLUIN_RELIC_COIN,
        ItemTemplate(
            template_id=KARLUIN_RELIC_COIN,
            name="Karluin Ancient Coin",
            kind=ItemKind.MISC,
            weight=0.02,
            stack_limit=20,
            base_value_col=18,
            tags=("relic", "floor_5", "karluin", "coin"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_4,),
                notes="Coins are explicitly among relics found around Karluin; this generic coin identity/value is simulation scaffolding.",
            ),
        ),
    )
    catalog.items.setdefault(
        KARLUIN_RELIC_GEM,
        ItemTemplate(
            template_id=KARLUIN_RELIC_GEM,
            name="Karluin Relic Gem",
            kind=ItemKind.MISC,
            weight=0.04,
            stack_limit=10,
            base_value_col=42,
            tags=("relic", "floor_5", "karluin", "gem"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_4,),
                notes="Gems are explicitly among Karluin relic finds; this generic gem identity/value is simulation scaffolding.",
            ),
        ),
    )

    # Replace the earlier broad Floor-5 entries with location-accurate Karluin catacomb versions.
    AINCRAD_MONSTERS[MOURNFUL_WRAITH] = MonsterDefinition(
        monster_id=MOURNFUL_WRAITH,
        name="Mournful Wraith",
        floor_number=5,
        level=8,
        location_id="floor_5_karluin_catacombs_lower",
        hp_factor=0.90,
        quest_kill_id=MOURNFUL_WRAITH,
        loot_table_id="aincrad_mournful_wraith",
        tags=("undead", "astral", "catacombs", "thirty_year_lament"),
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=(PROGRESSIVE_4,),
            notes="Mournful Wraith is a Floor 5 astral monster encountered in Karluin's underground catacombs; level/HP are simulation.",
        ),
    )
    AINCRAD_MONSTERS[SLY_SHREWMAN] = MonsterDefinition(
        monster_id=SLY_SHREWMAN,
        name="Sly Shrewman",
        floor_number=5,
        level=8,
        location_id="floor_5_karluin_catacombs_lower",
        hp_factor=0.95,
        quest_kill_id=SLY_SHREWMAN,
        loot_table_id="aincrad_sly_shrewman",
        tags=("humanoid", "catacombs", "robbing", "steals_ground_items", "fast_retreat"),
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=(PROGRESSIVE_4, SHREWMAN_REFERENCE),
            notes=(
                "Sly Shrewman uses Robbing on player-dropped items, overwriting their ownership and fleeing at very high speed. "
                "Level/HP are simulation."
            ),
        ),
    )
    AINCRAD_MONSTER_LOOT_TABLES.setdefault(
        "aincrad_mournful_wraith",
        LootTable(
            table_id="aincrad_mournful_wraith",
            col_min=24,
            col_max=38,
            xp_min=70,
            xp_max=105,
            entries=(),
            provenance="simulation_rewards",
        ),
    )
    AINCRAD_MONSTER_LOOT_TABLES.setdefault(
        "aincrad_sly_shrewman",
        LootTable(
            table_id="aincrad_sly_shrewman",
            col_min=20,
            col_max=32,
            xp_min=62,
            xp_max=94,
            entries=(),
            provenance="simulation_rewards; stolen items are handled by the Karluin scenario",
        ),
    )
    return catalog
