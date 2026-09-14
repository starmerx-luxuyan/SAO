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
    "health", "create_character", "get_character_state", "inspect_catalog_entry", "list_catalog",
    "list_vendors", "export_save_json", "import_save_json", "get_turn_contract", "turn_execute",
    "system_menu", "get_campaign_setup_status", "begin_campaign_setup", "finalize_campaign_setup",
    "get_custom_mechanics_schema", "create_configured_character", "configure_character_setup",
    "set_character_custom_mechanics", "get_character_setup_state", "grant_character_item",
    "remove_character_item_setup", "get_custom_catalog_state", "register_custom_weapon_definition",
    "register_custom_armor_definition", "register_custom_consumable_definition",
    "register_custom_item_definition", "remove_custom_item_definition", "register_custom_skill_definition",
    "register_custom_sword_skill_definition", "validate_campaign_blueprint", "preview_campaign_blueprint",
    "apply_campaign_blueprint",
}
PUBLIC_UI_URIS = {"ui://sao/v1.3.3/system-menu.html"}
REMOVED_HOSTED_TOOLS = {
    "get_gm_observation", "get_gm_decision_contract", "preview_gm_decision", "execute_gm_decision",
    "character_hud", "boss_raid_hud", "buy_from_vendor", "sell_to_vendor", "create_party", "join_party",
    "reopen_campaign_setup", "mark_floor_boss_defeated", "advance_world_time", "set_npc_goal",
}


def test_release_version_metadata_is_consistent():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == "1.3.3"
    assert manifest["version"] == __version__
    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/sao_mcp/__init__.py"


def test_release_plugin_uses_hosted_mcp():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    mcp_config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    assert manifest["mcpServers"] == "./.mcp.json"
    assert mcp_config["mcpServers"]["sao_aincrad"] == {"type": "http", "url": HOSTED_MCP_URL}


def test_release_persistence_schema_is_v4():
    assert SAVE_SCHEMA == "sao.aincrad.save.v4"


def test_release_system_menu_resource_is_packaged_with_python_module():
    ui = files("sao_mcp.ui")
    assert ui.joinpath("system_menu.html").is_file()


def test_hosted_public_mcp_surface_is_exact_and_gated():
    from sao_mcp.server_public import mcp

    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    assert set(tools) == PUBLIC_TOOL_NAMES
    assert REMOVED_HOSTED_TOOLS.isdisjoint(tools)
    assert tools["system_menu"].meta["ui"]["resourceUri"] == "ui://sao/v1.3.3/system-menu.html"


def test_full_internal_surface_keeps_admin_and_gm_diagnostics():
    from sao_mcp.server_bootstrap import mcp

    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert {
        "reopen_campaign_setup", "validate_campaign_amendment", "preview_campaign_amendment",
        "apply_campaign_amendment", "mark_floor_boss_defeated", "advance_world_time",
        "get_gm_observation", "get_gm_decision_contract", "preview_gm_decision", "execute_gm_decision",
    } <= names


def test_public_ui_declares_one_resource_with_csp_and_widget_domain():
    from sao_mcp.server_public import apps
    from sao_mcp.ui.app_security import WIDGET_DOMAIN

    resources = {str(binding.resource.uri): binding.resource for binding in apps.resources()}
    assert set(resources) == PUBLIC_UI_URIS
    for resource in resources.values():
        ui_meta = resource.meta["ui"]
        assert ui_meta["domain"] == WIDGET_DOMAIN
        assert ui_meta["csp"] == {
            "connectDomains": [], "resourceDomains": [], "frameDomains": [], "baseUriDomains": []
        }
