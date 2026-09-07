from __future__ import annotations

import sao_mcp.server as core_server
from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.runtime.timeline_runtime import TimelineRaidAincradRuntime
from sao_mcp.server_adventure import register_adventure_tools
from sao_mcp.server_economy import register_economy_tools
from sao_mcp.server_inventory import register_inventory_tools
from sao_mcp.server_progression import register_progression_tools
from sao_mcp.server_spatial import register_spatial_tools
from sao_mcp.server_timeline import register_timeline_tools

# Core tools registered in sao_mcp.server resolve that module's global `runtime` at call time.
# Replace the empty bootstrap runtime before any user calls so old/core and extended tools share
# one boss-aware, spatially authoritative, 48-player-capable, timeline-capable state.
if not isinstance(core_server.runtime, TimelineRaidAincradRuntime):
    core_server.runtime = TimelineRaidAincradRuntime(seed=0xA1C0)

mcp = core_server.mcp
runtime = core_server.runtime

if not hasattr(runtime, "economy"):
    runtime.economy = EconomyRuntime()

register_adventure_tools(mcp, runtime)
register_inventory_tools(mcp, runtime)
register_progression_tools(mcp, runtime)
register_economy_tools(mcp, runtime, runtime.economy)
register_spatial_tools(mcp, runtime)
register_timeline_tools(mcp, runtime)

from sao_mcp.server_bosses import register_boss_tools  # noqa: E402

register_boss_tools(mcp, runtime)

# Import after all state/tool groups exist so UI views can expose every panel and boss state.
from sao_mcp import server_ui as _server_ui  # noqa: E402,F401
from sao_mcp import server_boss_ui as _server_boss_ui  # noqa: E402,F401

__all__ = ["mcp", "runtime"]
