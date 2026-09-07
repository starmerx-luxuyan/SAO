from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field

from sao_mcp.corpus.housing import PropertyKind


@dataclass(slots=True)
class PropertyState:
    property_id: str
    listing_id: str
    name: str
    kind: PropertyKind
    parent_location_id: str
    interior_location_id: str
    owner_actor_ids: list[str] = field(default_factory=list)
    guild_id: str | None = None
    guest_actor_ids: list[str] = field(default_factory=list)
    storage_id: str | None = None
    purchased_at_ms: int = 0
    purchase_price_col: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


class HousingState:
    def __init__(self) -> None:
        self.properties: dict[str, PropertyState] = {}

    def create(
        self,
        *,
        listing_id: str,
        name: str,
        kind: PropertyKind,
        parent_location_id: str,
        owner_actor_ids: list[str] | None,
        guild_id: str | None,
        storage_id: str | None,
        purchased_at_ms: int,
        purchase_price_col: int,
    ) -> PropertyState:
        property_id = f"property_{uuid.uuid4().hex[:12]}"
        state = PropertyState(
            property_id=property_id,
            listing_id=listing_id,
            name=name,
            kind=kind,
            parent_location_id=parent_location_id,
            interior_location_id=f"{property_id}_interior",
            owner_actor_ids=list(owner_actor_ids or []),
            guild_id=guild_id,
            storage_id=storage_id,
            purchased_at_ms=purchased_at_ms,
            purchase_price_col=purchase_price_col,
        )
        self.properties[property_id] = state
        return state

    def dump_state(self) -> dict:
        return {property_id: asdict(state) for property_id, state in self.properties.items()}

    def load_state(self, payload: dict) -> None:
        self.properties = {
            property_id: PropertyState(
                property_id=row["property_id"],
                listing_id=row["listing_id"],
                name=row["name"],
                kind=PropertyKind(row["kind"]),
                parent_location_id=row["parent_location_id"],
                interior_location_id=row["interior_location_id"],
                owner_actor_ids=list(row.get("owner_actor_ids", [])),
                guild_id=row.get("guild_id"),
                guest_actor_ids=list(row.get("guest_actor_ids", [])),
                storage_id=row.get("storage_id"),
                purchased_at_ms=int(row.get("purchased_at_ms", 0)),
                purchase_price_col=int(row.get("purchase_price_col", 0)),
                metadata=dict(row.get("metadata", {})),
            )
            for property_id, row in payload.items()
        }
