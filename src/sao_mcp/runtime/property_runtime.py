from __future__ import annotations

from sao_mcp.runtime.family_runtime import FamilyCommunityAincradRuntime


class PropertyFamilyAincradRuntime(FamilyCommunityAincradRuntime):
    """Family runtime with cross-actor item-instance occupancy for shared marriage inventories."""

    def equipped_instance_owner(self, instance_id: str) -> tuple[str, str] | None:
        for actor in self.actors.values():
            for slot, equipped_id in actor.equipment.items():
                if equipped_id == instance_id:
                    return actor.actor_id, slot
        return None

    def require_instance_not_equipped(self, instance_id: str, *, except_actor_id: str | None = None) -> None:
        owner = self.equipped_instance_owner(instance_id)
        if owner is None:
            return
        actor_id, slot = owner
        if except_actor_id is not None and actor_id == except_actor_id:
            return
        raise ValueError(f"item instance is equipped by actor {actor_id} in slot {slot}")

    def equip_item(self, actor_id: str, instance_id: str):
        owner = self.equipped_instance_owner(instance_id)
        if owner is not None and owner[0] != actor_id:
            raise ValueError("item instance is already equipped by another actor")
        return super().equip_item(actor_id, instance_id)

    def transfer_inventory_item(
        self,
        source_id: str,
        destination_id: str,
        instance_id: str,
        *,
        quantity: int | None = None,
    ):
        self.require_instance_not_equipped(instance_id)
        return super().transfer_inventory_item(
            source_id,
            destination_id,
            instance_id,
            quantity=quantity,
        )

    def deposit_shared_storage(
        self,
        actor_id: str,
        storage_id: str,
        instance_id: str,
        *,
        quantity: int | None = None,
    ):
        self.require_instance_not_equipped(instance_id)
        return super().deposit_shared_storage(
            actor_id,
            storage_id,
            instance_id,
            quantity=quantity,
        )

    def validate_item_disposition(self, actor_id: str, instance_id: str) -> None:
        if instance_id not in self.actors[actor_id].inventory:
            raise KeyError(instance_id)
        self.require_instance_not_equipped(instance_id)
