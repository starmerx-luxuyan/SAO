from __future__ import annotations

import asyncio
import json
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


def test_character_hud_returns_root_structured_view_model():
    actor_id = load_kageaki()
    result = call("character_hud", {"actor_id": actor_id})
    assert result.is_error is False
    payload = result.structured_content
    assert payload is not None and "result" not in payload
    assert payload["schema"] == "sao.ui.character.v1"
    actor = payload["actor"]
    assert actor["name"] == "凑斗景明"
    assert actor["level"] == 7
    assert actor["hp"] == 1561 and actor["maxHp"] == 1561
    assert actor["col"] == 88_888
    star = next(s for s in payload["skills"]["equipped"] if s["id"] == "star_sword")
    assert star["proficiency"] == 238
    weapon = payload["equipment"]["weapon"]
    assert "Anneal Blade" in weapon["name"]
    assert sum(weapon["enhancements"].values()) == 3
    assert json.loads(result.content[0].text)["actor"]["level"] == 7


def test_system_menu_returns_root_structured_view_model():
    actor_id = load_kageaki()
    result = call("system_menu", {"actor_id": actor_id})
    payload = result.structured_content
    assert payload is not None and "result" not in payload
    assert payload["schema"] == "sao.ui.system.v1"
    assert payload["character"]["actor"]["name"] == "凑斗景明"
    assert payload["character"]["actor"]["col"] == 88_888


def test_embedded_views_consume_structured_payloads_not_text_content():
    ui = files("sao_mcp.ui")
    for filename in ("hud.html", "system_menu.html", "boss_raid.html"):
        html = ui.joinpath(filename).read_text(encoding="utf-8")
        assert "window.openai?.toolOutput" in html
        assert "ui/notifications/tool-result" in html
        assert "structuredContent" in html
        assert "result?.content?.[0]?.text" not in html
        assert "JSON.parse(text)" not in html
