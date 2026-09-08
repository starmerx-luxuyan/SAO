from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.quests import CORE_QUESTS
from sao_mcp.domain.models import DamageType, ItemKind, Provenance, ProvenanceKind, WeaponClass, WeaponTemplate
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition
from sao_mcp.rules.quests import QuestDefinition, QuestObjectiveDefinition, QuestObjectiveKind, QuestReward


PROGRESSIVE_7 = "Sword Art Online Progressive Volume 7: Rhapsody of Crimson Heat (Start)"
QUEST_ID = "prisoners_of_the_tree_palace"
LAVIK_ID = "npc_floor7_lavik"
HARIN_CAPTAIN_ID = "npc_floor7_harin_guard_captain"
LAVIK_SABER_ID = "lavik_dark_elven_saber"
KIZMEL_SABER_ID = "kizmel_repaired_saber"
ELVEN_STOUT_SWORD_ID = "elven_stout_sword"


def _canon(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(PROGRESSIVE_7,), notes=notes)


def _inferred(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(PROGRESSIVE_7,), notes=notes)


def _sim(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, sources=(PROGRESSIVE_7,), notes=notes)


def apply_floor7_elfwar_corpus(catalog: Catalog) -> Catalog:
    catalog.weapons.setdefault(
        ELVEN_STOUT_SWORD_ID,
        WeaponTemplate(
            template_id=ELVEN_STOUT_SWORD_ID,
            name="Elven Stout Sword",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.ONE_HAND_SWORD,
            damage_type=DamageType.SLASH,
            attack_min=66,
            attack_max=82,
            required_level=12,
            required_strength=26,
            weight=25.0,
            base_durability=560,
            base_speed_ms=650,
            reach_m=1.7,
            tags=("elf_war", "forest_elf", "kizmel_temporary_weapon"),
            provenance=_inferred(
                "The Elven Stout Sword is a canon one-handed sword taken from a Forest Elf captain and loaned to Kizmel after Kysarah broke her saber. Numeric combat fields are simulation."
            ),
        ),
    )
    catalog.weapons.setdefault(
        KIZMEL_SABER_ID,
        WeaponTemplate(
            template_id=KIZMEL_SABER_ID,
            name="Kizmel's Saber",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.ONE_HAND_CURVED_SWORD,
            damage_type=DamageType.SLASH,
            attack_min=74,
            attack_max=92,
            required_level=1,
            required_strength=1,
            weight=23.0,
            base_durability=610,
            base_speed_ms=610,
            reach_m=1.75,
            tags=("elf_war", "kizmel", "dark_elf_saber"),
            provenance=_inferred(
                "Harin's confiscated-weapon store contains Kizmel's saber alongside the Elven Stout Sword. Its proper item name and numeric stats are not established here, so the template label is descriptive."
            ),
        ),
    )
    catalog.weapons.setdefault(
        LAVIK_SABER_ID,
        WeaponTemplate(
            template_id=LAVIK_SABER_ID,
            name="Lavik's Dark Elven Saber",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.ONE_HAND_CURVED_SWORD,
            damage_type=DamageType.SLASH,
            attack_min=88,
            attack_max=108,
            required_level=1,
            required_strength=1,
            weight=27.0,
            base_durability=760,
            base_speed_ms=680,
            reach_m=1.8,
            tags=("elf_war", "lavik", "dark_elf_saber"),
            provenance=_sim(
                "Lavik is canonically a formidable saber user and former Sandalwood Knights commander. The saber's proper name and all numeric weapon fields are simulation."
            ),
        ),
    )

    CORE_QUESTS.setdefault(
        QUEST_ID,
        QuestDefinition(
            quest_id=QUEST_ID,
            name="Prisoners of the Tree Palace",
            floor_number=7,
            giver_id=HARIN_CAPTAIN_ID,
            turn_in_id="npc_kizmel",
            objectives=(
                QuestObjectiveDefinition(
                    "escape_b2_cell",
                    QuestObjectiveKind.DISCOVER,
                    "harin_b2_cell_escaped",
                ),
                QuestObjectiveDefinition(
                    "recover_confiscated_weapons",
                    QuestObjectiveKind.DISCOVER,
                    "harin_confiscated_weapons_recovered",
                ),
                QuestObjectiveDefinition(
                    "meet_lavik",
                    QuestObjectiveKind.TALK,
                    LAVIK_ID,
                ),
                QuestObjectiveDefinition(
                    "rejoin_kizmel",
                    QuestObjectiveKind.TALK,
                    "npc_kizmel",
                ),
                QuestObjectiveDefinition(
                    "escape_harin_tree_palace",
                    QuestObjectiveKind.DISCOVER,
                    "harin_tree_palace_escaped",
                ),
            ),
            reward=QuestReward(),
            repeatable=False,
            provenance=_inferred(
                "Release-route Elf War quest triggered after the players are suspected of collaborating with the Fallen Elves and imprisoned beneath Harin Tree Palace. The canon quest explicitly requires escaping the cell, recovering confiscated weapons and rejoining Kizmel; this runtime also records the completed palace escape as the vertical-slice endpoint."
            ),
        ),
    )

    CORE_NPCS.setdefault(
        HARIN_CAPTAIN_ID,
        NPCDefinition(
            npc_id=HARIN_CAPTAIN_ID,
            name="Harin Guard Captain",
            home_location_id="floor_7_harin_tree_palace",
            roles=("dark_elf", "harin_guard", "arresting_officer"),
            quest_ids=(),
            knowledge_tags=("harin_tree_palace", "fallen_elf_suspects", "basement_prison", "confiscated_weapons"),
            provenance=_inferred(
                "The arrest is carried out by a Dark Elf captain and four soldiers. The personal name is not established here, so this descriptive NPC label is used."
            ),
        ),
    )
    CORE_NPCS.setdefault(
        LAVIK_ID,
        NPCDefinition(
            npc_id=LAVIK_ID,
            name="Lavik Fen Cortassios",
            home_location_id="floor_7_harin_lavik_cell",
            roles=("dark_elf", "prisoner", "fugitive", "former_sandalwood_knights_commander", "saber_user"),
            quest_ids=(),
            knowledge_tags=("harin_prison", "seventh_story_prison", "kizmel", "kysarah", "sandalwood_knights", "yofilis"),
            provenance=_canon(
                "Dark Elf imprisoned beneath Harin for roughly thirty years. After joining Kirito and Asuna's escape he is revealed to be the former commander of the Sandalwood Knights."
            ),
        ),
    )
    return catalog
