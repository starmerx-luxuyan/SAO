from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path: str, old: str, new: str, expected: int) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} matches, found {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new), encoding="utf-8")


# Ground-loot cache actors are container objects, not item owners. Keep them distinct from a
# normal one-actor inventory while preserving marriage-shared inventory as one actor pool.
path = "src/sao_mcp/rules/state_authority.py"
replace_once(
    path,
    "    determined by the container: an actor inventory pool, shared storage, or market escrow.\n",
    "    determined by the container: an actor inventory pool, ground-loot cache, shared storage, or market escrow.\n",
)
replace_once(
    path,
    '''            matches.append(
                ItemContainerRef(
                    "actor_inventory",
                    "actors:" + "::".join(actor_ids),
                    actor_ids,
                    item,
                )
            )
''',
    '''            ground_cache_actor_id = (
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
''',
)
replace_once(
    path,
    '''    for actor_ids, inventory in _actor_inventory_pools(runtime):
        if len(actor_ids) > 1:
''',
    '''    for actor_ids, inventory in _actor_inventory_pools(runtime):
        ground_cache_actor_id = (
            actor_ids[0]
            if len(actor_ids) == 1
            and runtime.actors[actor_ids[0]].metadata.get("ground_loot_cache") is True
            else None
        )
        if len(actor_ids) > 1:
''',
)
replace_once(
    path,
    '''            container = "actors:" + "::".join(actor_ids)
            previous = seen_instances.setdefault(instance_id, container)
            if previous != container:
                raise RuntimeError(
                    f"item instance {instance_id} exists in multiple live containers: {previous}, {container}"
                )
            if item.owner_id not in actor_ids:
                raise RuntimeError(
                    f"item {instance_id} owner_id projection {item.owner_id!r} is outside its actor inventory {actor_ids}"
                )
''',
    '''            container = (
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
''',
)

# NPC transport is itself one of the approved location authorities. It already resolves a
# materialized NPC first and falls back to NPCState only when no materialized actor exists.
path = "tests/test_current_state_authority_source.py"
replace_once(
    path,
    '    Path("runtime/npc_autonomy_runtime.py"),\n',
    '    Path("runtime/npc_autonomy_runtime.py"),\n    Path("rules/transport.py"),\n',
)

# Scenario decisions must ask the runtime for current NPC location, so a materialized NPC wins.
path = "src/sao_mcp/scenarios/floor4_nocturne.py"
replace_count(
    path,
    'self.runtime.npcs.states[YOFILIS_ID].location_id',
    'self.runtime.npc_location_id(YOFILIS_ID)',
    4,
)
replace_count(
    path,
    'self.runtime.npcs.states[CETRANN_ID].location_id',
    'self.runtime.npc_location_id(CETRANN_ID)',
    1,
)

