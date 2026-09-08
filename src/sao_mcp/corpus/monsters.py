from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind
from sao_mcp.rules.loot import LootEntry, LootTable


AINCRAD_REFERENCE = "https://swordartonline.fandom.com/wiki/Aincrad"


@dataclass(slots=True, frozen=True)
class MonsterDefinition:
    monster_id: str
    name: str
    floor_number: int
    level: int
    location_id: str
    hp_factor: float = 1.0
    quest_kill_id: str = ""
    loot_table_id: str = ""
    tags: tuple[str, ...] = ()
    provenance: Provenance = Provenance(ProvenanceKind.CANON_INFERRED)


def _monster(
    monster_id: str,
    name: str,
    floor: int,
    *,
    level: int | None = None,
    location: str = "field",
    hp_factor: float = 1.0,
    tags: tuple[str, ...] = (),
    sources: tuple[str, ...] = (AINCRAD_REFERENCE,),
    notes: str = "",
    exact_level: bool = False,
) -> MonsterDefinition:
    resolved_level = level if level is not None else max(1, floor + 2)
    if location == "field":
        location_id = "floor_1_west_field" if floor == 1 else f"floor_{floor}_field"
    elif location == "labyrinth":
        location_id = f"floor_{floor}_labyrinth"
    else:
        location_id = location
    level_note = (
        f"Level {resolved_level} is canon." if exact_level else f"Level {resolved_level} is simulation calibration."
    )
    extra = f" {notes}" if notes else ""
    return MonsterDefinition(
        monster_id=monster_id,
        name=name,
        floor_number=floor,
        level=resolved_level,
        location_id=location_id,
        hp_factor=hp_factor,
        quest_kill_id=monster_id,
        loot_table_id=f"aincrad_{monster_id}",
        tags=tags,
        provenance=Provenance(
            ProvenanceKind.CANON if exact_level else ProvenanceKind.CANON_INFERRED,
            sources=sources,
            notes=f"Monster identity and floor are canon-backed. {level_note}{extra}",
        ),
    )


