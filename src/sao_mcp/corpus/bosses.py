from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import (
    ArmorTemplate,
    DamageType,
    ItemKind,
    Provenance,
    ProvenanceKind,
    WeaponClass,
    WeaponTemplate,
)


@dataclass(slots=True, frozen=True)
class BossActionDefinition:
    action_id: str
    name: str
    telegraph_ms: int
    active_ms: int
    recovery_ms: int
    damage_multiplier: float
    reach_m: float
    accuracy_modifier: float = 0.0
    max_targets: int = 1
    stagger_ms: int = 0
    tags: tuple[str, ...] = ()
    provenance: Provenance = Provenance(ProvenanceKind.SIMULATION)


@dataclass(slots=True, frozen=True)
class BossPhaseDefinition:
    phase_id: str
    name: str
    activate_after_depleted_bars: int
    weapon_template_id: str
    offhand_template_id: str | None
    action_ids: tuple[str, ...]
    provenance: Provenance


@dataclass(slots=True, frozen=True)
class BossDefinition:
    boss_id: str
    name: str
    floor_number: int
    level: int
    hp_bars: int
    hp_per_bar: int
    strength: int
    agility: int
    armor: int
    evasion: int
    phases: tuple[BossPhaseDefinition, ...]
    initial_minion_template_id: str | None
    initial_minion_count: int
    minions_per_bar_depletion: int
    minion_spawn_bar_depletions: tuple[int, ...]
    last_attack_bonus_template_id: str | None
    provenance: Provenance


@dataclass(slots=True, frozen=True)
class BossMinionDefinition:
    template_id: str
    name: str
    level: int
    hp: int
    strength: int
    agility: int
    armor: int
    evasion: int
    weapon_template_id: str
    provenance: Provenance


ILLFANG_ACTIONS: dict[str, BossActionDefinition] = {
    "illfang_overhead_cleave": BossActionDefinition(
        "illfang_overhead_cleave",
        "Bone Axe Overhead Cleave",
        telegraph_ms=850,
        active_ms=260,
        recovery_ms=520,
        damage_multiplier=1.28,
        reach_m=2.35,
        accuracy_modifier=-0.02,
        max_targets=1,
        stagger_ms=420,
        tags=("axe", "heavy", "single_target"),
        provenance=Provenance(
            ProvenanceKind.SIMULATION,
            notes="Playable attack timing and multiplier derived from Illfang's canon bone-axe fighting style.",
        ),
    ),
    "illfang_sweeping_axe": BossActionDefinition(
        "illfang_sweeping_axe",
        "Sweeping Bone Axe",
        telegraph_ms=1050,
        active_ms=320,
        recovery_ms=680,
        damage_multiplier=0.88,
        reach_m=3.0,
        accuracy_modifier=-0.07,
        max_targets=4,
        stagger_ms=260,
        tags=("axe", "sweep", "area"),
        provenance=Provenance(
            ProvenanceKind.SIMULATION,
            notes="Area-attack geometry/timing is runtime combat calibration.",
        ),
    ),
    "illfang_shield_bash": BossActionDefinition(
        "illfang_shield_bash",
        "Leather Buckler Bash",
        telegraph_ms=560,
        active_ms=150,
        recovery_ms=390,
        damage_multiplier=0.52,
        reach_m=1.45,
        accuracy_modifier=0.07,
        max_targets=1,
        stagger_ms=900,
        tags=("shield", "control", "single_target"),
        provenance=Provenance(
            ProvenanceKind.SIMULATION,
            notes="Control action is runtime calibration around the canon buckler equipment.",
        ),
    ),
    "illfang_nodachi_combo": BossActionDefinition(
        "illfang_nodachi_combo",
        "Nodachi Sword-Skill Combo",
        telegraph_ms=690,
        active_ms=720,
        recovery_ms=930,
        damage_multiplier=1.82,
        reach_m=3.15,
        accuracy_modifier=0.06,
        max_targets=1,
        stagger_ms=520,
        tags=("nodachi", "katana_skill", "combo", "lethal"),
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
            notes=(
                "Illfang's formal-service final phase uses the hidden long blade and Katana-class techniques. "
                "Exact action timing/damage is simulation calibration."
            ),
        ),
    ),
    "illfang_nodachi_whirl": BossActionDefinition(
        "illfang_nodachi_whirl",
        "Nodachi Circular Slash",
        telegraph_ms=940,
        active_ms=460,
        recovery_ms=820,
        damage_multiplier=1.05,
        reach_m=3.35,
        accuracy_modifier=-0.02,
        max_targets=6,
        stagger_ms=340,
        tags=("nodachi", "katana_skill", "area"),
        provenance=Provenance(
            ProvenanceKind.SIMULATION,
            sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
            notes="Specific circular attack package is runtime calibration for the canon final-phase weapon style.",
        ),
    ),
}


