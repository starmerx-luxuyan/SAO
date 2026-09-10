from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.access import actor_faction_ids


@dataclass(slots=True, frozen=True)
class ItemContainerRef:
    """Authoritative current container for one live item instance.

    ``ItemInstance.owner_id`` is a projection used by serialization/UI. Current ownership is
    determined by the container: an actor inventory pool, ground-loot cache, shared storage, or market escrow.
    Married actors may intentionally share one inventory object, so one inventory container can
    have two actor members without inventing a single holder.
    """

    kind: str
    container_id: str
    actor_ids: tuple[str, ...]
    item: ItemInstance

    @property
    def sole_actor_id(self) -> str | None:
        if self.kind == "actor_inventory" and len(self.actor_ids) == 1:
            return self.actor_ids[0]
        return None


def _actor_inventory_pools(runtime) -> list[tuple[tuple[str, ...], dict[str, ItemInstance]]]:
    pools: dict[int, tuple[dict[str, ItemInstance], list[str]]] = {}
    for actor_id, actor in runtime.actors.items():
        if actor.actor_id != actor_id:
            raise RuntimeError(f"actor registry key disagrees with actor_id: {actor_id} != {actor.actor_id}")
        marker = id(actor.inventory)
        if marker not in pools:
            pools[marker] = (actor.inventory, [])
        pools[marker][1].append(actor_id)
    return [
        (tuple(sorted(actor_ids)), inventory)
        for inventory, actor_ids in pools.values()
    ]


def locate_runtime_item(runtime, instance_id: str) -> ItemContainerRef | None:
    """Locate an item from live containers instead of trusting ``ItemInstance.owner_id``."""

    matches: list[ItemContainerRef] = []
    for actor_ids, inventory in _actor_inventory_pools(runtime):
        if instance_id in inventory:
            item = inventory[instance_id]
            if item.instance_id != instance_id:
                raise RuntimeError(
                    f"actor inventory key disagrees with item instance_id: {instance_id} != {item.instance_id}"
                )
            ground_cache_actor_id = (
                actor_ids[0]
                if len(actor_ids) == 1
                and runtime.actors[actor_ids[0]].metadata.get("ground_loot_cache") is True
                else None
            )
            matches.append(
                ItemContainerRef(
                    "ground_cache" if ground_cache_actor_id is not None else "actor_inventory",
                    ground_cache_actor_id or ("actors:" + "::".join(actor_ids)),
                    () if ground_cache_actor_id is not None else actor_ids,
                    item,
                )
            )

    relationships = getattr(runtime, "relationships", None)
    if relationships is not None:
        for storage_id, storage in relationships.storages.items():
            if instance_id not in storage.items:
                continue
            item = storage.items[instance_id]
            if item.instance_id != instance_id:
                raise RuntimeError(
                    f"storage key disagrees with item instance_id: {instance_id} != {item.instance_id}"
                )
            matches.append(ItemContainerRef("shared_storage", storage_id, (), item))

    economy = getattr(runtime, "economy", None)
    if economy is not None:
        for listing_id, listing in economy.player_listings.items():
            if listing.item.instance_id != instance_id:
                continue
            matches.append(ItemContainerRef("market_escrow", listing_id, (), listing.item))

    if len(matches) > 1:
        locations = ", ".join(f"{row.kind}:{row.container_id}" for row in matches)
        raise RuntimeError(f"item instance {instance_id} exists in multiple live containers: {locations}")
    return matches[0] if matches else None


def require_sole_actor_item_holder(runtime, instance_id: str):
    """Return the one actor physically represented as holding an item.

    Shared marriage inventory, storage and market escrow deliberately do not collapse to an
    arbitrary actor. Callers that require one holder must resolve that ambiguity explicitly.
    """

    located = locate_runtime_item(runtime, instance_id)
    if located is None:
        raise KeyError(instance_id)
    actor_id = located.sole_actor_id
    if actor_id is None:
        raise ValueError(
            f"item {instance_id} has no single actor holder; current container is "
            f"{located.kind}:{located.container_id}"
        )
    return runtime.actors[actor_id], located.item


def authoritative_guild_id(runtime, actor_id: str) -> str | None:
    """Resolve guild membership from ``GuildState.member_ids``.

    ``CombatantState.guild_id`` is retained as a synchronized projection for save/UI compatibility,
    but it cannot create membership on its own.
    """

    if actor_id not in runtime.actors:
        raise KeyError(actor_id)
    relationships = getattr(runtime, "relationships", None)
    if relationships is None:
        return None
    matches = [
        guild_id
        for guild_id, guild in relationships.guilds.items()
        if actor_id in guild.member_ids
    ]
    if len(matches) > 1:
        raise RuntimeError(f"actor {actor_id} belongs to multiple GuildState records: {sorted(matches)}")
    resolved = matches[0] if matches else None
    projected = runtime.actors[actor_id].guild_id
    if projected != resolved:
        raise RuntimeError(
            f"actor {actor_id} guild_id projection {projected!r} disagrees with GuildState {resolved!r}"
        )
    return resolved


