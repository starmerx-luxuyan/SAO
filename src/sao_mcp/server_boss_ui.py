from __future__ import annotations

from pathlib import Path
from typing import Any

from sao_mcp.server import apps, runtime
from sao_mcp.ui.boss_views import boss_raid_view


BOSS_RAID_HTML = (Path(__file__).parent / "ui" / "boss_raid.html").read_text(encoding="utf-8")


@apps.tool(
    resource_uri="ui://sao/boss-raid.html",
    title="Aincrad Boss Raid HUD",
    description="Render segmented boss HP bars, telegraph state, raid roster, minions, threat and boss events.",
)
def boss_raid_hud(encounter_id: str, boss_id: str | None = None) -> dict[str, Any]:
    return boss_raid_view(runtime, encounter_id, boss_id)


apps.add_html_resource(
    "ui://sao/boss-raid.html",
    BOSS_RAID_HTML,
    title="Aincrad Boss Raid HUD",
    prefers_border=True,
)
