from __future__ import annotations

from collections.abc import Callable

from sao_mcp.runtime.communications_runtime import CommunicatingAincradRuntime


WorldAdvanceHook = Callable[[int, int], None]


class WorldEventAincradRuntime(CommunicatingAincradRuntime):
    """Full social runtime with callbacks driven by authoritative world-time changes."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.world_advance_hooks: list[WorldAdvanceHook] = []

    def register_world_advance_hook(self, hook: WorldAdvanceHook) -> None:
        self.world_advance_hooks.append(hook)

    def _emit_world_advance(self, before_ms: int) -> None:
        after_ms = self.world.now_ms
        if after_ms == before_ms:
            return
        for hook in tuple(self.world_advance_hooks):
            hook(before_ms, after_ms)

    def advance_world(self, elapsed_ms: int) -> list[int]:
        before_ms = self.world.now_ms
        activated = super().advance_world(elapsed_ms)
        self._emit_world_advance(before_ms)
        return activated

    def travel_actor(self, actor_id: str, destination_id: str):
        # GameRuntime.travel_actor delegates to the data-only travel rule, which advances
        # WorldState directly. Emit the same authoritative time event after that commit.
        before_ms = self.world.now_ms
        resolution = super().travel_actor(actor_id, destination_id)
        self._emit_world_advance(before_ms)
        return resolution
