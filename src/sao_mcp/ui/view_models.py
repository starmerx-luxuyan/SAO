from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import CombatantState, EncounterState, ItemInstance
from sao_mcp.rules.inventory import carry_capacity, inventory_weight
from sao_mcp.rules.progression import current_experience, experience_to_reach_level, skill_slot_count


def _json_default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"cannot encode {type(value)!r}")


def dumps_view(view: dict[str, Any]) -> str:
    return json.dumps(view, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def _item_view(item: ItemInstance, catalog: Catalog, *, equipped: bool = False) -> dict[str, Any]:
    template = catalog.item(item.template_id)
    return {
        "instanceId": item.instance_id,
        "templateId": template.template_id,
        "name": template.name,
        "kind": template.kind.value,
        "quantity": item.quantity,
        "weight": template.weight,
        "durability": item.durability,
        "maxDurability": item.max_durability,
        "quality": item.quality,
        "makerId": item.maker_id,
        "craftGrade": item.metadata.get("craft_grade"),
        "crafted": bool(item.metadata.get("crafted", False)),
        "enhancements": {track.value: value for track, value in item.enhancements.items()},
        "attemptsUsed": item.enhancement_attempts_used,
        "maxAttempts": item.max_enhancement_attempts,
        "broken": item.broken,
        "equipped": equipped,
        "provenance": {
            "kind": template.provenance.kind.value,
            "sources": list(template.provenance.sources),
            "notes": template.provenance.notes,
        },
    }


def character_view(
    actor: CombatantState,
    catalog: Catalog,
    encounter: EncounterState | None = None,
) -> dict[str, Any]:
    equipment: dict[str, dict[str, Any]] = {}
    equipped_ids = set(actor.equipment.values())
    for slot, instance_id in actor.equipment.items():
        if instance_id in actor.inventory:
            equipment[slot] = _item_view(actor.inventory[instance_id], catalog, equipped=True)

    inventory = [
        _item_view(instance, catalog, equipped=instance.instance_id in equipped_ids)
        for instance in actor.inventory.values()
    ]

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

    xp = current_experience(actor)
    level_floor_xp = experience_to_reach_level(actor.level)
    next_level_xp = experience_to_reach_level(actor.level + 1)
    xp_span = max(1, next_level_xp - level_floor_xp)
    xp_ratio = max(0.0, min(1.0, (xp - level_floor_xp) / xp_span))

    view: dict[str, Any] = {
        "schema": "sao.ui.character.v1",
        "actor": {
            "id": actor.actor_id,
            "name": actor.name,
            "kind": actor.kind.value,
            "level": actor.level,
            "experience": xp,
            "nextLevelExperience": next_level_xp,
            "experienceRatio": xp_ratio,
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
        "equipment": equipment,
        "inventory": inventory,
        "weight": {
            "current": round(inventory_weight(actor, catalog), 2),
            "capacity": round(carry_capacity(actor), 2),
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
            "recentEvents": [asdict(event) for event in encounter.events[-10:]],
        }
    return view
