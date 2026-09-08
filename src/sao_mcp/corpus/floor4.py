from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES
from sao_mcp.corpus.quests import CORE_QUESTS
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind
from sao_mcp.rules.loot import LootEntry, LootTable
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition
from sao_mcp.rules.quests import (
    QuestDefinition,
    QuestObjectiveDefinition,
    QuestObjectiveKind,
    QuestReward,
)


PROGRESSIVE_3 = "Sword Art Online Progressive Volume 3: Barcarolle of Froth"
REFERENCE = "https://swordartonline.fandom.com/wiki/Shipwright_of_Yore"
QUEST_ID = "shipwright_of_yore"
ROMOLO_ID = "npc_floor4_romolo"
YOFILIS_ID = "npc_floor4_yofilis"
GONDOLA_TARGET = "floor4_personal_gondola_constructed"
SECRET_TARGET = "floor4_water_carriers_secret_discovered"

STANDARD_MATERIALS = {
    "sealant": "bear_fat",
    "lumber": "shipwright_solid_lumber",
    "fasteners": "bear_claw",
    "upholstery": "bear_pelt",
}
PREMIUM_MATERIALS = {
    "sealant": "legendary_bear_fat",
    "lumber": "noblewood_core",
    "fasteners": "fire_bear_claw",
    "upholstery": "fire_bear_pelt",
}
OPTIONAL_RAM_MATERIAL = "fire_bear_horn"


def _material(template_id: str, name: str, *, premium: bool = False, notes: str = "") -> ItemTemplate:
    return ItemTemplate(
        template_id=template_id,
        name=name,
        kind=ItemKind.MATERIAL,
        weight=1.0 if not premium else 1.2,
        stack_limit=20,
        tags=("floor_4", "shipwright_of_yore", "premium" if premium else "standard"),
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=(PROGRESSIVE_3, REFERENCE),
            notes=(
                "Item identity/role is canon-backed. Weight, stack limit and the runtime's one-unit-per-category "
                "construction requirement are simulation. " + notes
            ).strip(),
        ),
    )


def apply_floor4_shipwright_corpus(catalog: Catalog) -> Catalog:
    materials = {
        "bear_fat": _material("bear_fat", "Bear Fat", notes="Standard waterproofing material."),
        "shipwright_solid_lumber": _material(
            "shipwright_solid_lumber", "Solid Birch/Oak Lumber", notes="Standard structural lumber accepted by Romolo."
        ),
        "bear_claw": _material("bear_claw", "Bear Claw", notes="Standard material carved into nails/fasteners."),
        "bear_pelt": _material("bear_pelt", "Bear Pelt", notes="Standard material used for gondola seat upholstery."),
        "legendary_bear_fat": _material(
            "legendary_bear_fat", "Legendary Bear Fat", premium=True,
            notes="Premium waterproofing material obtained from Magnatherium."
        ),
        "noblewood_core": _material(
            "noblewood_core", "Noblewood Core", premium=True,
            notes="Premium heartwood from huge aged teak trees; Magnatherium charges can help fell the trees."
        ),
        "fire_bear_claw": _material(
            "fire_bear_claw", "Fire-Bear's Claw", premium=True,
            notes="Premium gondola fastener material associated with Magnatherium."
        ),
        "fire_bear_pelt": _material(
            "fire_bear_pelt", "Fire-Bear's Pelt", premium=True,
            notes="Premium gondola upholstery material associated with Magnatherium."
        ),
        "fire_bear_horn": _material(
            "fire_bear_horn", "Fire-Bear's Horn", premium=True,
            notes="Optional material that can arm the custom gondola with a ram."
        ),
    }
    for template_id, item in materials.items():
        catalog.items.setdefault(template_id, item)

    magnatherium = AINCRAD_MONSTERS["magnatherium"]
    AINCRAD_MONSTER_LOOT_TABLES[magnatherium.loot_table_id] = LootTable(
        table_id=magnatherium.loot_table_id,
        col_min=120,
        col_max=190,
        xp_min=420,
        xp_max=620,
        entries=(
            LootEntry("legendary_bear_fat", 1.0),
            LootEntry("fire_bear_claw", 1.0),
            LootEntry("fire_bear_pelt", 1.0),
            LootEntry("fire_bear_horn", 0.35),
        ),
        provenance="canon_premium_material_roles_plus_simulation_drop_rates_and_rewards",
    )

    CORE_QUESTS.setdefault(
        QUEST_ID,
        QuestDefinition(
            quest_id=QUEST_ID,
            name="Shipwright of Yore",
            floor_number=4,
            giver_id=ROMOLO_ID,
            turn_in_id=YOFILIS_ID,
            objectives=(
                QuestObjectiveDefinition(
                    "construct_personal_gondola",
                    QuestObjectiveKind.DISCOVER,
                    GONDOLA_TARGET,
                    required=1,
                    required_for_completion=False,
                ),
                QuestObjectiveDefinition(
                    "discover_water_carriers_secret",
                    QuestObjectiveKind.DISCOVER,
                    SECRET_TARGET,
                    required=1,
                ),
            ),
            reward=QuestReward(),
            repeatable=False,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_3, REFERENCE),
                notes=(
                    "Dark-Elf-route model of the multi-stage Floor 4 quest. Building a personal gondola is a mid-quest reward. "
                    "The final stage follows the Water Carriers Guild to a submerged Fallen Elf hideout; the discovered shipbuilding "
                    "plot is reported at Yofel Castle, where it leads into the Laketop Fortress continuation."
                ),
            ),
        ),
    )
    CORE_NPCS.setdefault(
        ROMOLO_ID,
        NPCDefinition(
            npc_id=ROMOLO_ID,
            name="Romolo",
            home_location_id="floor_4_rovia",
            roles=("quest_giver", "shipwright", "gondola_builder"),
            quest_ids=(QUEST_ID,),
            knowledge_tags=("shipwright_of_yore", "water_carriers_guild", "gondola", "fallen_elves"),
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=(PROGRESSIVE_3, "https://swordartonline.fandom.com/wiki/Romolo"),
                notes="Former shipwright in Rovia and giver of Shipwright of Yore.",
            ),
        ),
    )
    CORE_NPCS.setdefault(
        YOFILIS_ID,
        NPCDefinition(
            npc_id=YOFILIS_ID,
            name="Leyshren Zed Yofilis",
            home_location_id="floor_4_yofel_castle",
            roles=("dark_elf", "viscount", "quest_turn_in", "elf_war"),
            quest_ids=(),
            knowledge_tags=("yofel_castle", "forest_elf_invasion", "fallen_elves", "lapis_key"),
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=(PROGRESSIVE_3, "https://swordartonline.fandom.com/wiki/Yofel_Castle"),
                notes="Dark Elven viscount controlling Yofel Castle; receives the report about the impending ship-borne invasion.",
            ),
        ),
    )
    return catalog
