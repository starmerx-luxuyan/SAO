from __future__ import annotations

import uuid

from sao_mcp.corpus.housing import CORE_PROPERTY_LISTINGS, PropertyKind
from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import Provenance, ProvenanceKind, ZoneKind
from sao_mcp.rules.housing import HousingState
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.relationships import SharedStorage
from sao_mcp.runtime.communications_runtime import CommunicatingAincradRuntime


PROPERTY_ENTRY_TIME_MS = 15_000  # Simulation transition time.


class HousingAincradRuntime(CommunicatingAincradRuntime):
    """Full communicating runtime plus persistent property ownership and interior world nodes."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.housing = HousingState()

    def _materialized_npc_actor(self, npc_id: str):
        matches = [
            actor
            for actor in self.actors.values()
            if actor.metadata.get("npc_definition_id") == npc_id
        ]
        if len(matches) > 1:
            raise RuntimeError(f"multiple materialized actors exist for NPC {npc_id}")
        return matches[0] if matches else None

    def npc_location_id(self, npc_id: str) -> str:
        if npc_id not in self.npcs.states:
            raise KeyError(npc_id)
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is None:
            return self.npcs.states[npc_id].location_id
        if materialized.location_id is None:
            raise RuntimeError(f"materialized NPC {npc_id} has no world location")
        return materialized.location_id

    def interact_npc(self, actor_id: str, npc_id: str):
        materialized = self._materialized_npc_actor(npc_id)
        if materialized is not None and not materialized.alive:
            raise ValueError("materialized NPC is not alive for interaction")
        actor = self.actors[actor_id]
        interaction = self.npcs.interact_at(
            actor_id,
            npc_id,
            actor_location_id=actor.location_id,
            npc_location_id=self.npc_location_id(npc_id),
            now_ms=self.world.now_ms,
            quests=self.quests,
        )
        self.quests.record_event(
            actor_id,
            kind=QuestObjectiveKind.TALK,
            target_id=npc_id,
        )
        return interaction

    def claim_quest(self, actor_id: str, quest_id: str):
        actor = self.actors[actor_id]
        definition = self.quests.definitions[quest_id]
        materialized = self._materialized_npc_actor(definition.turn_in_id)
        if materialized is not None and not materialized.alive:
            raise ValueError("materialized quest turn-in NPC is not alive")
        if actor.location_id != self.npc_location_id(definition.turn_in_id):
            raise ValueError("quest must be turned in to the designated NPC")
        return self.quests.claim(actor, quest_id, self.catalog, now_ms=self.world.now_ms)

    def _register_property_location(self, state) -> None:
        if state.interior_location_id in self.world_map.locations:
            return
        parent = self.world_map.locations[state.parent_location_id]
        listing = CORE_PROPERTY_LISTINGS.get(state.listing_id)
        provenance = listing.provenance if listing else Provenance(
            ProvenanceKind.SIMULATION,
            notes="Dynamic property restored from persistent campaign state.",
        )
        interior = LocationDefinition(
            location_id=state.interior_location_id,
            floor_number=parent.floor_number,
            name=state.name,
            zone_kind=ZoneKind.SAFE_TOWN,
            safe_zone=True,
            provenance=provenance,
        )
        self.world_map.locations[interior.location_id] = interior
        edge = TravelConnection(
            state.parent_location_id,
            interior.location_id,
            PROPERTY_ENTRY_TIME_MS,
            True,
            True,
            Provenance(ProvenanceKind.SIMULATION, notes="Property door transition time."),
        )
        self.world_map.connections = tuple(self.world_map.connections) + (edge,)
        self.world_map.adjacency.setdefault(state.parent_location_id, []).append(edge)
        self.world_map.adjacency.setdefault(interior.location_id, []).append(
            TravelConnection(
                interior.location_id,
                state.parent_location_id,
                PROPERTY_ENTRY_TIME_MS,
                True,
                True,
                edge.provenance,
            )
        )

    def list_property_market(self, *, floor_number: int | None = None) -> list[dict]:
        rows = []
        for listing in CORE_PROPERTY_LISTINGS.values():
            parent = self.world_map.locations[listing.parent_location_id]
            if floor_number is not None and parent.floor_number != floor_number:
                continue
            sold = any(state.listing_id == listing.listing_id for state in self.housing.properties.values())
            rows.append(
                {
                    "listingId": listing.listing_id,
                    "name": listing.name,
                    "kind": listing.kind.value,
                    "floor": parent.floor_number,
                    "parentLocationId": listing.parent_location_id,
                    "priceCol": listing.price_col,
                    "storageSlots": listing.storage_slots,
                    "uniqueWorldAsset": listing.unique_world_asset,
                    "sold": bool(sold and listing.unique_world_asset),
                    "questPrerequisites": list(listing.quest_prerequisites),
                    "provenance": {
                        "kind": listing.provenance.kind.value,
                        "sources": list(listing.provenance.sources),
                        "notes": listing.provenance.notes,
                    },
                }
            )
        return rows

    def _check_listing_available(self, listing) -> None:
        if listing.unique_world_asset and any(
            state.listing_id == listing.listing_id for state in self.housing.properties.values()
        ):
            raise ValueError("this unique property has already been purchased")

    def purchase_residence(self, actor_id: str, listing_id: str, *, joint_marriage: bool = True):
        actor = self.actors[actor_id]
        listing = CORE_PROPERTY_LISTINGS[listing_id]
        if listing.kind is not PropertyKind.RESIDENCE:
            raise ValueError("listing is not a player residence")
        if actor.location_id != listing.parent_location_id:
            raise ValueError("buyer must be at the property's parent location")
        self._check_listing_available(listing)
        completed = self.quests.completed_by_actor.get(actor_id, set())
        missing = [quest_id for quest_id in listing.quest_prerequisites if quest_id not in completed]
        if missing:
            raise ValueError(f"property purchase prerequisites are incomplete: {missing}")
        marriage = self.relationships.marriage_for(actor_id) if joint_marriage else None
        if marriage is not None:
            if marriage.shared_wallet_col < listing.price_col:
                raise ValueError("insufficient shared marriage Col")
            self.relationships.apply_wallet_delta(actor_id, -listing.price_col, self.actors)
            owners = list(marriage.partner_ids)
        else:
            if actor.col < listing.price_col:
                raise ValueError("insufficient Col")
            actor.col -= listing.price_col
            owners = [actor_id]

        storage = SharedStorage(
            storage_id=f"propertystore_{uuid.uuid4().hex[:12]}",
            storage_kind="property",
            member_ids=list(owners),
        )
        self.relationships.storages[storage.storage_id] = storage
        state = self.housing.create(
            listing_id=listing.listing_id,
            name=listing.name,
            kind=listing.kind,
            parent_location_id=listing.parent_location_id,
            owner_actor_ids=owners,
            guild_id=None,
            storage_id=storage.storage_id,
            purchased_at_ms=self.world.now_ms,
            purchase_price_col=listing.price_col,
        )
        state.metadata["storage_slots"] = listing.storage_slots
        state.metadata["joint_marriage_purchase"] = bool(marriage is not None)
        self._register_property_location(state)
        return state

    def purchase_guild_headquarters(self, guild_id: str, operator_id: str, listing_id: str):
        listing = CORE_PROPERTY_LISTINGS[listing_id]
        if listing.kind is not PropertyKind.GUILD_HEADQUARTERS:
            raise ValueError("listing is not a guild headquarters")
        guild = self.relationships.guilds[guild_id]
        if operator_id != guild.leader_id and operator_id not in guild.manager_ids:
            raise ValueError("guild headquarters purchase requires Contract Scroll management permission")
        operator = self.actors[operator_id]
        if operator.location_id != listing.parent_location_id:
            raise ValueError("operator must be at the headquarters parent location")
        if guild.headquarters_location_id:
            raise ValueError("guild already has a registered headquarters")
        if guild.vault_col < listing.price_col:
            raise ValueError("guild vault has insufficient Col")
        self._check_listing_available(listing)
        guild.vault_col -= listing.price_col
        state = self.housing.create(
            listing_id=listing.listing_id,
            name=listing.name,
            kind=listing.kind,
            parent_location_id=listing.parent_location_id,
            owner_actor_ids=[],
            guild_id=guild_id,
            storage_id=guild.storage_id,
            purchased_at_ms=self.world.now_ms,
            purchase_price_col=listing.price_col,
        )
        state.metadata["storage_slots"] = listing.storage_slots
        guild.headquarters_location_id = state.interior_location_id
        self._register_property_location(state)
        return state

    def can_enter_property(self, actor_id: str, property_id: str) -> bool:
        state = self.housing.properties[property_id]
        if state.kind is PropertyKind.GUILD_HEADQUARTERS:
            guild = self.relationships.guilds.get(state.guild_id or "")
            return bool(guild and actor_id in guild.member_ids)
        return actor_id in state.owner_actor_ids or actor_id in state.guest_actor_ids

    def grant_property_guest(self, owner_id: str, property_id: str, guest_id: str, *, enabled: bool = True):
        state = self.housing.properties[property_id]
        if state.kind is not PropertyKind.RESIDENCE:
            raise ValueError("guild headquarters access follows guild membership")
        if owner_id not in state.owner_actor_ids:
            raise ValueError("only a property owner can change guest access")
        if enabled and guest_id not in state.guest_actor_ids:
            state.guest_actor_ids.append(guest_id)
        if not enabled and guest_id in state.guest_actor_ids:
            state.guest_actor_ids.remove(guest_id)
        return state

    def enter_property(self, actor_id: str, property_id: str):
        actor = self.actors[actor_id]
        state = self.housing.properties[property_id]
        if actor.location_id != state.parent_location_id:
            raise ValueError("actor must be outside this property before entering")
        if not self.can_enter_property(actor_id, property_id):
            raise ValueError("actor is not authorized to enter this property")
        self.world.now_ms += PROPERTY_ENTRY_TIME_MS
        actor.location_id = state.interior_location_id
        actor.metadata["inside_property_id"] = property_id
        return state

    def exit_property(self, actor_id: str):
        actor = self.actors[actor_id]
        property_id = actor.metadata.get("inside_property_id")
        if not property_id or property_id not in self.housing.properties:
            raise ValueError("actor is not inside a registered property")
        state = self.housing.properties[str(property_id)]
        self.world.now_ms += PROPERTY_ENTRY_TIME_MS
        actor.location_id = state.parent_location_id
        actor.metadata.pop("inside_property_id", None)
        return state

    def deposit_property_storage(self, actor_id: str, property_id: str, instance_id: str, *, quantity: int | None = None):
        state = self.housing.properties[property_id]
        if actor_id not in state.owner_actor_ids and state.kind is not PropertyKind.GUILD_HEADQUARTERS:
            raise ValueError("guests cannot mutate private property storage")
        if state.kind is PropertyKind.GUILD_HEADQUARTERS and not self.can_enter_property(actor_id, property_id):
            raise ValueError("only guild members can mutate headquarters storage")
        storage = self.relationships.storages[state.storage_id]
        slots = int(state.metadata.get("storage_slots", 0))
        if instance_id not in storage.items and slots > 0 and len(storage.items) >= slots:
            raise ValueError("property storage has no free slots")
        return self.deposit_shared_storage(actor_id, state.storage_id, instance_id, quantity=quantity)

    def withdraw_property_storage(self, actor_id: str, property_id: str, stored_instance_id: str, *, quantity: int | None = None):
        state = self.housing.properties[property_id]
        if actor_id not in state.owner_actor_ids and state.kind is not PropertyKind.GUILD_HEADQUARTERS:
            raise ValueError("guests cannot mutate private property storage")
        if state.kind is PropertyKind.GUILD_HEADQUARTERS and not self.can_enter_property(actor_id, property_id):
            raise ValueError("only guild members can mutate headquarters storage")
        return self.withdraw_shared_storage(
            actor_id,
            state.storage_id,
            stored_instance_id,
            quantity=quantity,
        )

    def dump_housing_state(self) -> dict:
        return self.housing.dump_state()

    def load_housing_state(self, payload: dict) -> None:
        self.housing.load_state(payload)
        for state in self.housing.properties.values():
            self._register_property_location(state)
