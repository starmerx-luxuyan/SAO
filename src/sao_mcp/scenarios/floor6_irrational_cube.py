from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6 import (
    IRRATIONAL_CUBE_ID,
    TARGET_CODE,
    TARGET_FACE,
    apply_floor6_boss_corpus,
    apply_floor6_world_seed,
)
from sao_mcp.corpus.floor6_finale import COMBINED_IRON_KEY_ID, GOLDEN_CUBE_ID
from sao_mcp.domain.models import EntityKind, StatusEffectState, StatusType
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.social import apply_unlawful_hostile_action


BOSS_ROOM = "floor_6_boss_room"
ROTATION_ACTION_MS = 900  # Simulation action time for one row/column rotation.
INITIAL_FACE = ((3, 4, 2), (1, 5, 8), (9, 6, 7))
GOLDEN_CUBE_BIND_MS = 120_000  # Simulation duration for the canon extreme immobilisation effect.


class Floor6IrrationalCubeScenario:
    """Official-service Floor 6 guardian: Golden Cube activation, numbered armor, black core and last-pixel finish."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        apply_floor6_world_seed(runtime.world_map)
        apply_floor6_boss_corpus(runtime.catalog)

    def _instances(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor6_irrational_cube_instances", {})

    def _instance(self, instance_id: str) -> dict:
        try:
            return self._instances()[instance_id]
        except KeyError as exc:
            raise KeyError(f"unknown Floor 6 Irrational Cube instance: {instance_id}") from exc

    @staticmethod
    def _face_as_rows(face) -> list[list[int]]:
        return [list(row) for row in face]

    @staticmethod
    def _matches_target(face: list[list[int]]) -> bool:
        return tuple(tuple(row) for row in face) == TARGET_FACE

    def activate_guardian(
        self,
        player_ids: list[str],
        golden_cube_holder_id: str,
        golden_cube_instance_id: str,
    ) -> dict:
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("Irrational Cube raid needs at least one player")
        if len(players) > 48:
            raise ValueError("one Aincrad raid group cannot exceed 48 players")
        if not self.runtime.world.floors[6].unlocked:
            raise ValueError("Floor 6 is not unlocked")
        for actor_id in players:
            actor = self.runtime.actors[actor_id]
            if actor.kind is not EntityKind.PLAYER or not actor.alive or actor.location_id != BOSS_ROOM:
                raise ValueError("all raid participants must be living players in the Floor 6 Boss Room")

        holder = self.runtime.actors[golden_cube_holder_id]
        if not holder.alive or holder.location_id != BOSS_ROOM:
            raise ValueError("the Golden Cube holder must be alive in the Floor 6 Boss Room")
        cube_item = holder.inventory[golden_cube_instance_id]
        if cube_item.template_id != GOLDEN_CUBE_ID:
            raise ValueError("the supplied item is not the Stachion Golden Cube")

        encounter, boss = self.runtime.start_floor_boss_encounter(
            players,
            boss_definition_id=IRRATIONAL_CUBE_ID,
        )
        if golden_cube_holder_id not in encounter.participants:
            encounter.participants[golden_cube_holder_id] = holder
            encounter.positions[golden_cube_holder_id] = (-2.6, 0.0)

        holder.inventory.pop(golden_cube_instance_id)
        cube_item.owner_id = boss.actor_id
        cube_item.metadata["inserted_into_irrational_cube"] = True
        cube_item.metadata["inserted_at_ms"] = self.runtime.world.now_ms
        boss.inventory[cube_item.instance_id] = cube_item
        boss.metadata.update(
            {
                "golden_cube_instance_id": cube_item.instance_id,
                "numbered_armor_active": True,
                "black_core_exposed": False,
                "hp_floor": boss.max_hp,
                "outer_armor_cube_count": 26,
                "golden_cube_required": True,
            }
        )
        self.runtime._append(
            encounter,
            "golden_cube_inserted",
            golden_cube_holder_id,
            boss.actor_id,
            golden_cube_instance_id=cube_item.instance_id,
            outer_armor_cube_count=26,
        )

        instance_id = f"cube6_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "player_ids": players,
            "golden_cube_holder_id": golden_cube_holder_id,
            "golden_cube_instance_id": cube_item.instance_id,
            "stage": "number_face_puzzle",
            "face": self._face_as_rows(INITIAL_FACE),
            "target_code": TARGET_CODE,
            "rotation_count": 0,
            "started_at_ms": self.runtime.world.now_ms,
            "puzzle_solved_at_ms": None,
            "encounter_id": encounter.encounter_id,
            "boss_id": boss.actor_id,
            "cube_ejected_by_actor_id": None,
            "combined_key_instance_id": None,
            "golden_cube_destroyed": False,
        }
        self._instances()[instance_id] = state
        return self.status(instance_id)

    def _after_rotation(self, state: dict) -> dict:
        state["rotation_count"] += 1
        self.runtime.advance_world(ROTATION_ACTION_MS)
        self.runtime.advance_encounter(state["encounter_id"], ROTATION_ACTION_MS)
        if self._matches_target(state["face"]):
            boss = self.runtime.actors[state["boss_id"]]
            boss.metadata["numbered_armor_active"] = False
            boss.metadata["black_core_exposed"] = True
            boss.metadata["hp_floor"] = 1
            state["stage"] = "black_core_battle"
            state["puzzle_solved_at_ms"] = self.runtime.world.now_ms
            self.runtime._append(
                self.runtime.encounters[state["encounter_id"]],
                "irrational_cube_numbered_armor_collapsed",
                None,
                boss.actor_id,
                outer_armor_cube_count=26,
                hp_floor=1,
            )
        return self.status(state["instance_id"])

    def rotate_row(self, instance_id: str, row: int, direction: str) -> dict:
        state = self._instance(instance_id)
        if state["stage"] != "number_face_puzzle":
            raise ValueError("number-face rows can only be rotated while the numbered armor is active")
        if row not in (0, 1, 2):
            raise ValueError("row must be 0, 1 or 2")
        direction = direction.lower()
        values = list(state["face"][row])
        if direction == "left":
            values = values[1:] + values[:1]
        elif direction == "right":
            values = values[-1:] + values[:-1]
        else:
            raise ValueError("row direction must be left or right")
        state["face"][row] = values
        return self._after_rotation(state)

    def rotate_column(self, instance_id: str, column: int, direction: str) -> dict:
        state = self._instance(instance_id)
        if state["stage"] != "number_face_puzzle":
            raise ValueError("number-face columns can only be rotated while the numbered armor is active")
        if column not in (0, 1, 2):
            raise ValueError("column must be 0, 1 or 2")
        direction = direction.lower()
        values = [state["face"][row][column] for row in range(3)]
        if direction == "up":
            values = values[1:] + values[:1]
        elif direction == "down":
            values = values[-1:] + values[:-1]
        else:
            raise ValueError("column direction must be up or down")
        for row in range(3):
            state["face"][row][column] = values[row]
        return self._after_rotation(state)

    def eject_golden_cube(
        self,
        instance_id: str,
        actor_id: str,
        combined_key_instance_id: str,
    ) -> dict:
        state = self._instance(instance_id)
        if state["stage"] != "black_core_battle":
            raise ValueError("the Golden Cube can be ejected only after the numbered armor has collapsed")
        encounter = self.runtime.encounters[state["encounter_id"]]
        if actor_id not in encounter.participants or not encounter.participants[actor_id].alive:
            raise ValueError("the key user must be a living participant in the boss encounter")
        boss = self.runtime.actors[state["boss_id"]]
        if boss.hp != 1:
            raise ValueError("the reverse keyhole becomes the finishing mechanic at the black core's final HP pixel")
        actor = self.runtime.actors[actor_id]
        key = actor.inventory[combined_key_instance_id]
        if key.template_id != COMBINED_IRON_KEY_ID:
            raise ValueError("the reverse keyhole requires the combined Cylon/Theano iron key")
        cube_item = boss.inventory.pop(state["golden_cube_instance_id"])
        cube_item.owner_id = actor_id
        cube_item.metadata["ejected_from_irrational_cube"] = True
        cube_item.metadata["ejected_at_ms"] = self.runtime.world.now_ms
        add_item(actor, cube_item, self.runtime.catalog, allow_overweight=True)
        key.metadata["used_to_eject_golden_cube"] = True
        key.metadata["survives_floor6_boss"] = True
        state["stage"] = "golden_cube_ejected"
        state["cube_ejected_by_actor_id"] = actor_id
        state["combined_key_instance_id"] = key.instance_id
        self.runtime._append(
            encounter,
            "golden_cube_ejected",
            actor_id,
            boss.actor_id,
            golden_cube_instance_id=cube_item.instance_id,
            combined_key_instance_id=key.instance_id,
        )
        return self.status(instance_id)

    def use_golden_cube_bind(self, instance_id: str, actor_id: str) -> dict:
        """Use the ejected cube's canon Bind power; ordinary crime rules apply to a player using it on other players."""
        state = self._instance(instance_id)
        if state["stage"] not in {"golden_cube_ejected", "golden_cube_bind_active"}:
            raise ValueError("the Golden Cube must first be ejected from the black core")
        actor = self.runtime.actors[actor_id]
        cube_item = actor.inventory[state["golden_cube_instance_id"]]
        if cube_item.template_id != GOLDEN_CUBE_ID:
            raise ValueError("actor does not hold the ejected Golden Cube")
        encounter = self.runtime.encounters[state["encounter_id"]]
        affected: list[str] = []
        for target_id, target in encounter.participants.items():
            if target_id == actor_id or not target.alive:
                continue
            target.statuses = [status for status in target.statuses if status.stack_key != "golden_cube_bind"]
            target.statuses.append(
                StatusEffectState(
                    effect_id=f"golden_cube_bind:{actor_id}:{target_id}:{encounter.time_ms}",
                    status_type=StatusType.STUN,
                    source_id=actor_id,
                    remaining_ms=GOLDEN_CUBE_BIND_MS,
                    magnitude=1.0,
                    tick_interval_ms=GOLDEN_CUBE_BIND_MS,
                    until_next_tick_ms=GOLDEN_CUBE_BIND_MS,
                    stack_key="golden_cube_bind",
                    tags=("golden_cube", "bind", "extreme_immobilisation"),
                )
            )
            if actor.kind is EntityKind.PLAYER and target.kind is EntityKind.PLAYER:
                apply_unlawful_hostile_action(actor, target, safe_zone=False)
            affected.append(target_id)
        cube_item.metadata["bind_used_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "golden_cube_bind_active"
        self.runtime._append(
            encounter,
            "golden_cube_bind",
            actor_id,
            None,
            affected_actor_ids=affected,
        )
        return {"instance_id": instance_id, "actor_id": actor_id, "affected_actor_ids": affected, "state": self.status(instance_id)}

    def reinsert_cube_and_destroy_core(self, instance_id: str, actor_id: str) -> dict:
        state = self._instance(instance_id)
        if state["stage"] not in {"golden_cube_ejected", "golden_cube_bind_active"}:
            raise ValueError("the Golden Cube must be ejected before it can be reinserted for destruction")
        actor = self.runtime.actors[actor_id]
        cube_item = actor.inventory.get(state["golden_cube_instance_id"])
        if cube_item is None or cube_item.template_id != GOLDEN_CUBE_ID:
            raise ValueError("actor must possess the ejected Golden Cube")
        boss = self.runtime.actors[state["boss_id"]]
        if boss.hp != 1:
            raise ValueError("the black core must still be at its final HP pixel")
        encounter = self.runtime.encounters[state["encounter_id"]]

        actor.inventory.pop(cube_item.instance_id)
        cube_item.owner_id = boss.actor_id
        cube_item.metadata["reinserted_for_destruction"] = True
        boss.inventory[cube_item.instance_id] = cube_item
        boss.metadata.pop("hp_floor", None)
        boss.hp = 0
        boss.alive = False
        boss.inventory.pop(cube_item.instance_id, None)
        cube_item.owner_id = None
        cube_item.metadata["destroyed_with_irrational_cube"] = True
        state["golden_cube_destroyed"] = True
        state["stage"] = "cleared"
        state["cleared_at_ms"] = self.runtime.world.now_ms
        for participant in encounter.participants.values():
            participant.statuses = [status for status in participant.statuses if status.stack_key != "golden_cube_bind"]
        self.runtime._append(
            encounter,
            "golden_cube_reinserted_and_destroyed",
            actor_id,
            boss.actor_id,
            golden_cube_instance_id=cube_item.instance_id,
        )
        self.runtime._resolve_defeat(encounter, boss, actor_id)
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._instance(instance_id)
        boss = self.runtime.actors[state["boss_id"]]
        return {
            "instance_id": instance_id,
            "stage": state["stage"],
            "player_ids": list(state["player_ids"]),
            "face": [list(row) for row in state["face"]],
            "target_code": state["target_code"],
            "rotation_count": state["rotation_count"],
            "puzzle_solved": self._matches_target(state["face"]),
            "encounter_id": state["encounter_id"],
            "boss_id": state["boss_id"],
            "boss": self.runtime.boss_bar_state(boss),
            "numbered_armor_active": bool(boss.metadata.get("numbered_armor_active")),
            "black_core_exposed": bool(boss.metadata.get("black_core_exposed")),
            "hp_floor": boss.metadata.get("hp_floor"),
            "golden_cube_instance_id": state["golden_cube_instance_id"],
            "cube_ejected_by_actor_id": state.get("cube_ejected_by_actor_id"),
            "combined_key_instance_id": state.get("combined_key_instance_id"),
            "golden_cube_destroyed": bool(state.get("golden_cube_destroyed")),
        }


def install_floor6_irrational_cube_scenario(runtime) -> Floor6IrrationalCubeScenario:
    required = {GOLDEN_CUBE_ID, COMBINED_IRON_KEY_ID}
    if any(template_id not in runtime.catalog.items for template_id in required):
        raise RuntimeError("Floor 6 Golden Cube finale corpus was not loaded")
    return Floor6IrrationalCubeScenario(runtime)
