from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str, *, count: int | None = None) -> None:
    file = ROOT / path
    text = file.read_text(encoding="utf-8")
    found = text.count(old)
    expected = 1 if count is None else count
    if found != expected:
        raise RuntimeError(f"{path}: expected {expected} occurrences, found {found}: {old[:80]!r}")
    file.write_text(text.replace(old, new), encoding="utf-8")


replace(
    "src/sao_mcp/server_public.py",
    "def character_hud(actor_id: str, encounter_id: str | None = None) -> str:\n    actor = runtime.actors[actor_id]\n    encounter = runtime.encounters.get(encounter_id) if encounter_id else None\n    return dumps_view(character_view(actor, runtime.catalog, encounter))",
    "def character_hud(actor_id: str, encounter_id: str | None = None) -> dict[str, Any]:\n    actor = runtime.actors[actor_id]\n    encounter = runtime.encounters.get(encounter_id) if encounter_id else None\n    return character_view(actor, runtime.catalog, encounter)",
)
replace(
    "src/sao_mcp/server_public.py",
    "def system_menu(actor_id: str, encounter_id: str | None = None) -> str:\n    return dumps_view(system_menu_view(runtime, actor_id, encounter_id))",
    "def system_menu(actor_id: str, encounter_id: str | None = None) -> dict[str, Any]:\n    return system_menu_view(runtime, actor_id, encounter_id)",
)
replace(
    "src/sao_mcp/server_public.py",
    "def boss_raid_hud(encounter_id: str, boss_id: str | None = None) -> str:\n    return dumps_view(boss_raid_view(runtime, encounter_id, boss_id))",
    "def boss_raid_hud(encounter_id: str, boss_id: str | None = None) -> dict[str, Any]:\n    return boss_raid_view(runtime, encounter_id, boss_id)",
)
replace(
    "src/sao_mcp/server.py",
    "def character_hud(actor_id: str, encounter_id: str | None = None) -> str:\n    actor = runtime.actors[actor_id]\n    encounter = runtime.encounters.get(encounter_id) if encounter_id else None\n    return dumps_view(character_view(actor, runtime.catalog, encounter))",
    "def character_hud(actor_id: str, encounter_id: str | None = None) -> dict[str, Any]:\n    actor = runtime.actors[actor_id]\n    encounter = runtime.encounters.get(encounter_id) if encounter_id else None\n    return character_view(actor, runtime.catalog, encounter)",
)
replace(
    "src/sao_mcp/server_ui.py",
    "from pathlib import Path\n\nfrom sao_mcp.server import apps, runtime\nfrom sao_mcp.ui.system_views import system_menu_view\nfrom sao_mcp.ui.view_models import dumps_view",
    "from pathlib import Path\nfrom typing import Any\n\nfrom sao_mcp.server import apps, runtime\nfrom sao_mcp.ui.system_views import system_menu_view",
)
replace(
    "src/sao_mcp/server_ui.py",
    "def system_menu(actor_id: str, encounter_id: str | None = None) -> str:\n    return dumps_view(system_menu_view(runtime, actor_id, encounter_id))",
    "def system_menu(actor_id: str, encounter_id: str | None = None) -> dict[str, Any]:\n    return system_menu_view(runtime, actor_id, encounter_id)",
)
replace(
    "src/sao_mcp/server_boss_ui.py",
    "from pathlib import Path\n\nfrom sao_mcp.server import apps, runtime\nfrom sao_mcp.ui.boss_views import boss_raid_view\nfrom sao_mcp.ui.view_models import dumps_view",
    "from pathlib import Path\nfrom typing import Any\n\nfrom sao_mcp.server import apps, runtime\nfrom sao_mcp.ui.boss_views import boss_raid_view",
)
replace(
    "src/sao_mcp/server_boss_ui.py",
    "def boss_raid_hud(encounter_id: str, boss_id: str | None = None) -> str:\n    return dumps_view(boss_raid_view(runtime, encounter_id, boss_id))",
    "def boss_raid_hud(encounter_id: str, boss_id: str | None = None) -> dict[str, Any]:\n    return boss_raid_view(runtime, encounter_id, boss_id)",
)

old_plain = "window.addEventListener('message',ev=>{const text=ev.data?.result?.content?.[0]?.text;if(!text)return;try{render(JSON.parse(text))}catch{}});"
old_err = "window.addEventListener('message',ev=>{const text=ev.data?.result?.content?.[0]?.text;if(!text)return;try{render(JSON.parse(text))}catch(err){console.error(err)}});"
new_listener = "function hydrate(v){if(v)render(v)}\nif(window.openai?.toolOutput)hydrate(window.openai.toolOutput);\nwindow.addEventListener('openai:set_globals',()=>hydrate(window.openai?.toolOutput));\nwindow.addEventListener('message',ev=>{if(ev.data?.method==='ui/notifications/tool-result')hydrate(ev.data.params?.structuredContent)});"
replace("src/sao_mcp/ui/hud.html", old_plain, new_listener)
replace("src/sao_mcp/ui/system_menu.html", old_err, new_listener)
replace("src/sao_mcp/ui/boss_raid.html", old_err, new_listener)

