from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:140]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# A defeated monster can close a simple encounter when no combatant remains to fight it.
# Player End Phase is deliberately excluded so SAO's revival window remains live.
path = "src/sao_mcp/runtime/engine.py"
replace_once(
    path,
    '''        for hook in tuple(self.defeat_hooks):
            hook(encounter, target, killer_id)

    def _advance_encounter_to''',
    '''        for hook in tuple(self.defeat_hooks):
            hook(encounter, target, killer_id)
        if (
            target.kind in (EntityKind.MONSTER, EntityKind.BOSS)
            and encounter.active
            and not any(
                actor.kind is EntityKind.PLAYER and actor.metadata.get("death_state") == "end_phase"
                for actor in encounter.participants.values()
            )
            and sum(1 for actor in encounter.participants.values() if actor.alive) <= 1
        ):
            self.end_encounter(encounter.encounter_id, reason="combat_resolved")

    def _advance_encounter_to''',
)
replace_once(
    path,
    '''        self._append(
            encounter,
            "participants_left",
            None,
            None,
            actor_ids=list(members),
            reason=reason,
        )

    def end_encounter''',
    '''        self._append(
            encounter,
            "participants_left",
            None,
            None,
            actor_ids=list(members),
            reason=reason,
        )
        if (
            encounter.active
            and not any(
                actor.kind is EntityKind.PLAYER and actor.metadata.get("death_state") == "end_phase"
                for actor in encounter.participants.values()
            )
            and sum(1 for actor in encounter.participants.values() if actor.alive) <= 1
        ):
            self.end_encounter(encounter_id, reason=f"{reason}:combat_resolved")

    def end_encounter''',
)

# End Phase remains a live encounter condition even though the fallen player is not alive.
path = "src/sao_mcp/rules/travel.py"
replace_once(
    path,
    '''        actor.alive
        and actor.actor_id not in member_ids
        and actor.location_id == origin_location_id
''',
    '''        (actor.alive or actor.metadata.get("death_state") == "end_phase")
        and actor.actor_id not in member_ids
        and actor.location_id == origin_location_id
''',
)

# Duel completion gets an explicit encounter lifecycle. If a player is in the ten-second
# End Phase, keep it live until revival/finalization and close it then.
path = "src/sao_mcp/runtime/social_runtime.py"
replace_once(
    path,
    '''    def _close_duel_encounters(self, duel_id: str) -> None:
        for encounter in self._duel_encounters(duel_id):
            # Duel completion ends PvP authorization and threat, but the encounter remains the
            # authoritative record for spatial state, End Phase timing, and revival actions.
            encounter.threat.clear()
''',
    '''    def _close_duel_encounters(self, duel_id: str) -> None:
        for encounter in self._duel_encounters(duel_id):
            encounter.threat.clear()
            if not encounter.active:
                continue
            if any(
                actor.kind is EntityKind.PLAYER and actor.metadata.get("death_state") == "end_phase"
                for actor in encounter.participants.values()
            ):
                continue
            self.end_encounter(encounter.encounter_id, reason=f"duel_completed:{duel_id}")
''',
)
replace_once(
    path,
    '''        self._append(
            encounter,
            "player_revived",
            reviver_id,
            target_id,
            item_template_id="divine_stone_returning_soul",
            hp_after=target.hp,
            recovery_until_ms=target.recovery_until_ms,
        )
        return {
''',
    '''        self._append(
            encounter,
            "player_revived",
            reviver_id,
            target_id,
            item_template_id="divine_stone_returning_soul",
            hp_after=target.hp,
            recovery_until_ms=target.recovery_until_ms,
        )
        for duel_id in self._duel_ids_for_encounter(encounter):
            if self.duels.duels[duel_id].status is DuelStatus.COMPLETED:
                self._close_duel_encounters(duel_id)
        return {
''',
)
replace_once(
    path,
    '''                self._append(
                    encounter,
                    "player_death_finalized",
                    None,
                    actor.actor_id,
                    death_at_ms=actor.metadata.get("death_at_encounter_ms"),
                )

    def _advance_encounter_to''',
    '''                self._append(
                    encounter,
                    "player_death_finalized",
                    None,
                    actor.actor_id,
                    death_at_ms=actor.metadata.get("death_at_encounter_ms"),
                )
        for duel_id in self._duel_ids_for_encounter(encounter):
            if self.duels.duels[duel_id].status is DuelStatus.COMPLETED:
                self._close_duel_encounters(duel_id)

    def _advance_encounter_to''',
)

# Multi-player boss victory needs an explicit scenario resolution point because several living
# allies remain and the engine cannot infer team hostility from headcount alone.
path = "src/sao_mcp/scenarios/floor5_fuscus.py"
replace_once(
    path,
    '''        state["flag_instance_id"] = item.instance_id
        state["stage"] = "post_boss_secret_drop"
        return {"instance_id": instance_id, "resolved": True, "drop_created": True}
''',
    '''        state["flag_instance_id"] = item.instance_id
        state["stage"] = "post_boss_secret_drop"
        if encounter.active:
            self.runtime.end_encounter(encounter.encounter_id, reason="fuscus_defeated")
        return {"instance_id": instance_id, "resolved": True, "drop_created": True}
''',
)

# The blocker encounter is resolved at this explicit pursuit transition before the party travels on.
path = "src/sao_mcp/scenarios/floor7_pursuit.py"
replace_once(
    path,
    '''        pursuit["trail_outcome"] = "maintained" if combat_elapsed_ms <= TRAIL_MARGIN_MS else "lost"

        for scout_id in pursuit["fallen_scout_ids"]:
''',
    '''        pursuit["trail_outcome"] = "maintained" if combat_elapsed_ms <= TRAIL_MARGIN_MS else "lost"
        if encounter.active:
            self.runtime.end_encounter(encounter.encounter_id, reason="labyrinth_blockers_defeated")

        for scout_id in pursuit["fallen_scout_ids"]:
''',
)

# Persistence fixtures must describe actors actually present in their active encounter.
path = "tests/test_adventure_persistence.py"
replace_once(
    path,
    '''    monster = rt.create_training_monster(level=2)
    enc = rt.start_encounter([actor.actor_id, monster.actor_id])
''',
    '''    monster = rt.create_training_monster(level=2)
    actor.location_id = monster.location_id
    enc = rt.start_encounter([actor.actor_id, monster.actor_id])
''',
)

path = "tests/test_spatial_combat.py"
replace_once(
    path,
    '''    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (-3.25, 1.5)
''',
    '''    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (-3.25, 1.5)
''',
)

path = "tests/test_timeline_combat.py"
replace_once(
    path,
    '''    monster = runtime.create_training_monster(level=1)
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
''',
    '''    monster = runtime.create_training_monster(level=1)
    player.location_id = monster.location_id
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id])
    encounter.positions[player.actor_id] = (0.0, 0.0)
''',
)

path = "tests/test_boss_persistence.py"
replace_once(
    path,
    '''    player = runtime.create_character("Saver", level=8)
    encounter, boss = runtime.start_floor_boss_encounter([player.actor_id], enforce_location=False)
''',
    '''    player = runtime.create_character("Saver", level=8)
    runtime.world.floors[1].unlocked = True
    player.location_id = "floor_1_boss_room"
    encounter, boss = runtime.start_floor_boss_encounter([player.actor_id])
''',
)
