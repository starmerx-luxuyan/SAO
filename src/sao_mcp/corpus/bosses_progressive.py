from __future__ import annotations

from sao_mcp.corpus.bosses import (
    BossActionDefinition,
    BossDefinition,
    BossMinionDefinition,
    BossPhaseDefinition,
)
from sao_mcp.domain.models import DamageType, ItemKind, Provenance, ProvenanceKind, WeaponClass, WeaponTemplate


P1 = "Sword Art Online Progressive Volume 1: Rondo of a Fragile Blade"
P2 = "Sword Art Online Progressive Volume 2: Concerto of Black and White"
P3 = "Sword Art Online Progressive Volume 3: Barcarolle of Froth"
P4 = "Sword Art Online Progressive Volume 4: Scherzo of Deep Night"


def _canon(source: str, notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(source,), notes=notes)


def _inferred(source: str, notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(source,), notes=notes)


def _sim(source: str, notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, sources=(source,), notes=notes)


PROGRESSIVE_BOSS_ACTIONS: dict[str, BossActionDefinition] = {
    # Floor 2 — Asterius and the Taurus mid-bosses.
    "asterius_hammer_sweep": BossActionDefinition(
        "asterius_hammer_sweep", "King's Hammer Sweep", 1050, 420, 760, 1.12, 4.2,
        accuracy_modifier=-0.05, max_targets=6, stagger_ms=520,
        tags=("hammer", "area", "taurus"),
        provenance=_sim(P1, "Asterius uses a massive hammer; sweep geometry/timing is simulation."),
    ),
    "asterius_hammer_crush": BossActionDefinition(
        "asterius_hammer_crush", "King's Hammer Crush", 1280, 300, 920, 1.78, 3.0,
        accuracy_modifier=-0.08, max_targets=1, stagger_ms=1100,
        tags=("hammer", "heavy", "single_target"),
        provenance=_sim(P1, "Heavy hammer strike calibrated for the canonical weapon."),
    ),
    "asterius_lightning_breath": BossActionDefinition(
        "asterius_lightning_breath", "Lightning Breath", 1250, 320, 880, 1.18, 18.0,
        accuracy_modifier=0.04, max_targets=8, stagger_ms=1800,
        tags=("lightning", "breath", "line", "stun"),
        provenance=_canon(P1, "Asterius telegraphs by drawing breath and unleashes long-range lightning capable of stunning or paralysing victims; numeric combat fields are simulation."),
    ),
    "nato_numbing_impact": BossActionDefinition(
        "nato_numbing_impact", "Numbing Impact", 900, 260, 650, 0.72, 4.0,
        max_targets=5, stagger_ms=3000, tags=("hammer", "area", "stun", "numbing"),
        provenance=_canon(P1, "Nato slams its two-handed hammer down, producing sparks that stun affected players for about three seconds."),
    ),
    "baran_numbing_detonation": BossActionDefinition(
        "baran_numbing_detonation", "Numbing Detonation", 980, 300, 700, 0.82, 7.0,
        max_targets=7, stagger_ms=3000, tags=("hammer", "area", "stun", "numbing", "paralysis_on_repeat"),
        provenance=_canon(P1, "Baran's Numbing Detonation has a wider effective area than Nato's technique and repeated exposure can escalate into paralysis."),
    ),
    # Floor 3 — Nerius.
    "nerius_branch_sweep": BossActionDefinition(
        "nerius_branch_sweep", "Evil Branch Sweep", 900, 420, 650, 0.98, 4.6,
        max_targets=6, stagger_ms=420, tags=("branch", "area"),
        provenance=_sim(P2, "Treant limb sweep derived from Nerius's tree-like combat form."),
    ),
    "nerius_root_crush": BossActionDefinition(
        "nerius_root_crush", "Root Crush", 1150, 350, 760, 1.42, 3.4,
        max_targets=3, stagger_ms=680, tags=("root", "area", "heavy"),
        provenance=_sim(P2, "Root attack package is simulation around the canonical treant identity."),
    ),
    "nerius_blue_flame": BossActionDefinition(
        "nerius_blue_flame", "Blue-Flame Breath", 1350, 650, 820, 1.22, 10.0,
        accuracy_modifier=-0.02, max_targets=8, stagger_ms=260,
        tags=("blue_flame", "breath", "cone", "area"),
        provenance=_inferred(P2, "Nerius is associated with a blue-flame mouth/breath attack; exact timing and damage are simulation."),
    ),
    # Floor 4 — Wythege.
    "wythege_tail_sweep": BossActionDefinition(
        "wythege_tail_sweep", "Hippocampus Tail Sweep", 760, 340, 520, 0.92, 4.8,
        max_targets=6, stagger_ms=360, tags=("tail", "area"),
        provenance=_sim(P3, "Tail-sweep package for the canonical hippocampus body form."),
    ),
    "wythege_water_breath": BossActionDefinition(
        "wythege_water_breath", "Scalding Water Breath", 1080, 560, 650, 1.10, 9.0,
        max_targets=7, stagger_ms=300, tags=("water", "breath", "cone", "area"),
        provenance=_inferred(P3, "Water-breath attack is consistent with the canonical water-themed boss; exact combat fields are simulation."),
    ),
    "wythege_water_inflow": BossActionDefinition(
        "wythege_water_inflow", "Water Inflow", 1800, 900, 1100, 0.68, 30.0,
        accuracy_modifier=0.10, max_targets=48, stagger_ms=700,
        tags=("water_inflow", "environmental", "arena_wide", "counterable_from_outside"),
        provenance=_canon(P3, "Wythege can flood the boss chamber with Water Inflow; opening the boss-room door from outside can release the water. Damage/timing values are simulation."),
    ),
    # Floor 5 — Fuscus.
    "fuscus_roar": BossActionDefinition(
        "fuscus_roar", "Vacant Colossus Roar", 650, 250, 500, 0.22, 30.0,
        accuracy_modifier=0.15, max_targets=48, stagger_ms=420,
        tags=("roar", "arena_wide", "defense_down"),
        provenance=_inferred(P4, "Fuscus opens the formal fight with an unavoidable roar associated with a defense-down debuff; status magnitude remains simulation."),
    ),
    "fuscus_eye_beam": BossActionDefinition(
        "fuscus_eye_beam", "Colossus Eye Beam", 1000, 500, 720, 1.30, 16.0,
        accuracy_modifier=0.02, max_targets=5, stagger_ms=240,
        tags=("beam", "line", "ranged"),
        provenance=_inferred(P4, "The head phase uses beam-like ranged attacks; exact damage/timing is simulation."),
    ),
    "fuscus_arm_smash": BossActionDefinition(
        "fuscus_arm_smash", "Disembodied Arm Smash", 1150, 380, 760, 1.58, 4.2,
        accuracy_modifier=-0.06, max_targets=4, stagger_ms=780,
        tags=("arm", "slam", "area"),
        provenance=_inferred(P4, "The first phase attacks through giant body parts before the full colossus assembles."),
    ),
    "fuscus_body_sweep": BossActionDefinition(
        "fuscus_body_sweep", "Colossus Body Sweep", 780, 560, 780, 1.00, 7.2,
        max_targets=8, stagger_ms=420, tags=("full_body", "area", "sweep"),
        provenance=_sim(P4, "Full-body sweep calibrated for Fuscus's second phase."),
    ),
    "fuscus_ground_crush": BossActionDefinition(
        "fuscus_ground_crush", "Vacant Ground Crush", 1450, 460, 980, 1.74, 6.5,
        accuracy_modifier=-0.08, max_targets=8, stagger_ms=900,
        tags=("full_body", "slam", "area", "heavy"),
        provenance=_sim(P4, "Large ground-impact action calibrated for Fuscus's assembled form."),
    ),
}


