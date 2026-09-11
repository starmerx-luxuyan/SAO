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


def test_release_persistence_schema_is_v3():
    assert SAVE_SCHEMA == "sao.aincrad.save.v3"


def test_release_ui_resources_are_packaged_with_python_module():
    ui = files("sao_mcp.ui")
    assert ui.joinpath("hud.html").is_file()
    assert ui.joinpath("system_menu.html").is_file()
    assert ui.joinpath("boss_raid.html").is_file()


def test_release_public_mcp_surface_contains_critical_tools():
    from sao_mcp.server_bootstrap import mcp

    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    required = {
        "health",
        "create_character",
        "attack",
        "get_inventory",
        "list_locations",
        "advance_world_time",
        "export_save_json",
        "import_save_json",
        "get_gm_observation",
        "preview_gm_decision",
        "execute_gm_decision",
    }
    assert required <= names
