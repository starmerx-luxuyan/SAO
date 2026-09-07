from __future__ import annotations

from sao_mcp.domain.models import ZoneKind
from sao_mcp.rules.inventory import personal_carry_capacity
from sao_mcp.rules.relationships import RelationshipRuntime
from sao_mcp.runtime.social_runtime import SocialTimelineAincradRuntime


GUILD_PARTY_BONUS_PER_ADDITIONAL_MEMBER = 0.02
GUILD_PARTY_BONUS_CAP = 0.10


class CommunityAincradRuntime(SocialTimelineAincradRuntime):
    """Social runtime plus authoritative friend/guild/marriage storage and finance integration."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.relationships = RelationshipRuntime()

    def _refresh_marriage_capacity(self, actor_id: str) -> None:
        marriage = self.relationships.marriage_for(actor_id)
        if marriage is None:
            self.actors[actor_id].metadata.pop("shared_carry_capacity_override", None)
            return
        a = self.actors[marriage.partner_ids[0]]
        b = self.actors[marriage.partner_ids[1]]
        shared = personal_carry_capacity(a) + personal_carry_capacity(b)
        a.metadata["shared_carry_capacity_override"] = shared
        b.metadata["shared_carry_capacity_override"] = shared

    def _is_dungeon_location(self, location_id: str | None) -> bool:
        if not location_id or location_id not in self.world_map.locations:
            return False
        return self.world_map.locations[location_id].zone_kind in {
            ZoneKind.DUNGEON,
            ZoneKind.LABYRINTH,
            ZoneKind.BOSS_ROOM,
        }

    def request_friend(self, sender_id: str, target_id: str):
        return self.relationships.request_friend(self.actors[sender_id], self.actors[target_id])

    def accept_friend(self, request_id: str, target_id: str):
        return self.relationships.accept_friend(request_id, target_id=target_id)

    def decline_friend(self, request_id: str, target_id: str):
        return self.relationships.decline_friend(request_id, target_id=target_id)

    def create_friend_storage(self, actor_id: str, friend_id: str):
        return self.relationships.create_friend_storage(actor_id, friend_id)

    def create_guild(self, leader_id: str, name: str, *, emblem: str = "◇", tax_rate: float = 0.05):
        return self.relationships.create_guild(
            self.actors[leader_id], name, emblem=emblem, tax_rate=tax_rate
        )

    def invite_to_guild(self, guild_id: str, inviter_id: str, target_id: str):
        return self.relationships.invite_to_guild(guild_id, inviter_id, self.actors[target_id])

    def accept_guild_invite(self, invite_id: str, target_id: str):
        return self.relationships.accept_guild_invite(invite_id, self.actors[target_id])

    def set_guild_manager(self, guild_id: str, operator_id: str, member_id: str, enabled: bool):
        return self.relationships.set_guild_manager(guild_id, operator_id, member_id, enabled)

    def configure_guild(self, guild_id: str, operator_id: str, **kwargs):
        guild = self.relationships.configure_guild(guild_id, operator_id, **kwargs)
        for member_id in guild.member_ids:
            if member_id in self.actors:
                self.actors[member_id].metadata["guild_emblem"] = guild.emblem
        return guild

    def request_marriage(self, sender_id: str, target_id: str):
        sender = self.actors[sender_id]
        target = self.actors[target_id]
        if sender.location_id != target.location_id:
            raise ValueError("marriage request requires both players at the same location")
        return self.relationships.request_marriage(sender, target)

    def accept_marriage(self, request_id: str, target_id: str):
        request = self.relationships.marriage_requests[request_id]
        sender = self.actors[request.sender_id]
        target = self.actors[request.target_id]
        if sender.location_id != target.location_id or sender.location_id is None:
            raise ValueError("marriage participants must remain colocated when accepting")
        marriage = self.relationships.accept_marriage(
            request_id,
            sender,
            target,
            accepter_id=target_id,
            now_ms=self.world.now_ms,
        )
        self._refresh_marriage_capacity(sender.actor_id)
        return marriage

    def partner_status(self, actor_id: str) -> dict:
        marriage = self.relationships.marriage_for(actor_id)
        if marriage is None:
            raise ValueError("actor is not married")
        spouse_id = marriage.partner_ids[1] if marriage.partner_ids[0] == actor_id else marriage.partner_ids[0]
        spouse = self.actors[spouse_id]
        return {
            "actorId": spouse.actor_id,
            "name": spouse.name,
            "level": spouse.level,
            "hp": spouse.hp,
            "maxHp": spouse.max_hp,
            "alive": spouse.alive,
            "locationId": spouse.location_id,
            "cursor": spouse.cursor.value,
            "equipment": dict(spouse.equipment),
            "statuses": [status.status_type.value for status in spouse.statuses],
        }

    def relationship_position(self, actor_id: str, target_id: str) -> dict:
        actor = self.actors[actor_id]
        target = self.actors[target_id]
        married = bool(self.relationships.marriage_for(actor_id) and actor.metadata.get("spouse_id") == target_id)
        friends = self.relationships.are_friends(actor_id, target_id)
        guildmates = bool(actor.guild_id and actor.guild_id == target.guild_id)
        if not (married or friends or guildmates):
            raise ValueError("position search requires friendship, guild comradeship or marriage")
        if guildmates and self._is_dungeon_location(target.location_id):
            return {"available": False, "reason": "guild position search is unavailable while the target is in a dungeon"}
        return {"available": True, "targetId": target_id, "locationId": target.location_id}

    def deposit_shared_storage(self, actor_id: str, storage_id: str, instance_id: str, *, quantity: int | None = None):
        storage = self.relationships.storages[storage_id]
        actor = self.actors[actor_id]
        if storage.storage_kind == "guild" and self._is_dungeon_location(actor.location_id):
            raise ValueError("guild storage cannot be opened in a dungeon")
        if storage.storage_kind == "friend_common":
            for member_id in storage.member_ids:
                if member_id in self.actors and self.actors[member_id].metadata.get("permanent_death"):
                    raise ValueError("friend common inventory is inaccessible after a member's death")
        return self.relationships.deposit_storage(actor, storage_id, instance_id, quantity=quantity)

    def withdraw_shared_storage(self, actor_id: str, storage_id: str, stored_instance_id: str, *, quantity: int | None = None):
        storage = self.relationships.storages[storage_id]
        actor = self.actors[actor_id]
        if storage.storage_kind == "guild" and self._is_dungeon_location(actor.location_id):
            raise ValueError("guild storage cannot be opened in a dungeon")
        if storage.storage_kind == "friend_common":
            for member_id in storage.member_ids:
                if member_id in self.actors and self.actors[member_id].metadata.get("permanent_death"):
                    raise ValueError("friend common inventory is inaccessible after a member's death")
        return self.relationships.withdraw_storage(
            actor, storage_id, stored_instance_id, self.catalog, quantity=quantity
        )

    def _settle_income_after_existing_credit(self, actor_id: str, gross_col: int, *, source: str) -> dict:
        actor = self.actors[actor_id]
        tax, guild = self.relationships.guild_tax_for(actor, gross_col)
        net = gross_col - tax
        marriage = self.relationships.marriage_for(actor_id)
        if marriage is not None:
            balance = self.relationships.apply_wallet_delta(actor_id, net, self.actors)
        else:
            actor.col -= tax
            balance = actor.col
        if guild is not None and tax:
            guild.vault_col += tax
        return {
            "actorId": actor_id,
            "source": source,
            "grossCol": gross_col,
            "guildTaxCol": tax,
            "netCol": net,
            "balanceCol": balance,
            "guildId": guild.guild_id if guild else None,
        }

    def _settle_expense_after_existing_debit(self, actor_id: str, amount: int) -> int:
        marriage = self.relationships.marriage_for(actor_id)
        if marriage is None:
            return self.actors[actor_id].col
        return self.relationships.apply_wallet_delta(actor_id, -amount, self.actors)

    def _grant_defeat_rewards(self, encounter, target, killer):
        payload = super()._grant_defeat_rewards(encounter, target, killer)
        if not payload:
            return payload
        finance_rows = []
        for row in payload.get("recipients", []):
            actor_id = row["actor_id"]
            gross = int(row.get("col", 0))
            if gross:
                finance_rows.append(self._settle_income_after_existing_credit(actor_id, gross, source="combat_loot"))
            self._refresh_marriage_capacity(actor_id)
        if finance_rows:
            payload["finance"] = finance_rows
            self._append(encounter, "income_settled", killer.actor_id, target.actor_id, rows=finance_rows)
        return payload

    def claim_quest(self, actor_id: str, quest_id: str):
        result = super().claim_quest(actor_id, quest_id)
        if result.col:
            self._settle_income_after_existing_credit(actor_id, result.col, source=f"quest:{quest_id}")
        self._refresh_marriage_capacity(actor_id)
        return result

    def repair_inventory_item(self, actor_id: str, instance_id: str, **kwargs):
        result = super().repair_inventory_item(actor_id, instance_id, **kwargs)
        if result.cost_col:
            self._settle_expense_after_existing_debit(actor_id, result.cost_col)
        return result

    def economy_buy_from_vendor(self, economy, actor_id: str, vendor_id: str, template_id: str, quantity: int):
        actor = self.actors[actor_id]
        result = economy.buy_from_vendor(
            actor, vendor_id, template_id, quantity, self.catalog, actor_location_id=actor.location_id
        )
        self._settle_expense_after_existing_debit(actor_id, result.total_col)
        return result

    def economy_sell_to_vendor(self, economy, actor_id: str, vendor_id: str, instance_id: str, *, quantity: int | None):
        actor = self.actors[actor_id]
        result = economy.sell_to_vendor(
            actor, vendor_id, instance_id, self.catalog,
            quantity=quantity, actor_location_id=actor.location_id,
        )
        self._settle_income_after_existing_credit(actor_id, result.received_col, source="vendor_sale")
        return result

    def economy_buy_player_listing(self, economy, buyer_id: str, listing_id: str, *, quantity: int | None):
        listing = economy.player_listings[listing_id]
        seller_id = listing.seller_id
        buyer = self.actors[buyer_id]
        seller = self.actors[seller_id]
        buyer_marriage = self.relationships.marriage_for(buyer_id)
        if buyer_marriage and seller_id in buyer_marriage.partner_ids:
            raise ValueError("spouses already share inventory and wallet; buying one another's listing is invalid")
        result = economy.buy_player_listing(
            buyer, seller, listing_id, self.catalog,
            buyer_location_id=buyer.location_id, quantity=quantity,
        )
        self._settle_expense_after_existing_debit(buyer_id, result.total_col)
        self._settle_income_after_existing_credit(seller_id, result.total_col, source="player_market_sale")
        return result

    def start_encounter(self, actor_ids, **kwargs):
        encounter = super().start_encounter(actor_ids, **kwargs)
        players = [actor for actor in encounter.participants.values() if actor.kind.value == "player"]
        for actor in players:
            actor.metadata.pop("guild_party_stat_bonus", None)
            if not actor.guild_id or not actor.party_id:
                continue
            count = sum(
                1 for other in players
                if other.actor_id != actor.actor_id
                and other.guild_id == actor.guild_id
                and other.party_id == actor.party_id
            )
            if count:
                actor.metadata["guild_party_stat_bonus"] = min(
                    GUILD_PARTY_BONUS_CAP,
                    count * GUILD_PARTY_BONUS_PER_ADDITIONAL_MEMBER,
                )
        return encounter

    def dump_relationship_state(self) -> dict:
        return self.relationships.dump_state()

    def load_relationship_state(self, payload: dict) -> None:
        self.relationships.load_state(payload, self.actors)
        for actor_id in list(self.relationships.marriage_by_actor):
            if actor_id in self.actors:
                self._refresh_marriage_capacity(actor_id)
