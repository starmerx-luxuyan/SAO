from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import CombatantState, ItemInstance
from sao_mcp.rules.inventory import add_item


@dataclass(slots=True, frozen=True)
class LootEntry:
    template_id: str
    chance: float
    min_quantity: int = 1
    max_quantity: int = 1


@dataclass(slots=True, frozen=True)
class LootTable:
    table_id: str
    col_min: int = 0
    col_max: int = 0
    xp_min: int = 0
    xp_max: int = 0
    entries: tuple[LootEntry, ...] = ()
    provenance: str = "simulation"


@dataclass(slots=True, frozen=True)
class LootDrop:
    template_id: str
    quantity: int


@dataclass(slots=True, frozen=True)
class LootRoll:
    table_id: str
    col: int
    xp: int
    drops: tuple[LootDrop, ...]


def roll_loot(table: LootTable, rng: random.Random) -> LootRoll:
    col = rng.randint(table.col_min, table.col_max) if table.col_max >= table.col_min else table.col_min
    xp = rng.randint(table.xp_min, table.xp_max) if table.xp_max >= table.xp_min else table.xp_min
    drops: list[LootDrop] = []
    for entry in table.entries:
        chance = max(0.0, min(1.0, entry.chance))
        if rng.random() <= chance:
            lo = max(1, entry.min_quantity)
            hi = max(lo, entry.max_quantity)
            drops.append(LootDrop(entry.template_id, rng.randint(lo, hi)))
    return LootRoll(table.table_id, max(0, col), max(0, xp), tuple(drops))


def grant_loot(
    actor: CombatantState,
    roll: LootRoll,
    catalog: Catalog,
    *,
    allow_overweight: bool = True,
) -> list[ItemInstance]:
    actor.col += roll.col
    actor.metadata["experience"] = int(actor.metadata.get("experience", 0)) + roll.xp
    granted: list[ItemInstance] = []
    for drop in roll.drops:
        template = catalog.item(drop.template_id)
        stack_target = next(
            (
                item
                for item in actor.inventory.values()
                if item.template_id == drop.template_id
                and item.durability is None
                and item.quantity < template.stack_limit
            ),
            None,
        )
        remaining = drop.quantity
        if stack_target is not None:
            room = max(0, template.stack_limit - stack_target.quantity)
            merged = min(room, remaining)
            stack_target.quantity += merged
            remaining -= merged
        while remaining > 0:
            qty = min(template.stack_limit, remaining)
            item = ItemInstance(
                instance_id=f"item_{uuid.uuid4().hex[:12]}",
                template_id=drop.template_id,
                owner_id=actor.actor_id,
                quantity=qty,
            )
            add_item(actor, item, catalog, allow_overweight=allow_overweight)
            granted.append(item)
            remaining -= qty
    return granted
