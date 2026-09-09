from __future__ import annotations

from sao_mcp.corpus.location_access import (
    DARK_ELVES,
    FALLEN_ELVES,
    FOREST_ELVES,
    LOCATION_ACCESS_RULES,
)
from sao_mcp.domain.models import CombatantState
from sao_mcp.rules.npcs import CORE_NPCS


ROLE_FACTIONS = {
    "dark_elf": DARK_ELVES,
    "forest_elf": FOREST_ELVES,
    "fallen_elf": FALLEN_ELVES,
}


def actor_faction_ids(actor: CombatantState) -> tuple[str, ...]:
    explicit = actor.metadata.get("faction_ids", ())
    if not isinstance(explicit, (list, tuple, set)) or any(not isinstance(value, str) for value in explicit):
        raise RuntimeError(f"actor {actor.actor_id} has invalid faction_ids metadata")
    factions = {value for value in explicit if value}

    definition_id = actor.metadata.get("npc_definition_id")
    if definition_id is not None:
        if not isinstance(definition_id, str) or definition_id not in CORE_NPCS:
            raise RuntimeError(f"actor {actor.actor_id} references unknown NPC definition {definition_id!r}")
        definition = CORE_NPCS[definition_id]
        factions.update(ROLE_FACTIONS[role] for role in definition.roles if role in ROLE_FACTIONS)
    return tuple(sorted(factions))


def require_location_access(actor: CombatantState, destination_id: str) -> None:
    rule = LOCATION_ACCESS_RULES.get(destination_id)
    if rule is None:
        return
    factions = set(actor_faction_ids(actor))
    forbidden = factions.intersection(rule.forbidden_faction_ids)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise ValueError(f"location access denied to actor faction(s): {joined}")
