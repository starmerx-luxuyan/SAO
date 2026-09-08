from __future__ import annotations

import uuid


BOSS_DEFINITION_ID = "asterius_the_taurus_king"
NATO_ID = "nato_colonel_taurus"
BARAN_ID = "baran_general_taurus"
BOSS_ROOM = "floor_2_boss_room"


class Floor2TaurusRaidScenario:
    """Progressive Floor 2 raid sequence: the Taurus mid-boss pair followed by Asterius."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def _instances(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor2_taurus_raid_instances", {})

    def _instance(self, instance_id: str) -> dict:
        try:
            return self._instances()[instance_id]
        except KeyError as exc:
            raise KeyError(f"unknown Floor 2 Taurus raid instance: {instance_id}") from exc

    def start_raid(self, player_ids: list[str]) -> dict:
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("Floor 2 raid needs at least one player")
        if len(players) > 48:
            raise ValueError("one Aincrad raid group cannot exceed 48 players")
        if not self.runtime.world.floors[2].unlocked:
            raise ValueError("Floor 2 is not unlocked")
        for actor_id in players:
            actor = self.runtime.actors[actor_id]
            if not actor.alive or actor.location_id != BOSS_ROOM:
                raise ValueError("all raid participants must be living players in the Floor 2 Boss Room")

        # Asterius is constructed up front only to bind the existing minion factory to his encounter family;
        # he is not an encounter participant until both Taurus mid-bosses have fallen.
        asterius = self.runtime.create_floor_boss(BOSS_DEFINITION_ID)
        nato = self.runtime._create_boss_minion(NATO_ID, boss_id=asterius.actor_id)
        baran = self.runtime._create_boss_minion(BARAN_ID, boss_id=asterius.actor_id)
        encounter = self.runtime.start_encounter(
            players + [nato.actor_id, baran.actor_id],
            zone_id=BOSS_ROOM,
        )
        self.runtime._append(
            encounter,
            "floor2_taurus_midbosses_started",
            None,
            None,
            nato_id=nato.actor_id,
            baran_id=baran.actor_id,
            waiting_boss_id=asterius.actor_id,
        )
        instance_id = f"taurus2_{uuid.uuid4().hex[:12]}"
        instance = {
            "instance_id": instance_id,
            "encounter_id": encounter.encounter_id,
            "player_ids": players,
            "stage": "nato_and_baran",
            "nato_id": nato.actor_id,
            "baran_id": baran.actor_id,
            "asterius_id": asterius.actor_id,
            "started_at_ms": self.runtime.world.now_ms,
            "asterius_entered_at_ms": None,
        }
        self._instances()[instance_id] = instance
        return dict(instance)

    def unleash_asterius(self, instance_id: str) -> dict:
        instance = self._instance(instance_id)
        if instance["stage"] == "asterius":
            return dict(instance)
        encounter = self.runtime.encounters[instance["encounter_id"]]
        nato = self.runtime.actors[instance["nato_id"]]
        baran = self.runtime.actors[instance["baran_id"]]
        if nato.alive or baran.alive:
            raise ValueError("Nato and Baran must both be defeated before Asterius enters")

        boss = self.runtime.actors[instance["asterius_id"]]
        encounter.participants[boss.actor_id] = boss
        self.runtime._arrange_raid_formation(encounter, boss)
        self.runtime._append(
            encounter,
            "floor2_asterius_entered",
            boss.actor_id,
            None,
            boss_definition_id=BOSS_DEFINITION_ID,
            hp_bars=self.runtime.boss_definition(boss).hp_bars,
        )
        instance["stage"] = "asterius"
        instance["asterius_entered_at_ms"] = self.runtime.world.now_ms
        return dict(instance)

    def status(self, instance_id: str) -> dict:
        instance = self._instance(instance_id)
        return {
            **instance,
            "nato_alive": self.runtime.actors[instance["nato_id"]].alive,
            "baran_alive": self.runtime.actors[instance["baran_id"]].alive,
            "asterius_alive": self.runtime.actors[instance["asterius_id"]].alive,
        }


def install_floor2_taurus_raid_scenario(runtime) -> Floor2TaurusRaidScenario:
    return Floor2TaurusRaidScenario(runtime)
