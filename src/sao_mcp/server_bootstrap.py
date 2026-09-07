from __future__ import annotations

from sao_mcp.server import mcp, runtime
from sao_mcp.server_adventure import register_adventure_tools
from sao_mcp.server_inventory import register_inventory_tools

register_adventure_tools(mcp, runtime)
register_inventory_tools(mcp, runtime)

__all__ = ["mcp", "runtime"]
