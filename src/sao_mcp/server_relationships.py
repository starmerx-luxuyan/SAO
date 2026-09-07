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


def register_relationship_tools(mcp, runtime) -> None:
    @mcp.tool()
    def send_friend_request(sender_id: str, target_id: str) -> str:
        """Send an Aincrad friend request."""
        return _json(asdict(runtime.request_friend(sender_id, target_id)))

    @mcp.tool()
    def accept_friend_request(request_id: str, target_id: str) -> str:
        """Accept a pending friend request."""
        return _json(asdict(runtime.accept_friend(request_id, target_id)))

    @mcp.tool()
    def decline_friend_request(request_id: str, target_id: str) -> str:
        """Decline a pending friend request."""
        return _json(asdict(runtime.decline_friend(request_id, target_id)))

    @mcp.tool()
    def create_friend_common_inventory(actor_id: str, friend_id: str) -> str:
        """Create or inspect the common inventory tab available to registered friends."""
        return _json(asdict(runtime.create_friend_storage(actor_id, friend_id)))

    @mcp.tool()
    def relationship_position_check(actor_id: str, target_id: str) -> str:
        """Use friend/guild/marriage position-search permissions instead of omniscient location lookup."""
        return _json(runtime.relationship_position(actor_id, target_id))

    @mcp.tool()
    def create_guild(
        leader_id: str,
        name: str,
        emblem: str = "◇",
        tax_rate: float = 0.05,
    ) -> str:
        """Create a guild runtime record with Contract Scroll management, vault and common storage."""
        return _json(asdict(runtime.create_guild(leader_id, name, emblem=emblem, tax_rate=tax_rate)))

    @mcp.tool()
    def invite_guild_member(guild_id: str, inviter_id: str, target_id: str) -> str:
        """Send a guild invite; inviter must have Contract Scroll management permission."""
        return _json(asdict(runtime.invite_to_guild(guild_id, inviter_id, target_id)))

    @mcp.tool()
    def accept_guild_invitation(invite_id: str, target_id: str) -> str:
        """Accept a pending guild invitation."""
        return _json(asdict(runtime.accept_guild_invite(invite_id, target_id)))

    @mcp.tool()
    def set_guild_manager(guild_id: str, leader_id: str, member_id: str, enabled: bool = True) -> str:
        """Grant or revoke Contract Scroll management permission."""
        return _json(asdict(runtime.set_guild_manager(guild_id, leader_id, member_id, enabled)))

    @mcp.tool()
    def configure_guild(
        guild_id: str,
        operator_id: str,
        tax_rate: float | None = None,
        emblem: str | None = None,
        headquarters_location_id: str | None = None,
    ) -> str:
        """Manage guild tax rate, emblem and registered headquarters through Contract Scroll authority."""
        return _json(
            asdict(
                runtime.configure_guild(
                    guild_id,
                    operator_id,
                    tax_rate=tax_rate,
                    emblem=emblem,
                    headquarters_location_id=headquarters_location_id,
                )
            )
        )

    @mcp.tool()
    def request_marriage(sender_id: str, target_id: str) -> str:
        """Send an Aincrad marriage request while both players are colocated."""
        return _json(asdict(runtime.request_marriage(sender_id, target_id)))

    @mcp.tool()
    def accept_marriage(request_id: str, target_id: str) -> str:
        """Accept marriage, merging both inventories and wallets with two-person storage capacity."""
        return _json(asdict(runtime.accept_marriage(request_id, target_id)))

    @mcp.tool()
    def get_spouse_status(actor_id: str) -> str:
        """Return the partner-status visibility granted by Aincrad marriage."""
        return _json(runtime.partner_status(actor_id))

    @mcp.tool()
    def deposit_shared_storage(
        actor_id: str,
        storage_id: str,
        instance_id: str,
        quantity: int | None = None,
    ) -> str:
        """Deposit an unequipped item into an authorized friend/guild shared storage."""
        return _json(
            asdict(
                runtime.deposit_shared_storage(
                    actor_id, storage_id, instance_id, quantity=quantity
                )
            )
        )

    @mcp.tool()
    def withdraw_shared_storage(
        actor_id: str,
        storage_id: str,
        stored_instance_id: str,
        quantity: int | None = None,
    ) -> str:
        """Withdraw an item from authorized friend/guild storage, enforcing dungeon and carry rules."""
        return _json(
            asdict(
                runtime.withdraw_shared_storage(
                    actor_id, storage_id, stored_instance_id, quantity=quantity
                )
            )
        )

    @mcp.tool()
    def get_relationship_state(actor_id: str) -> str:
        """Return player-visible friend, guild, marriage and shared-storage identifiers for one actor."""
        actor = runtime.actors[actor_id]
        marriage = runtime.relationships.marriage_for(actor_id)
        guild = runtime.relationships.guilds.get(actor.guild_id) if actor.guild_id else None
        storages = [
            {
                "storageId": storage.storage_id,
                "kind": storage.storage_kind,
                "memberIds": list(storage.member_ids),
                "itemCount": sum(item.quantity for item in storage.items.values()),
            }
            for storage in runtime.relationships.storages.values()
            if actor_id in storage.member_ids
        ]
        return _json(
            {
                "actorId": actor_id,
                "friends": sorted(runtime.relationships.friends.get(actor_id, set())),
                "guild": asdict(guild) if guild else None,
                "marriage": asdict(marriage) if marriage else None,
                "sharedStorages": storages,
            }
        )
