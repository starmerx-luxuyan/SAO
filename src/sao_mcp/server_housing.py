from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_housing_tools(mcp, runtime) -> None:
    @mcp.tool()
    def list_property_market(floor_number: int | None = None) -> str:
        """List purchasable player-home/guild-HQ listings with provenance and quest gates."""
        return _json({"properties": runtime.list_property_market(floor_number=floor_number)})

    @mcp.tool()
    def purchase_residence(actor_id: str, listing_id: str, joint_marriage: bool = True) -> str:
        """Buy a player residence from the authoritative personal/shared wallet."""
        return _json(asdict(runtime.purchase_residence(actor_id, listing_id, joint_marriage=joint_marriage)))

    @mcp.tool()
    def purchase_guild_headquarters(guild_id: str, operator_id: str, listing_id: str) -> str:
        """Purchase a guild headquarters from the guild vault with Contract Scroll permission."""
        return _json(asdict(runtime.purchase_guild_headquarters(guild_id, operator_id, listing_id)))

    @mcp.tool()
    def grant_property_guest(owner_id: str, property_id: str, guest_id: str, enabled: bool = True) -> str:
        """Grant or revoke a guest's access to a private player residence."""
        return _json(asdict(runtime.grant_property_guest(owner_id, property_id, guest_id, enabled=enabled)))

    @mcp.tool()
    def enter_property(actor_id: str, property_id: str) -> str:
        """Enter an authorized property interior and mutate the actor's real world location."""
        state = runtime.enter_property(actor_id, property_id)
        return _json({"property": asdict(state), "locationId": runtime.actors[actor_id].location_id, "nowMs": runtime.world.now_ms})

    @mcp.tool()
    def exit_property(actor_id: str) -> str:
        """Leave the currently entered property and return to its parent world location."""
        state = runtime.exit_property(actor_id)
        return _json({"property": asdict(state), "locationId": runtime.actors[actor_id].location_id, "nowMs": runtime.world.now_ms})

    @mcp.tool()
    def deposit_property_storage(
        actor_id: str,
        property_id: str,
        instance_id: str,
        quantity: int | None = None,
    ) -> str:
        """Deposit into a residence/HQ storage using ownership, membership and slot rules."""
        return _json(asdict(runtime.deposit_property_storage(actor_id, property_id, instance_id, quantity=quantity)))

    @mcp.tool()
    def withdraw_property_storage(
        actor_id: str,
        property_id: str,
        stored_instance_id: str,
        quantity: int | None = None,
    ) -> str:
        """Withdraw from a residence/HQ storage using ownership, membership and carry rules."""
        return _json(asdict(runtime.withdraw_property_storage(actor_id, property_id, stored_instance_id, quantity=quantity)))

    @mcp.tool()
    def get_property_state(property_id: str | None = None, actor_id: str | None = None) -> str:
        """Inspect one property or properties owned/accessible by a player."""
        if property_id is not None:
            return _json(asdict(runtime.housing.properties[property_id]))
        if actor_id is None:
            raise ValueError("provide property_id or actor_id")
        rows = [
            asdict(state)
            for state in runtime.housing.properties.values()
            if runtime.can_enter_property(actor_id, state.property_id)
        ]
        return _json({"actorId": actor_id, "properties": rows})