def quest_owner_ids(runtime, quest_id: str) -> tuple[str, ...]:
    """Return actors whose authoritative QuestRuntime progress contains this quest."""

    if quest_id not in runtime.quests.definitions:
        raise KeyError(quest_id)
    return tuple(
        sorted(
            actor_id
            for actor_id, progress in runtime.quests.progress_by_actor.items()
            if quest_id in progress
        )
    )


def assert_runtime_state_authority(runtime) -> None:
    """Validate current-state single-source-of-truth invariants before persistence boundaries."""

    relationships = getattr(runtime, "relationships", None)

    # Actor inventory pools are containers. Sharing one pool is legal only for one active marriage.
    seen_instances: dict[str, str] = {}
    for actor_ids, inventory in _actor_inventory_pools(runtime):
        ground_cache_actor_id = (
            actor_ids[0]
            if len(actor_ids) == 1
            and runtime.actors[actor_ids[0]].metadata.get("ground_loot_cache") is True
            else None
        )
        if len(actor_ids) > 1:
            if relationships is None or len(actor_ids) != 2:
                raise RuntimeError(f"unowned shared actor inventory pool: {actor_ids}")
            marriages = [
                marriage
                for marriage in relationships.marriages.values()
                if marriage.active and tuple(sorted(marriage.partner_ids)) == actor_ids
            ]
            if len(marriages) != 1:
                raise RuntimeError(f"shared actor inventory is not backed by one active marriage: {actor_ids}")
        for instance_id, item in inventory.items():
            if item.instance_id != instance_id:
                raise RuntimeError(
                    f"actor inventory key disagrees with item instance_id: {instance_id} != {item.instance_id}"
                )
            container = (
                f"ground:{ground_cache_actor_id}"
                if ground_cache_actor_id is not None
                else "actors:" + "::".join(actor_ids)
            )
            previous = seen_instances.setdefault(instance_id, container)
            if previous != container:
                raise RuntimeError(
                    f"item instance {instance_id} exists in multiple live containers: {previous}, {container}"
                )
            if ground_cache_actor_id is not None:
                if item.owner_id is not None:
                    raise RuntimeError(
                        f"ground-cache item {instance_id} has stale owner_id {item.owner_id!r}"
                    )
            elif item.owner_id not in actor_ids:
                raise RuntimeError(
                    f"item {instance_id} owner_id projection {item.owner_id!r} is outside its actor inventory {actor_ids}"
                )

    if relationships is not None:
        # Shared storage is the current container; stored items have no single actor owner.
        for storage_id, storage in relationships.storages.items():
            if storage.storage_id != storage_id:
                raise RuntimeError(f"storage registry key disagrees with storage_id: {storage_id}")
            for instance_id, item in storage.items.items():
                if item.instance_id != instance_id:
                    raise RuntimeError(
                        f"storage key disagrees with item instance_id: {instance_id} != {item.instance_id}"
                    )
                previous = seen_instances.setdefault(instance_id, f"storage:{storage_id}")
                if previous != f"storage:{storage_id}":
                    raise RuntimeError(
                        f"item instance {instance_id} exists in multiple live containers: "
                        f"{previous}, storage:{storage_id}"
                    )
                if item.owner_id is not None:
                    raise RuntimeError(
                        f"stored item {instance_id} has stale single-owner projection {item.owner_id!r}"
                    )

        # GuildState is membership authority. Actor.guild_id and guild storage membership are projections.
        membership: dict[str, str] = {}
        for guild_id, guild in relationships.guilds.items():
            if guild.guild_id != guild_id:
                raise RuntimeError(f"guild registry key disagrees with guild_id: {guild_id}")
            if len(set(guild.member_ids)) != len(guild.member_ids):
                raise RuntimeError(f"guild {guild_id} contains duplicate member ids")
            if guild.leader_id not in guild.member_ids:
                raise RuntimeError(f"guild {guild_id} leader is not a member")
            if any(manager_id not in guild.member_ids for manager_id in guild.manager_ids):
                raise RuntimeError(f"guild {guild_id} manager is not a member")
            if guild.storage_id not in relationships.storages:
                raise RuntimeError(f"guild {guild_id} references missing storage {guild.storage_id}")
            storage = relationships.storages[guild.storage_id]
            if storage.storage_kind != "guild":
                raise RuntimeError(f"guild {guild_id} storage has wrong kind {storage.storage_kind!r}")
            if set(storage.member_ids) != set(guild.member_ids):
                raise RuntimeError(f"guild {guild_id} storage membership disagrees with GuildState")
            for actor_id in guild.member_ids:
                if actor_id not in runtime.actors:
                    raise RuntimeError(f"guild {guild_id} references missing actor {actor_id}")
                previous = membership.setdefault(actor_id, guild_id)
                if previous != guild_id:
                    raise RuntimeError(f"actor {actor_id} belongs to multiple guilds: {previous}, {guild_id}")
        for actor_id, actor in runtime.actors.items():
            if actor.guild_id != membership.get(actor_id):
                raise RuntimeError(
                    f"actor {actor_id} guild_id projection {actor.guild_id!r} disagrees with "
                    f"GuildState {membership.get(actor_id)!r}"
                )

    economy = getattr(runtime, "economy", None)
    if economy is not None:
        for listing_id, listing in economy.player_listings.items():
            if listing.listing_id != listing_id:
                raise RuntimeError(f"listing registry key disagrees with listing_id: {listing_id}")
            if listing.seller_id not in runtime.actors:
                raise RuntimeError(f"listing {listing_id} references missing seller {listing.seller_id}")
            item = listing.item
            previous = seen_instances.setdefault(item.instance_id, f"listing:{listing_id}")
            if previous != f"listing:{listing_id}":
                raise RuntimeError(
                    f"item instance {item.instance_id} exists in multiple live containers: "
                    f"{previous}, listing:{listing_id}"
                )
            if item.owner_id is not None:
                raise RuntimeError(
                    f"market escrow item {item.instance_id} has stale owner_id {item.owner_id!r}"
                )

    # NPCDefinition/NPCState are one registry; a materialized NPC actor supersedes NPCState location.
    materialized: dict[str, str] = {}
    for npc_id, state in runtime.npcs.states.items():
        if state.npc_id != npc_id or npc_id not in runtime.npcs.definitions:
            raise RuntimeError(f"NPC state registry is inconsistent for {npc_id}")
    for actor in runtime.actors.values():
        definition_id = actor.metadata.get("npc_definition_id")
        if definition_id is None:
            continue
        if not isinstance(definition_id, str) or definition_id not in runtime.npcs.definitions:
            raise RuntimeError(
                f"actor {actor.actor_id} references unknown NPC definition {definition_id!r}"
            )
        previous = materialized.setdefault(definition_id, actor.actor_id)
        if previous != actor.actor_id:
            raise RuntimeError(
                f"NPC {definition_id} has multiple materialized actors: {previous}, {actor.actor_id}"
            )
        location_lookup = getattr(runtime, "npc_location_id", None)
        if location_lookup is not None:
            resolved = location_lookup(definition_id)
            if actor.location_id is None:
                if resolved is not None:
                    raise RuntimeError(
                        f"travelling materialized NPC {definition_id} unexpectedly resolves to {resolved}"
                    )
            elif resolved != actor.location_id:
                raise RuntimeError(
                    f"materialized NPC {definition_id} location authority disagrees: "
                    f"{actor.location_id!r} != {resolved!r}"
                )

    # Faction decisions must be resolvable through the single access helper.
    for actor in runtime.actors.values():
        actor_faction_ids(actor)

    # Quest ownership is the outer progress_by_actor key. Inner ids and completion history must agree.
    for actor_id, progress_by_quest in runtime.quests.progress_by_actor.items():
        if actor_id not in runtime.actors:
            raise RuntimeError(f"quest progress references missing actor {actor_id}")
        for quest_id, progress in progress_by_quest.items():
            if quest_id not in runtime.quests.definitions:
                raise RuntimeError(f"quest progress references unknown quest {quest_id}")
            if progress.quest_id != quest_id:
                raise RuntimeError(
                    f"quest progress key {quest_id} disagrees with embedded quest_id {progress.quest_id}"
                )
            if progress.claimed and quest_id not in runtime.quests.completed_by_actor.get(actor_id, set()):
                raise RuntimeError(
                    f"claimed quest {quest_id} for {actor_id} is absent from completion history"
                )
    for actor_id, completed in runtime.quests.completed_by_actor.items():
        if actor_id not in runtime.actors:
            raise RuntimeError(f"quest completion history references missing actor {actor_id}")
        for quest_id in completed:
            if quest_id not in runtime.quests.definitions:
                raise RuntimeError(f"quest completion history references unknown quest {quest_id}")
            definition = runtime.quests.definitions[quest_id]
            if not definition.repeatable:
                progress = runtime.quests.progress_by_actor.get(actor_id, {}).get(quest_id)
                if progress is None or not progress.claimed:
                    raise RuntimeError(
                        f"non-repeatable completed quest {quest_id} for {actor_id} lacks claimed progress"
                    )
