from __future__ import annotations

import os

from sao_mcp.server_bootstrap import mcp


def main() -> None:
    transport = os.getenv("SAO_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "streamable-http":
        host = os.getenv("SAO_MCP_HOST", "127.0.0.1")
        port = int(os.getenv("SAO_MCP_PORT", "8000"))
        mcp.run(transport="streamable-http", host=host, port=port)
        return
    if transport != "stdio":
        raise ValueError("SAO_MCP_TRANSPORT must be 'stdio' or 'streamable-http'")
    mcp.run()
