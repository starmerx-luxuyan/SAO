from __future__ import annotations

import math
import uuid

from sao_mcp.corpus.floor5_flag import FLAG_OF_VALOR
from sao_mcp.domain.models import EntityKind, ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.state_authority import authoritative_guild_id, locate_runtime_item


FUSCUS_ID = "fuscus_the_vacant_colossus"
BOSS_ROOM = "floor_5_boss_room"
FLAG_AURA_RANGE_M = 12.0  # Simulation; canon only establishes a limited area of effect.
FLAG_STAT_BONUS = 0.08  # Simulation magnitude applied to the existing all-stat combat path.


class Floor5FuscusScenario:
    """Floor 5 Fuscus raid plus the secret personal Flag of Valor drop and deployable guild aura."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def _instances(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor5_fuscus_instances", {})

    def _instance(self, instance_id: str) -> dict:
        try:
            return self._instances()[instance_id]
        except KeyError as exc:
            raise KeyError(f"unknown Floor 5 Fuscus instance: {instance_id}") from exc

    def start_raid(self, player_ids: list[str]) -> dict:
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("Fuscus raid needs at least one player")
        if not self.runtime.world.floors[5].unlocked:
            raise ValueError("Floor 5 is not unlocked")
        for actor_id in players:
            actor = self.runtime.actors[actor_id]
            if actor.kind is not EntityKind.PLAYER or not actor.alive or actor.location_id != BOSS_ROOM:
                raise ValueError("all Fuscus raid participants must be living players in the Floor 5 Boss Room")

        encounter, boss = self.runtime.start_floor_boss_encounter(
            players,
            boss_definition_id=FUSCUS_ID,
        )
        instance_id = f"fuscus5_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "encounter_id": encounter.encounter_id,
            "boss_id": boss.actor_id,
            "player_ids": players,
            "stage": "battle",
            "started_at_ms": self.runtime.world.now_ms,
            "flag_drop_resolved": False,
            "flag_recipient_id": None,
            "flag_instance_id": None,
        }
        self._instances()[instance_id] = state
        return self.status(instance_id)

    def resolve_hidden_flag_drop(self, instance_id: str) -> dict:
        state = self._instance(instance_id)
        boss = self.runtime.actors[state["boss_id"]]
        if boss.alive:
            raise ValueError("Fuscus must be defeated before the Flag of Valor drop resolves")
        if state["flag_drop_resolved"]:
            return {"instance_id": instance_id, "resolved": True, "drop_created": True}

        encounter = self.runtime.encounters[state["encounter_id"]]
        candidates = sorted(
            actor.actor_id
            for actor in encounter.participants.values()
            if actor.kind is EntityKind.PLAYER and actor.alive
        )
        if not candidates:
            candidates = sorted(state["player_ids"])
        recipient_id = self.runtime.rng.choice(candidates)
        item = ItemInstance(
            instance_id=f"flag_{uuid.uuid4().hex[:12]}",
            template_id=FLAG_OF_VALOR,
            owner_id=recipient_id,
            quantity=1,
            metadata={
                "fuscus_instance_id": instance_id,
                "hidden_personal_drop": True,
                "allocation": "random_raid_participant_simulation",
            },
        )
        add_item(self.runtime.actors[recipient_id], item, self.runtime.catalog, allow_overweight=True)
        state["flag_drop_resolved"] = True
        state["flag_recipient_id"] = recipient_id
        state["flag_instance_id"] = item.instance_id
        state["stage"] = "post_boss_secret_drop"
        return {"instance_id": instance_id, "resolved": True, "drop_created": True}

    def check_personal_flag_drop(self, actor_id: str, instance_id: str) -> dict:
        state = self._instance(instance_id)
        if actor_id not in state["player_ids"]:
            raise ValueError("only raid participants can inspect their personal Fuscus drop")
        if not state["flag_drop_resolved"]:
            return {"actor_id": actor_id, "resolved": False, "received": False}
        received = state["flag_recipient_id"] == actor_id
        return {
            "actor_id": actor_id,
            "resolved": True,
            "received": received,
            "instance_id": state["flag_instance_id"] if received else None,
            "template_id": FLAG_OF_VALOR if received else None,
        }

    def _owned_flag(self, actor_id: str) -> ItemInstance:
        actor = self.runtime.actors[actor_id]
        for item in actor.inventory.values():
            if item.template_id == FLAG_OF_VALOR:
                return item
        raise ValueError("actor does not possess the Flag of Valor")

    @staticmethod
    def _clear_flag_source(encounter, source_actor_id: str) -> None:
        for actor in encounter.participants.values():
            if actor.metadata.get("flag_of_valor_source_actor_id") != source_actor_id:
                continue
            actor.metadata.pop("flag_of_valor_stat_bonus", None)
            actor.metadata.pop("flag_of_valor_source_actor_id", None)
            actor.metadata.pop("flag_of_valor_encounter_id", None)

    def _deployment_state(self, state: dict) -> dict | None:
        flag_id = state.get("flag_instance_id")
        if not flag_id:
            return None
        located = locate_runtime_item(self.runtime, flag_id)
        if located is None:
            if state.get("flag_drop_resolved"):
                raise RuntimeError("resolved Flag of Valor instance is missing from authoritative containers")
            return None
        flag = located.item
        if flag.template_id != FLAG_OF_VALOR:
            raise RuntimeError("Fuscus flag instance ID points to the wrong item template")
        encounter_id = flag.metadata.get("deployed_encounter_id")
        if encounter_id is None:
            return None
        deployed_by_actor_id = flag.metadata.get("deployed_by_actor_id")
        if not isinstance(deployed_by_actor_id, str):
            raise RuntimeError("deployed Flag of Valor has no authoritative wielder")
        if located.kind != "actor_inventory" or deployed_by_actor_id not in located.actor_ids:
            raise RuntimeError("deployed Flag of Valor is no longer in its wielder's inventory pool")
        if encounter_id not in self.runtime.encounters:
            raise RuntimeError("deployed Flag of Valor references an unknown encounter")
        encounter = self.runtime.encounters[encounter_id]
        affected = sorted(
            actor_id
            for actor_id, actor in encounter.participants.items()
            if actor.metadata.get("flag_of_valor_source_actor_id") == deployed_by_actor_id
            and actor.metadata.get("flag_of_valor_encounter_id") == encounter_id
        )
        return {
            "owner_id": deployed_by_actor_id,
            "flag_instance_id": flag.instance_id,
            "encounter_id": encounter_id,
            "range_m": FLAG_AURA_RANGE_M,
            "stat_bonus": FLAG_STAT_BONUS,
            "affected_actor_ids": affected,
        }

    def refresh_flag_aura(self, actor_id: str, encounter_id: str) -> dict:
        owner = self.runtime.actors[actor_id]
        flag = self._owned_flag(actor_id)
        owner_guild_id = authoritative_guild_id(self.runtime, actor_id)
        if owner_guild_id is None:
            raise ValueError("Flag of Valor requires the wielder to belong to a guild")
        encounter = self.runtime.encounters[encounter_id]
        if actor_id not in encounter.participants or not owner.alive:
            raise ValueError("flag wielder must be a living participant in the encounter")

        self._clear_flag_source(encounter, actor_id)
        owner_pos = encounter.positions.get(actor_id)
        if owner_pos is None:
            raise ValueError("encounter has no authoritative position for the flag wielder")

        for target_id, target in encounter.participants.items():
            if target_id == actor_id or target.kind is not EntityKind.PLAYER or not target.alive:
                continue
            if authoritative_guild_id(self.runtime, target_id) != owner_guild_id:
                continue
            target_pos = encounter.positions.get(target_id)
            if target_pos is None:
                continue
            distance = math.dist(owner_pos, target_pos)
            if distance > FLAG_AURA_RANGE_M:
                continue
            target.metadata["flag_of_valor_stat_bonus"] = FLAG_STAT_BONUS
            target.metadata["flag_of_valor_source_actor_id"] = actor_id
            target.metadata["flag_of_valor_encounter_id"] = encounter_id

        flag.metadata["deployed_encounter_id"] = encounter_id
        flag.metadata["deployed_by_actor_id"] = actor_id
        state = next(
            state
            for state in self._instances().values()
            if state.get("flag_instance_id") == flag.instance_id
        )
        deployment = self._deployment_state(state)
        if deployment is None:
            raise RuntimeError("Flag of Valor deployment did not become authoritative")
        return deployment

    def withdraw_flag(self, actor_id: str, encounter_id: str) -> dict:
        flag = self._owned_flag(actor_id)
        encounter = self.runtime.encounters[encounter_id]
        self._clear_flag_source(encounter, actor_id)
        flag.metadata.pop("deployed_encounter_id", None)
        flag.metadata.pop("deployed_by_actor_id", None)
        return {"owner_id": actor_id, "encounter_id": encounter_id, "deployed": False}

    def status(self, instance_id: str) -> dict:
        state = self._instance(instance_id)
        boss = self.runtime.actors[state["boss_id"]]
        return {
            "instance_id": instance_id,
            "encounter_id": state["encounter_id"],
            "boss_id": boss.actor_id,
            "boss_alive": boss.alive,
            "boss": self.runtime.boss_bar_state(boss),
            "stage": state["stage"],
            "flag_drop_resolved": state["flag_drop_resolved"],
            "flag_deployment": self._deployment_state(state),
        }


def install_floor5_fuscus_scenario(runtime) -> Floor5FuscusScenario:
    return Floor5FuscusScenario(runtime)
