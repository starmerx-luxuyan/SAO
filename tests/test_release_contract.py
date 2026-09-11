from __future__ import annotations

import asyncio
import json
import tomllib
from importlib.resources import files
from pathlib import Path

from sao_mcp import __version__
from sao_mcp.runtime.persistence import SAVE_SCHEMA


ROOT = Path(__file__).resolve().parents[1]
HOSTED_MCP_URL = "https://sao-aincrad-mcp-production.up.railway.app/mcp"
PUBLIC_TOOL_NAMES = {
    "health",
    "create_character",
    "get_character_state",
    "inspect_catalog_entry",
    "list_catalog",
    "export_save_json",
    "import_save_json",
    "get_gm_observation",
    "get_gm_decision_contract",
    "preview_gm_decision",
    "execute_gm_decision",
    "character_hud",
    "system_menu",
    "boss_raid_hud",
}
PUBLIC_UI_URIS = {
    "ui://sao/aincrad-hud.html",
    "ui://sao/system-menu.html",
    "ui://sao/boss-raid.html",
}


def test_release_version_metadata_is_consistent():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == "1.0.0"
    assert manifest["version"] == __version__
    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/sao_mcp/__init__.py"

    from sao_mcp.server import health

    assert json.loads(health())["version"] == __version__


def test_release_plugin_uses_hosted_mcp():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    mcp_config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))

    assert manifest["mcpServers"] == "./.mcp.json"
    assert set(mcp_config["mcpServers"]) == {"sao_aincrad"}
    server = mcp_config["mcpServers"]["sao_aincrad"]
    assert server == {"type": "http", "url": HOSTED_MCP_URL}


def test_release_plugin_publication_metadata_is_complete():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    interface = manifest["interface"]

    assert manifest["homepage"].startswith("https://")
    assert manifest["repository"].startswith("https://")
    assert {"Interactive", "Read", "Write"} <= set(interface["capabilities"])
    assert interface["websiteURL"].startswith("https://")
    assert interface["privacyPolicyURL"].startswith("https://")
    assert interface["termsOfServiceURL"].startswith("https://")
    assert (ROOT / "docs" / "PRIVACY.md").is_file()
    assert (ROOT / "docs" / "TERMS.md").is_file()


def test_release_persistence_schema_is_v3():
    assert SAVE_SCHEMA == "sao.aincrad.save.v3"


def test_release_ui_resources_are_packaged_with_python_module():
    ui = files("sao_mcp.ui")
    assert ui.joinpath("hud.html").is_file()
    assert ui.joinpath("system_menu.html").is_file()
    assert ui.joinpath("boss_raid.html").is_file()


def test_hosted_public_mcp_surface_is_exact_and_gated():
    from sao_mcp.server_public import mcp

    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert names == PUBLIC_TOOL_NAMES
    assert {
        "mark_floor_boss_defeated",
        "advance_world_time",
        "add_player_population_cohort",
        "materialize_wild_monster",
        "set_npc_goal",
        "assign_guild_goal",
    }.isdisjoint(names)


def test_full_internal_surface_remains_available_for_development():
    from sao_mcp.server_bootstrap import mcp

    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert {"mark_floor_boss_defeated", "advance_world_time"} <= names
    assert PUBLIC_TOOL_NAMES - {"system_menu", "boss_raid_hud"} <= names


def test_public_ui_declares_csp_and_widget_domain():
    from sao_mcp.server_public import apps
    from sao_mcp.ui.app_security import WIDGET_DOMAIN

    resources = {str(binding.resource.uri): binding.resource for binding in apps.resources()}
    assert set(resources) == PUBLIC_UI_URIS
    for resource in resources.values():
        assert resource.mime_type == "text/html;profile=mcp-app"
        ui_meta = resource.meta["ui"]
        assert ui_meta["domain"] == WIDGET_DOMAIN
        assert ui_meta["csp"] == {
            "connectDomains": [],
            "resourceDomains": [],
            "frameDomains": [],
            "baseUriDomains": [],
        }
