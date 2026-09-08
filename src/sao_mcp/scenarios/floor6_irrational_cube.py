from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6 import (
    IRRATIONAL_CUBE_ID,
    TARGET_CODE,
    TARGET_FACE,
    apply_floor6_boss_corpus,
    apply_floor6_world_seed,
)
from sao_mcp.domain.models import EntityKind


BOSS_ROOM = "floor_6_boss_room"
ROTATION_ACTION_MS = 900  # Simulation action time for one row/column rotation.
INITIAL_FACE = ((3, 4, 2), (1, 5, 8), (9, 6, 7))


class Floor6IrrationalCubeScenario:
    """Number-face invulnerability puzzle followed by the normal Floor 6 boss combat phase."""

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

    def start_puzzle(self, player_ids: list[str]) -> dict:
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("Irrational Cube trial needs at least one player")
        if len(players) > 48:
            raise ValueError("one Aincrad raid group cannot exceed 48 players")
        if not self.runtime.world.floors[6].unlocked:
            raise ValueError("Floor 6 is not unlocked")
        for actor_id in players:
            actor = self.runtime.actors[actor_id]
            if (
                actor.kind is not EntityKind.PLAYER
                or not actor.alive
                or actor.location_id != BOSS_ROOM
            ):
                raise ValueError("all participants must be living players in the Floor 6 Boss Room")

        instance_id = f"cube6_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "player_ids": players,
            "stage": "number_face_puzzle",
            "face": self._face_as_rows(INITIAL_FACE),
            "target_code": TARGET_CODE,
            "rotation_count": 0,
            "started_at_ms": self.runtime.world.now_ms,
            "puzzle_solved_at_ms": None,
            "encounter_id": None,
            "boss_id": None,
        }
        self._instances()[instance_id] = state
        return self.status(instance_id)

    def _after_rotation(self, state: dict) -> dict:
        state["rotation_count"] += 1
        self.runtime.advance_world(ROTATION_ACTION_MS)
        if self._matches_target(state["face"]):
            state["stage"] = "puzzle_solved"
            state["puzzle_solved_at_ms"] = self.runtime.world.now_ms
        return self.status(state["instance_id"])

    def rotate_row(self, instance_id: str, row: int, direction: str) -> dict:
        state = self._instance(instance_id)
        if state["stage"] != "number_face_puzzle":
            raise ValueError("number-face rows can only be rotated during the invulnerable puzzle phase")
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
            raise ValueError("number-face columns can only be rotated during the invulnerable puzzle phase")
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

    def engage_boss(self, instance_id: str) -> dict:
        state = self._instance(instance_id)
        if state["stage"] == "battle":
            return self.status(instance_id)
        if state["stage"] != "puzzle_solved":
            raise ValueError("The Irrational Cube remains invulnerable until the number face matches the door code")

        encounter, boss = self.runtime.start_floor_boss_encounter(
            state["player_ids"],
            boss_definition_id=IRRATIONAL_CUBE_ID,
        )
        boss.metadata["number_face_puzzle_solved"] = True
        boss.metadata["number_face_target_code"] = TARGET_CODE
        state["stage"] = "battle"
        state["encounter_id"] = encounter.encounter_id
        state["boss_id"] = boss.actor_id
        return self.status(instance_id)

    def status(self, instance_id: str) -> dict:
        state = self._instance(instance_id)
        boss_state = None
        if state.get("boss_id"):
            boss = self.runtime.actors[state["boss_id"]]
            boss_state = self.runtime.boss_bar_state(boss)
            if not boss.alive and state["stage"] == "battle":
                state["stage"] = "cleared"
        return {
            "instance_id": instance_id,
            "stage": state["stage"],
            "player_ids": list(state["player_ids"]),
            "face": [list(row) for row in state["face"]],
            "target_code": state["target_code"],
            "rotation_count": state["rotation_count"],
            "puzzle_solved": self._matches_target(state["face"]),
            "encounter_id": state.get("encounter_id"),
            "boss_id": state.get("boss_id"),
            "boss": boss_state,
        }


def install_floor6_irrational_cube_scenario(runtime) -> Floor6IrrationalCubeScenario:
    return Floor6IrrationalCubeScenario(runtime)
