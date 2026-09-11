from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import Provenance, ProvenanceKind


@dataclass(slots=True, frozen=True)
class VendorListingDefinition:
    template_id: str
    unit_price_col: int


@dataclass(slots=True, frozen=True)
class VendorDefinition:
    vendor_id: str
    name: str
    location_id: str
    listings: tuple[VendorListingDefinition, ...]
    buyback_rate: float
    infinite_stock: bool
    provenance: Provenance


BEGINNER_VENDOR = VendorDefinition(
    vendor_id="npc_vendor_town_of_beginnings",
    name="Town of Beginnings General Vendor",
    location_id="floor_1_town_of_beginnings",
    listings=(
        VendorListingDefinition("starter_one_hand_sword", 120),
        VendorListingDefinition("starter_rapier", 115),
        VendorListingDefinition("starter_dagger", 80),
        VendorListingDefinition("starter_mace", 135),
        VendorListingDefinition("starter_spear", 140),
        VendorListingDefinition("starter_leather_coat", 95),
        VendorListingDefinition("starter_leather_gloves", 35),
        VendorListingDefinition("starter_leather_boots", 40),
        VendorListingDefinition("healing_potion_basic", 18),
        VendorListingDefinition("field_bread", 5),
    ),
    buyback_rate=0.42,
    infinite_stock=False,
    provenance=Provenance(
        ProvenanceKind.SIMULATION,
        notes=(
            "NPC vendors with limited assortments and system-set prices are canon-backed. "
            "This particular beginner assortment and all listed prices are runtime calibration."
        ),
    ),
)


BEGINNER_REINFORCEMENT_VENDOR = VendorDefinition(
    vendor_id="npc_reinforcement_supplier_town_of_beginnings",
    name="Town of Beginnings Reinforcement Supplier",
    location_id="floor_1_town_of_beginnings",
    listings=(
        VendorListingDefinition("reinforcement_base_material", 14),
        VendorListingDefinition("reinforcement_sharpness_material", 24),
        VendorListingDefinition("reinforcement_quickness_material", 24),
        VendorListingDefinition("reinforcement_accuracy_material", 24),
        VendorListingDefinition("reinforcement_heaviness_material", 24),
        VendorListingDefinition("reinforcement_durability_material", 24),
        VendorListingDefinition("iron_ingot", 26),
    ),
    buyback_rate=0.35,
    infinite_stock=False,
    provenance=Provenance(
        ProvenanceKind.SIMULATION,
        sources=("Sword Art Online Progressive Volume 1: Rondo of a Fragile Blade",),
        notes=(
            "Base/additional reinforcement material roles are canon. This low-floor system supplier, "
            "its assortment and its Col prices are runtime scaffolding for a closed playable loop."
        ),
    ),
)


CORE_VENDORS: dict[str, VendorDefinition] = {
    BEGINNER_VENDOR.vendor_id: BEGINNER_VENDOR,
    BEGINNER_REINFORCEMENT_VENDOR.vendor_id: BEGINNER_REINFORCEMENT_VENDOR,
}