_MONSTER_ROWS = (
    # Floor 1
    _monster("frenzy_boar", "Frenzy Boar", 1, level=1, hp_factor=0.72, tags=("beast",)),
    _monster("dire_wolf", "Dire Wolf", 1, level=2, hp_factor=0.82, tags=("beast",)),
    _monster(
        "little_nepenthes", "Little Nepenthes", 1, level=3, hp_factor=0.78,
        tags=("plant", "secret_medicine"),
        sources=("https://swordartonline.fandom.com/wiki/Little_Nepenthes",),
        notes="It can drop the Little Nepenthes Ovule used by Secret Medicine of the Forest.",
        exact_level=True,
    ),
    _monster("large_nepenthes", "Large Nepenthes", 1, level=4, hp_factor=1.15, tags=("plant",)),

    # Floor 2
    _monster("jagged_worm", "Jagged Worm", 2, level=4, hp_factor=0.82, tags=("insectoid",)),
    _monster("lesser_taurus_striker", "Lesser Taurus Striker", 2, level=5, hp_factor=1.10, tags=("taurus", "humanoid")),
    _monster("red_spotted_beetle", "Red Spotted Beetle", 2, level=4, hp_factor=0.88, tags=("insect",)),
    _monster("storm_hornet", "Storm Hornet", 2, level=4, hp_factor=0.72, tags=("flying", "insect")),
    _monster("taurus_ironguard", "Taurus Ironguard", 2, level=6, hp_factor=1.35, tags=("taurus", "armored")),
    _monster("taurus_ringhurler", "Taurus Ringhurler", 2, level=6, hp_factor=1.10, tags=("taurus", "ranged")),
    _monster("trembling_cow", "Trembling Cow", 2, level=4, hp_factor=1.00, tags=("beast",)),
    _monster("trembling_ox", "Trembling Ox", 2, level=5, hp_factor=1.20, tags=("beast",)),
    _monster(
        "windwasp", "Windwasp", 2, level=5, hp_factor=0.72,
        tags=("flying", "insect", "needle_drop"),
        sources=("https://swordartonline.fandom.com/wiki/Windwasp",),
        notes="Its Needle of Windwasp drop is canon; exact level is simulation.",
    ),

    # Floor 3
    _monster("coppice_spider", "Coppice Spider", 3, level=5, hp_factor=0.90, tags=("spider",)),
    _monster("dark_elven_wolf_handler", "Dark Elven Wolf Handler", 3, level=7, hp_factor=1.05, tags=("dark_elf", "humanoid")),
    _monster("elder_treant", "Elder Treant", 3, level=8, hp_factor=1.45, tags=("plant", "treant")),
    _monster("elder_sapling", "Elder Sapling", 3, level=6, hp_factor=0.95, tags=("plant", "treant")),
    _monster("fallen_elf_warrior", "Fallen Elf Warrior", 3, level=7, hp_factor=1.10, tags=("fallen_elf", "humanoid")),
    _monster("forest_elven_falconer", "Forest Elven Falconer", 3, level=7, hp_factor=1.00, tags=("forest_elf", "humanoid", "ranged")),
    _monster("roaring_wolf", "Roaring Wolf", 3, level=6, hp_factor=0.92, tags=("beast",)),
    _monster("thicket_spider", "Thicket Spider", 3, level=6, hp_factor=0.88, tags=("spider",)),
    _monster("treant_sapling", "Treant Sapling", 3, level=5, hp_factor=0.90, tags=("plant", "treant")),

    # Floor 4
    _monster("dark_elven_gatekeeper", "Dark Elven Gatekeeper", 4, level=9, hp_factor=1.30, tags=("dark_elf", "humanoid", "elite")),
    _monster("fallen_elven_foreman", "Fallen Elven Foreman", 4, level=8, hp_factor=1.15, tags=("fallen_elf", "humanoid")),
    _monster("fallen_elven_guard", "Fallen Elven Guard", 4, level=8, hp_factor=1.10, tags=("fallen_elf", "humanoid")),
    _monster("forest_elven_heavy_warrior", "Forest Elven Heavy Warrior", 4, level=9, hp_factor=1.35, tags=("forest_elf", "humanoid", "armored")),
    _monster("forest_elven_inferior_knight", "Forest Elven Inferior Knight", 4, level=8, hp_factor=1.15, tags=("forest_elf", "humanoid")),
    _monster("forest_elven_light_warrior", "Forest Elven Light Warrior", 4, level=8, hp_factor=1.00, tags=("forest_elf", "humanoid")),
    _monster("forest_elven_rower", "Forest Elven Rower", 4, level=7, hp_factor=1.00, tags=("forest_elf", "humanoid")),
    _monster("forest_elven_spearman", "Forest Elven Spearman", 4, level=8, hp_factor=1.05, tags=("forest_elf", "humanoid", "spear")),
    _monster("forest_elven_swordsman", "Forest Elven Swordsman", 4, level=8, hp_factor=1.05, tags=("forest_elf", "humanoid", "sword")),
    _monster("gaudy_nepenthes", "Gaudy Nepenthes", 4, level=7, hp_factor=1.00, tags=("plant",)),
    _monster(
        "magnatherium", "Magnatherium", 4, level=10, hp_factor=3.2,
        tags=("rare_named_monster", "beast", "shipwright_of_yore"),
        sources=("https://swordartonline.fandom.com/wiki/Magnatherium",),
        notes="Rare named monster in the Bear Forest; it drops high-quality materials for Shipwright of Yore.",
    ),
    _monster(
        "scuttle_crab", "Scuttle Crab", 4, level=9, location="labyrinth", hp_factor=2.1,
        tags=("crustacean", "tough", "mouth_weak_point", "blind_breath"),
        sources=("https://swordartonline.fandom.com/wiki/Scuttle_Crab",),
        notes="Found in a sunken dungeon; known drops include gems, Great Crab Shell and crab meat.",
    ),

    # Floor 5-7
    _monster("mournful_wraith", "Mournful Wraith", 5, level=8, hp_factor=0.90, tags=("undead",)),
    _monster("sly_shrewman", "Sly Shrewman", 5, level=8, hp_factor=0.95, tags=("humanoid",)),
    _monster("moldy_mummy", "Moldy Mummy", 5, level=9, hp_factor=1.05, tags=("undead",)),
    _monster("annoying_wraith", "Annoying Wraith", 6, level=9, hp_factor=0.92, tags=("undead",)),
    _monster("covetous_ooze", "Covetous Ooze", 6, level=10, hp_factor=1.20, tags=("slime",)),
    _monster("argent_serpent", "Argent Serpent", 7, level=11, hp_factor=1.05, tags=("serpent",)),
    _monster("blazing_newt", "Blazing Newt", 7, level=11, hp_factor=1.00, tags=("reptile", "fire")),
    _monster("bouncy_slater", "Bouncy Slater", 7, level=10, hp_factor=0.90, tags=("insectoid",)),
    _monster("giant_pincerat", "Giant Pincerat", 7, level=12, hp_factor=1.35, tags=("beast",)),
    _monster("greasy_wormlizard", "Greasy Wormlizard", 7, level=11, hp_factor=1.10, tags=("reptile",)),
    _monster("hematomelibe", "Hematomelibe", 7, level=12, hp_factor=1.15, tags=("insectoid",)),

    # Later Aincrad
    _monster("kuchina_elite_assassin", "Kuchina Elite Assassin", 10, level=15, hp_factor=1.10, tags=("humanoid", "elite")),
    _monster(
        "killer_mantis", "Killer Mantis", 20, level=25, hp_factor=1.05,
        tags=("insect", "canon_cor_reward:180"),
        notes="Canon establishes a 180 Cor defeat reward; level is simulation.",
    ),
    _monster("maroon_wolf", "Maroon Wolf", 22, level=27, hp_factor=0.95, tags=("beast",)),
    _monster("dark_dwarf_miner", "Dark Dwarf Miner", 27, level=32, location="labyrinth", hp_factor=1.05, tags=("humanoid", "dwarf")),
    _monster("granite_elemental", "Granite Elemental", 27, level=33, location="labyrinth", hp_factor=1.45, tags=("elemental", "stone")),
    _monster("blood_wolf_leader", "Blood Wolf Leader", 28, level=34, hp_factor=1.25, tags=("beast", "elite")),
    _monster(
        "drunk_ape", "Drunk Ape", 35, level=40, hp_factor=1.35,
        tags=("beast", "club", "high_strength", "low_speed"),
        sources=("https://swordartonline.fandom.com/wiki/Drunk_Ape",),
        notes="One of the strongest monsters in Floor 35's Forest of Wandering; slow but powerful.",
    ),
    _monster("balloon_roussette", "Balloon Roussette", 39, level=44, hp_factor=0.95, tags=("flying",)),
    _monster("giant_ant", "Giant Ant", 46, level=51, hp_factor=1.10, tags=("insect",)),
    _monster("ant_queen", "Ant Queen", 46, level=54, hp_factor=2.8, tags=("insect", "elite")),
    _monster("garish_gerbera", "Garish Gerbera", 47, level=52, hp_factor=1.00, tags=("plant",)),
    _monster("giant_venus_fly_trap", "Giant Venus Fly Trap", 47, level=53, hp_factor=1.20, tags=("plant",)),
    _monster("land_anemone", "Land Anemone", 47, level=52, hp_factor=1.05, tags=("plant",)),
    _monster(
        "x_rphan_white_wyrm", "X'rphan the White Wyrm", 55, level=60,
        location="floor_55_west_mountain", hp_factor=7.0,
        tags=("field_boss", "dragon", "nocturnal", "crystallite_ingot_quest"),
        sources=("https://swordartonline.fandom.com/wiki/X%27rphan_the_White_Wyrm",),
        notes="Nocturnal Floor 55 West Mountain Field Boss associated with production of Crystallite Ingot.",
    ),
    _monster(
        "frozen_bone", "Frozen Bone", 55, level=59,
        location="floor_55_west_mountain", hp_factor=1.05, tags=("undead", "ice"),
    ),
    _monster("bull_slug", "Bull Slug", 61, level=66, hp_factor=1.10, tags=("slug",)),
    _monster(
        "ragout_rabbit", "Ragout Rabbit", 74, level=78, hp_factor=0.45,
        tags=("rare", "elusive", "s_rank_ingredient_drop"),
        sources=("https://swordartonline.fandom.com/wiki/74th_Floor_%28Aincrad%29",),
        notes="Ragout Rabbit is a known Floor 74 monster and drops S-rank Ragout Rabbit's Meat.",
    ),
    _monster(
        "lizardman_lord", "Lizardman Lord", 74, level=82, location="labyrinth", hp_factor=1.35,
        tags=("humanoid", "sword_skill:fell_crescent", "shield", "canon_reward:8120xp:1000cor"),
        sources=("https://swordartonline.fandom.com/wiki/Lizardman_Lord",),
        notes="Lives in the Floor 74 Labyrinth, can use Fell Crescent, and grants exactly 8120 EXP and 1000 Cor.",
        exact_level=True,
    ),
    _monster(
        "demonic_servant", "Demonic Servant", 74, level=80, location="labyrinth", hp_factor=1.45,
        tags=("undead", "skeleton", "sword_skill:vertical_square", "impact_weakness", "slash_resistance"),
        sources=("https://swordartonline.fandom.com/wiki/Demonic_Servant",),
        notes="Powerful skeletal swordsman able to use Vertical Square; weak to impact weapons and resistant to swords.",
    ),
)


