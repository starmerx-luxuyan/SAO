from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from mcp.server.apps import Apps
from mcp.server.mcpserver import MCPServer

from sao_mcp.domain.models import DefenseMode, EnhancementTrack
from sao_mcp.rules.crafting import preview_enhancement
from sao_mcp.rules.progression import skill_slot_count
from sao_mcp.runtime.engine import GameRuntime
from sao_mcp.ui.view_models import character_view, dumps_view


runtime = GameRuntime(seed=0xA1C0)
apps = Apps()
HUD_HTML = (Path(__file__).parent / "ui" / "hud.html").read_text(encoding="utf-8")


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


@apps.tool(
    resource_uri="ui://sao/aincrad-hud.html",
    title="Aincrad HUD",
    description="Render the authoritative SAO character and encounter HUD.",
)
def character_hud(actor_id: str, encounter_id: str | None = None) -> str:
    actor = runtime.actors[actor_id]
    encounter = runtime.encounters.get(encounter_id) if encounter_id else None
    return dumps_view(character_view(actor, runtime.catalog, encounter))


apps.add_html_resource(
    "ui://sao/aincrad-hud.html",
    HUD_HTML,
    title="Aincrad System HUD",
    prefers_border=True,
)

mcp = MCPServer(
    "SAO Aincrad Runtime",
    extensions=[apps],
    instructions=(
        "Use the runtime as the mechanical source of truth for Aincrad. "
        "Do not invent HP, damage, durability, inventory, enhancement, cooldown, crime, skill proficiency, "
        "party/raid, encounter or floor-progression mutations outside these tools. "
        "Canon-backed and simulation-calibrated fields are explicitly distinguished by provenance."
    ),
)


@mcp.tool()
def health() -> str:
    """Return runtime/plugin health and schema version."""
    return _json({"ok": True, "runtime": "sao-aincrad", "version": "0.1.0", "actors": len(runtime.actors), "encounters": len(runtime.encounters)})


@mcp.tool()
def create_character(name: str, level: int = 1) -> str:
    """Create a playable Aincrad character with legal starting equipment and skill slots."""
    actor = runtime.create_character(name, level=level)
    return dumps_view(character_view(actor, runtime.catalog))


@mcp.tool()
def create_training_encounter(actor_id: str, monster_level: int | None = None) -> str:
    """Create a field encounter against a training monster for a player."""
    actor = runtime.actors[actor_id]
    monster = runtime.create_training_monster(level=monster_level or actor.level)
    encounter = runtime.start_encounter([actor_id, monster.actor_id])
    return _json({"encounterId": encounter.encounter_id, "playerId": actor_id, "monsterId": monster.actor_id, "zoneId": encounter.zone_id})


@mcp.tool()
def get_character_state(actor_id: str, encounter_id: str | None = None) -> str:
    """Return player-visible character state as the same view model used by the HUD."""
    encounter = runtime.encounters.get(encounter_id) if encounter_id else None
    return dumps_view(character_view(runtime.actors[actor_id], runtime.catalog, encounter))


@mcp.tool()
def skill_slots_for_level(level: int) -> str:
    """Return the canonical Aincrad equipped-skill slot count for a character level."""
    return _json({"level": level, "slots": skill_slot_count(level), "provenance": "canon"})


@mcp.tool()
def inspect_catalog_entry(template_or_skill_id: str) -> str:
    """Inspect an item, skill or Sword Skill, including canon/simulation provenance."""
    if template_or_skill_id in runtime.catalog.weapons:
        value = runtime.catalog.weapons[template_or_skill_id]
        kind = "weapon"
    elif template_or_skill_id in runtime.catalog.consumables:
        value = runtime.catalog.consumables[template_or_skill_id]
        kind = "consumable"
    elif template_or_skill_id in runtime.catalog.skills:
        value = runtime.catalog.skills[template_or_skill_id]
        kind = "skill"
    elif template_or_skill_id in runtime.catalog.sword_skills:
        value = runtime.catalog.sword_skills[template_or_skill_id]
        kind = "sword_skill"
    else:
        raise KeyError(template_or_skill_id)
    return _json({"kind": kind, "record": asdict(value)})


@mcp.tool()
def list_catalog(category: str) -> str:
    """List compact IDs/names for core catalog entries."""
    mapping = {
        "weapons": runtime.catalog.weapons,
        "consumables": runtime.catalog.consumables,
        "skills": runtime.catalog.skills,
        "sword_skills": runtime.catalog.sword_skills,
    }.get(category)
    if mapping is None:
        raise ValueError("category must be weapons, consumables, skills, or sword_skills")
    return _json({"category": category, "entries": [{"id": key, "name": value.name} for key, value in mapping.items()]})


