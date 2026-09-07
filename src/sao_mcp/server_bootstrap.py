from __future__ import annotations

from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.server import mcp, runtime
from sao_mcp.server_adventure import register_adventure_tools
from sao_mcp.server_economy import register_economy_tools
from sao_mcp.server_inventory import register_inventory_tools
from sao_mcp.server_progression import register_progression_tools

if not hasattr(runtime, "economy"):
    runtime.economy = EconomyRuntime()

register_adventure_tools(mcp, runtime)
register_inventory_tools(mcp, runtime)
register_progression_tools(mcp, runtime)
register_economy_tools(mcp, runtime, runtime.economy)

__all__ = ["mcp", "runtime"]
