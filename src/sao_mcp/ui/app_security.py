from __future__ import annotations

from mcp.server.apps import ResourceCsp


WIDGET_DOMAIN = "sao-aincrad-mcp-production.up.railway.app"
WIDGET_CSP = ResourceCsp(
    connect_domains=[],
    resource_domains=[],
    frame_domains=[],
    base_uri_domains=[],
)
