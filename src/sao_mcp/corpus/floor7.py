from __future__ import annotations

from sao_mcp.corpus.bosses import CORE_BOSS_ACTIONS, CORE_BOSSES, BossActionDefinition, BossDefinition, BossPhaseDefinition
from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import DamageType, ItemKind, ItemTemplate, Provenance, ProvenanceKind, WeaponClass, WeaponTemplate
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition


PROGRESSIVE_7 = "Sword Art Online Progressive Volume 7: Rhapsody of Crimson Heat (Start)"
PROGRESSIVE_8 = "Sword Art Online Progressive Volume 8: Rhapsody of Crimson Heat (Finish)"

VOLCOIN_ID = "volcoin"
SWORD_OF_VOLUPTA_ID = "sword_of_volupta"
NIRRNIR_ID = "npc_floor7_nirrnir_nachtoy"
KIO_ID = "npc_floor7_kio"
BARDUN_ID = "npc_floor7_bardun_korloy"
AGHYELLR_ID = "aghyellr_the_igneous_wyrm"
AGHYELLR_WEAPON_ID = "aghyellr_natural_attack"

VOLCOIN_COR_VALUE = 100
SWORD_OF_VOLUPTA_PRICE_VOLCOIN = 100_000


def _canon(notes: str, source: str = PROGRESSIVE_7) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(source,), notes=notes)


def _inferred(notes: str, *sources: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=tuple(sources) or (PROGRESSIVE_7,), notes=notes)


def _sim(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, notes=notes)


