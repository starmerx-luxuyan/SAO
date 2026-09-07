from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from sao_mcp.domain.models import DefenseMode


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_timeline_tools(mcp, runtime) -> None:
    @mcp.tool()
    def get_combat_timeline(encounter_id: str) -> str:
        """Inspect queued player impacts and pending Boss execution points."""
        return _json(runtime.timeline_state(encounter_id))

    @mcp.tool()
    def begin_timeline_attack(
        encounter_id: str,
        attacker_id: str,
        target_id: str,
        sword_skill_id: str | None = None,
        defense: str = "auto",
        seed: int | None = None,
    ) -> str:
        """Begin an attack without resolving it immediately; useful for actions overlapping Boss telegraphs."""
        action = runtime.queue_player_attack(
            encounter_id,
            attacker_id,
            target_id,
            sword_skill_id=sword_skill_id,
            defense=DefenseMode(defense),
            seed=seed,
        )
        return _json(asdict(action))

    @mcp.tool()
    def process_next_combat_event(encounter_id: str) -> str:
        """Advance to and resolve exactly the next ordered Boss/player timeline event."""
        return _json(runtime.process_next_timeline_event(encounter_id))
