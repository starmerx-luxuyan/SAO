from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sao_mcp.domain.models import Provenance, ProvenanceKind


class PropertyKind(StrEnum):
    RESIDENCE = "residence"
    GUILD_HEADQUARTERS = "guild_headquarters"


@dataclass(slots=True, frozen=True)
class PropertyListingDefinition:
    listing_id: str
    name: str
    kind: PropertyKind
    parent_location_id: str
    price_col: int
    storage_slots: int
    unique_world_asset: bool = False
    quest_prerequisites: tuple[str, ...] = ()
    provenance: Provenance = Provenance(ProvenanceKind.SIMULATION)


CORE_PROPERTY_LISTINGS: dict[str, PropertyListingDefinition] = {
    "town_beginner_room": PropertyListingDefinition(
        listing_id="town_beginner_room",
        name="Town of Beginnings Rental-Style Room",
        kind=PropertyKind.RESIDENCE,
        parent_location_id="floor_1_town_of_beginnings",
        price_col=1_200,
        storage_slots=24,
        provenance=Provenance(
            ProvenanceKind.SIMULATION,
            notes="General player housing is canon-backed; this low-floor room and its price/capacity are runtime calibration.",
        ),
    ),
    "floor22_forest_house_k4": PropertyListingDefinition(
        listing_id="floor22_forest_house_k4",
        name="Forest House K4",
        kind=PropertyKind.RESIDENCE,
        parent_location_id="floor_22_forest_house_site",
        price_col=5_000_000,
        storage_slots=180,
        unique_world_asset=True,
        quest_prerequisites=("witch_of_the_west_and_three_treasures",),
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=(
                "Sword Art Online Volume 1, Chapter 17",
                "Sword Art Online: The Day Before",
            ),
            notes=(
                "Identity, southwestern Floor 22 forest location, player-home status and quest-gated purchase are canon. "
                "The runtime price and storage capacity are simulation calibration, not treated as locked canon numbers."
            ),
        ),
    ),
    "selmburg_furnished_residence": PropertyListingDefinition(
        listing_id="selmburg_furnished_residence",
        name="Selmburg Furnished Residence",
        kind=PropertyKind.RESIDENCE,
        parent_location_id="floor_61_selmburg",
        price_col=4_000_000,
        storage_slots=140,
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=("Sword Art Online Volume 1",),
            notes=(
                "Selmburg contains player residences and Asuna owned a furnished home there. "
                "This purchasable generic listing, price and capacity are simulation calibration."
            ),
        ),
    ),
    "granzam_guild_headquarters": PropertyListingDefinition(
        listing_id="granzam_guild_headquarters",
        name="Granzam Guild Headquarters",
        kind=PropertyKind.GUILD_HEADQUARTERS,
        parent_location_id="floor_55_granzam",
        price_col=50_000_000,
        storage_slots=800,
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=("Sword Art Online guild system",),
            notes=(
                "Guilds can purchase headquarters restricted to guild members. "
                "This Granzam listing, price and capacity are simulation calibration."
            ),
        ),
    ),
}
