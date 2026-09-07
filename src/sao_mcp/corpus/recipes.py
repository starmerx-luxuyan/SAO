from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import Provenance, ProvenanceKind


@dataclass(slots=True, frozen=True)
class MaterialRequirement:
    template_id: str
    quantity: int


@dataclass(slots=True, frozen=True)
class WeaponRecipe:
    recipe_id: str
    product_template_id: str
    materials: tuple[MaterialRequirement, ...]
    difficulty: float
    nominal_hammer_hits: int
    provenance: Provenance


_SIM = Provenance(
    ProvenanceKind.SIMULATION,
    notes=(
        "The forge workflow and quality variance are canon-backed. Exact low-tier material counts, "
        "difficulty and hammer-hit counts are playable runtime calibration."
    ),
)


WEAPON_RECIPES: dict[str, WeaponRecipe] = {
    "iron_one_hand_sword": WeaponRecipe(
        "iron_one_hand_sword",
        "starter_one_hand_sword",
        (MaterialRequirement("iron_ingot", 2),),
        difficulty=0.85,
        nominal_hammer_hits=10,
        provenance=_SIM,
    ),
    "iron_rapier": WeaponRecipe(
        "iron_rapier",
        "starter_rapier",
        (MaterialRequirement("iron_ingot", 2),),
        difficulty=0.95,
        nominal_hammer_hits=12,
        provenance=_SIM,
    ),
    "iron_dagger": WeaponRecipe(
        "iron_dagger",
        "starter_dagger",
        (MaterialRequirement("iron_ingot", 1),),
        difficulty=0.70,
        nominal_hammer_hits=7,
        provenance=_SIM,
    ),
    "iron_mace": WeaponRecipe(
        "iron_mace",
        "starter_mace",
        (MaterialRequirement("iron_ingot", 3),),
        difficulty=0.90,
        nominal_hammer_hits=13,
        provenance=_SIM,
    ),
    "iron_spear": WeaponRecipe(
        "iron_spear",
        "starter_spear",
        (MaterialRequirement("iron_ingot", 3),),
        difficulty=1.00,
        nominal_hammer_hits=14,
        provenance=_SIM,
    ),
}
