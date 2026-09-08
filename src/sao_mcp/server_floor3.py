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


def register_floor3_tools(mcp, scenario) -> None:
    @mcp.tool()
    def search_floor3_dead_scout(actor_id: str) -> str:
        """Search the dead Dark Elf scout in the Queen Spider's Nest and recover the leaf emblem."""
        item = scenario.search_dead_scout(actor_id)
        return _json(asdict(item))

    @mcp.tool()
    def create_nephila_regina_encounter(actor_id: str) -> str:
        """Start the Nephila Regina Flag-Mob encounter for Vanquishing the Spiders."""
        encounter, monster = scenario.create_nephila_encounter(actor_id)
        return _json(
            {
                "encounterId": encounter.encounter_id,
                "monsterId": monster.actor_id,
                "monsterTemplateId": monster.metadata.get("monster_id"),
                "name": monster.name,
                "level": monster.level,
                "maxHp": monster.max_hp,
                "locationId": monster.location_id,
            }
        )
