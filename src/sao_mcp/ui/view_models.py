from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import CombatantState, EncounterState, ItemInstance
from sao_mcp.rules.progression import default_carry_capacity, skill_slot_count


def _json_default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"cannot encode {type(value)!r}")


def dumps_view(view: dict[str, Any]) -> str:
    return json.dumps(view, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def _item_weight(item: ItemInstance, catalog: Catalog) -> float:
    template = catalog.item(item.template_id)
    return template.weight * max(1, item.quantity)


def character_view(actor: CombatantState, catalog: Catalog, encounter: EncounterState | None = None) -> dict[str, Any]:
    weapon = None
    weapon_instance_id = actor.equipment.get("weapon")
    if weapon_instance_id and weapon_instance_id in actor.inventory:
        instance = actor.inventory[weapon_instance_id]
        template = catalog.item(instance.template_id)
        weapon = {
            "instanceId": instance.instance_id,
            "templateId": template.template_id,
            "name": template.name,
            "durability": instance.durability,
            "maxDurability": instance.max_durability,
            "enhancements": {track.value: value for track, value in instance.enhancements.items()},
            "attemptsUsed": instance.enhancement_attempts_used,
            "maxAttempts": instance.max_enhancement_attempts,
            "broken": instance.broken,
        }

    inventory = []
    total_weight = 0.0
    for instance in actor.inventory.values():
        template = catalog.item(instance.template_id)
        total_weight += _item_weight(instance, catalog)
        inventory.append(
            {
                "instanceId": instance.instance_id,
                "templateId": template.template_id,
                "name": template.name,
                "kind": template.kind.value,
                "quantity": instance.quantity,
                "weight": template.weight,
                "durability": instance.durability,
                "maxDurability": instance.max_durability,
                "equipped": instance.instance_id in actor.equipment.values(),
            }
        )

    now_ms = encounter.time_ms if encounter else 0
    cooldowns = {
        key: max(0, until - now_ms)
        for key, until in actor.cooldowns_until_ms.items()
        if until > now_ms
    }
    state = "ready"
    if now_ms < actor.committed_until_ms:
        state = "committed"
    elif now_ms < actor.recovery_until_ms:
        state = "post_motion"

    view: dict[str, Any] = {
        "schema": "sao.ui.character.v1",
        "actor": {
            "id": actor.actor_id,
            "name": actor.name,
            "kind": actor.kind.value,
            "level": actor.level,
            "hp": actor.hp,
            "maxHp": actor.max_hp,
            "hpRatio": actor.hp / actor.max_hp if actor.max_hp else 0.0,
            "strength": actor.strength,
            "agility": actor.agility,
            "armor": actor.armor,
            "cursor": actor.cursor.value,
            "col": actor.col,
            "alive": actor.alive,
            "locationId": actor.location_id,
            "partyId": actor.party_id,
            "guildId": actor.guild_id,
            "combatState": state,
            "recoveryRemainingMs": max(0, actor.recovery_until_ms - now_ms),
        },
        "skills": {
            "slotsUsed": len(actor.equipped_skills),
            "slotsTotal": skill_slot_count(actor.level),
            "equipped": [
                {
                    "id": skill_id,
                    "name": catalog.skills.get(skill_id).name if skill_id in catalog.skills else skill_id,
                    "proficiency": actor.skill_proficiencies.get(skill_id, 0.0),
                    "maxProficiency": 1000,
                }
                for skill_id in actor.equipped_skills
            ],
        },
        "equipment": {"weapon": weapon},
        "inventory": inventory,
        "weight": {
            "current": round(total_weight, 2),
            "capacity": round(default_carry_capacity(actor.strength, actor.skill_proficiencies.get("extended_weight_limit", 0.0)), 2),
        },
        "statuses": [asdict(status) for status in actor.statuses],
        "cooldownsMs": cooldowns,
    }

    if encounter:
        view["encounter"] = {
            "id": encounter.encounter_id,
            "timeMs": encounter.time_ms,
            "zoneId": encounter.zone_id,
            "safeZone": encounter.safe_zone,
            "antiCrystal": encounter.anti_crystal,
            "participants": [
                {
                    "id": other.actor_id,
                    "name": other.name,
                    "kind": other.kind.value,
                    "hp": other.hp,
                    "maxHp": other.max_hp,
                    "hpRatio": other.hp / other.max_hp if other.max_hp else 0.0,
                    "alive": other.alive,
                    "partyId": other.party_id,
                }
                for other in encounter.participants.values()
                if other.actor_id != actor.actor_id
            ],
            "recentEvents": [asdict(event) for event in encounter.events[-8:]],
        }
    return view
