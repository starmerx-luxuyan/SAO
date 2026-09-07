from __future__ import annotations

from sao_mcp.rules.economy import EconomyRuntime


class GuardedEconomyRuntime(EconomyRuntime):
    """Economy adapter that asks the authoritative runtime whether an instance may leave inventory."""

    def __init__(self, runtime, vendors=None) -> None:
        super().__init__(vendors=vendors)
        self.runtime = runtime

    def sell_to_vendor(self, seller, vendor_id, instance_id, catalog, *, quantity, actor_location_id):
        self.runtime.validate_item_disposition(seller.actor_id, instance_id)
        return super().sell_to_vendor(
            seller,
            vendor_id,
            instance_id,
            catalog,
            quantity=quantity,
            actor_location_id=actor_location_id,
        )

    def create_player_listing(
        self,
        seller,
        instance_id,
        *,
        location_id,
        unit_price_col,
        quantity,
        now_ms,
    ):
        self.runtime.validate_item_disposition(seller.actor_id, instance_id)
        return super().create_player_listing(
            seller,
            instance_id,
            location_id=location_id,
            unit_price_col=unit_price_col,
            quantity=quantity,
            now_ms=now_ms,
        )


def make_runtime_economy(runtime) -> EconomyRuntime:
    if hasattr(runtime, "validate_item_disposition"):
        return GuardedEconomyRuntime(runtime)
    return EconomyRuntime()
