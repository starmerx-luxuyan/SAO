from __future__ import annotations

import json
from enum import Enum
from typing import Any


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_floor7_campaign_tools(mcp, campaign) -> None:
    @mcp.tool()
    def get_floor7_campaign_handoff(harin_instance_id: str, aghyellr_instance_id: str) -> str:
        """Validate the authoritative Floor 7 -> Floor 8 handoff across five sacred keys, Nirrnir, Civis Nocte, Doleful Nocturne and Aghyellr blood."""
        return _json(campaign.handoff(harin_instance_id, aghyellr_instance_id))
