from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import (
    DamageType,
    ItemKind,
    ItemTemplate,
    Provenance,
    ProvenanceKind,
    SkillDefinition,
    SkillKind,
    SwordSkillDefinition,
    WeaponClass,
    WeaponTemplate,
)
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition


PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
KIZMEL_ID = "npc_kizmel"
BOUHROUM_ID = "npc_floor6_bouhroum"
GINDO_ID = "pc_floor6_gindo"
KYSARAH_ID = "npc_floor6_kysarah"
AGATE_KEY_ID = "elf_war_agate_key"
SACRED_KEY_BAG_ID = "elf_war_four_sacred_keys_bag"
MEDITATION_SKILL_ID = "meditation"
TSUMUJIGURUMA_ID = "tsumujiguruma"
KYSARAH_KATANA_ID = "kysarah_unnamed_katana"


def _canon(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(PROGRESSIVE_6,), notes=notes)


def _inferred(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(PROGRESSIVE_6,), notes=notes)


def apply_floor6_elfwar_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        AGATE_KEY_ID,
        ItemTemplate(
            template_id=AGATE_KEY_ID,
            name="Agate Key",
            kind=ItemKind.QUEST,
            weight=0.12,
            stack_limit=1,
            tags=("floor_6", "elf_war", "sacred_key", "agate_key"),
            provenance=_canon(
                "Sacred Elf War key recovered by Kirito, Asuna and Kizmel from the southern Floor 6 key shrine and returned to Castle Galey. Weight is simulation."
            ),
        ),
    )
    catalog.items.setdefault(
        SACRED_KEY_BAG_ID,
        ItemTemplate(
            template_id=SACRED_KEY_BAG_ID,
            name="Bag of Four Elf War Sacred Keys",
            kind=ItemKind.QUEST,
            weight=0.65,
            stack_limit=1,
            tags=("floor_6", "elf_war", "sacred_keys", "count_4", "kysarah_target"),
            provenance=_inferred(
                "The Castle Galey/Qusack incident explicitly involves a bag containing the four sacred Elf War keys collected so far. This container item preserves the canonical count without inventing unverified individual key names; weight is simulation."
            ),
        ),
    )

    catalog.skills.setdefault(
        MEDITATION_SKILL_ID,
        SkillDefinition(
            skill_id=MEDITATION_SKILL_ID,
            name="Meditation",
            kind=SkillKind.EXTRA,
            description="Extra Skill learned through Bouhroum's three-hour concentration trial on Floor 6.",
            provenance=_canon(
                "Bouhroum's Floor 6 trial grants Meditation; on completion Kirito immediately received 500 proficiency and the Awakening mod when equipping it."
            ),
        ),
    )
    catalog.sword_skills.setdefault(
        TSUMUJIGURUMA_ID,
        SwordSkillDefinition(
            skill_id=TSUMUJIGURUMA_ID,
            name="Tsumujiguruma",
            weapon_class=WeaponClass.KATANA,
            prerequisite_proficiency=620.0,
            hits=(1.35,),
            windup_ms=920,
            active_ms=420,
            post_motion_ms=760,
            accuracy_modifier=-0.03,
            lunge_m=2.6,
            stagger=0.9,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_6,),
                notes=(
                    "Tsumujiguruma is a canon Katana Sword Skill used by Kysarah to knock Kirito's party and Qusack away during the key theft. "
                    "Timing, proficiency threshold and multipliers are simulation calibration."
                ),
            ),
        ),
    )
    catalog.weapons.setdefault(
        KYSARAH_KATANA_ID,
        WeaponTemplate(
            template_id=KYSARAH_KATANA_ID,
            name="Kysarah's Katana",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.KATANA,
            damage_type=DamageType.SLASH,
            attack_min=158,
            attack_max=202,
            required_level=1,
            required_strength=1,
            weight=32,
            base_durability=780,
            base_speed_ms=650,
            reach_m=1.75,
            provenance=Provenance(
                ProvenanceKind.SIMULATION,
                sources=(PROGRESSIVE_6,),
                notes="Kysarah canonically uses the Katana skill Tsumujiguruma; the weapon's proper name and numeric stats are not established here, so this template is descriptive simulation scaffolding."
            ),
        ),
    )

    CORE_NPCS.setdefault(
        KIZMEL_ID,
        NPCDefinition(
            npc_id=KIZMEL_ID,
            name="Kizmel",
            home_location_id="floor_6_castle_galey",
            roles=("dark_elf", "royal_guard", "elf_war_companion", "swordswoman"),
            quest_ids=(),
            knowledge_tags=("elf_war", "sacred_keys", "castle_galey", "fallen_elves", "kysarah"),
            provenance=_canon(
                "Dark Elven Royal Guard and long-running Elf War campaign companion who reunites with Kirito and Asuna at Castle Galey on Floor 6."
            ),
        ),
    )
    CORE_NPCS.setdefault(
        BOUHROUM_ID,
        NPCDefinition(
            npc_id=BOUHROUM_ID,
            name="Bouhroum the Storyteller",
            home_location_id="floor_6_castle_galey_storyteller_summit",
            roles=("dark_elf", "storyteller", "meditation_trainer", "awakening_trainer"),
            quest_ids=(),
            knowledge_tags=("meditation", "awakening", "fallen_elf_poison", "castle_galey_spirit_tree"),
            provenance=_canon(
                "Dark Elven storyteller living above Castle Galey. His three-hour concentration trial grants Meditation and its Awakening mod on the release route."
            ),
        ),
    )
    CORE_NPCS.setdefault(
        GINDO_ID,
        NPCDefinition(
            npc_id=GINDO_ID,
            name="Gindo",
            home_location_id="floor_6_castle_galey",
            roles=("named_player", "qusack_leader", "heavy_spearman", "coerced_saboteur"),
            quest_ids=(),
            knowledge_tags=("qusack", "hostages", "black_poncho_player", "spirit_tree_poisoning"),
            provenance=_canon(
                "Leader of the quest-focused guild Qusack. His guildmates are taken hostage by the black-poncho PK instigator, forcing him to poison Castle Galey's spirit-tree spring."
            ),
        ),
    )
    CORE_NPCS.setdefault(
        KYSARAH_ID,
        NPCDefinition(
            npc_id=KYSARAH_ID,
            name="Kysarah the Ransacker",
            home_location_id="floor_6_qusack_rescue_cave",
            roles=("fallen_elf", "adjutant", "ransacker", "katana_user", "key_thief"),
            quest_ids=(),
            knowledge_tags=("elf_war_keys", "paired_iron_keys", "combined_iron_key", "general_nltzahh", "tsumujiguruma"),
            provenance=_canon(
                "Fallen Elf adjutant who attacks the Qusack rescue party, steals the four sacred keys, coerces the players into surrendering Cylon's and Theano's iron keys, and crushes the repelling pair into a single key despite the charm."
            ),
        ),
    )
    return catalog
