from __future__ import annotations

from sao_mcp.corpus.bosses import CORE_BOSS_ACTIONS, CORE_BOSSES, BossActionDefinition, BossDefinition, BossPhaseDefinition
from sao_mcp.corpus.floor6_world import FLOOR6_MAIN_SETTLEMENT, floor6_connections, floor6_locations
from sao_mcp.domain.models import DamageType, ItemKind, Provenance, ProvenanceKind, WeaponClass, WeaponTemplate


PROGRESSIVE_5 = "Sword Art Online Progressive Volume 5: Canon of the Golden Rule (Start)"
PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
FLOOR6_TIMELINE = "https://swordartonline.fandom.com/wiki/Sword_Art_Online_Timeline"
IRRATIONAL_CUBE_ID = "the_irrational_cube"
IRRATIONAL_CUBE_WEAPON_ID = "irrational_cube_natural_attack"
TARGET_FACE = ((8, 3, 4), (1, 5, 9), (6, 7, 2))
TARGET_CODE = "834159672"


def _canon(notes: str, *sources: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=tuple(sources) or (PROGRESSIVE_5,), notes=notes)


def _inferred(notes: str, *sources: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=tuple(sources) or (PROGRESSIVE_5,), notes=notes)


def _sim(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.SIMULATION, notes=notes)


def apply_floor6_world_seed(world_map) -> None:
    """Verify that the authoritative base world already contains the Floor 6 Progressive geometry."""
    expected_locations = set(floor6_locations()) | {FLOOR6_MAIN_SETTLEMENT[0]}
    missing_locations = sorted(expected_locations.difference(world_map.locations))
    if missing_locations:
        raise RuntimeError(f"base world is missing Floor 6 locations: {missing_locations}")
    if "floor_6_main_town" in world_map.locations:
        raise RuntimeError("base world still contains the obsolete Floor 6 placeholder settlement")

    existing_edges = {(edge.from_location_id, edge.to_location_id) for edge in world_map.connections}
    expected_edges = {(edge.from_location_id, edge.to_location_id) for edge in floor6_connections()}
    missing_edges = sorted(expected_edges.difference(existing_edges))
    if missing_edges:
        raise RuntimeError(f"base world is missing Floor 6 travel connections: {missing_edges}")


def apply_floor6_boss_corpus(catalog) -> None:
    catalog.weapons.setdefault(
        IRRATIONAL_CUBE_WEAPON_ID,
        WeaponTemplate(
            template_id=IRRATIONAL_CUBE_WEAPON_ID,
            name="Irrational Cube Core Impact",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.OTHER,
            damage_type=DamageType.BLUNT,
            attack_min=185,
            attack_max=235,
            required_level=1,
            required_strength=1,
            weight=0,
            base_durability=20_000,
            base_speed_ms=980,
            reach_m=5.0,
            provenance=_sim("Natural-impact template for the exposed black core after the numbered invincible armor has fallen."),
        ),
    )

    actions = {
        "irrational_cube_face_slam": BossActionDefinition(
            "irrational_cube_face_slam",
            "Black-Core Arm Slam",
            1100,
            420,
            820,
            1.48,
            5.5,
            accuracy_modifier=-0.04,
            max_targets=6,
            stagger_ms=680,
            tags=("black_core", "arm", "slam", "area"),
            provenance=_sim("Damage/timing package for the exposed-core combat phase; not a claimed named canon attack."),
        ),
        "irrational_cube_rotation_burst": BossActionDefinition(
            "irrational_cube_rotation_burst",
            "Core Arm Burst",
            900,
            460,
            700,
            1.05,
            8.0,
            max_targets=8,
            stagger_ms=360,
            tags=("black_core", "six_arms", "area"),
            provenance=_sim("Area package for the six-arm exposed black core; exact action/timing is simulation."),
        ),
        "irrational_cube_corner_crush": BossActionDefinition(
            "irrational_cube_corner_crush",
            "Core Heavy Crush",
            1450,
            320,
            960,
            1.82,
            3.5,
            accuracy_modifier=-0.08,
            max_targets=2,
            stagger_ms=980,
            tags=("black_core", "heavy", "crush"),
            provenance=_sim("Heavy exposed-core attack; exact numbers/action package are simulation."),
        ),
    }
    CORE_BOSS_ACTIONS.update({key: value for key, value in actions.items() if key not in CORE_BOSS_ACTIONS})

    # Official-service Progressive describes one HP gauge after the Golden Cube activates the guardian.
    # hp_per_bar and ordinary stats remain runtime calibration; the numbered outer armor is handled by the scenario puzzle.
    CORE_BOSSES[IRRATIONAL_CUBE_ID] = BossDefinition(
        boss_id=IRRATIONAL_CUBE_ID,
        name="The Irrational Cube",
        floor_number=6,
        level=41,
        hp_bars=1,
        hp_per_bar=69_600,
        strength=108,
        agility=34,
        armor=180,
        evasion=2,
        phases=(
            BossPhaseDefinition(
                "exposed_black_core",
                "Exposed Black Core",
                0,
                IRRATIONAL_CUBE_WEAPON_ID,
                None,
                (
                    "irrational_cube_face_slam",
                    "irrational_cube_rotation_burst",
                    "irrational_cube_corner_crush",
                ),
                _inferred(
                    "Once a correct numbered face causes the twenty-six golden armor cubes to crumble, a half-metre black core containing the Golden Cube is exposed and sprouts six black arms. Exact combat actions are simulation.",
                    PROGRESSIVE_6,
                ),
            ),
        ),
        initial_minion_template_id=None,
        initial_minion_count=0,
        minions_per_bar_depletion=0,
        minion_spawn_bar_depletions=(),
        last_attack_bonus_template_id=None,
        provenance=_inferred(
            "The Irrational Cube is the Floor 6 Floor Boss. In the official-service route Theano must first return the Golden Cube to the black core, which activates a giant 3x3-numbered golden armor shell. "
            "The raid rotates rows/columns until one face forms the required 1-9 magic square; the twenty-six armor cubes then collapse, exposing the single-HP-gauge black core. "
            "At the last pixel of HP a reverse-side keyhole can eject the Golden Cube. Numeric HP/stats are simulation calibration.",
            PROGRESSIVE_6,
        ),
    )