AINCRAD_MONSTERS: dict[str, MonsterDefinition] = {row.monster_id: row for row in _MONSTER_ROWS}


def _sim_loot(row: MonsterDefinition) -> LootTable:
    col_center = max(5, row.floor_number * 3 + row.level)
    xp_center = max(12, row.level * 20)
    return LootTable(
        table_id=row.loot_table_id,
        col_min=max(0, int(col_center * 0.75)),
        col_max=max(1, int(col_center * 1.25)),
        xp_min=max(0, int(xp_center * 0.80)),
        xp_max=max(1, int(xp_center * 1.20)),
        provenance="simulation_floor_scaled",
    )


AINCRAD_MONSTER_LOOT_TABLES: dict[str, LootTable] = {
    row.loot_table_id: _sim_loot(row) for row in _MONSTER_ROWS
}

# Canon-locked rewards/drops where source material is explicit.
AINCRAD_MONSTER_LOOT_TABLES[AINCRAD_MONSTERS["windwasp"].loot_table_id] = LootTable(
    table_id=AINCRAD_MONSTERS["windwasp"].loot_table_id,
    col_min=12,
    col_max=26,
    xp_min=80,
    xp_max=125,
    entries=(LootEntry("needle_of_windwasp", 1.0),),
    provenance="canon_drop_plus_simulation_col_xp",
)
AINCRAD_MONSTER_LOOT_TABLES[AINCRAD_MONSTERS["magnatherium"].loot_table_id] = LootTable(
    table_id=AINCRAD_MONSTERS["magnatherium"].loot_table_id,
    col_min=80,
    col_max=150,
    xp_min=300,
    xp_max=450,
    entries=(LootEntry("legendary_bear_fats", 1.0),),
    provenance="canon_quest_drop_plus_simulation_col_xp",
)
AINCRAD_MONSTER_LOOT_TABLES[AINCRAD_MONSTERS["scuttle_crab"].loot_table_id] = LootTable(
    table_id=AINCRAD_MONSTERS["scuttle_crab"].loot_table_id,
    col_min=65,
    col_max=110,
    xp_min=260,
    xp_max=390,
    entries=(
        LootEntry("great_crab_shell", 1.0),
        LootEntry("great_crab_leg_meat", 0.75, 1, 2),
        LootEntry("great_crab_claw_meat", 0.45),
    ),
    provenance="canon_drop_identities_plus_simulation_rates_col_xp",
)
AINCRAD_MONSTER_LOOT_TABLES[AINCRAD_MONSTERS["killer_mantis"].loot_table_id] = LootTable(
    table_id=AINCRAD_MONSTERS["killer_mantis"].loot_table_id,
    col_min=180,
    col_max=180,
    xp_min=450,
    xp_max=620,
    provenance="canon_cor_reward_plus_simulation_xp",
)
AINCRAD_MONSTER_LOOT_TABLES[AINCRAD_MONSTERS["ragout_rabbit"].loot_table_id] = LootTable(
    table_id=AINCRAD_MONSTERS["ragout_rabbit"].loot_table_id,
    col_min=0,
    col_max=0,
    xp_min=900,
    xp_max=1200,
    entries=(LootEntry("ragout_rabbit_meat", 1.0),),
    provenance="canon_meat_drop_plus_simulation_xp",
)
AINCRAD_MONSTER_LOOT_TABLES[AINCRAD_MONSTERS["lizardman_lord"].loot_table_id] = LootTable(
    table_id=AINCRAD_MONSTERS["lizardman_lord"].loot_table_id,
    col_min=1000,
    col_max=1000,
    xp_min=8120,
    xp_max=8120,
    provenance="canon_exact_reward",
)