replace("src/sao_mcp/__init__.py", '__version__ = "1.3.0"', '__version__ = "1.3.1"')
plugin_path = ROOT / ".codex-plugin/plugin.json"
manifest = json.loads(plugin_path.read_text(encoding="utf-8"))
if manifest.get("version") != "1.3.0":
    raise RuntimeError(f"unexpected plugin version {manifest.get('version')!r}")
manifest["version"] = "1.3.1"
plugin_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
replace("tests/test_release_contract.py", 'assert __version__ == "1.3.0"', 'assert __version__ == "1.3.1"')

ci = ROOT / ".github/workflows/ci.yml"
ci_text = ci.read_text(encoding="utf-8")
if "v1.3.0" not in ci_text or '"1.3.0"' not in ci_text:
    raise RuntimeError("CI v1.3.0 contract changed unexpectedly")
ci_text = ci_text.replace("v1.3.0", "v1.3.1").replace('"1.3.0"', '"1.3.1"')
ci_text = ci_text.replace("docs/V1.3.0.md", "docs/V1.3.1.md")
ci.write_text(ci_text, encoding="utf-8")
replace("scripts/build_kageaki_day3_save.py", '"SAO_Kageaki_Day3_v1.3.0.save.json"', '"SAO_Kageaki_Day3_v1.3.1.save.json"')

readme = ROOT / "README.md"
text = readme.read_text(encoding="utf-8")
if "**v1.3.0**" not in text:
    raise RuntimeError("README release marker missing")
readme.write_text(text.replace("**v1.3.0**", "**v1.3.1**", 1), encoding="utf-8")

(ROOT / "docs/V1.3.1.md").write_text(
    "# SAO Aincrad v1.3.1 — Embedded UI Hydration Fix\n\n"
    "v1.3.1 repairs the MCP Apps data bridge for Character HUD, System Menu, and Boss Raid HUD.\n\n"
    "- UI-bound tools return object-rooted dictionaries, so MCP `structuredContent` is the view model itself.\n"
    "- ChatGPT views consume `window.openai.toolOutput`; standard MCP Apps views consume `ui/notifications/tool-result` structured content.\n"
    "- Embedded UIs no longer parse model-facing TextContent.\n"
    "- Regression coverage includes Kageaki Day 3 hydration values.\n",
    encoding="utf-8",
)

(ROOT / "tests/test_ui_structured_hydration.py").write_text(
'''from __future__ import annotations\n\nimport asyncio\nimport json\nfrom importlib.resources import files\n\nfrom mcp import Client\n\nfrom scripts.build_kageaki_day3_save import build_save\nfrom sao_mcp import server_public\nfrom sao_mcp.runtime.persistence import import_runtime\n\n\ndef call(name: str, arguments: dict):\n    async def run():\n        async with Client(server_public.mcp, raise_exceptions=True) as client:\n            return await client.call_tool(name, arguments)\n    return asyncio.run(run())\n\n\ndef load_kageaki() -> str:\n    import_runtime(build_save(), into=server_public.runtime)\n    ids = [a.actor_id for a in server_public.runtime.actors.values() if a.name == "凑斗景明"]\n    assert len(ids) == 1\n    return ids[0]\n\n\ndef test_character_hud_returns_root_structured_view_model():\n    actor_id = load_kageaki()\n    result = call("character_hud", {"actor_id": actor_id})\n    assert result.is_error is False\n    payload = result.structured_content\n    assert payload is not None and "result" not in payload\n    assert payload["schema"] == "sao.ui.character.v1"\n    actor = payload["actor"]\n    assert actor["name"] == "凑斗景明"\n    assert actor["level"] == 7\n    assert actor["hp"] == 1561 and actor["maxHp"] == 1561\n    assert actor["col"] == 88_888\n    star = next(s for s in payload["skills"]["equipped"] if s["id"] == "star_sword")\n    assert star["proficiency"] == 238\n    weapon = payload["equipment"]["weapon"]\n    assert "Anneal Blade" in weapon["name"]\n    assert sum(weapon["enhancements"].values()) == 3\n    assert json.loads(result.content[0].text)["actor"]["level"] == 7\n\n\ndef test_system_menu_returns_root_structured_view_model():\n    actor_id = load_kageaki()\n    result = call("system_menu", {"actor_id": actor_id})\n    payload = result.structured_content\n    assert payload is not None and "result" not in payload\n    assert payload["schema"] == "sao.ui.system.v1"\n    assert payload["character"]["actor"]["name"] == "凑斗景明"\n    assert payload["character"]["actor"]["col"] == 88_888\n\n\ndef test_embedded_views_consume_structured_payloads_not_text_content():\n    ui = files("sao_mcp.ui")\n    for filename in ("hud.html", "system_menu.html", "boss_raid.html"):\n        html = ui.joinpath(filename).read_text(encoding="utf-8")\n        assert "window.openai?.toolOutput" in html\n        assert "ui/notifications/tool-result" in html\n        assert "structuredContent" in html\n        assert "result?.content?.[0]?.text" not in html\n        assert "JSON.parse(text)" not in html\n''', encoding="utf-8")

print("applied v1.3.1 UI hydration patch")