def apply_floor7_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        VOLCOIN_ID,
        ItemTemplate(
            template_id=VOLCOIN_ID,
            name="Volcoin",
            kind=ItemKind.MISC,
            weight=0.0,
            stack_limit=1_000_000,
            base_value_col=VOLCOIN_COR_VALUE,
            tags=("floor_7", "volupta", "grand_casino", "casino_chip", "currency"),
            provenance=_canon(
                "Official Volupta Grand Casino chip. One Volcoin is worth 100 Cor; runtime keeps casino balances as currency metadata rather than physical-weight stacks."
            ),
        ),
    )
    catalog.weapons.setdefault(
        SWORD_OF_VOLUPTA_ID,
        WeaponTemplate(
            template_id=SWORD_OF_VOLUPTA_ID,
            name="Sword of Volupta",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.ONE_HAND_SWORD,
            damage_type=DamageType.SLASH,
            attack_min=88,
            attack_max=106,
            required_level=17,
            required_strength=36,
            weight=24.0,
            base_durability=720,
            base_speed_ms=590,
            reach_m=1.75,
            tags=(
                "floor_7",
                "volupta_grand_casino_prize",
                "advertised_name_sword_of_volupta",
                "sealed_true_identity",
                "hp_regeneration",
                "poison_nullification",
                "guaranteed_critical",
                "experience_drain_without_civis_nocte",
            ),
            provenance=_inferred(
                "The casino advertises Falhari's Sword of Volupta for 100,000 Volcoins. Its listed effects are continuous wound/HP recovery, poison nullification and guaranteed critical hits. "
                "The weapon's later-revealed true identity is Doleful Nocturne, with an experience-drain penalty for non-Night users. The public template name intentionally remains Sword of Volupta so ordinary inventory/UI does not reveal that identity early. Attack, requirements, weight, durability and timing are simulation.",
                PROGRESSIVE_7,
                PROGRESSIVE_8,
            ),
        ),
    )

    CORE_NPCS.setdefault(
        NIRRNIR_ID,
        NPCDefinition(
            npc_id=NIRRNIR_ID,
            name="Nirrnir Nachtoy",
            home_location_id="floor_7_volupta_grand_casino",
            roles=("nachtoy_matriarch", "casino_co_ruler", "monster_handler", "dominus_nocte"),
            quest_ids=(),
            knowledge_tags=("volupta", "monster_arena", "storm_lykaon", "korloy_conspiracy", "sealed_sword_identity", "civis_nocte"),
            provenance=_canon("Young head of House Nachtoy, one of the two families controlling the Volupta Grand Casino.", PROGRESSIVE_7),
        ),
    )
    CORE_NPCS.setdefault(
        KIO_ID,
        NPCDefinition(
            npc_id=KIO_ID,
            name="Kio",
            home_location_id="floor_7_volupta_grand_casino",
            roles=("warrior_maid", "nirrnir_retainer", "escort"),
            quest_ids=(),
            knowledge_tags=("nirrnir", "nachtoy", "korloy", "casino_stables", "sword_of_volupta", "aghyellr"),
            provenance=_canon("Nirrnir's warrior maid and close retainer during the Floor 7 casino and dragon-blood storyline.", PROGRESSIVE_7),
        ),
    )
    CORE_NPCS.setdefault(
        BARDUN_ID,
        NPCDefinition(
            npc_id=BARDUN_ID,
            name="Bardun Korloy",
            home_location_id="floor_7_volupta_grand_casino",
            roles=("korloy_patriarch", "casino_co_ruler", "antagonist"),
            quest_ids=(),
            knowledge_tags=("volupta", "monster_arena", "korloy_stables", "nachtoy_rivalry", "argent_serpent"),
            provenance=_canon("Patriarch of House Korloy and rival co-ruler of the Volupta Grand Casino.", PROGRESSIVE_7),
        ),
    )

    catalog.weapons.setdefault(
        AGHYELLR_WEAPON_ID,
        WeaponTemplate(
            template_id=AGHYELLR_WEAPON_ID,
            name="Aghyellr Claws, Tail and Flame",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER,
            damage_type=DamageType.MIXED,
            attack_min=215,
            attack_max=280,
            required_level=1,
            required_strength=1,
            weight=0.0,
            base_durability=30_000,
            base_speed_ms=980,
            reach_m=5.2,
            provenance=_sim("Natural weapon package for the Floor 7 dragon. Canon attack identities feed tags; numeric weapon stats are simulation."),
        ),
    )

    actions = {
        "aghyellr_foreclaw_sweep": BossActionDefinition(
            "aghyellr_foreclaw_sweep", "Foreclaw Sweep", 720, 320, 520, 1.15, 4.8,
            accuracy_modifier=0.02, max_targets=3, stagger_ms=430,
            tags=("claw", "sweep", "area"),
            provenance=_sim("Playable timing/damage for Aghyellr's canon forelimb attacks."),
        ),
        "aghyellr_tail_sweep": BossActionDefinition(
            "aghyellr_tail_sweep", "Igneous Tail Sweep", 980, 430, 670, 1.22, 6.4,
            accuracy_modifier=-0.04, max_targets=7, stagger_ms=720,
            tags=("tail", "sweep", "area"),
            provenance=_sim("Playable timing/damage for the canon tail attacks and battlefield-rubble pressure."),
        ),
        "aghyellr_flame_breath": BossActionDefinition(
            "aghyellr_flame_breath", "Flame Breath", 1450, 920, 1150, 1.68, 11.0,
            accuracy_modifier=-0.08, max_targets=10, stagger_ms=250,
            tags=("flame", "breath", "area", "cone"),
            provenance=_inferred("Aghyellr breathes fire; exact telegraph, reach, target cap and multiplier are simulation.", PROGRESSIVE_8),
        ),
        "aghyellr_aerial_crash": BossActionDefinition(
            "aghyellr_aerial_crash", "Aerial Crash", 2200, 520, 1600, 1.95, 14.0,
            accuracy_modifier=-0.15, max_targets=20, stagger_ms=1300,
            tags=("flight", "landing", "shockwave", "area"),
            provenance=_inferred(
                "Late in the official-service battle Aghyellr takes flight and crashes back down, producing a room-wide impact. Exact mechanics are simulation.",
                PROGRESSIVE_8,
            ),
        ),
    }
    CORE_BOSS_ACTIONS.update({key: value for key, value in actions.items() if key not in CORE_BOSS_ACTIONS})
    CORE_BOSSES.setdefault(
        AGHYELLR_ID,
        BossDefinition(
            boss_id=AGHYELLR_ID,
            name="Aghyellr the Igneous Wyrm",
            floor_number=7,
            level=27,
            hp_bars=6,
            hp_per_bar=13_800,
            strength=126,
            agility=58,
            armor=390,
            evasion=7,
            phases=(
                BossPhaseDefinition(
                    "ground_wyrm",
                    "Grounded Igneous Wyrm",
                    0,
                    AGHYELLR_WEAPON_ID,
                    None,
                    ("aghyellr_foreclaw_sweep", "aghyellr_tail_sweep", "aghyellr_flame_breath"),
                    _inferred(
                        "Ground combat uses forelimbs, tail and fire breath. Intimidating Gaze is handled by the Floor 7 scenario because it applies a level-sensitive status rather than ordinary damage.",
                        PROGRESSIVE_8,
                    ),
                ),
                BossPhaseDefinition(
                    "airborne_wyrm",
                    "Airborne Igneous Wyrm",
                    5,
                    AGHYELLR_WEAPON_ID,
                    None,
                    ("aghyellr_flame_breath", "aghyellr_aerial_crash"),
                    _inferred("The late battle includes Aghyellr taking flight; exact phase threshold is simulation.", PROGRESSIVE_8),
                ),
            ),
            initial_minion_template_id=None,
            initial_minion_count=0,
            minions_per_bar_depletion=0,
            minion_spawn_bar_depletions=(),
            last_attack_bonus_template_id=None,
            provenance=_inferred(
                "Floor 7 Floor Boss. Canon identity is Aghyellr the Igneous Wyrm, a roughly ten-metre fire wyrm with a head about four metres high. "
                "Official-service additions include Intimidating Gaze; HP/bar combat numbers are simulation calibration.",
                PROGRESSIVE_8,
            ),
        ),
    )
    return catalog