def apply_aincrad_monster_drop_items(catalog: Catalog) -> Catalog:
    """Seed only named monster drops required by the playable monster corpus."""
    rows = {
        "needle_of_windwasp": ItemTemplate(
            "needle_of_windwasp", "Needle of Windwasp", ItemKind.MATERIAL,
            weight=0.1, stack_limit=50, tags=("floor_2", "windwasp_drop"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=("https://swordartonline.fandom.com/wiki/Windwasp",),
                notes="Drop identity is canon; weight/stack are simulation.",
            ),
        ),
        "legendary_bear_fats": ItemTemplate(
            "legendary_bear_fats", "Legendary Bear Fats", ItemKind.QUEST,
            weight=1.0, stack_limit=5, tags=("floor_4", "shipwright_of_yore", "magnatherium_drop"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=("https://swordartonline.fandom.com/wiki/Magnatherium",),
                notes="High-quality quest material dropped by Magnatherium; weight/stack are simulation.",
            ),
        ),
        "great_crab_shell": ItemTemplate(
            "great_crab_shell", "Great Crab Shell", ItemKind.MATERIAL,
            weight=4.0, stack_limit=10, tags=("floor_4", "scuttle_crab_drop"),
            provenance=Provenance(ProvenanceKind.CANON_INFERRED, sources=("https://swordartonline.fandom.com/wiki/Scuttle_Crab",), notes="Drop identity is canon; weight/stack are simulation."),
        ),
        "great_crab_leg_meat": ItemTemplate(
            "great_crab_leg_meat", "Great Crab Leg Meat", ItemKind.FOOD,
            weight=1.0, stack_limit=10, tags=("floor_4", "scuttle_crab_drop"),
            provenance=Provenance(ProvenanceKind.CANON_INFERRED, sources=("https://swordartonline.fandom.com/wiki/Scuttle_Crab",), notes="Drop identity is canon; weight/stack are simulation."),
        ),
        "great_crab_claw_meat": ItemTemplate(
            "great_crab_claw_meat", "Great Crab Claw Meat", ItemKind.FOOD,
            weight=0.8, stack_limit=10, tags=("floor_4", "scuttle_crab_drop"),
            provenance=Provenance(ProvenanceKind.CANON_INFERRED, sources=("https://swordartonline.fandom.com/wiki/Scuttle_Crab",), notes="Drop identity is canon; weight/stack are simulation."),
        ),
    }
    for template_id, item in rows.items():
        catalog.items.setdefault(template_id, item)
    return catalog
