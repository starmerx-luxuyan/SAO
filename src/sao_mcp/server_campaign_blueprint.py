from __future__ import annotations

import json
from enum import Enum
from typing import Any

from sao_mcp.runtime.campaign_blueprint import (
    apply_campaign_blueprint as _apply_campaign_blueprint,
    preview_campaign_blueprint as _preview_campaign_blueprint,
    validate_campaign_blueprint as _validate_campaign_blueprint,
)


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_campaign_blueprint_tools(mcp, runtime) -> None:
    @mcp.tool()
    def validate_campaign_blueprint(blueprint: dict[str, Any]) -> str:
        """Validate a complete custom-start blueprint against a cloned authoritative runtime without mutation."""
        return _json(_validate_campaign_blueprint(runtime, blueprint))

    @mcp.tool()
    def preview_campaign_blueprint(blueprint: dict[str, Any]) -> str:
        """Execute a complete custom-start blueprint on a cloned runtime and return the resulting setup preview."""
        return _json(_preview_campaign_blueprint(runtime, blueprint))

    @mcp.tool()
    def apply_campaign_blueprint(blueprint: dict[str, Any]) -> str:
        """Apply a fully validated blueprint during open setup; the blueprint is built off-state before commit and does not finalize setup."""
        return _json(_apply_campaign_blueprint(runtime, blueprint))
