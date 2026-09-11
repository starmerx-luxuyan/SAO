from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import CombatantState, ItemInstance
from sao_mcp.rules.inventory import add_item, can_receive


class RequestStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class FriendRequest:
    request_id: str
    sender_id: str
    target_id: str
    status: RequestStatus = RequestStatus.PENDING


@dataclass(slots=True)
class SharedStorage:
    storage_id: str
    storage_kind: str
    member_ids: list[str]
    items: dict[str, ItemInstance] = field(default_factory=dict)


@dataclass(slots=True)
class GuildState:
    guild_id: str
    name: str
    leader_id: str
    member_ids: list[str]
    manager_ids: list[str] = field(default_factory=list)
    emblem: str = "◇"
    tax_rate: float = 0.05
    vault_col: int = 0
    storage_id: str = ""
    headquarters_location_id: str | None = None


@dataclass(slots=True)
class GuildInvite:
    invite_id: str
    guild_id: str
    inviter_id: str
    target_id: str
    status: RequestStatus = RequestStatus.PENDING


@dataclass(slots=True)
class MarriageRequest:
    request_id: str
    sender_id: str
    target_id: str
    status: RequestStatus = RequestStatus.PENDING


@dataclass(slots=True)
class MarriageState:
    marriage_id: str
    partner_ids: tuple[str, str]
    shared_wallet_col: int
    active: bool = True
    started_at_ms: int = 0
    ended_at_ms: int | None = None
    end_reason: str | None = None


