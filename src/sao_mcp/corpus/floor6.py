from __future__ import annotations

from sao_mcp.corpus.bosses import CORE_BOSS_ACTIONS, CORE_BOSSES, BossActionDefinition, BossDefinition, BossPhaseDefinition
from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import DamageType, ItemKind, Provenance, ProvenanceKind, WeaponClass, WeaponTemplate, ZoneKind


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
    """Replace the functional Floor-6 placeholder town with verified Progressive locations."""
    placeholder = "floor_6_main_town"
    if placeholder in world_map.locations:
        world_map.locations.pop(placeholder, None)
        world_map.adjacency.pop(placeholder, None)
        world_map.connections = tuple(
            edge
            for edge in world_map.connections
            if edge.from_location_id != placeholder and edge.to_location_id != placeholder
        )
        for node_id, edges in list(world_map.adjacency.items()):
            world_map.adjacency[node_id] = [
                edge
                for edge in edges
                if edge.from_location_id != placeholder and edge.to_location_id != placeholder
            ]

    locations = {
        "floor_6_stachion": LocationDefinition(
            "floor_6_stachion",
            6,
            "Stachion",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            teleport_gate=True,
            provenance=_canon(
                "Main settlement of Floor 6 and the opening urban location of Canon of the Golden Rule; Stachion is characterised by puzzle mechanisms throughout the city.",
                PROGRESSIVE_5,
            ),
        ),
        "floor_6_stachion_puzzle_quarter": LocationDefinition(
            "floor_6_stachion_puzzle_quarter",
            6,
            "Stachion Puzzle Quarter",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=_inferred(
                "Descriptive runtime node grouping Stachion's canon puzzle-heavy urban content; this label is not a canon district proper name.",
                PROGRESSIVE_5,
            ),
        ),
        "floor_6_suribus": LocationDefinition(
            "floor_6_suribus",
            6,
            "Suribus",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=_canon(
                "Named eastern settlement on Floor 6. Pithagrus maintains a second residence here during the golden-key investigation.",
                PROGRESSIVE_5,
            ),
        ),
        "floor_6_pithagrus_suribus_house": LocationDefinition(
            "floor_6_pithagrus_suribus_house",
            6,
            "Pithagrus's Suribus House",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=_inferred(
                "Pithagrus's second/secret home in Suribus, associated with the golden-key investigation. Exact house layout is abstracted.",
                PROGRESSIVE_5,
            ),
        ),
        "floor_6_ararro": LocationDefinition(
            "floor_6_ararro",
            6,
            "Ararro",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=_inferred("Named Floor 6 settlement in Progressive; exact local geometry is abstracted.", PROGRESSIVE_5),
        ),
        "floor_6_castle_galey": LocationDefinition(
            "floor_6_castle_galey",
            6,
            "Castle Galey",
            ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=_canon(
                "Dark Elf stronghold on Floor 6 where Kirito and Asuna reunite with Kizmel and continue the Elf War campaign.",
                PROGRESSIVE_5,
                PROGRESSIVE_6,
                FLOOR6_TIMELINE,
            ),
        ),
        "floor_6_lake_talpha": LocationDefinition(
            "floor_6_lake_talpha",
            6,
            "Lake Talpha",
            ZoneKind.FIELD,
            provenance=_canon(
                "Named Floor 6 lake crossed during the later Dark Elf route with Kizmel.",
                PROGRESSIVE_6,
                FLOOR6_TIMELINE,
            ),
        ),
    }
    for location_id, location in locations.items():
        world_map.locations.setdefault(location_id, location)

    p = _sim("Travel durations are runtime calibration; endpoint relationships follow the verified Floor 6 route.")
    edges = (
        TravelConnection("floor_6_stachion", "floor_6_stachion_puzzle_quarter", 4 * 60_000, provenance=p),
        TravelConnection("floor_6_stachion", "floor_6_field", 10 * 60_000, provenance=p),
        TravelConnection("floor_6_field", "floor_6_suribus", 28 * 60_000, provenance=p),
        TravelConnection("floor_6_suribus", "floor_6_pithagrus_suribus_house", 3 * 60_000, provenance=p),
        TravelConnection("floor_6_field", "floor_6_ararro", 22 * 60_000, provenance=p),
        TravelConnection("floor_6_field", "floor_6_castle_galey", 42 * 60_000, provenance=p),
        TravelConnection("floor_6_castle_galey", "floor_6_lake_talpha", 24 * 60_000, provenance=p),
        TravelConnection("floor_6_lake_talpha", "floor_6_labyrinth", 48 * 60_000, provenance=p),
    )
    existing = {(edge.from_location_id, edge.to_location_id) for edge in world_map.connections}
    for edge in edges:
        if (edge.from_location_id, edge.to_location_id) in existing:
            continue
        world_map.connections = tuple(world_map.connections) + (edge,)
        world_map.adjacency.setdefault(edge.from_location_id, []).append(edge)
        if edge.bidirectional:
            world_map.adjacency.setdefault(edge.to_location_id, []).append(
                TravelConnection(
                    edge.to_location_id,
                    edge.from_location_id,
                    edge.travel_ms,
                    True,
                    edge.requires_floor_unlocked,
                    edge.provenance,
                )
            )


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