# Flag ownership follows its actual live container. Deployment identity is the actor who plants
# the flag, while guild membership comes from GuildState rather than CombatantState.guild_id.
path = "src/sao_mcp/scenarios/floor5_fuscus.py"
replace_once(
    path,
    'from sao_mcp.rules.inventory import add_item, locate_item_container\n',
    'from sao_mcp.rules.inventory import add_item\nfrom sao_mcp.rules.state_authority import authoritative_guild_id, locate_runtime_item\n',
)
replace_once(
    path,
    '''        located = locate_item_container(self.runtime.actors, flag_id)
        if located is None:
            if state.get("flag_drop_resolved"):
                raise RuntimeError("resolved Flag of Valor instance is missing from authoritative inventories")
            return None
        container, flag = located
        if flag.template_id != FLAG_OF_VALOR:
            raise RuntimeError("Fuscus flag instance ID points to the wrong item template")
        encounter_id = flag.metadata.get("deployed_encounter_id")
        if encounter_id is None:
            return None
        if flag.owner_id != container.actor_id:
            raise RuntimeError("deployed Flag of Valor owner_id disagrees with its authoritative inventory container")
        if encounter_id not in self.runtime.encounters:
            raise RuntimeError("deployed Flag of Valor references an unknown encounter")
        encounter = self.runtime.encounters[encounter_id]
        affected = sorted(
            actor_id
            for actor_id, actor in encounter.participants.items()
            if actor.metadata.get("flag_of_valor_source_actor_id") == flag.owner_id
            and actor.metadata.get("flag_of_valor_encounter_id") == encounter_id
        )
        return {
            "owner_id": flag.owner_id,
''',
    '''        located = locate_runtime_item(self.runtime, flag_id)
        if located is None:
            if state.get("flag_drop_resolved"):
                raise RuntimeError("resolved Flag of Valor instance is missing from authoritative containers")
            return None
        flag = located.item
        if flag.template_id != FLAG_OF_VALOR:
            raise RuntimeError("Fuscus flag instance ID points to the wrong item template")
        encounter_id = flag.metadata.get("deployed_encounter_id")
        if encounter_id is None:
            return None
        deployed_by_actor_id = flag.metadata.get("deployed_by_actor_id")
        if not isinstance(deployed_by_actor_id, str):
            raise RuntimeError("deployed Flag of Valor has no authoritative wielder")
        if located.kind != "actor_inventory" or deployed_by_actor_id not in located.actor_ids:
            raise RuntimeError("deployed Flag of Valor is no longer in its wielder's inventory pool")
        if encounter_id not in self.runtime.encounters:
            raise RuntimeError("deployed Flag of Valor references an unknown encounter")
        encounter = self.runtime.encounters[encounter_id]
        affected = sorted(
            actor_id
            for actor_id, actor in encounter.participants.items()
            if actor.metadata.get("flag_of_valor_source_actor_id") == deployed_by_actor_id
            and actor.metadata.get("flag_of_valor_encounter_id") == encounter_id
        )
        return {
            "owner_id": deployed_by_actor_id,
''',
)
replace_once(
    path,
    '''        owner = self.runtime.actors[actor_id]
        flag = self._owned_flag(actor_id)
        if not owner.guild_id:
            raise ValueError("Flag of Valor requires the wielder to belong to a guild")
''',
    '''        owner = self.runtime.actors[actor_id]
        flag = self._owned_flag(actor_id)
        owner_guild_id = authoritative_guild_id(self.runtime, actor_id)
        if owner_guild_id is None:
            raise ValueError("Flag of Valor requires the wielder to belong to a guild")
''',
)
replace_once(
    path,
    '''            if target.guild_id != owner.guild_id:
                continue
''',
    '''            if authoritative_guild_id(self.runtime, target_id) != owner_guild_id:
                continue
''',
)
replace_once(
    path,
    '        flag.metadata["deployed_encounter_id"] = encounter_id\n',
    '        flag.metadata["deployed_encounter_id"] = encounter_id\n        flag.metadata["deployed_by_actor_id"] = actor_id\n',
)
replace_once(
    path,
    '''        flag.metadata.pop("deployed_encounter_id", None)
        return {"owner_id": actor_id, "encounter_id": encounter_id, "deployed": False}
''',
    '''        flag.metadata.pop("deployed_encounter_id", None)
        flag.metadata.pop("deployed_by_actor_id", None)
        return {"owner_id": actor_id, "encounter_id": encounter_id, "deployed": False}
''',
)

# Floor 6 named-key states resolve the live container instead of the legacy actor-inventory-only helper.
path = "src/sao_mcp/scenarios/floor6_buxum.py"
replace_once(
    path,
    'from sao_mcp.rules.inventory import add_item, locate_item_container\n',
    'from sao_mcp.rules.inventory import add_item\nfrom sao_mcp.rules.state_authority import require_sole_actor_item_holder\n',
)
replace_once(
    path,
    '''        located = locate_item_container(self.runtime.actors, key_id)
        if located is None:
            return None
        container, key = located
        if key.template_id != COMBINED_IRON_KEY_ID:
            raise RuntimeError("Floor 6 combined-key instance ID points to the wrong item template")
        if key.owner_id is not None and key.owner_id != container.actor_id:
            raise RuntimeError("Floor 6 combined key owner_id disagrees with its authoritative inventory container")
        return container, key
''',
    '''        try:
            holder, key = require_sole_actor_item_holder(self.runtime, key_id)
        except KeyError:
            return None
        if key.template_id != COMBINED_IRON_KEY_ID:
            raise RuntimeError("Floor 6 combined-key instance ID points to the wrong item template")
        return holder, key
''',
)
replace_once(
    path,
    '''        if key.owner_id != holder.actor_id or holder.metadata.get("npc_definition_id") != KYSARAH_ID:
            raise ValueError("the canonical Buxum betrayal requires the combined key previously stolen by Kysarah")
''',
    '''        if holder.metadata.get("npc_definition_id") != KYSARAH_ID:
            raise ValueError("the canonical Buxum betrayal requires the combined key previously stolen by Kysarah")
''',
)

path = "src/sao_mcp/scenarios/floor6_elfwar.py"
replace_once(
    path,
    'from sao_mcp.rules.inventory import add_item, locate_item_container\n',
    'from sao_mcp.rules.inventory import add_item\nfrom sao_mcp.rules.state_authority import locate_runtime_item\n',
)
replace_once(
    path,
    '''        located = locate_item_container(self.runtime.actors, combined_id) if combined_id else None
        combined_holder = None
        combined_exists = located is not None
        if located is not None:
            container, combined = located
            if combined.template_id != COMBINED_IRON_KEY_ID:
                raise RuntimeError("Floor 6 combined-key instance ID points to the wrong item template")
            if combined.owner_id is not None and combined.owner_id != container.actor_id:
                raise RuntimeError("Floor 6 combined key owner_id disagrees with its authoritative inventory container")
            combined_holder = combined.owner_id
''',
    '''        located = locate_runtime_item(self.runtime, combined_id) if combined_id else None
        combined_holder = None
        combined_exists = located is not None
        if located is not None:
            combined = located.item
            if combined.template_id != COMBINED_IRON_KEY_ID:
                raise RuntimeError("Floor 6 combined-key instance ID points to the wrong item template")
            combined_holder = located.sole_actor_id
''',
)

