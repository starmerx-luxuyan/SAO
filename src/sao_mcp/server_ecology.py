from __future__ import annotations

import json
from dataclasses import asdict


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def register_monster_ecology_tools(mcp, runtime) -> None:
    @mcp.tool()
    def get_monster_ecology_state(location_id: str | None = None) -> str:
        """Inspect living monster density, depletion, recovery, danger and background resource supply."""
        return _json(runtime.monster_ecology_state(location_id))

    @mcp.tool()
    def get_monster_ecology_history(limit: int = 100) -> str:
        """Inspect recent monster recovery, hunting, materialization, losses and retreat events."""
        if limit < 1:
            raise ValueError("limit must be positive")
        return _json({"events": runtime.monster_ecology_history[-limit:]})

    @mcp.tool()
    def materialize_wild_monster(monster_id: str) -> str:
        """Materialize one real monster actor from the authoritative local ecology population."""
        actor = runtime.materialize_ecological_monster(monster_id)
        return _json(asdict(actor))

    @mcp.tool()
    def release_wild_monster(actor_id: str) -> str:
        """Return a living non-encounter ecological monster actor to its abstract local population."""
        runtime.release_ecological_monster(actor_id)
        return _json({"released": actor_id})
