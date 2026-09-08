from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES, MonsterDefinition
from sao_mcp.domain.models import Provenance, ProvenanceKind
from sao_mcp.rules.loot import LootEntry, LootTable


PROGRESSIVE_7 = "Sword Art Online Progressive Volume 7: Rhapsody of Crimson Heat (Start)"
PROGRESSIVE_8 = "Sword Art Online Progressive Volume 8: Rhapsody of Crimson Heat (Finish)"


def _monster(
    monster_id: str,
    name: str,
    location_id: str,
    *,
    level: int,
    hp_factor: float = 1.0,
    tags: tuple[str, ...] = (),
    notes: str = "",
) -> MonsterDefinition:
    return MonsterDefinition(
        monster_id=monster_id,
        name=name,
        floor_number=7,
        level=level,
        location_id=location_id,
        hp_factor=hp_factor,
        quest_kill_id=monster_id,
        loot_table_id=f"aincrad_{monster_id}",
        tags=tags,
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=(PROGRESSIVE_7, PROGRESSIVE_8),
            notes=f"Monster identity and Floor 7 context/location are canon-backed where stated; Level {level}, HP factor and unspecified combat numbers are simulation. {notes}".strip(),
        ),
    )


def _empty_loot(monster_id: str, *, col: tuple[int, int], xp: tuple[int, int], entries=()) -> None:
    AINCRAD_MONSTER_LOOT_TABLES[f"aincrad_{monster_id}"] = LootTable(
        table_id=f"aincrad_{monster_id}",
        col_min=col[0],
        col_max=col[1],
        xp_min=xp[0],
        xp_max=xp[1],
        entries=tuple(entries),
        provenance="simulation_col_xp_and_drop_rates; named drops/observed drops are canon only where noted",
    )


def apply_floor7_monster_corpus(catalog: Catalog) -> Catalog:
    rows = {
        "verdian_lancer_beetle": _monster(
            "verdian_lancer_beetle",
            "Verdian Lancer Beetle",
            "floor_7_verdian_plains",
            level=14,
            hp_factor=1.05,
            tags=("insect", "flying", "horn_charge", "underside_weak_point", "ganglion_weak_point"),
            notes=(
                "Its full-speed horn can pierce plate armor; the underside leg-root ganglion is a weak point. "
                "A Healing Crystal was observed as a drop, but canon does not establish its probability."
            ),
        ),
        "verdian_poison_wasp": _monster(
            "verdian_poison_wasp",
            "Verdian Poison Wasp",
            "floor_7_verdian_plains",
            level=13,
            hp_factor=0.78,
            tags=("insect", "flying", "poison"),
            notes="A stronger Floor 7 poison-wasp variant encountered while farming the Verdian Plains.",
        ),
        "greasy_wormlizard": _monster(
            "greasy_wormlizard",
            "Greasy Worm Lizard",
            "floor_7_verdian_plains",
            level=13,
            hp_factor=1.10,
            tags=("reptile", "worm", "burrowing"),
            notes="Emerges from the ground and is described as a snake/earthworm/lizard-like creature.",
        ),
        "verdian_rock_boar": _monster(
            "verdian_rock_boar",
            "Verdian Rock Boar",
            "floor_7_verdian_plains",
            level=15,
            hp_factor=1.35,
            tags=("beast", "boar", "large"),
            notes="Large Floor 7 monster; its size makes it unsuitable for the Monster Arena cage.",
        ),
        "verdian_bighorn": _monster(
            "verdian_bighorn",
            "Verdian Bighorn",
            "floor_7_verdian_plains",
            level=15,
            hp_factor=1.28,
            tags=("beast", "bighorn", "monster_arena_eligible"),
            notes="Canon Monster Arena contender; historically defeated Tiny Glyptodont in the all-in match.",
        ),
        "rusty_lykaon": _monster(
            "rusty_lykaon",
            "Rusty Lykaon",
            "floor_7_field_of_bones",
            level=14,
            hp_factor=1.02,
            tags=("beast", "lykaon", "pack_hunter", "monster_arena_eligible"),
            notes="Dog-like Floor 7 monster; individually manageable but naturally dangerous in packs. Arena specimen later revealed as a Storm Lykaon.",
        ),
        "storm_lykaon": _monster(
            "storm_lykaon",
            "Storm Lykaon",
            "floor_7_monster_arena",
            level=17,
            hp_factor=1.35,
            tags=("beast", "lykaon", "upper_variant", "rotating_storm_attack"),
            notes="Higher Rusty Lykaon variant with a body-spinning storm/tornado-like special attack; natural Floor 7 habitat is not identified.",
        ),
        "bouncy_slater": _monster(
            "bouncy_slater",
            "Bouncy Slater",
            "floor_7_monster_arena",
            level=14,
            hp_factor=0.90,
            tags=("insectoid", "monster_arena_eligible"),
            notes="Canon opponent in the first observed Volupta Monster Arena match.",
        ),
        "tiny_glyptodont": _monster(
            "tiny_glyptodont",
            "Tiny Glyptodont",
            "floor_7_monster_arena",
            level=15,
            hp_factor=1.18,
            tags=("beast", "armored", "monster_arena_eligible"),
            notes="Canon Monster Arena contender in the later all-in match against Verdian Bighorn.",
        ),
        "hematomelibe": _monster(
            "hematomelibe",
            "Hematomelibe",
            "floor_7_looserock_forest",
            level=15,
            hp_factor=1.15,
            tags=("insectoid", "looserock_forest"),
        ),
        "dark_elven_royal_guard": _monster(
            "dark_elven_royal_guard",
            "Dark Elven Royal Guard",
            "floor_7_harin_tree_palace",
            level=18,
            hp_factor=1.45,
            tags=("dark_elf", "humanoid", "royal_guard", "elite"),
            notes="Named Dark Elf military monster/NPC type associated with Floor 7.",
        ),
        "tiny_lurking_spider": _monster(
            "tiny_lurking_spider",
            "Tiny Lurking Spider",
            "floor_7_labyrinth",
            level=17,
            hp_factor=0.78,
            tags=("spider", "labyrinth", "ambush"),
        ),
        "armor_plated_monitor": _monster(
            "armor_plated_monitor",
            "Armor-Plated Monitor",
            "floor_7_labyrinth",
            level=18,
            hp_factor=1.42,
            tags=("reptile", "labyrinth", "armored"),
        ),
    }
    AINCRAD_MONSTERS.update(rows)

    _empty_loot(
        "verdian_lancer_beetle",
        col=(44, 72),
        xp=(150, 220),
        entries=(LootEntry("healing_crystal", 0.03),),
    )
    for monster_id, col, xp in (
        ("verdian_poison_wasp", (34, 55), (120, 180)),
        ("greasy_wormlizard", (38, 62), (130, 195)),
        ("verdian_rock_boar", (58, 92), (190, 280)),
        ("verdian_bighorn", (62, 98), (205, 300)),
        ("rusty_lykaon", (48, 78), (165, 245)),
        ("storm_lykaon", (80, 125), (285, 390)),
        ("bouncy_slater", (45, 72), (155, 225)),
        ("tiny_glyptodont", (58, 90), (190, 275)),
        ("hematomelibe", (55, 85), (180, 260)),
        ("dark_elven_royal_guard", (95, 145), (360, 500)),
        ("tiny_lurking_spider", (48, 76), (180, 260)),
        ("armor_plated_monitor", (82, 126), (300, 430)),
    ):
        _empty_loot(monster_id, col=col, xp=xp)
    return catalog
