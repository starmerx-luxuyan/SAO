from __future__ import annotations

import uuid

from sao_mcp.corpus.floor5 import (
    BLUE_BLUEBERRY_TART,
    KARLUIN_RELIC_COIN,
    KARLUIN_RELIC_GEM,
    MOURNFUL_WRAITH,
    RING_OF_LUMINESCENCE,
    SLY_SHREWMAN,
)
from sao_mcp.corpus.loot import CORE_LOOT_TABLES
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES
from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.inventory import add_item, recompute_equipment_stats


KARLUIN = "floor_5_karluin"
BLINK_AND_BRINK = "floor_5_blink_and_brink"
CATACOMBS_L1 = "floor_5_karluin_catacombs_l1"
CATACOMBS_LOWER = "floor_5_karluin_catacombs_lower"
RUINED_TEMPLE = "floor_5_karluin_ruined_temple"
OLD_CASTLE = "floor_5_karluin_old_castle"
OLD_CASTLE_BASEMENT = "floor_5_karluin_old_castle_basement"

RELIC_BONUS_MS = 60 * 60 * 1000
RELIC_SEARCH_MS = 5 * 60 * 1000
MEAL_TIME_MS = 10 * 60 * 1000  # Simulation meal duration; the one-hour buff itself is canon.

RELIC_LOCATIONS = {
    KARLUIN,
    CATACOMBS_L1,
    CATACOMBS_LOWER,
    RUINED_TEMPLE,
    OLD_CASTLE,
    OLD_CASTLE_BASEMENT,
}