ILLFANG = BossDefinition(
    boss_id="illfang_the_kobold_lord",
    name="Illfang the Kobold Lord",
    floor_number=1,
    level=6,
    hp_bars=4,
    hp_per_bar=3600,
    strength=36,
    agility=28,
    armor=145,
    evasion=7,
    phases=(
        BossPhaseDefinition(
            "axe_buckler",
            "Bone Axe & Buckler",
            activate_after_depleted_bars=0,
            weapon_template_id="illfang_bone_axe",
            offhand_template_id="illfang_leather_buckler",
            action_ids=(
                "illfang_overhead_cleave",
                "illfang_sweeping_axe",
                "illfang_shield_bash",
            ),
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
                notes="Illfang fights the first three HP bars with a bone axe and leather buckler.",
            ),
        ),
        BossPhaseDefinition(
            "nodachi",
            "Hidden Nodachi",
            activate_after_depleted_bars=3,
            weapon_template_id="illfang_nodachi",
            offhand_template_id=None,
            action_ids=("illfang_nodachi_combo", "illfang_nodachi_whirl"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
                notes=(
                    "On the fourth HP bar the formal-service encounter changes to the concealed long blade, "
                    "invalidating beta-derived weapon expectations."
                ),
            ),
        ),
    ),
    initial_minion_template_id="ruin_kobold_sentinel",
    initial_minion_count=3,
    minions_per_bar_depletion=3,
    minion_spawn_bar_depletions=(1, 2, 3),
    last_attack_bonus_template_id="coat_of_midnight",
    provenance=Provenance(
        ProvenanceKind.CANON_INFERRED,
        sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
        notes=(
            "Boss identity, Floor 1 placement, four HP bars, Sentinel reinforcement structure, weapon-phase change, "
            "and Last Attack bonus identity are canon. Boss level, HP values and numeric combat stats are simulation."
        ),
    ),
)


RUIN_KOBOLD_SENTINEL = BossMinionDefinition(
    template_id="ruin_kobold_sentinel",
    name="Ruin Kobold Sentinel",
    level=4,
    hp=1050,
    strength=24,
    agility=21,
    armor=82,
    evasion=4,
    weapon_template_id="ruin_kobold_halberd",
    provenance=Provenance(
        ProvenanceKind.CANON_INFERRED,
        sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
        notes="Minion identity and polearm/halberd role are canon; all numeric combat stats are simulation.",
    ),
)


CORE_BOSSES: dict[str, BossDefinition] = {ILLFANG.boss_id: ILLFANG}
CORE_BOSS_MINIONS: dict[str, BossMinionDefinition] = {
    RUIN_KOBOLD_SENTINEL.template_id: RUIN_KOBOLD_SENTINEL
}
CORE_BOSS_ACTIONS = ILLFANG_ACTIONS


def apply_boss_catalog_seed(catalog):
    catalog.weapons.setdefault(
        "illfang_bone_axe",
        WeaponTemplate(
            template_id="illfang_bone_axe",
            name="Illfang's Bone Axe",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.TWO_HAND_AXE,
            damage_type=DamageType.BLUNT,
            attack_min=72,
            attack_max=94,
            required_level=1,
            required_strength=1,
            weight=48,
            base_durability=5000,
            base_speed_ms=1020,
            reach_m=2.25,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
                notes="Weapon identity is canon; numeric stats are simulation.",
            ),
        ),
    )
    catalog.weapons.setdefault(
        "illfang_nodachi",
        WeaponTemplate(
            template_id="illfang_nodachi",
            name="Illfang's Nodachi",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.KATANA,
            damage_type=DamageType.SLASH,
            attack_min=88,
            attack_max=116,
            required_level=1,
            required_strength=1,
            weight=34,
            base_durability=5000,
            base_speed_ms=760,
            reach_m=2.75,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
                notes="Formal-service final-phase long-blade identity is canon-inferred; numeric stats are simulation.",
            ),
        ),
    )
    catalog.weapons.setdefault(
        "ruin_kobold_halberd",
        WeaponTemplate(
            template_id="ruin_kobold_halberd",
            name="Ruin Kobold Halberd",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.SPEAR,
            damage_type=DamageType.MIXED,
            attack_min=44,
            attack_max=59,
            required_level=1,
            required_strength=1,
            weight=29,
            base_durability=3200,
            base_speed_ms=860,
            reach_m=2.65,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
                notes="Sentinel polearm identity is canon-inferred; numeric stats are simulation.",
            ),
        ),
    )
    catalog.armors.setdefault(
        "illfang_leather_buckler",
        ArmorTemplate(
            template_id="illfang_leather_buckler",
            name="Illfang's Leather Buckler",
            kind=ItemKind.SHIELD,
            weight=16,
            armor=34,
            base_durability=4000,
            slot="offhand",
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
                notes="Buckler identity is canon; armor/durability/weight are simulation.",
            ),
        ),
    )
    catalog.armors.setdefault(
        "coat_of_midnight",
        ArmorTemplate(
            template_id="coat_of_midnight",
            name="Coat of Midnight",
            kind=ItemKind.ARMOR,
            weight=14,
            armor=38,
            base_durability=440,
            slot="body",
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=("Sword Art Online Progressive Volume 1: Aria of a Starless Night",),
                notes="Last Attack bonus identity is canon; runtime defensive stats are simulation.",
            ),
        ),
    )
    return catalog