class RelationshipRuntime:
    """Persistent relationship state. Mechanical storage/wallet mutation is explicit and auditable."""

    def __init__(self) -> None:
        self.friend_requests: dict[str, FriendRequest] = {}
        self.friends: dict[str, set[str]] = {}
        self.storages: dict[str, SharedStorage] = {}
        self.friend_storage_by_pair: dict[str, str] = {}
        self.guilds: dict[str, GuildState] = {}
        self.guild_invites: dict[str, GuildInvite] = {}
        self.marriage_requests: dict[str, MarriageRequest] = {}
        self.marriages: dict[str, MarriageState] = {}
        self.marriage_by_actor: dict[str, str] = {}

    @staticmethod
    def _pair_key(a: str, b: str) -> str:
        return "::".join(sorted((a, b)))

    @staticmethod
    def _player(actor: CombatantState) -> None:
        if actor.kind.value != "player":
            raise ValueError("relationship operation requires player characters")
        if not actor.alive:
            raise ValueError("defeated players cannot create relationship requests")

    def are_friends(self, a: str, b: str) -> bool:
        return b in self.friends.get(a, set()) and a in self.friends.get(b, set())

    def request_friend(self, sender: CombatantState, target: CombatantState) -> FriendRequest:
        self._player(sender)
        self._player(target)
        if sender.actor_id == target.actor_id:
            raise ValueError("cannot friend oneself")
        if self.are_friends(sender.actor_id, target.actor_id):
            raise ValueError("players are already friends")
        for request in self.friend_requests.values():
            if request.status is RequestStatus.PENDING and {request.sender_id, request.target_id} == {sender.actor_id, target.actor_id}:
                return request
        request = FriendRequest(f"friendreq_{uuid.uuid4().hex[:12]}", sender.actor_id, target.actor_id)
        self.friend_requests[request.request_id] = request
        return request

    def accept_friend(self, request_id: str, *, target_id: str) -> FriendRequest:
        request = self.friend_requests[request_id]
        if request.status is not RequestStatus.PENDING or request.target_id != target_id:
            raise ValueError("friend request cannot be accepted by this player")
        request.status = RequestStatus.ACCEPTED
        self.friends.setdefault(request.sender_id, set()).add(request.target_id)
        self.friends.setdefault(request.target_id, set()).add(request.sender_id)
        return request

    def decline_friend(self, request_id: str, *, target_id: str) -> FriendRequest:
        request = self.friend_requests[request_id]
        if request.status is not RequestStatus.PENDING or request.target_id != target_id:
            raise ValueError("friend request cannot be declined by this player")
        request.status = RequestStatus.DECLINED
        return request

    def remove_friend(self, actor_id: str, friend_id: str) -> None:
        self.friends.get(actor_id, set()).discard(friend_id)
        self.friends.get(friend_id, set()).discard(actor_id)

    def create_friend_storage(self, actor_id: str, friend_id: str) -> SharedStorage:
        if not self.are_friends(actor_id, friend_id):
            raise ValueError("common inventory requires an accepted friendship")
        pair = self._pair_key(actor_id, friend_id)
        storage_id = self.friend_storage_by_pair.get(pair)
        if storage_id:
            return self.storages[storage_id]
        storage = SharedStorage(
            storage_id=f"friendstore_{uuid.uuid4().hex[:12]}",
            storage_kind="friend_common",
            member_ids=sorted((actor_id, friend_id)),
        )
        self.storages[storage.storage_id] = storage
        self.friend_storage_by_pair[pair] = storage.storage_id
        return storage

    def create_guild(
        self,
        leader: CombatantState,
        name: str,
        *,
        emblem: str = "◇",
        tax_rate: float = 0.05,
    ) -> GuildState:
        self._player(leader)
        if leader.guild_id:
            raise ValueError("player already belongs to a guild")
        clean = name.strip()
        if not clean:
            raise ValueError("guild name is required")
        if any(guild.name.casefold() == clean.casefold() for guild in self.guilds.values()):
            raise ValueError("guild name is already in use")
        if not 0.0 <= tax_rate <= 0.50:
            raise ValueError("guild tax_rate must be between 0 and 0.50")
        guild_id = f"guild_{uuid.uuid4().hex[:12]}"
        storage = SharedStorage(
            storage_id=f"guildstore_{uuid.uuid4().hex[:12]}",
            storage_kind="guild",
            member_ids=[leader.actor_id],
        )
        self.storages[storage.storage_id] = storage
        guild = GuildState(
            guild_id=guild_id,
            name=clean,
            leader_id=leader.actor_id,
            member_ids=[leader.actor_id],
            emblem=emblem[:8] or "◇",
            tax_rate=tax_rate,
            storage_id=storage.storage_id,
        )
        self.guilds[guild_id] = guild
        leader.guild_id = guild_id
        leader.metadata["guild_emblem"] = guild.emblem
        return guild

    def _can_manage_guild(self, guild: GuildState, actor_id: str) -> bool:
        return actor_id == guild.leader_id or actor_id in guild.manager_ids

    def invite_to_guild(self, guild_id: str, inviter_id: str, target: CombatantState) -> GuildInvite:
        guild = self.guilds[guild_id]
        if not self._can_manage_guild(guild, inviter_id):
            raise ValueError("guild invitation requires Contract Scroll management permission")
        self._player(target)
        if target.guild_id:
            raise ValueError("target already belongs to a guild")
        invite = GuildInvite(f"guildinvite_{uuid.uuid4().hex[:12]}", guild_id, inviter_id, target.actor_id)
        self.guild_invites[invite.invite_id] = invite
        return invite

    def accept_guild_invite(self, invite_id: str, target: CombatantState) -> GuildState:
        invite = self.guild_invites[invite_id]
        if invite.status is not RequestStatus.PENDING or invite.target_id != target.actor_id:
            raise ValueError("guild invitation cannot be accepted by this player")
        if target.guild_id:
            raise ValueError("target already belongs to a guild")
        guild = self.guilds[invite.guild_id]
        invite.status = RequestStatus.ACCEPTED
        guild.member_ids.append(target.actor_id)
        target.guild_id = guild.guild_id
        target.metadata["guild_emblem"] = guild.emblem
        self.storages[guild.storage_id].member_ids.append(target.actor_id)
        return guild

    def set_guild_manager(self, guild_id: str, operator_id: str, member_id: str, enabled: bool) -> GuildState:
        guild = self.guilds[guild_id]
        if operator_id != guild.leader_id:
            raise ValueError("only the guild leader can grant Contract Scroll management permission")
        if member_id not in guild.member_ids:
            raise ValueError("manager must be a guild member")
        if enabled and member_id not in guild.manager_ids:
            guild.manager_ids.append(member_id)
        if not enabled and member_id in guild.manager_ids:
            guild.manager_ids.remove(member_id)
        return guild

    def configure_guild(
        self,
        guild_id: str,
        operator_id: str,
        *,
        tax_rate: float | None = None,
        emblem: str | None = None,
        headquarters_location_id: str | None = None,
    ) -> GuildState:
        guild = self.guilds[guild_id]
        if not self._can_manage_guild(guild, operator_id):
            raise ValueError("guild configuration requires Contract Scroll management permission")
        if tax_rate is not None:
            if not 0.0 <= tax_rate <= 0.50:
                raise ValueError("guild tax_rate must be between 0 and 0.50")
            guild.tax_rate = tax_rate
        if emblem is not None:
            guild.emblem = emblem[:8] or "◇"
        if headquarters_location_id is not None:
            guild.headquarters_location_id = headquarters_location_id
        return guild

    def leave_guild(self, actor: CombatantState) -> None:
        if not actor.guild_id:
            return
        guild = self.guilds[actor.guild_id]
        if actor.actor_id == guild.leader_id and len(guild.member_ids) > 1:
            raise ValueError("guild leader must transfer leadership before leaving")
        guild.member_ids.remove(actor.actor_id)
        if actor.actor_id in guild.manager_ids:
            guild.manager_ids.remove(actor.actor_id)
        storage = self.storages[guild.storage_id]
        if actor.actor_id in storage.member_ids:
            storage.member_ids.remove(actor.actor_id)
        actor.guild_id = None
        actor.metadata.pop("guild_emblem", None)

    def request_marriage(self, sender: CombatantState, target: CombatantState) -> MarriageRequest:
        self._player(sender)
        self._player(target)
        if sender.actor_id == target.actor_id:
            raise ValueError("cannot marry oneself")
        if sender.actor_id in self.marriage_by_actor or target.actor_id in self.marriage_by_actor:
            raise ValueError("one of the players is already married")
        request = MarriageRequest(f"marriagereq_{uuid.uuid4().hex[:12]}", sender.actor_id, target.actor_id)
        self.marriage_requests[request.request_id] = request
        return request

    def accept_marriage(
        self,
        request_id: str,
        sender: CombatantState,
        target: CombatantState,
        *,
        accepter_id: str,
        now_ms: int,
    ) -> MarriageState:
        request = self.marriage_requests[request_id]
        if request.status is not RequestStatus.PENDING or request.target_id != accepter_id:
            raise ValueError("marriage request cannot be accepted by this player")
        if sender.actor_id != request.sender_id or target.actor_id != request.target_id:
            raise ValueError("marriage participant state does not match request")
        if sender.actor_id in self.marriage_by_actor or target.actor_id in self.marriage_by_actor:
            raise ValueError("one of the players is already married")
        request.status = RequestStatus.ACCEPTED
        shared_inventory = dict(sender.inventory)
        for instance_id, item in target.inventory.items():
            if instance_id in shared_inventory:
                raise ValueError("inventory instance collision prevents marriage merge")
            shared_inventory[instance_id] = item
        sender.inventory = shared_inventory
        target.inventory = shared_inventory
        shared_col = sender.col + target.col
        sender.col = shared_col
        target.col = shared_col
        marriage = MarriageState(
            marriage_id=f"marriage_{uuid.uuid4().hex[:12]}",
            partner_ids=(sender.actor_id, target.actor_id),
            shared_wallet_col=shared_col,
            started_at_ms=now_ms,
        )
        self.marriages[marriage.marriage_id] = marriage
        self.marriage_by_actor[sender.actor_id] = marriage.marriage_id
        self.marriage_by_actor[target.actor_id] = marriage.marriage_id
        sender.metadata["marriage_id"] = marriage.marriage_id
        sender.metadata["spouse_id"] = target.actor_id
        target.metadata["marriage_id"] = marriage.marriage_id
        target.metadata["spouse_id"] = sender.actor_id
        return marriage

    def marriage_for(self, actor_id: str) -> MarriageState | None:
        marriage_id = self.marriage_by_actor.get(actor_id)
        if not marriage_id:
            return None
        marriage = self.marriages.get(marriage_id)
        return marriage if marriage and marriage.active else None

    def apply_wallet_delta(self, actor_id: str, delta: int, actors: dict[str, CombatantState]) -> int:
        marriage = self.marriage_for(actor_id)
        if marriage is None:
            actor = actors[actor_id]
            actor.col += delta
            return actor.col
        marriage.shared_wallet_col += delta
        if marriage.shared_wallet_col < 0:
            marriage.shared_wallet_col -= delta
            raise ValueError("shared marriage wallet cannot become negative")
        for partner_id in marriage.partner_ids:
            actors[partner_id].col = marriage.shared_wallet_col
        return marriage.shared_wallet_col

    def sync_wallet_from_actor(self, actor_id: str, actors: dict[str, CombatantState]) -> int:
        marriage = self.marriage_for(actor_id)
        if marriage is None:
            return actors[actor_id].col
        marriage.shared_wallet_col = actors[actor_id].col
        for partner_id in marriage.partner_ids:
            actors[partner_id].col = marriage.shared_wallet_col
        return marriage.shared_wallet_col

    def guild_tax_for(self, actor: CombatantState, gross_col: int) -> tuple[int, GuildState | None]:
        if gross_col <= 0:
            return 0, None
        matches = [guild for guild in self.guilds.values() if actor.actor_id in guild.member_ids]
        if len(matches) > 1:
            raise RuntimeError(f"actor belongs to multiple authoritative guilds: {actor.actor_id}")
        if not matches:
            return 0, None
        guild = matches[0]
        return max(0, int(gross_col * guild.tax_rate)), guild

    def deposit_storage(
        self,
        actor: CombatantState,
        storage_id: str,
        instance_id: str,
        *,
        quantity: int | None = None,
    ) -> ItemInstance:
        storage = self.storages[storage_id]
        if actor.actor_id not in storage.member_ids:
            raise ValueError("actor cannot access this shared storage")
        if instance_id not in actor.inventory:
            raise KeyError(instance_id)
        if instance_id in actor.equipment.values():
            raise ValueError("equipped items must be unequipped before deposit")
        source = actor.inventory[instance_id]
        qty = source.quantity if quantity is None else quantity
        if qty < 1 or qty > source.quantity:
            raise ValueError("invalid storage deposit quantity")
        moving = deepcopy(source)
        moving.instance_id = f"stored_{uuid.uuid4().hex[:12]}"
        moving.quantity = qty
        moving.owner_id = None
        source.quantity -= qty
        if source.quantity <= 0:
            actor.inventory.pop(instance_id)
        storage.items[moving.instance_id] = moving
        return moving

    def withdraw_storage(
        self,
        actor: CombatantState,
        storage_id: str,
        stored_instance_id: str,
        catalog: Catalog,
        *,
        quantity: int | None = None,
    ) -> ItemInstance:
        storage = self.storages[storage_id]
        if actor.actor_id not in storage.member_ids:
            raise ValueError("actor cannot access this shared storage")
        source = storage.items[stored_instance_id]
        qty = source.quantity if quantity is None else quantity
        if qty < 1 or qty > source.quantity:
            raise ValueError("invalid storage withdrawal quantity")
        moving = deepcopy(source)
        moving.instance_id = f"item_{uuid.uuid4().hex[:12]}"
        moving.quantity = qty
        moving.owner_id = actor.actor_id
        if not can_receive(actor, moving, catalog):
            raise ValueError("withdrawal would exceed carrying capacity")
        source.quantity -= qty
        if source.quantity <= 0:
            storage.items.pop(stored_instance_id)
        add_item(actor, moving, catalog)
        return moving

    def dump_state(self) -> dict:
        return {
            "friend_requests": {key: asdict(value) for key, value in self.friend_requests.items()},
            "friends": {actor_id: sorted(values) for actor_id, values in self.friends.items()},
            "storages": {key: asdict(value) for key, value in self.storages.items()},
            "friend_storage_by_pair": dict(self.friend_storage_by_pair),
            "guilds": {key: asdict(value) for key, value in self.guilds.items()},
            "guild_invites": {key: asdict(value) for key, value in self.guild_invites.items()},
            "marriage_requests": {key: asdict(value) for key, value in self.marriage_requests.items()},
            "marriages": {key: asdict(value) for key, value in self.marriages.items()},
            "marriage_by_actor": dict(self.marriage_by_actor),
        }

    @staticmethod
    def _item_from_payload(payload: dict) -> ItemInstance:
        from sao_mcp.domain.models import EnhancementTrack

        row = dict(payload)
        row["enhancements"] = {
            EnhancementTrack(key): int(value)
            for key, value in row.get("enhancements", {}).items()
        }
        return ItemInstance(**row)

    def load_state(self, payload: dict, actors: dict[str, CombatantState]) -> None:
        self.friend_requests = {
            key: FriendRequest(
                request_id=row["request_id"], sender_id=row["sender_id"], target_id=row["target_id"],
                status=RequestStatus(row["status"]),
            )
            for key, row in payload.get("friend_requests", {}).items()
        }
        self.friends = {actor_id: set(values) for actor_id, values in payload.get("friends", {}).items()}
        self.storages = {}
        for key, row in payload.get("storages", {}).items():
            storage = SharedStorage(
                storage_id=row["storage_id"],
                storage_kind=row["storage_kind"],
                member_ids=list(row.get("member_ids", [])),
                items={
                    item_id: self._item_from_payload(item)
                    for item_id, item in row.get("items", {}).items()
                },
            )
            self.storages[key] = storage
        self.friend_storage_by_pair = dict(payload.get("friend_storage_by_pair", {}))
        self.guilds = {
            key: GuildState(
                guild_id=row["guild_id"], name=row["name"], leader_id=row["leader_id"],
                member_ids=list(row.get("member_ids", [])), manager_ids=list(row.get("manager_ids", [])),
                emblem=row.get("emblem", "◇"), tax_rate=float(row.get("tax_rate", 0.05)),
                vault_col=int(row.get("vault_col", 0)), storage_id=row.get("storage_id", ""),
                headquarters_location_id=row.get("headquarters_location_id"),
            )
            for key, row in payload.get("guilds", {}).items()
        }
        self.guild_invites = {
            key: GuildInvite(
                invite_id=row["invite_id"], guild_id=row["guild_id"], inviter_id=row["inviter_id"],
                target_id=row["target_id"], status=RequestStatus(row["status"]),
            )
            for key, row in payload.get("guild_invites", {}).items()
        }
        self.marriage_requests = {
            key: MarriageRequest(
                request_id=row["request_id"], sender_id=row["sender_id"], target_id=row["target_id"],
                status=RequestStatus(row["status"]),
            )
            for key, row in payload.get("marriage_requests", {}).items()
        }
        self.marriages = {
            key: MarriageState(
                marriage_id=row["marriage_id"], partner_ids=tuple(row["partner_ids"]),
                shared_wallet_col=int(row["shared_wallet_col"]), active=bool(row.get("active", True)),
                started_at_ms=int(row.get("started_at_ms", 0)), ended_at_ms=row.get("ended_at_ms"),
                end_reason=row.get("end_reason"),
            )
            for key, row in payload.get("marriages", {}).items()
        }
        self.marriage_by_actor = dict(payload.get("marriage_by_actor", {}))

        # Pydantic restores each actor inventory independently. Relink active spouses to one pool and one wallet.
        for marriage in self.marriages.values():
            if not marriage.active:
                continue
            a_id, b_id = marriage.partner_ids
            if a_id not in actors or b_id not in actors:
                continue
            a, b = actors[a_id], actors[b_id]
            pool = a.inventory
            if set(pool) != set(b.inventory):
                for item_id, item in b.inventory.items():
                    pool.setdefault(item_id, item)
            a.inventory = pool
            b.inventory = pool
            a.col = marriage.shared_wallet_col
            b.col = marriage.shared_wallet_col
            a.metadata["marriage_id"] = marriage.marriage_id
            b.metadata["marriage_id"] = marriage.marriage_id
            a.metadata["spouse_id"] = b_id
            b.metadata["spouse_id"] = a_id