PROGRESSIVE_BOSS_MINIONS: dict[str, BossMinionDefinition] = {
    "nato_colonel_taurus": BossMinionDefinition(
        "nato_colonel_taurus", "Nato the Colonel Taurus", 12, 7200, 52, 34, 150, 5,
        "nato_two_hand_hammer",
        _inferred(P1, "Nato is a three-HP-gauge Floor 2 mid-boss armed with a two-handed hammer. Numeric combat stats and flattened runtime HP are simulation."),
    ),
    "baran_general_taurus": BossMinionDefinition(
        "baran_general_taurus", "Baran the General Taurus", 13, 10500, 60, 31, 170, 5,
        "baran_golden_hammer",
        _inferred(P1, "Baran is the second Floor 2 mid-boss, formerly the beta Floor Boss, armed with a golden battle hammer. Numeric combat stats are simulation."),
    ),
}


PROGRESSIVE_BOSSES: dict[str, BossDefinition] = {
    "asterius_the_taurus_king": BossDefinition(
        boss_id="asterius_the_taurus_king",
        name="Asterius the Taurus King",
        floor_number=2,
        level=14,
        hp_bars=6,
        hp_per_bar=5200,
        strength=72,
        agility=35,
        armor=190,
        evasion=5,
        phases=(
            BossPhaseDefinition(
                "taurus_king", "Taurus King", 0, "asterius_king_hammer", None,
                ("asterius_hammer_sweep", "asterius_hammer_crush", "asterius_lightning_breath"),
                _canon(P1, "Asterius is the official-service Floor 2 boss, has six HP bars, uses a massive hammer and long-range lightning breath."),
            ),
        ),
        initial_minion_template_id=None,
        initial_minion_count=0,
        minions_per_bar_depletion=0,
        minion_spawn_bar_depletions=(),
        last_attack_bonus_template_id=None,
        provenance=_inferred(P1, "Boss identity, six HP bars, Nato/Baran support and lightning-breath behaviour are canon; numeric level/HP/stats are simulation."),
        initial_minion_template_ids=("nato_colonel_taurus", "baran_general_taurus"),
    ),
    "nerius_the_evil_treant": BossDefinition(
        boss_id="nerius_the_evil_treant",
        name="Nerius the Evil Treant",
        floor_number=3,
        level=20,
        hp_bars=4,
        hp_per_bar=6600,
        strength=76,
        agility=30,
        armor=220,
        evasion=4,
        phases=(
            BossPhaseDefinition(
                "evil_treant", "Evil Treant", 0, "nerius_branch_claws", None,
                ("nerius_branch_sweep", "nerius_root_crush", "nerius_blue_flame"),
                _canon(P2, "Nerius the Evil Treant is the Floor 3 Floor Boss."),
            ),
        ),
        initial_minion_template_id=None,
        initial_minion_count=0,
        minions_per_bar_depletion=0,
        minion_spawn_bar_depletions=(),
        last_attack_bonus_template_id=None,
        provenance=_inferred(P2, "Boss identity and floor placement are canon; HP bars and all numeric combat stats are simulation."),
    ),
    "wythege_the_hippocampus": BossDefinition(
        boss_id="wythege_the_hippocampus",
        name="Wythege the Hippocampus",
        floor_number=4,
        level=27,
        hp_bars=6,
        hp_per_bar=7900,
        strength=82,
        agility=48,
        armor=235,
        evasion=8,
        phases=(
            BossPhaseDefinition(
                "hippocampus", "Hippocampus", 0, "wythege_natural_attack", None,
                ("wythege_tail_sweep", "wythege_water_breath", "wythege_water_inflow"),
                _canon(P3, "Wythege is the six-HP-bar Floor 4 boss and can use Water Inflow to flood the chamber."),
            ),
        ),
        initial_minion_template_id=None,
        initial_minion_count=0,
        minions_per_bar_depletion=0,
        minion_spawn_bar_depletions=(),
        last_attack_bonus_template_id=None,
        provenance=_inferred(P3, "Boss identity, six HP bars and Water Inflow are canon; numeric HP/stats and ordinary attack tuning are simulation."),
    ),
    "fuscus_the_vacant_colossus": BossDefinition(
        boss_id="fuscus_the_vacant_colossus",
        name="Fuscus the Vacant Colossus",
        floor_number=5,
        level=34,
        hp_bars=6,
        hp_per_bar=9600,
        strength=96,
        agility=26,
        armor=285,
        evasion=3,
        phases=(
            BossPhaseDefinition(
                "disembodied", "Disembodied Colossus", 0, "fuscus_disembodied_attack", None,
                ("fuscus_roar", "fuscus_eye_beam", "fuscus_arm_smash"),
                _canon(P4, "Fuscus initially manifests as separated giant body parts/head rather than a conventional complete body."),
            ),
            BossPhaseDefinition(
                "assembled", "Assembled Colossus", 3, "fuscus_full_body_attack", None,
                ("fuscus_eye_beam", "fuscus_body_sweep", "fuscus_ground_crush"),
                _inferred(P4, "Fuscus has a later full-body combat phase; transition point is runtime calibration."),
            ),
        ),
        initial_minion_template_id=None,
        initial_minion_count=0,
        minions_per_bar_depletion=0,
        minion_spawn_bar_depletions=(),
        last_attack_bonus_template_id=None,
        provenance=_inferred(P4, "Boss identity, Floor 5 placement, six HP bars and unusual body-part/full-body fight structure are canon; numeric combat stats are simulation."),
    ),
}