@mcp.tool()
def attack(
    encounter_id: str,
    attacker_id: str,
    target_id: str,
    sword_skill_id: str | None = None,
    defense: str = "auto",
    distance_m: float = 1.0,
    seed: int | None = None,
) -> str:
    """Resolve one physical or Sword Skill attack and mutate authoritative encounter state."""
    result = runtime.attack(
        encounter_id,
        attacker_id,
        target_id,
        sword_skill_id=sword_skill_id,
        defense=DefenseMode(defense),
        distance_m=distance_m,
        seed=seed,
    )
    encounter = runtime.encounters[encounter_id]
    return _json({"resolution": asdict(result), "timeMs": encounter.time_ms, "targetHp": encounter.participants[target_id].hp})


@mcp.tool()
def perform_switch(encounter_id: str, outgoing_id: str, incoming_id: str, target_id: str) -> str:
    """Execute the player-devised Switch tactic when a valid party opening exists."""
    return _json(asdict(runtime.switch(encounter_id, outgoing_id, incoming_id, target_id)))


@mcp.tool()
def monster_target(encounter_id: str, monster_id: str) -> str:
    """Return the target selected from the monster's current threat state."""
    return _json({"monsterId": monster_id, "targetId": runtime.monster_target(encounter_id, monster_id)})


@mcp.tool()
def use_item(actor_id: str, instance_id: str, encounter_id: str | None = None) -> str:
    """Consume a potion/crystal after cooldown, silence and anti-crystal legality checks."""
    result = runtime.use_inventory_item(actor_id, instance_id, encounter_id=encounter_id)
    return _json(asdict(result))


@mcp.tool()
def preview_weapon_enhancement(
    actor_id: str,
    instance_id: str,
    smith_proficiency: float,
    material_quality: float = 1.0,
    item_difficulty: float = 1.0,
) -> str:
    """Preview a simulation-calibrated enhancement probability without mutating the item."""
    item = runtime.actors[actor_id].inventory[instance_id]
    return _json(asdict(preview_enhancement(item, smith_proficiency=smith_proficiency, material_quality=material_quality, item_difficulty=item_difficulty)))


@mcp.tool()
def enhance_weapon(
    actor_id: str,
    instance_id: str,
    track: str,
    smith_proficiency: float,
    material_quality: float = 1.0,
    item_difficulty: float = 1.0,
    seed: int | None = None,
    allow_destructive_overcap: bool = False,
) -> str:
    """Attempt one of the five Aincrad weapon enhancement tracks; success and failure consume attempts."""
    result = runtime.enhance_item(
        actor_id,
        instance_id,
        EnhancementTrack(track),
        smith_proficiency=smith_proficiency,
        material_quality=material_quality,
        item_difficulty=item_difficulty,
        seed=seed,
        allow_destructive_overcap=allow_destructive_overcap,
    )
    return _json(asdict(result))


@mcp.tool()
def create_party(leader_id: str) -> str:
    """Create a party; canonical maximum is six members."""
    return _json(asdict(runtime.create_party(leader_id)))


@mcp.tool()
def join_party(party_id: str, actor_id: str) -> str:
    """Join an existing party, enforcing the six-member maximum."""
    return _json(asdict(runtime.join_party(party_id, actor_id)))


@mcp.tool()
def create_raid(leader_id: str, party_id: str) -> str:
    """Create a raid group from a party; full raid maximum is eight parties."""
    return _json(asdict(runtime.create_raid(leader_id, party_id)))


@mcp.tool()
def join_raid(raid_id: str, party_id: str) -> str:
    """Add a party to a raid, enforcing the eight-party maximum."""
    return _json(asdict(runtime.join_raid(raid_id, party_id)))


@mcp.tool()
def mark_floor_boss_defeated(floor_number: int) -> str:
    """Mark a floor boss defeated and schedule the next floor's automatic gate activation."""
    runtime.floor_boss_defeated(floor_number)
    return _json(asdict(runtime.world.floors[floor_number]))


@mcp.tool()
def advance_world_time(elapsed_ms: int) -> str:
    """Advance persistent Aincrad world time and process scheduled floor activation."""
    activated = runtime.advance_world(elapsed_ms)
    return _json({"nowMs": runtime.world.now_ms, "activatedFloors": activated})
