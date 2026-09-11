from __future__ import annotations

import os


def _load_mcp(transport: str):
    surface = os.getenv("SAO_MCP_SURFACE", "").strip().lower()
    if not surface:
        surface = "public" if transport == "streamable-http" else "full"
    if surface == "public":
        from sao_mcp.server_public import mcp

        return mcp
    if surface == "full":
        from sao_mcp.server_bootstrap import mcp

        return mcp
    raise ValueError("SAO_MCP_SURFACE must be 'public' or 'full'")


def main() -> None:
    transport = os.getenv("SAO_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "streamable-http"}:
        raise ValueError("SAO_MCP_TRANSPORT must be 'stdio' or 'streamable-http'")

    mcp = _load_mcp(transport)
    if transport == "streamable-http":
        host = os.getenv("SAO_MCP_HOST", "127.0.0.1")
        port = int(os.getenv("SAO_MCP_PORT", "8000"))
        mcp.run(transport="streamable-http", host=host, port=port)
        return
    mcp.run()