def extend_progressive_boss_corpus(
    bosses: dict[str, BossDefinition],
    minions: dict[str, BossMinionDefinition],
    actions: dict[str, BossActionDefinition],
) -> None:
    bosses.update(PROGRESSIVE_BOSSES)
    minions.update(PROGRESSIVE_BOSS_MINIONS)
    actions.update(PROGRESSIVE_BOSS_ACTIONS)


def apply_progressive_boss_catalog_seed(catalog) -> None:
    weapons = {
        "asterius_king_hammer": WeaponTemplate(
            "asterius_king_hammer", "Asterius's Massive Hammer", ItemKind.WEAPON,
            weapon_class=WeaponClass.MACE, damage_type=DamageType.BLUNT,
            attack_min=118, attack_max=152, required_level=1, required_strength=1,
            weight=85, base_durability=9000, base_speed_ms=1180, reach_m=3.6,
            provenance=_inferred(P1, "Asterius's enormous hammer is canon; numeric weapon fields are simulation."),
        ),
        "nato_two_hand_hammer": WeaponTemplate(
            "nato_two_hand_hammer", "Nato's Two-Handed Hammer", ItemKind.WEAPON,
            weapon_class=WeaponClass.MACE, damage_type=DamageType.BLUNT,
            attack_min=74, attack_max=96, required_level=1, required_strength=1,
            weight=48, base_durability=6000, base_speed_ms=980, reach_m=2.4,
            provenance=_inferred(P1, "Nato's two-handed hammer is canon; numeric fields are simulation."),
        ),
        "baran_golden_hammer": WeaponTemplate(
            "baran_golden_hammer", "Baran's Golden Battle Hammer", ItemKind.WEAPON,
            weapon_class=WeaponClass.MACE, damage_type=DamageType.BLUNT,
            attack_min=86, attack_max=111, required_level=1, required_strength=1,
            weight=58, base_durability=7000, base_speed_ms=1060, reach_m=2.9,
            provenance=_inferred(P1, "Baran's golden battle hammer is canon; numeric fields are simulation."),
        ),
        "nerius_branch_claws": WeaponTemplate(
            "nerius_branch_claws", "Nerius Branch Claws", ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER, damage_type=DamageType.BLUNT,
            attack_min=112, attack_max=145, required_level=1, required_strength=1,
            weight=0, base_durability=10000, base_speed_ms=900, reach_m=4.0,
            provenance=_sim(P2, "Natural-weapon template for the canonical treant boss body."),
        ),
        "wythege_natural_attack": WeaponTemplate(
            "wythege_natural_attack", "Wythege Natural Attack", ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER, damage_type=DamageType.BLUNT,
            attack_min=132, attack_max=168, required_level=1, required_strength=1,
            weight=0, base_durability=10000, base_speed_ms=780, reach_m=3.8,
            provenance=_sim(P3, "Natural-weapon template for the canonical hippocampus boss body."),
        ),
        "fuscus_disembodied_attack": WeaponTemplate(
            "fuscus_disembodied_attack", "Fuscus Disembodied Strike", ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER, damage_type=DamageType.BLUNT,
            attack_min=154, attack_max=194, required_level=1, required_strength=1,
            weight=0, base_durability=12000, base_speed_ms=1060, reach_m=5.0,
            provenance=_sim(P4, "Natural attack template for the separated body-part phase."),
        ),
        "fuscus_full_body_attack": WeaponTemplate(
            "fuscus_full_body_attack", "Fuscus Colossus Strike", ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER, damage_type=DamageType.BLUNT,
            attack_min=178, attack_max=222, required_level=1, required_strength=1,
            weight=0, base_durability=14000, base_speed_ms=1120, reach_m=6.0,
            provenance=_sim(P4, "Natural attack template for Fuscus's assembled body phase."),
        ),
    }
    for template_id, weapon in weapons.items():
        catalog.weapons.setdefault(template_id, weapon)