path = "src/sao_mcp/scenarios/floor6_stachion.py"
replace_once(
    path,
    'from sao_mcp.rules.inventory import add_item, locate_item_container\n',
    'from sao_mcp.rules.inventory import add_item\nfrom sao_mcp.rules.state_authority import locate_runtime_item\n',
)
replace_once(
    path,
    '''            located = locate_item_container(self.runtime.actors, key_instance_id)
            if located is not None:
                container, key = located
                if key.template_id != GOLDEN_KEY_ID:
                    raise RuntimeError("Stachion confiscated golden-key instance ID points to the wrong item template")
                if key.owner_id is not None and key.owner_id != container.actor_id:
                    raise RuntimeError("Stachion golden key owner_id disagrees with its authoritative inventory container")
                key_owner_id = key.owner_id
            else:
                key_owner_id = None
''',
    '''            located = locate_runtime_item(self.runtime, key_instance_id)
            if located is not None:
                key = located.item
                if key.template_id != GOLDEN_KEY_ID:
                    raise RuntimeError("Stachion confiscated golden-key instance ID points to the wrong item template")
                key_owner_id = located.sole_actor_id
            else:
                key_owner_id = None
''',
)

# Floor 8 scenario membership decisions resolve from GuildState; actor.guild_id remains only a projection.
path = "src/sao_mcp/scenarios/floor8_emergency.py"
replace_once(
    path,
    'from sao_mcp.rules.spawn import create_character_at\n',
    'from sao_mcp.rules.spawn import create_character_at\nfrom sao_mcp.rules.state_authority import authoritative_guild_id\n',
)
replace_once(
    path,
    '''        if joined.guild_id != guild_id or actor.guild_id != guild_id:
            raise RuntimeError("Floor 8 incident player did not join the authoritative clearing GuildState")
''',
    '''        if authoritative_guild_id(self.runtime, actor.actor_id) != guild_id:
            raise RuntimeError("Floor 8 incident player did not join the authoritative clearing GuildState")
''',
)
replace_once(
    path,
    '                "guild_id": self.runtime.actors[actor_id].guild_id,\n',
    '                "guild_id": authoritative_guild_id(self.runtime, actor_id),\n',
)

path = "src/sao_mcp/scenarios/floor8_sluva.py"
replace_once(
    path,
    'from sao_mcp.rules.group_travel import group_travel_record, travel_together\n',
    'from sao_mcp.rules.group_travel import group_travel_record, travel_together\nfrom sao_mcp.rules.state_authority import authoritative_guild_id\n',
)
replace_once(
    path,
    '''        guild_ids = sorted({self.runtime.actors[actor_id].guild_id for actor_id in custody_ids})
        if guild_ids != [ALS_GUILD_ID, DKB_GUILD_ID]:
''',
    '''        resolved_guild_ids = [authoritative_guild_id(self.runtime, actor_id) for actor_id in custody_ids]
        if any(guild_id is None for guild_id in resolved_guild_ids):
            raise RuntimeError("Sluva custody includes an actor outside the authoritative guild registry")
        guild_ids = sorted(set(resolved_guild_ids))
        if guild_ids != [ALS_GUILD_ID, DKB_GUILD_ID]:
''',
)
replace_once(
    path,
    '''            expected_members = {
                actor_id for actor_id in custody_ids if self.runtime.actors[actor_id].guild_id == guild_id
            }
''',
    '''            expected_members = {
                actor_id
                for actor_id in custody_ids
                if authoritative_guild_id(self.runtime, actor_id) == guild_id
            }
''',
)

# Market authority test must install the same economy adapter persistence/bootstrap uses.
path = "tests/test_state_authority.py"
replace_once(
    path,
    'from sao_mcp.runtime.persistence import export_runtime, import_runtime\n',
    'from sao_mcp.runtime.persistence import export_runtime, import_runtime\nfrom sao_mcp.runtime.property_economy import make_runtime_economy\n',
)
replace_once(
    path,
    '''    runtime = PopulationAincradRuntime(seed=617)
    seller = runtime.create_character("Seller", level=5)
''',
    '''    runtime = PopulationAincradRuntime(seed=617)
    runtime.economy = make_runtime_economy(runtime)
    seller = runtime.create_character("Seller", level=5)
''',
)
