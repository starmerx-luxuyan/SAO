from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:150]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Boss disengage removes summoned minions through encounter membership authority.
path = "src/sao_mcp/rules/raids.py"
replace_once(
    path,
    '''    for actor_id, actor in list(encounter.participants.items()):
        if actor.metadata.get("boss_parent_id") == boss.actor_id:
            encounter.participants.pop(actor_id, None)
    runtime._append(
''',
    '''    minion_ids = [
        actor_id
        for actor_id, actor in encounter.participants.items()
        if actor.metadata.get("boss_parent_id") == boss.actor_id
    ]
    if minion_ids:
        runtime.remove_encounter_participants(
            encounter.encounter_id, minion_ids, reason="boss_disengage_minion_reset"
        )
    runtime._append(
''',
)

# Boss minions are real actors at the boss location, so add them through the central live roster.
path = "src/sao_mcp/runtime/aincrad_runtime.py"
replace_once(
    path,
    '''            minion = self._create_boss_minion(definition.initial_minion_template_id, boss_id=boss.actor_id)
            encounter.participants[minion.actor_id] = minion
            spawned.append(minion.actor_id)
''',
    '''            minion = self._create_boss_minion(definition.initial_minion_template_id, boss_id=boss.actor_id)
            self.add_encounter_participant(encounter.encounter_id, minion.actor_id)
            spawned.append(minion.actor_id)
''',
)

# Historical Witch encounter remains intact after resolution; only an active roster needs removal.
path = "src/sao_mcp/scenarios/floor22_witch.py"
replace_once(
    path,
    '''        encounter = runtime.encounters.get(state.get("witch_encounter_id"))
        if encounter is not None:
            for actor_id in returning_ids:
                encounter.participants.pop(actor_id, None)
                encounter.positions.pop(actor_id, None)
                encounter.threat.pop(actor_id, None)
                for table in encounter.threat.values():
                    table.pop(actor_id, None)

        return_started_at_ms = runtime.world.now_ms
''',
    '''        encounter = runtime.encounters.get(state.get("witch_encounter_id"))
        if encounter is not None and encounter.active:
            active_returners = [actor_id for actor_id in returning_ids if actor_id in encounter.participants]
            if active_returners:
                runtime.remove_encounter_participants(
                    encounter.encounter_id,
                    active_returners,
                    reason="witch_defeated_log_house_return",
                )

        return_started_at_ms = runtime.world.now_ms
''',
)

# Floor 2 second-phase boss entry is a live roster join.
path = "src/sao_mcp/scenarios/floor2_taurus_raid.py"
replace_once(
    path,
    '''        encounter = self.runtime.encounters[instance["encounter_id"]]
        boss = self.runtime.actors[instance["asterius_id"]]
        encounter.participants[boss.actor_id] = boss
        self.runtime._arrange_raid_formation(encounter, boss)
''',
    '''        encounter = self.runtime.encounters[instance["encounter_id"]]
        boss = self.runtime.actors[instance["asterius_id"]]
        self.runtime.add_encounter_participant(encounter.encounter_id, boss.actor_id)
        self.runtime._arrange_raid_formation(encounter, boss)
''',
)

# Buxum enters and leaves the active boss encounter through the central roster authority.
path = "src/sao_mcp/scenarios/floor6_buxum.py"
replace_once(
    path,
    '''        buxum = self._create_buxum(combined_key)
        encounter = self.runtime.encounters[cube_state["encounter_id"]]
        encounter.participants[buxum.actor_id] = buxum
        boss_position = encounter.positions.get(boss.actor_id, (1.15, 0.0))
        encounter.positions[buxum.actor_id] = (boss_position[0] + 1.65, boss_position[1] + 0.75)
''',
    '''        buxum = self._create_buxum(combined_key)
        encounter = self.runtime.encounters[cube_state["encounter_id"]]
        boss_position = encounter.positions.get(boss.actor_id, (1.15, 0.0))
        self.runtime.add_encounter_participant(
            encounter.encounter_id,
            buxum.actor_id,
            position=(boss_position[0] + 1.65, boss_position[1] + 0.75),
        )
''',
)
replace_once(
    path,
    '''        encounter.participants.pop(buxum.actor_id, None)
        encounter.positions.pop(buxum.actor_id, None)
        state["stage"] = "golden_cube_dropped"
''',
    '''        self.runtime.remove_encounter_participants(
            encounter.encounter_id, [buxum.actor_id], reason="buxum_retreat"
        )
        state["stage"] = "golden_cube_dropped"
''',
)

