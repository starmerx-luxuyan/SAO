from __future__ import annotations

import asyncio
import sys
from importlib.resources import files
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp import Client

from scripts.build_kageaki_day3_save import build_save
from sao_mcp import server_public
from sao_mcp.runtime.persistence import import_runtime


def call(name: str, arguments: dict):
    async def run():
        async with Client(server_public.mcp, raise_exceptions=True) as client:
            return await client.call_tool(name, arguments)
    return asyncio.run(run())


def load_kageaki() -> str:
    import_runtime(build_save(), into=server_public.runtime)
    ids = [a.actor_id for a in server_public.runtime.actors.values() if a.name == "凑斗景明"]
    assert len(ids) == 1
    return ids[0]


def test_system_menu_returns_root_structured_view_model():
    actor_id = load_kageaki()
    result = call("system_menu", {"actor_id": actor_id})
    assert result.is_error is False
    payload = result.structured_content
    assert payload is not None and "result" not in payload
    assert payload["schema"] == "sao.ui.system.v1"
    assert payload["character"]["actor"]["name"] == "凑斗景明"
    assert payload["character"]["actor"]["level"] == 7
    assert payload["character"]["actor"]["hp"] == 1561
    assert payload["character"]["actor"]["maxHp"] == 1561
    assert payload["character"]["actor"]["col"] == 88_888


def test_hosted_system_menu_consumes_structured_payload_not_text_content():
    html = files("sao_mcp.ui").joinpath("system_menu.html").read_text(encoding="utf-8")
    assert "window.openai?.toolOutput" in html
    assert "ui/notifications/tool-result" in html
    assert "structuredContent" in html
    assert "result?.content?.[0]?.text" not in html
    assert "JSON.parse(text)" not in html


def test_v133_exposes_only_system_menu_resource_and_tool_binding():
    expected = {"ui://sao/v1.3.3/system-menu.html"}
    resources = {str(binding.resource.uri) for binding in server_public.apps.resources()}
    assert resources == expected

    tools = {tool.name: tool for tool in asyncio.run(server_public.mcp.list_tools())}
    assert tools["system_menu"].meta["ui"]["resourceUri"] == "ui://sao/v1.3.3/system-menu.html"
    assert "character_hud" not in tools
    assert "boss_raid_hud" not in tools
