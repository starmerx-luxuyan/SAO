from __future__ import annotations

from sao_mcp.corpus.floor5_shortcut import (
    KARLUIN_SHORTCUT_CONNECTION_ID,
    KARLUIN_SHORTCUT_CONNECTIONS,
)
from sao_mcp.corpus.world import TravelConnection


DYNAMIC_TRAVEL_CONNECTIONS: dict[str, tuple[TravelConnection, ...]] = {
    KARLUIN_SHORTCUT_CONNECTION_ID: KARLUIN_SHORTCUT_CONNECTIONS,
}