# A separate Golden Cube holder joins the raid roster through the same authority.
path = "src/sao_mcp/scenarios/floor6_irrational_cube.py"
replace_once(
    path,
    '''        if golden_cube_holder_id not in encounter.participants:
            encounter.participants[golden_cube_holder_id] = holder
            encounter.positions[golden_cube_holder_id] = (-2.6, 0.0)
''',
    '''        if golden_cube_holder_id not in encounter.participants:
            self.runtime.add_encounter_participant(
                encounter.encounter_id, golden_cube_holder_id, position=(-2.6, 0.0)
            )
''',
)

# Basalt pursuit combat is explicitly resolved before Theano's route resumes.
path = "src/sao_mcp/scenarios/floor6_south.py"
replace_once(
    path,
    '''        theano = self.runtime.actors[state["theano_actor_id"]]
        encounter = self.runtime.encounters[state["basalt_encounter_id"]]
        encounter.participants = {actor_id: self.runtime.actors[actor_id]}
        encounter.positions = {actor_id: encounter.positions.get(actor_id, (-1.15, 0.0))}
        route = travel_route_together(self.runtime, [theano.actor_id], MURUTSUKI)
''',
    '''        theano = self.runtime.actors[state["theano_actor_id"]]
        encounter = self.runtime.encounters[state["basalt_encounter_id"]]
        if encounter.active:
            leaving = [member_id for member_id in encounter.participants if member_id != actor_id]
            if leaving:
                self.runtime.remove_encounter_participants(
                    encounter.encounter_id, leaving, reason="basalt_morpha_defeated"
                )
        route = travel_route_together(self.runtime, [theano.actor_id], MURUTSUKI)
''',
)

# Morte and Joe are physical reinforcements into the carriage encounter.
path = "src/sao_mcp/scenarios/floor6_stachion.py"
replace_once(
    path,
    '''        morte = self._create_hostile_player("Morte", MORTE_HATCHET_ID, level=24, strength=52, agility=47)
        joe = self._create_hostile_player("Joe", JOE_DAGGER_ID, level=22, strength=38, agility=56)
        encounter.participants[morte.actor_id] = morte
        encounter.participants[joe.actor_id] = joe
        player_position = encounter.positions.get(actor_id, (-1.15, 0.0))
        encounter.positions[morte.actor_id] = (player_position[0] + 3.0, player_position[1] + 1.2)
        encounter.positions[joe.actor_id] = (player_position[0] + 3.2, player_position[1] - 1.2)
''',
    '''        morte = self._create_hostile_player("Morte", MORTE_HATCHET_ID, level=24, strength=52, agility=47)
        joe = self._create_hostile_player("Joe", JOE_DAGGER_ID, level=22, strength=38, agility=56)
        player_position = encounter.positions.get(actor_id, (-1.15, 0.0))
        self.runtime.add_encounter_participant(
            encounter.encounter_id,
            morte.actor_id,
            position=(player_position[0] + 3.0, player_position[1] + 1.2),
        )
        self.runtime.add_encounter_participant(
            encounter.encounter_id,
            joe.actor_id,
            position=(player_position[0] + 3.2, player_position[1] - 1.2),
        )
''',
)

# Nirrnir reaches the boss room through world travel first, then joins the encounter roster.
path = "src/sao_mcp/scenarios/floor7_aghyellr.py"
replace_once(
    path,
    '''            if nirrnir.location_id != BOSS_ROOM:
                raise RuntimeError("Nirrnir movement authority did not reach the Aghyellr Boss Room")
            encounter.participants[nirrnir.actor_id] = nirrnir
            encounter.positions[nirrnir.actor_id] = (-8.0, 0.0)
''',
    '''            if nirrnir.location_id != BOSS_ROOM:
                raise RuntimeError("Nirrnir movement authority did not reach the Aghyellr Boss Room")
            self.runtime.add_encounter_participant(
                encounter.encounter_id, nirrnir.actor_id, position=(-8.0, 0.0)
            )
''',
)
