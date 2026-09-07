from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.rules.progression import equip_skill, remove_skill, skill_slot_count


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_progression_tools(mcp, runtime) -> None:
    @mcp.tool()
    def list_available_skills(actor_id: str) -> str:
        """List catalog skills with equipped/proficiency state and remaining skill slots."""
        actor = runtime.actors[actor_id]
        return _json(
            {
                "actorId": actor_id,
                "slotsUsed": len(actor.equipped_skills),
                "slotsTotal": skill_slot_count(actor.level),
                "skills": [
                    {
                        "definition": asdict(definition),
                        "equipped": skill_id in actor.equipped_skills,
                        "proficiency": actor.skill_proficiencies.get(skill_id),
                    }
                    for skill_id, definition in runtime.catalog.skills.items()
                ],
            }
        )

    @mcp.tool()
    def equip_character_skill(actor_id: str, skill_id: str) -> str:
        """Equip a catalog skill into a free Aincrad skill slot."""
        if skill_id not in runtime.catalog.skills:
            raise KeyError(skill_id)
        actor = runtime.actors[actor_id]
        definition = runtime.catalog.skills[skill_id]
        for prerequisite in definition.prerequisites:
            if prerequisite not in actor.skill_proficiencies:
                raise ValueError(f"missing skill prerequisite: {prerequisite}")
        equip_skill(actor, skill_id)
        return _json(
            {
                "actorId": actor_id,
                "equippedSkills": list(actor.equipped_skills),
                "slotsUsed": len(actor.equipped_skills),
                "slotsTotal": skill_slot_count(actor.level),
            }
        )

    @mcp.tool()
    def remove_character_skill(actor_id: str, skill_id: str) -> str:
        """Remove an equipped skill; by canonical default its accumulated proficiency is lost."""
        actor = runtime.actors[actor_id]
        remove_skill(actor, skill_id, preserve_proficiency=False)
        return _json(
            {
                "actorId": actor_id,
                "removedSkillId": skill_id,
                "proficiencyLost": True,
                "equippedSkills": list(actor.equipped_skills),
            }
        )
