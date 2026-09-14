from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from mcp.server.apps import Apps
from mcp.server.mcpserver import MCPServer

from sao_mcp import __version__
from sao_mcp.runtime.character_setup import require_campaign_setup_open
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.player_runline import PlayerRunline
from sao_mcp.server_bootstrap import gm_decision_runtime, gm_turn_executor, runtime
from sao_mcp.server_campaign_blueprint import register_campaign_blueprint_tools
from sao_mcp.server_runline import register_player_runline_tools
from sao_mcp.server_setup import register_setup_tools
from sao_mcp.ui.app_security import WIDGET_CSP, WIDGET_DOMAIN
from sao_mcp.ui.system_views import system_menu_view
from sao_mcp.ui.view_models import character_view, dumps_view


UI_DIR = Path(__file__).parent / "ui"
SYSTEM_MENU_HTML = (UI_DIR / "system_menu.html").read_text(encoding="utf-8")


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


apps = Apps()

# v1.3.3 exposes exactly one visual surface. Character HUD and Boss Raid HUD are
# intentionally not registered on the hosted surface; their old HTML/view code may
# remain internal until repository cleanup, but players cannot discover/invoke it.
@apps.tool(
    resource_uri="ui://sao/v1.3.3/system-menu.html",
    title="Aincrad System Menu",
    description="Render the single player-visible Aincrad System Menu.",
)
def system_menu(actor_id: str, encounter_id: str | None = None) -> dict[str, Any]:
    return system_menu_view(runtime, actor_id, encounter_id)


apps.add_html_resource(
    "ui://sao/v1.3.3/system-menu.html",
    SYSTEM_MENU_HTML,
    title="Aincrad System Menu",
    csp=WIDGET_CSP,
    domain=WIDGET_DOMAIN,
    prefers_border=True,
)


mcp = MCPServer(
    "SAO Aincrad Player Runtime",
    extensions=[apps],
    instructions=(
        "This is the hosted Aincrad player surface. Ordinary play has one mutation boundary: turn_execute. "
        "The runtime always performs fresh observation, player projection, gate validation, execution, "
        "engine-owned settling, re-observation and System Menu refresh in that order. The model must not "
        "orchestrate observation/preview/execute/world-tick calls itself. Campaign setup is a separate explicit "
        "authority. The System Menu is the only hosted visual UI."
    ),
)


@mcp.tool()
def health() -> str:
    """Return hosted player-surface health and release version."""
    return _json(
        {
            "ok": True,
            "runtime": "sao-aincrad",
            "surface": "public",
            "version": __version__,
            "actors": len(runtime.actors),
            "encounters": len(runtime.encounters),
            "ordinary_play_entry": "turn_execute",
            "ui": "system_menu",
        }
    )


@mcp.tool()
def create_character(name: str, level: int = 1) -> str:
    """Create a legal starter character during the open campaign setup phase."""
    require_campaign_setup_open(runtime)
    actor = runtime.create_character(name, level=level)
    return dumps_view(character_view(actor, runtime.catalog))


@mcp.tool()
def get_character_state(actor_id: str, encounter_id: str | None = None) -> str:
    """Return player-visible character state as data; System Menu remains the sole UI."""
    encounter = runtime.encounters.get(encounter_id) if encounter_id else None
    return dumps_view(character_view(runtime.actors[actor_id], runtime.catalog, encounter))


@mcp.tool()
def inspect_catalog_entry(template_or_skill_id: str) -> str:
    """Inspect an item, skill or Sword Skill together with its provenance."""
    if template_or_skill_id in runtime.catalog.weapons:
        value = runtime.catalog.weapons[template_or_skill_id]
        kind = "weapon"
    elif template_or_skill_id in runtime.catalog.armors:
        value = runtime.catalog.armors[template_or_skill_id]
        kind = "armor"
    elif template_or_skill_id in runtime.catalog.consumables:
        value = runtime.catalog.consumables[template_or_skill_id]
        kind = "consumable"
    elif template_or_skill_id in runtime.catalog.items:
        value = runtime.catalog.items[template_or_skill_id]
        kind = "item"
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
    """List compact IDs and names for a public catalog category."""
    mapping = {
        "weapons": runtime.catalog.weapons,
        "armors": runtime.catalog.armors,
        "consumables": runtime.catalog.consumables,
        "items": runtime.catalog.items,
        "skills": runtime.catalog.skills,
        "sword_skills": runtime.catalog.sword_skills,
    }.get(category)
    if mapping is None:
        raise ValueError("category must be weapons, armors, consumables, items, skills, or sword_skills")
    return _json(
        {
            "category": category,
            "entries": [{"id": key, "name": value.name} for key, value in mapping.items()],
        }
    )


@mcp.tool()
def list_vendors(location_id: str | None = None) -> str:
    """Read living NPC vendor nodes. Purchases and sales mutate only through turn_execute."""
    rows = []
    for vendor in runtime.economy.vendors.values():
        if location_id is not None and vendor.location_id != location_id:
            continue
        state = getattr(runtime.economy, "vendor_state", None)
        rows.append(state(vendor.vendor_id) if state is not None else asdict(vendor))
    return _json({"vendors": rows})


@mcp.tool()
def export_save_json() -> str:
    """Export the complete deterministic campaign save as JSON."""
    return export_runtime(runtime)


@mcp.tool()
def import_save_json(save_json: str) -> str:
    """Restore a current or exactly migratable legacy save into this private campaign runtime."""
    import_runtime(save_json, into=runtime)
    return _json(
        {
            "ok": True,
            "actors": len(runtime.actors),
            "encounters": len(runtime.encounters),
            "worldTimeMs": runtime.world.now_ms,
        }
    )


register_setup_tools(mcp, runtime)
register_campaign_blueprint_tools(mcp, runtime)

player_runline = PlayerRunline(
    runtime,
    gm_turn_executor,
    gm_decision_runtime,
    system_menu_view,
)
register_player_runline_tools(mcp, player_runline)

__all__ = ["mcp", "apps", "runtime", "player_runline"]
