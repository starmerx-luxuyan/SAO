from __future__ import annotations

from pathlib import Path

from sao_mcp.server import apps, runtime
from sao_mcp.ui.system_views import system_menu_view
from sao_mcp.ui.view_models import dumps_view


SYSTEM_MENU_HTML = (Path(__file__).parent / "ui" / "system_menu.html").read_text(encoding="utf-8")


@apps.tool(
    resource_uri="ui://sao/system-menu.html",
    title="Aincrad System Menu",
    description=(
        "Render the authoritative multi-panel SAO system menu: character, equipment, skills, map, quests, "
        "local market and forge state."
    ),
)
def system_menu(actor_id: str, encounter_id: str | None = None) -> str:
    return dumps_view(system_menu_view(runtime, actor_id, encounter_id))


apps.add_html_resource(
    "ui://sao/system-menu.html",
    SYSTEM_MENU_HTML,
    title="Aincrad System Menu",
    prefers_border=True,
)
