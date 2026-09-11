from __future__ import annotations

from typing import Any

from sao_mcp.runtime.community_hooks import attach_community_economy
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime
from sao_mcp.runtime.property_economy import GuardedEconomyRuntime, make_runtime_economy


class EconomyLoopAincradRuntime(PopulationAincradRuntime):
    """Top-level runtime that resolves the living Aincrad economy on world-time boundaries."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        economy = make_runtime_economy(self)
        if not isinstance(economy, GuardedEconomyRuntime):
            raise RuntimeError("Aincrad economy loop requires the runtime-bound economy authority")
        self.economy: GuardedEconomyRuntime = economy
        attach_community_economy(self, self.economy)
        self.register_world_advance_hook(self._resolve_due_economy_activities)

    def _resolve_due_economy_activities(self, before_ms: int, after_ms: int) -> None:
        while self.economy.next_tick_at_ms <= after_ms:
            tick_ms = self.economy.next_tick_at_ms
            if tick_ms != after_ms:
                raise RuntimeError("economy tick boundary was skipped by world scheduler")
            self.economy.advance_living_market_tick(tick_ms)

    def _next_scheduler_boundary(self, target_ms: int) -> int:
        boundary = super()._next_scheduler_boundary(target_ms)
        now = self.world.now_ms
        tick = self.economy.next_tick_at_ms
        if now < tick <= target_ms:
            return min(boundary, tick)
        return boundary

    def aincrad_economy_state(self, location_id: str | None = None) -> dict[str, Any]:
        return self.economy.state(location_id)

    def economy_vendor_state(self, vendor_id: str) -> dict[str, Any]:
        return self.economy.vendor_state(vendor_id)

    def economy_history(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self.economy.market_history
        if limit is None:
            return list(rows)
        if limit < 1:
            raise ValueError("economy history limit must be positive")
        return list(rows[-limit:])