class Floor5KarluinScenario:
    """Karluin relic hunting and catacomb hazards from Scherzo of Deep Night."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        for monster_id in (MOURNFUL_WRAITH, SLY_SHREWMAN):
            definition = AINCRAD_MONSTERS[monster_id]
            CORE_LOOT_TABLES[definition.loot_table_id] = AINCRAD_MONSTER_LOOT_TABLES[
                definition.loot_table_id
            ]

    def order_blue_blueberry_tart(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != BLINK_AND_BRINK:
            raise ValueError("Blue-Blueberry Tart is served at BLINK & BRINK")
        self.runtime.advance_world(MEAL_TIME_MS)
        actor.metadata["relic_finding_bonus_until_ms"] = self.runtime.world.now_ms + RELIC_BONUS_MS
        actor.metadata["last_relic_food"] = BLUE_BLUEBERRY_TART
        return self.relic_bonus_state(actor_id)

    def relic_bonus_state(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        until = int(actor.metadata.get("relic_finding_bonus_until_ms", 0))
        remaining = max(0, until - self.runtime.world.now_ms)
        return {
            "actor_id": actor_id,
            "active": remaining > 0,
            "remaining_ms": remaining,
            "expires_at_ms": until,
            "works_in": sorted(RELIC_LOCATIONS),
        }

    def search_relic(self, actor_id: str) -> ItemInstance:
        actor = self.runtime.actors[actor_id]
        state = self.relic_bonus_state(actor_id)
        if not state["active"]:
            raise ValueError("Relic Finding Bonus is not active")
        if actor.location_id not in RELIC_LOCATIONS:
            raise ValueError("Relic Finding Bonus only works inside and below Karluin")
        self.runtime.advance_world(RELIC_SEARCH_MS)

        ring_found = bool(actor.metadata.get("karluin_luminescence_ring_found"))
        if actor.location_id == RUINED_TEMPLE and not ring_found:
            template_id = RING_OF_LUMINESCENCE
            actor.metadata["karluin_luminescence_ring_found"] = True
        else:
            search_count = int(actor.metadata.get("karluin_relic_search_count", 0))
            template_id = KARLUIN_RELIC_COIN if search_count % 2 == 0 else KARLUIN_RELIC_GEM
            actor.metadata["karluin_relic_search_count"] = search_count + 1

        item = ItemInstance(
            instance_id=f"relic_{uuid.uuid4().hex[:12]}",
            template_id=template_id,
            owner_id=actor_id,
            quantity=1,
        )
        add_item(actor, item, self.runtime.catalog, allow_overweight=True)
        return item

    def breathe_on_luminescence_ring(self, actor_id: str, instance_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        item = actor.inventory[instance_id]
        if item.template_id != RING_OF_LUMINESCENCE:
            raise ValueError("item is not the Ring of Luminescence")
        item.metadata["luminescent"] = True
        item.metadata["activated_at_ms"] = self.runtime.world.now_ms
        return {
            "instance_id": instance_id,
            "template_id": item.template_id,
            "luminescent": True,
        }

    def create_mournful_wraith_encounter(self, actor_id: str):
        actor = self.runtime.actors[actor_id]
        if actor.location_id != CATACOMBS_LOWER:
            raise ValueError("Mournful Wraith encounter requires Karluin's lower catacombs")
        definition = AINCRAD_MONSTERS[MOURNFUL_WRAITH]
        monster = self.runtime._create_monster(
            name=definition.name,
            level=definition.level,
            location_id=definition.location_id,
            hp_factor=definition.hp_factor,
            loot_table_id=definition.loot_table_id,
            quest_kill_id=definition.quest_kill_id,
        )
        monster.metadata.update({"monster_id": MOURNFUL_WRAITH, "monster_tags": list(definition.tags)})
        encounter = self.runtime.start_encounter([actor_id, monster.actor_id], zone_id=CATACOMBS_LOWER)
        return encounter, monster

    def trigger_shrewman_robbery(self, actor_id: str, instance_id: str):
        actor = self.runtime.actors[actor_id]
        if actor.location_id != CATACOMBS_LOWER:
            raise ValueError("Sly Shrewman robbery occurs in Karluin's lower catacombs")
        if instance_id not in actor.inventory:
            raise KeyError(instance_id)

        definition = AINCRAD_MONSTERS[SLY_SHREWMAN]
        thief = self.runtime._create_monster(
            name=definition.name,
            level=definition.level,
            location_id=definition.location_id,
            hp_factor=definition.hp_factor,
            loot_table_id=definition.loot_table_id,
            quest_kill_id=definition.quest_kill_id,
        )
        thief.metadata.update({"monster_id": SLY_SHREWMAN, "monster_tags": list(definition.tags)})

        item = actor.inventory.pop(instance_id)
        for slot, equipped_id in list(actor.equipment.items()):
            if equipped_id == instance_id:
                actor.equipment.pop(slot)
        recompute_equipment_stats(actor, self.runtime.catalog)
        item.owner_id = thief.actor_id
        item.metadata["robbed_from_actor_id"] = actor_id
        thief.inventory[instance_id] = item
        thief.metadata.setdefault("robbed_instance_ids", []).append(instance_id)

        encounter = self.runtime.start_encounter([actor_id, thief.actor_id], zone_id=CATACOMBS_LOWER)
        self.runtime._append(
            encounter,
            "sly_shrewman_robbing",
            thief.actor_id,
            actor_id,
            stolen_instance_id=instance_id,
            template_id=item.template_id,
            ownership_overwritten=True,
        )
        return encounter, thief, item

    def recover_shrewman_stolen_items(self, actor_id: str, thief_id: str) -> list[str]:
        actor = self.runtime.actors[actor_id]
        thief = self.runtime.actors[thief_id]
        if thief.alive:
            raise ValueError("the Sly Shrewman must be defeated before stolen items can be recovered")
        recovered: list[str] = []
        for instance_id in list(thief.metadata.get("robbed_instance_ids", ())):
            item = thief.inventory.pop(instance_id, None)
            if item is None:
                continue
            if item.metadata.get("robbed_from_actor_id") != actor_id:
                continue
            item.owner_id = actor_id
            item.metadata.pop("robbed_from_actor_id", None)
            add_item(actor, item, self.runtime.catalog, allow_overweight=True)
            recovered.append(instance_id)
        thief.metadata["robbed_instance_ids"] = [
            instance_id
            for instance_id in thief.metadata.get("robbed_instance_ids", ())
            if instance_id not in recovered
        ]
        return recovered


def install_floor5_karluin_scenario(runtime) -> Floor5KarluinScenario:
    required_locations = RELIC_LOCATIONS | {BLINK_AND_BRINK}
    missing = sorted(required_locations - set(runtime.world_map.locations))
    if missing:
        raise RuntimeError(f"Floor 5 Karluin world corpus is incomplete: {missing}")
    required_edges = {
        frozenset((KARLUIN, BLINK_AND_BRINK)),
        frozenset((KARLUIN, CATACOMBS_L1)),
        frozenset((CATACOMBS_L1, CATACOMBS_LOWER)),
        frozenset((KARLUIN, RUINED_TEMPLE)),
        frozenset((KARLUIN, OLD_CASTLE)),
        frozenset((OLD_CASTLE, OLD_CASTLE_BASEMENT)),
    }
    present_edges = {
        frozenset((edge.from_location_id, edge.to_location_id))
        for edge in runtime.world_map.connections
    }
    missing_edges = required_edges - present_edges
    if missing_edges:
        raise RuntimeError(f"Floor 5 Karluin world routes are incomplete: {sorted(map(sorted, missing_edges))}")
    return Floor5KarluinScenario(runtime)
