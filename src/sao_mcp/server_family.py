from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.rules.family import DivorceMode


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_family_tools(mcp, runtime) -> None:
    @mcp.tool()
    def propose_divorce(
        actor_id: str,
        mode: str = "auto_percentage",
        proposer_percent: int = 50,
        selected_item_ids: list[str] | None = None,
    ) -> str:
        """Propose canonical marriage-inventory allocation; surrender_all with 0% completes unilaterally."""
        return _json(
            asdict(
                runtime.propose_divorce(
                    actor_id,
                    mode=DivorceMode(mode),
                    proposer_percent=proposer_percent,
                    selected_item_ids=selected_item_ids,
                )
            )
        )

    @mcp.tool()
    def accept_divorce(proposal_id: str, target_id: str) -> str:
        """Accept a pending divorce allocation and separate the shared inventory/wallet."""
        return _json(asdict(runtime.accept_divorce(proposal_id, target_id)))

    @mcp.tool()
    def decline_divorce(proposal_id: str, target_id: str) -> str:
        """Decline a pending divorce allocation; marriage remains active."""
        return _json(asdict(runtime.decline_divorce(proposal_id, target_id)))

    @mcp.tool()
    def list_ground_drops(location_id: str) -> str:
        """List persistent items dropped because a post-marriage personal inventory could not hold them."""
        rows = runtime.world.global_flags.get("ground_drops", {}).get(location_id, [])
        return _json({"locationId": location_id, "drops": rows})
