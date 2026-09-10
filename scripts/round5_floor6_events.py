from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# -------------------- Buxum --------------------
replace_once(
    "src/sao_mcp/scenarios/floor6_buxum.py",
    '''BOSS_ROOM = "floor_6_boss_room"\nBUXUM_RETREAT_HP_RATIO = 0.35  # Simulation trigger; canon retreat follows loss of his sword and both forearms.\nAWAKENING_BURST_MS = 12_000  # Simulation marker window; canon only establishes a short superhuman burst.\n''',
    '''BOSS_ROOM = "floor_6_boss_room"\nBUXUM_RETREAT_HP_RATIO = 0.35  # Simulation trigger; canon retreat follows loss of his sword and both forearms.\nAWAKENING_BURST_MS = 12_000  # Simulation marker window; canon only establishes a short superhuman burst.\nBUXUM_BETRAYAL_EVENT_RULE_ID = "floor6.buxum_betrayal"\nBUXUM_RETREAT_EVENT_RULE_ID = "floor6.buxum_retreat"\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_buxum.py",
    '''    def __init__(self, runtime, cube) -> None:\n        self.runtime = runtime\n        self.cube = cube\n        runtime.register_defeat_hook(self._on_defeat)\n''',
    '''    def __init__(self, runtime, cube) -> None:\n        self.runtime = runtime\n        self.cube = cube\n        runtime.register_defeat_hook(self._on_defeat)\n        runtime.register_world_event_rule(\n            BUXUM_BETRAYAL_EVENT_RULE_ID,\n            self._discover_betrayal_events,\n            self._resolve_betrayal_event,\n        )\n        runtime.register_world_event_rule(\n            BUXUM_RETREAT_EVENT_RULE_ID,\n            self._discover_retreat_events,\n            self._resolve_retreat_event,\n        )\n        runtime.evaluate_world_events()\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_buxum.py",
    '''    def trigger_betrayal(self, cube_instance_id: str) -> dict:\n        cube_state = self.cube._instance(cube_instance_id)\n        if cube_state["stage"] != "black_core_battle":\n            raise ValueError("Buxum acts only after the numbered armor is broken and the black core is exposed")\n        boss = self.runtime.actors[cube_state["boss_id"]]\n        if boss.hp != 1:\n            raise ValueError("Buxum waits until The Irrational Cube is at its final HP pixel")\n        if cube_instance_id in self._states():\n            return self.status(cube_instance_id)\n\n        kysarah, combined_key = self._take_kysarah_combined_key()\n        buxum = self._create_buxum(combined_key)\n        encounter = self.runtime.encounters[cube_state["encounter_id"]]\n        boss_position = encounter.positions.get(boss.actor_id, (1.15, 0.0))\n        self.runtime.add_encounter_participant(\n            encounter.encounter_id,\n            buxum.actor_id,\n            position=(boss_position[0] + 1.65, boss_position[1] + 0.75),\n        )\n        self.runtime._append(\n            encounter,\n            "buxum_revealed",\n            buxum.actor_id,\n            boss.actor_id,\n            former_combined_key_holder_id=kysarah.actor_id,\n            combined_key_instance_id=combined_key.instance_id,\n            key_handoff_mechanism="canonically_unexplained",\n        )\n\n        # The existing guardian scenario owns the keyhole, cube-ejection and crime-aware Bind mechanics.\n        self.cube.eject_golden_cube(cube_instance_id, buxum.actor_id, combined_key.instance_id)\n        bind_result = self.cube.use_golden_cube_bind(cube_instance_id, buxum.actor_id)\n\n        state = {\n            "cube_instance_id": cube_instance_id,\n            "stage": "bind_active",\n            "buxum_actor_id": buxum.actor_id,\n            "encounter_id": encounter.encounter_id,\n            "combined_key_instance_id": combined_key.instance_id,\n            "golden_cube_instance_id": cube_state["golden_cube_instance_id"],\n            "former_combined_key_holder_id": kysarah.actor_id,\n            "awakening_actor_ids": [],\n            "cube_ground_cache_actor_id": None,\n            "cube_recovered_by_actor_id": None,\n            "triggered_at_ms": self.runtime.world.now_ms,\n            "bind_affected_actor_ids": list(bind_result["affected_actor_ids"]),\n        }\n        self._states()[cube_instance_id] = state\n        return self.status(cube_instance_id)\n''',
    '''    @staticmethod\n    def _event_instance_id(occurrence_id: str, rule_id: str) -> str:\n        prefix = f"{rule_id}:"\n        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):\n            raise RuntimeError(f"invalid {rule_id} occurrence id: {occurrence_id}")\n        return occurrence_id[len(prefix):]\n\n    def _discover_betrayal_events(self) -> list[str]:\n        located = self._combined_key_location()\n        if located is None or located.sole_actor_id is None:\n            return []\n        holder = self.runtime.actors[located.sole_actor_id]\n        if holder.metadata.get("npc_definition_id") != KYSARAH_ID:\n            return []\n\n        ready: list[str] = []\n        for cube_instance_id, cube_state in self.cube._instances().items():\n            if cube_instance_id in self._states() or cube_state["stage"] != "black_core_battle":\n                continue\n            boss = self.runtime.actors[cube_state["boss_id"]]\n            encounter = self.runtime.encounters[cube_state["encounter_id"]]\n            if boss.alive and boss.hp == 1 and encounter.active and boss.actor_id in encounter.participants:\n                ready.append(f"{BUXUM_BETRAYAL_EVENT_RULE_ID}:{cube_instance_id}")\n        return ready\n\n    def _resolve_betrayal_event(self, occurrence_id: str) -> dict:\n        cube_instance_id = self._event_instance_id(occurrence_id, BUXUM_BETRAYAL_EVENT_RULE_ID)\n        state = self._trigger_betrayal(cube_instance_id)\n        return {\n            "cube_instance_id": cube_instance_id,\n            "encounter_id": state["encounter_id"],\n            "buxum_actor_id": state["buxum_actor_id"],\n            "golden_cube_instance_id": state["golden_cube_instance_id"],\n        }\n\n    def _trigger_betrayal(self, cube_instance_id: str) -> dict:\n        cube_state = self.cube._instance(cube_instance_id)\n        if cube_state["stage"] != "black_core_battle":\n            raise ValueError("Buxum acts only after the numbered armor is broken and the black core is exposed")\n        boss = self.runtime.actors[cube_state["boss_id"]]\n        if boss.hp != 1:\n            raise ValueError("Buxum waits until The Irrational Cube is at its final HP pixel")\n        if cube_instance_id in self._states():\n            raise RuntimeError("Buxum betrayal occurrence attempted to resolve twice")\n\n        kysarah, combined_key = self._take_kysarah_combined_key()\n        buxum = self._create_buxum(combined_key)\n        encounter = self.runtime.encounters[cube_state["encounter_id"]]\n        boss_position = encounter.positions.get(boss.actor_id, (1.15, 0.0))\n        self.runtime.add_encounter_participant(\n            encounter.encounter_id,\n            buxum.actor_id,\n            position=(boss_position[0] + 1.65, boss_position[1] + 0.75),\n        )\n        self.runtime._append(\n            encounter,\n            "buxum_revealed",\n            buxum.actor_id,\n            boss.actor_id,\n            former_combined_key_holder_id=kysarah.actor_id,\n            combined_key_instance_id=combined_key.instance_id,\n            key_handoff_mechanism="canonically_unexplained",\n        )\n\n        # The existing guardian scenario owns the keyhole, cube-ejection and crime-aware Bind mechanics.\n        self.cube.eject_golden_cube(cube_instance_id, buxum.actor_id, combined_key.instance_id)\n        bind_result = self.cube.use_golden_cube_bind(cube_instance_id, buxum.actor_id)\n\n        state = {\n            "cube_instance_id": cube_instance_id,\n            "stage": "bind_active",\n            "buxum_actor_id": buxum.actor_id,\n            "encounter_id": encounter.encounter_id,\n            "combined_key_instance_id": combined_key.instance_id,\n            "golden_cube_instance_id": cube_state["golden_cube_instance_id"],\n            "former_combined_key_holder_id": kysarah.actor_id,\n            "awakening_actor_ids": [],\n            "cube_ground_cache_actor_id": None,\n            "cube_recovered_by_actor_id": None,\n            "triggered_at_ms": self.runtime.world.now_ms,\n            "bind_affected_actor_ids": list(bind_result["affected_actor_ids"]),\n        }\n        self._states()[cube_instance_id] = state\n        return self.status(cube_instance_id)\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_buxum.py",
    '''    def resolve_buxum_retreat(self, cube_instance_id: str) -> dict:\n        state = self._state(cube_instance_id)\n        if state["stage"] not in {"bind_active", "awakening_counterattack"}:\n            raise ValueError("Buxum is not in the active betrayal phase")\n        buxum = self.runtime.actors[state["buxum_actor_id"]]\n        weapon_id = buxum.equipment.get("weapon")\n        weapon_broken = bool(\n            not weapon_id\n            or weapon_id not in buxum.inventory\n            or buxum.inventory[weapon_id].broken\n        )\n        low_hp = buxum.hp <= max(1, int(round(buxum.max_hp * BUXUM_RETREAT_HP_RATIO)))\n        if buxum.alive and not low_hp and not weapon_broken:\n            raise ValueError("Buxum has not yet been overpowered enough to abandon the Golden Cube and retreat")\n\n        cache = self._drop_buxum_cube(state, buxum)\n        encounter = self.runtime.encounters[state["encounter_id"]]\n        if buxum.alive:\n            buxum.metadata["retreated"] = True\n            buxum.metadata["retreat_reason"] = "overpowered_after_golden_cube_bind"\n        self.runtime.remove_encounter_participants(\n            encounter.encounter_id, [buxum.actor_id], reason="buxum_retreat"\n        )\n        state["stage"] = "golden_cube_dropped"\n        state["cube_ground_cache_actor_id"] = cache.actor_id\n        state["buxum_retreat_at_ms"] = self.runtime.world.now_ms\n        self.runtime._append(\n            encounter,\n            "buxum_drops_cube_and_retreats",\n            buxum.actor_id,\n            None,\n            golden_cube_instance_id=state["golden_cube_instance_id"],\n            buxum_alive=buxum.alive,\n            weapon_broken=weapon_broken,\n            hp=buxum.hp,\n            max_hp=buxum.max_hp,\n        )\n        return self.status(cube_instance_id)\n''',
    '''    def _discover_retreat_events(self) -> list[str]:\n        ready: list[str] = []\n        for cube_instance_id, state in self._states().items():\n            if state["stage"] not in {"bind_active", "awakening_counterattack"}:\n                continue\n            buxum = self.runtime.actors[state["buxum_actor_id"]]\n            weapon_id = buxum.equipment.get("weapon")\n            weapon_broken = bool(\n                not weapon_id\n                or weapon_id not in buxum.inventory\n                or buxum.inventory[weapon_id].broken\n            )\n            low_hp = buxum.hp <= max(1, int(round(buxum.max_hp * BUXUM_RETREAT_HP_RATIO)))\n            if not buxum.alive or low_hp or weapon_broken:\n                ready.append(f"{BUXUM_RETREAT_EVENT_RULE_ID}:{cube_instance_id}")\n        return ready\n\n    def _resolve_retreat_event(self, occurrence_id: str) -> dict:\n        cube_instance_id = self._event_instance_id(occurrence_id, BUXUM_RETREAT_EVENT_RULE_ID)\n        state = self._resolve_buxum_retreat(cube_instance_id)\n        return {\n            "cube_instance_id": cube_instance_id,\n            "buxum_actor_id": state["buxum_actor_id"],\n            "golden_cube_instance_id": state["golden_cube_instance_id"],\n            "stage": state["stage"],\n        }\n\n    def _resolve_buxum_retreat(self, cube_instance_id: str) -> dict:\n        state = self._state(cube_instance_id)\n        if state["stage"] not in {"bind_active", "awakening_counterattack"}:\n            raise ValueError("Buxum is not in the active betrayal phase")\n        buxum = self.runtime.actors[state["buxum_actor_id"]]\n        weapon_id = buxum.equipment.get("weapon")\n        weapon_broken = bool(\n            not weapon_id\n            or weapon_id not in buxum.inventory\n            or buxum.inventory[weapon_id].broken\n        )\n        low_hp = buxum.hp <= max(1, int(round(buxum.max_hp * BUXUM_RETREAT_HP_RATIO)))\n        if buxum.alive and not low_hp and not weapon_broken:\n            raise ValueError("Buxum has not yet been overpowered enough to abandon the Golden Cube and retreat")\n\n        cache = self._drop_buxum_cube(state, buxum)\n        encounter = self.runtime.encounters[state["encounter_id"]]\n        if buxum.alive:\n            buxum.metadata["retreated"] = True\n            buxum.metadata["retreat_reason"] = "overpowered_after_golden_cube_bind"\n        self.runtime.remove_encounter_participants(\n            encounter.encounter_id, [buxum.actor_id], reason="buxum_retreat"\n        )\n        state["stage"] = "golden_cube_dropped"\n        state["cube_ground_cache_actor_id"] = cache.actor_id\n        state["buxum_retreat_at_ms"] = self.runtime.world.now_ms\n        self.runtime._append(\n            encounter,\n            "buxum_drops_cube_and_retreats",\n            buxum.actor_id,\n            None,\n            golden_cube_instance_id=state["golden_cube_instance_id"],\n            buxum_alive=buxum.alive,\n            weapon_broken=weapon_broken,\n            hp=buxum.hp,\n            max_hp=buxum.max_hp,\n        )\n        return self.status(cube_instance_id)\n''',
)

replace_once(
    "src/sao_mcp/scenarios/floor6_irrational_cube.py",
    '''            self.runtime._append(\n                self.runtime.encounters[state["encounter_id"]],\n                "irrational_cube_numbered_armor_collapsed",\n                None,\n                boss.actor_id,\n                outer_armor_cube_count=26,\n                hp_floor=1,\n            )\n        return self.status(state["instance_id"])\n''',
    '''            self.runtime._append(\n                self.runtime.encounters[state["encounter_id"]],\n                "irrational_cube_numbered_armor_collapsed",\n                None,\n                boss.actor_id,\n                outer_armor_cube_count=26,\n                hp_floor=1,\n            )\n            self.runtime.evaluate_world_events()\n        return self.status(state["instance_id"])\n''',
)

# Remove manual Buxum trigger/retreat tools.
replace_once(
    "src/sao_mcp/server_floor6_buxum.py",
    '''    @mcp.tool()\n    def trigger_floor6_buxum_betrayal(cube_instance_id: str) -> str:\n        """At The Irrational Cube's final HP pixel, reveal Buxum, pass him Kysarah's same combined-key instance, eject the Golden Cube and Bind the room."""\n        return _json(buxum.trigger_betrayal(cube_instance_id))\n\n''',
    '''''',
)
replace_once(
    "src/sao_mcp/server_floor6_buxum.py",
    '''    @mcp.tool()\n    def resolve_floor6_buxum_retreat(cube_instance_id: str) -> str:\n        """When Buxum is defeated, his weapon breaks, or the simulation low-HP retreat threshold is crossed, make him drop the Golden Cube and leave the encounter."""\n        return _json(buxum.resolve_buxum_retreat(cube_instance_id))\n\n''',
    '''''',
)

# -------------------- Stachion --------------------
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''AMBUSH_RETREAT_HP_RATIO = 0.25  # Simulation threshold; canon only establishes that the pair eventually retreat.\n''',
    '''AMBUSH_RETREAT_HP_RATIO = 0.25  # Simulation threshold; canon only establishes that the pair eventually retreat.\nMORTE_JOE_AMBUSH_EVENT_RULE_ID = "floor6.morte_joe_ambush"\nPARALYSIS_RELEASE_EVENT_RULE_ID = "floor6.paralysis_release"\nAMBUSHER_RETREAT_EVENT_RULE_ID = "floor6.ambusher_retreat"\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''    def __init__(self, runtime) -> None:\n        self.runtime = runtime\n''',
    '''    def __init__(self, runtime) -> None:\n        self.runtime = runtime\n        runtime.register_world_event_rule(\n            MORTE_JOE_AMBUSH_EVENT_RULE_ID,\n            self._discover_morte_joe_ambush_events,\n            self._resolve_morte_joe_ambush_event,\n        )\n        runtime.register_world_event_rule(\n            PARALYSIS_RELEASE_EVENT_RULE_ID,\n            self._discover_paralysis_release_events,\n            self._resolve_paralysis_release_event,\n        )\n        runtime.register_world_event_rule(\n            AMBUSHER_RETREAT_EVENT_RULE_ID,\n            self._discover_ambusher_retreat_events,\n            self._resolve_ambusher_retreat_event,\n        )\n        runtime.evaluate_world_events()\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''        self.runtime._append(\n            self.runtime.encounters[encounter_id], "transport_reaches_ambush_site", state["cylon_actor_id"], actor_id\n        )\n        return self.status(actor_id)\n''',
    '''        self.runtime._append(\n            self.runtime.encounters[encounter_id], "transport_reaches_ambush_site", state["cylon_actor_id"], actor_id\n        )\n        self.runtime.evaluate_world_events()\n        return self.status(actor_id)\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''    def trigger_morte_joe_ambush(self, actor_id: str) -> dict:\n        state = self._state(actor_id)\n        if state["stage"] != "morte_joe_ambush_pending":\n            raise ValueError("the carriage has not reached the Morte/Joe ambush point")\n        encounter = self.runtime.encounters[state["transport_encounter_id"]]\n        cylon = self.runtime.actors[state["cylon_actor_id"]]\n        morte = self._create_hostile_player("Morte", MORTE_HATCHET_ID, level=24, strength=52, agility=47)\n        joe = self._create_hostile_player("Joe", JOE_DAGGER_ID, level=22, strength=38, agility=56)\n        player_position = encounter.positions.get(actor_id, (-1.15, 0.0))\n        self.runtime.add_encounter_participant(\n            encounter.encounter_id,\n            morte.actor_id,\n            position=(player_position[0] + 3.0, player_position[1] + 1.2),\n        )\n        self.runtime.add_encounter_participant(\n            encounter.encounter_id,\n            joe.actor_id,\n            position=(player_position[0] + 3.2, player_position[1] - 1.2),\n        )\n        self.runtime._append(encounter, "morte_joe_ambush", morte.actor_id, cylon.actor_id, joe_actor_id=joe.actor_id)\n        cylon.hp = 0\n        cylon.alive = False\n        self.runtime._resolve_defeat(encounter, cylon, morte.actor_id)\n        cache = self._drop_cylon_inventory(cylon)\n        for status in self.runtime.actors[actor_id].statuses:\n            if status.stack_key == "scripted_cylon_paralysis":\n                status.remaining_ms = min(status.remaining_ms, POST_CYLON_DEATH_PARALYSIS_MS)\n                status.until_next_tick_ms = min(status.until_next_tick_ms, status.remaining_ms)\n        state.update(\n            stage="ambush_cylon_dead",\n            morte_actor_id=morte.actor_id,\n            joe_actor_id=joe.actor_id,\n            ground_cache_actor_id=cache.actor_id,\n            cylon_killed_at_ms=self.runtime.world.now_ms,\n        )\n        return self.status(actor_id)\n''',
    '''    @staticmethod\n    def _event_actor_id(occurrence_id: str, rule_id: str) -> str:\n        prefix = f"{rule_id}:"\n        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):\n            raise RuntimeError(f"invalid {rule_id} occurrence id: {occurrence_id}")\n        return occurrence_id[len(prefix):]\n\n    def _discover_morte_joe_ambush_events(self) -> list[str]:\n        return [\n            f"{MORTE_JOE_AMBUSH_EVENT_RULE_ID}:{actor_id}"\n            for actor_id, state in self._states().items()\n            if state["stage"] == "morte_joe_ambush_pending"\n        ]\n\n    def _resolve_morte_joe_ambush_event(self, occurrence_id: str) -> dict:\n        actor_id = self._event_actor_id(occurrence_id, MORTE_JOE_AMBUSH_EVENT_RULE_ID)\n        state = self._trigger_morte_joe_ambush(actor_id)\n        return {\n            "actor_id": actor_id,\n            "encounter_id": state["transport_encounter_id"],\n            "morte_actor_id": state["morte_actor_id"],\n            "joe_actor_id": state["joe_actor_id"],\n            "cylon_actor_id": state["cylon_actor_id"],\n        }\n\n    def _trigger_morte_joe_ambush(self, actor_id: str) -> dict:\n        state = self._state(actor_id)\n        if state["stage"] != "morte_joe_ambush_pending":\n            raise ValueError("the carriage has not reached the Morte/Joe ambush point")\n        encounter = self.runtime.encounters[state["transport_encounter_id"]]\n        cylon = self.runtime.actors[state["cylon_actor_id"]]\n        morte = self._create_hostile_player("Morte", MORTE_HATCHET_ID, level=24, strength=52, agility=47)\n        joe = self._create_hostile_player("Joe", JOE_DAGGER_ID, level=22, strength=38, agility=56)\n        player_position = encounter.positions.get(actor_id, (-1.15, 0.0))\n        self.runtime.add_encounter_participant(\n            encounter.encounter_id,\n            morte.actor_id,\n            position=(player_position[0] + 3.0, player_position[1] + 1.2),\n        )\n        self.runtime.add_encounter_participant(\n            encounter.encounter_id,\n            joe.actor_id,\n            position=(player_position[0] + 3.2, player_position[1] - 1.2),\n        )\n        self.runtime._append(encounter, "morte_joe_ambush", morte.actor_id, cylon.actor_id, joe_actor_id=joe.actor_id)\n        cylon.hp = 0\n        cylon.alive = False\n        self.runtime._resolve_defeat(encounter, cylon, morte.actor_id)\n        cache = self._drop_cylon_inventory(cylon)\n        for status in self.runtime.actors[actor_id].statuses:\n            if status.stack_key == "scripted_cylon_paralysis":\n                status.remaining_ms = min(status.remaining_ms, POST_CYLON_DEATH_PARALYSIS_MS)\n                status.until_next_tick_ms = min(status.until_next_tick_ms, status.remaining_ms)\n        state.update(\n            stage="ambush_cylon_dead",\n            morte_actor_id=morte.actor_id,\n            joe_actor_id=joe.actor_id,\n            ground_cache_actor_id=cache.actor_id,\n            cylon_killed_at_ms=self.runtime.world.now_ms,\n        )\n        return self.status(actor_id)\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''    def advance_to_paralysis_release(self, actor_id: str) -> dict:\n        state = self._state(actor_id)\n        if state["stage"] != "poison_cloud_deployed":\n            raise ValueError("the poison-cloud diversion has not been created")\n        actor = self.runtime.actors[actor_id]\n        remaining = max(\n            (status.remaining_ms for status in actor.statuses if status.stack_key == "scripted_cylon_paralysis"),\n            default=0,\n        )\n        if remaining:\n            self.runtime.advance_encounter(state["transport_encounter_id"], remaining)\n        actor.metadata.pop("scripted_capture", None)\n        state["stage"] = "morte_joe_pvp_active"\n        return self.status(actor_id)\n''',
    '''    def _discover_paralysis_release_events(self) -> list[str]:\n        ready: list[str] = []\n        for actor_id, state in self._states().items():\n            if state["stage"] != "poison_cloud_deployed":\n                continue\n            actor = self.runtime.actors[actor_id]\n            still_paralysed = any(\n                status.stack_key == "scripted_cylon_paralysis" and status.remaining_ms > 0\n                for status in actor.statuses\n            )\n            if not still_paralysed:\n                ready.append(f"{PARALYSIS_RELEASE_EVENT_RULE_ID}:{actor_id}")\n        return ready\n\n    def _resolve_paralysis_release_event(self, occurrence_id: str) -> dict:\n        actor_id = self._event_actor_id(occurrence_id, PARALYSIS_RELEASE_EVENT_RULE_ID)\n        state = self._state(actor_id)\n        if state["stage"] != "poison_cloud_deployed":\n            raise RuntimeError("paralysis-release event resolved outside the poison-cloud stage")\n        actor = self.runtime.actors[actor_id]\n        if any(\n            status.stack_key == "scripted_cylon_paralysis" and status.remaining_ms > 0\n            for status in actor.statuses\n        ):\n            raise RuntimeError("paralysis-release event resolved while paralysis is still active")\n        actor.metadata.pop("scripted_capture", None)\n        state["stage"] = "morte_joe_pvp_active"\n        state["paralysis_released_at_ms"] = self.runtime.world.now_ms\n        return {\n            "actor_id": actor_id,\n            "encounter_id": state["transport_encounter_id"],\n            "paralysis_released_at_ms": state["paralysis_released_at_ms"],\n        }\n\n    def wait_for_paralysis_release(self, actor_id: str) -> dict:\n        state = self._state(actor_id)\n        if state["stage"] != "poison_cloud_deployed":\n            raise ValueError("the poison-cloud diversion has not been created")\n        actor = self.runtime.actors[actor_id]\n        remaining = max(\n            (status.remaining_ms for status in actor.statuses if status.stack_key == "scripted_cylon_paralysis"),\n            default=0,\n        )\n        if remaining:\n            self.runtime.advance_encounter(state["transport_encounter_id"], remaining)\n        else:\n            self.runtime.evaluate_world_events()\n        occurrence_id = f"{PARALYSIS_RELEASE_EVENT_RULE_ID}:{actor_id}"\n        if occurrence_id not in self.runtime.world_events.occurrences:\n            raise RuntimeError("paralysis elapsed but the world event did not resolve")\n        return self.status(actor_id)\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''    def resolve_ambusher_retreat(self, actor_id: str) -> dict:\n        state = self._state(actor_id)\n        if state["stage"] != "morte_joe_pvp_active":\n            raise ValueError("Morte/Joe retreat can only resolve after the paralysis handoff to ordinary PvP")\n        encounter = self.runtime.encounters[state["transport_encounter_id"]]\n        hostiles = [self.runtime.actors[hostile_id] for hostile_id in self._ambusher_ids(state)]\n        trigger = any(not hostile.alive for hostile in hostiles) or any(\n            hostile.alive and hostile.max_hp > 0 and hostile.hp / hostile.max_hp <= AMBUSH_RETREAT_HP_RATIO\n            for hostile in hostiles\n        )\n        if not trigger:\n            raise ValueError("the ambushers have not yet reached the simulation retreat condition")\n\n        retreating = [hostile for hostile in hostiles if hostile.alive and not hostile.metadata.get("retreated")]\n        route = None\n        if retreating:\n            movement = exit_encounter_via_travel(\n                self.runtime,\n                encounter.encounter_id,\n                [hostile.actor_id for hostile in retreating],\n                FIELD,\n            )\n            route = group_travel_record(movement)\n        retreated_ids: list[str] = []\n        for hostile in retreating:\n            hostile.metadata["retreated"] = True\n            hostile.metadata["retreated_from_floor6_ambush_at_ms"] = self.runtime.world.now_ms\n            retreated_ids.append(hostile.actor_id)\n            self.runtime._append(\n                encounter,\n                "ambusher_retreated",\n                hostile.actor_id,\n                actor_id,\n                hp=hostile.hp,\n                max_hp=hostile.max_hp,\n                retreat_threshold_ratio=AMBUSH_RETREAT_HP_RATIO,\n                destination_id=FIELD,\n            )\n\n        if not self._ambushers_neutralized(state):\n            raise RuntimeError("ambush retreat did not clear every living hostile")\n        state["stage"] = "ambushers_neutralized_ground_loot"\n        state["ambushers_retreated_at_ms"] = self.runtime.world.now_ms\n        state["ambusher_retreat_ids"] = retreated_ids\n        state["ambusher_retreat_route"] = route\n        return self.status(actor_id)\n''',
    '''    def _discover_ambusher_retreat_events(self) -> list[str]:\n        ready: list[str] = []\n        for actor_id, state in self._states().items():\n            if state["stage"] != "morte_joe_pvp_active":\n                continue\n            hostiles = [self.runtime.actors[hostile_id] for hostile_id in self._ambusher_ids(state)]\n            if not hostiles:\n                continue\n            trigger = any(not hostile.alive for hostile in hostiles) or any(\n                hostile.alive and hostile.max_hp > 0 and hostile.hp / hostile.max_hp <= AMBUSH_RETREAT_HP_RATIO\n                for hostile in hostiles\n            )\n            if trigger:\n                ready.append(f"{AMBUSHER_RETREAT_EVENT_RULE_ID}:{actor_id}")\n        return ready\n\n    def _resolve_ambusher_retreat_event(self, occurrence_id: str) -> dict:\n        actor_id = self._event_actor_id(occurrence_id, AMBUSHER_RETREAT_EVENT_RULE_ID)\n        state = self._resolve_ambusher_retreat(actor_id)\n        return {\n            "actor_id": actor_id,\n            "encounter_id": state["transport_encounter_id"],\n            "retreated_actor_ids": list(state.get("ambusher_retreat_ids", [])),\n            "stage": state["stage"],\n        }\n\n    def _resolve_ambusher_retreat(self, actor_id: str) -> dict:\n        state = self._state(actor_id)\n        if state["stage"] != "morte_joe_pvp_active":\n            raise ValueError("Morte/Joe retreat can only resolve after the paralysis handoff to ordinary PvP")\n        encounter = self.runtime.encounters[state["transport_encounter_id"]]\n        hostiles = [self.runtime.actors[hostile_id] for hostile_id in self._ambusher_ids(state)]\n        trigger = any(not hostile.alive for hostile in hostiles) or any(\n            hostile.alive and hostile.max_hp > 0 and hostile.hp / hostile.max_hp <= AMBUSH_RETREAT_HP_RATIO\n            for hostile in hostiles\n        )\n        if not trigger:\n            raise ValueError("the ambushers have not yet reached the simulation retreat condition")\n\n        retreating = [hostile for hostile in hostiles if hostile.alive and not hostile.metadata.get("retreated")]\n        route = None\n        if retreating:\n            movement = exit_encounter_via_travel(\n                self.runtime,\n                encounter.encounter_id,\n                [hostile.actor_id for hostile in retreating],\n                FIELD,\n            )\n            route = group_travel_record(movement)\n        retreated_ids: list[str] = []\n        for hostile in retreating:\n            hostile.metadata["retreated"] = True\n            hostile.metadata["retreated_from_floor6_ambush_at_ms"] = self.runtime.world.now_ms\n            retreated_ids.append(hostile.actor_id)\n            self.runtime._append(\n                encounter,\n                "ambusher_retreated",\n                hostile.actor_id,\n                actor_id,\n                hp=hostile.hp,\n                max_hp=hostile.max_hp,\n                retreat_threshold_ratio=AMBUSH_RETREAT_HP_RATIO,\n                destination_id=FIELD,\n            )\n\n        if not self._ambushers_neutralized(state):\n            raise RuntimeError("ambush retreat did not clear every living hostile")\n        state["stage"] = "ambushers_neutralized_ground_loot"\n        state["ambushers_retreated_at_ms"] = self.runtime.world.now_ms\n        state["ambusher_retreat_ids"] = retreated_ids\n        state["ambusher_retreat_route"] = route\n        return self.status(actor_id)\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''    def recover_cylon_ground_loot(self, actor_id: str) -> dict:\n        state = self._state(actor_id)\n        if state["stage"] == "morte_joe_pvp_active" and self._ambushers_neutralized(state):\n            state["stage"] = "ambushers_neutralized_ground_loot"\n        if state["stage"] != "ambushers_neutralized_ground_loot":\n''',
    '''    def recover_cylon_ground_loot(self, actor_id: str) -> dict:\n        state = self._state(actor_id)\n        if state["stage"] != "ambushers_neutralized_ground_loot":\n''',
)

# Remove manual Stachion event triggers; keep only the explicit wait helper for passage of time.
replace_once(
    "src/sao_mcp/server_floor6.py",
    '''    @mcp.tool()\n    def trigger_floor6_morte_joe_ambush(actor_id: str) -> str:\n        """Start the carriage ambush: Morte kills Cylon and his key/jar/mask valuables become real ground-loot instances."""\n        return _json(stachion.trigger_morte_joe_ambush(actor_id))\n\n''',
    '''''',
)
replace_once(
    "src/sao_mcp/server_floor6.py",
    '''    @mcp.tool()\n    def advance_floor6_to_paralysis_release(actor_id: str) -> str:\n        """Advance the remaining scripted paralysis after the poison-cloud diversion, returning the scene to ordinary PvP rules."""\n        return _json(stachion.advance_to_paralysis_release(actor_id))\n\n''',
    '''    @mcp.tool()\n    def wait_floor6_for_paralysis_release(actor_id: str) -> str:\n        """Pass the remaining paralysis time; the actual release and PvP handoff are resolved by the world-event runtime."""\n        return _json(stachion.wait_for_paralysis_release(actor_id))\n\n''',
)
replace_once(
    "src/sao_mcp/server_floor6.py",
    '''    @mcp.tool()\n    def resolve_floor6_ambusher_retreat(actor_id: str) -> str:\n        """After ordinary PvP begins, let living ambushers retreat once one is defeated or the simulation low-HP retreat condition is reached."""\n        return _json(stachion.resolve_ambusher_retreat(actor_id))\n\n''',
    '''''',
)

# -------------------- Existing integration tests --------------------
replace_once(
    "tests/test_floor6_irrational_cube.py",
    '''    # Generic combat reaches the last pixel; the finale mechanic decides what happens next.\n    boss.hp = 1\n    boss.alive = True\n    betrayal = buxum_scene.trigger_betrayal(state["instance_id"])\n    buxum = runtime.actors[betrayal["buxum_actor_id"]]\n''',
    '''    # Generic combat reaches the last pixel; the world event, not a GM trigger, resolves Buxum's move.\n    boss.hp = 1\n    boss.alive = True\n    resolved = runtime.evaluate_world_events()\n    assert [row.rule_id for row in resolved] == ["floor6.buxum_betrayal"]\n    betrayal = buxum_scene.status(state["instance_id"])\n    buxum = runtime.actors[betrayal["buxum_actor_id"]]\n''',
)
replace_once(
    "tests/test_floor6_irrational_cube.py",
    '''    buxum.hp = max(1, int(buxum.max_hp * 0.20))\n    buxum.alive = True\n    retreat = buxum_scene.resolve_buxum_retreat(state["instance_id"])\n    assert retreat["stage"] == "golden_cube_dropped"\n''',
    '''    buxum.hp = max(1, int(buxum.max_hp * 0.20))\n    buxum.alive = True\n    resolved = runtime.evaluate_world_events()\n    assert [row.rule_id for row in resolved] == ["floor6.buxum_retreat"]\n    retreat = buxum_scene.status(state["instance_id"])\n    assert retreat["stage"] == "golden_cube_dropped"\n''',
)
replace_once(
    "tests/test_floor6_stachion.py",
    '''    stachion.advance_transport_to_ambush_site(player.actor_id)\n    state = stachion.trigger_morte_joe_ambush(player.actor_id)\n    morte = runtime.actors[state["morte_actor_id"]]\n''',
    '''    state = stachion.advance_transport_to_ambush_site(player.actor_id)\n    assert state["stage"] == "ambush_cylon_dead"\n    assert runtime.world_event_state(\n        f"floor6.morte_joe_ambush:{player.actor_id}"\n    )["status"] == "resolved"\n    morte = runtime.actors[state["morte_actor_id"]]\n''',
)
replace_once(
    "tests/test_floor6_stachion.py",
    '''    state = stachion.advance_to_paralysis_release(player.actor_id)\n    assert state["stage"] == "morte_joe_pvp_active"\n''',
    '''    state = stachion.wait_for_paralysis_release(player.actor_id)\n    assert state["stage"] == "morte_joe_pvp_active"\n    assert runtime.world_event_state(\n        f"floor6.paralysis_release:{player.actor_id}"\n    )["status"] == "resolved"\n''',
)
replace_once(
    "tests/test_floor6_stachion.py",
    '''    morte.hp = max(1, int(morte.max_hp * 0.20))\n    morte.alive = True\n    state = stachion.resolve_ambusher_retreat(player.actor_id)\n    assert state["ambushers_neutralized"]\n''',
    '''    morte.hp = max(1, int(morte.max_hp * 0.20))\n    morte.alive = True\n    runtime.evaluate_world_events()\n    state = stachion.status(player.actor_id)\n    assert state["ambushers_neutralized"]\n    assert runtime.world_event_state(\n        f"floor6.ambusher_retreat:{player.actor_id}"\n    )["status"] == "resolved"\n''',
)

Path("tests/test_world_event_authority.py").write_text(
    '''from pathlib import Path

from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor6_buxum import (
    BUXUM_BETRAYAL_EVENT_RULE_ID,
    BUXUM_RETREAT_EVENT_RULE_ID,
    Floor6BuxumScenario,
    install_floor6_buxum_scenario,
)
from sao_mcp.scenarios.floor6_irrational_cube import install_floor6_irrational_cube_scenario
from sao_mcp.scenarios.floor6_stachion import (
    AMBUSHER_RETREAT_EVENT_RULE_ID,
    MORTE_JOE_AMBUSH_EVENT_RULE_ID,
    PARALYSIS_RELEASE_EVENT_RULE_ID,
    Floor6StachionScenario,
    install_floor6_stachion_scenario,
)


ROOT = Path(__file__).resolve().parents[1]


def test_floor6_conditional_scene_transitions_are_registered_world_event_rules():
    runtime = HousingAincradRuntime(seed=811)
    cube = install_floor6_irrational_cube_scenario(runtime)
    install_floor6_buxum_scenario(runtime, cube)
    install_floor6_stachion_scenario(runtime)

    assert set(runtime.world_event_rules).issuperset(
        {
            BUXUM_BETRAYAL_EVENT_RULE_ID,
            BUXUM_RETREAT_EVENT_RULE_ID,
            MORTE_JOE_AMBUSH_EVENT_RULE_ID,
            PARALYSIS_RELEASE_EVENT_RULE_ID,
            AMBUSHER_RETREAT_EVENT_RULE_ID,
        }
    )


def test_migrated_conditional_events_have_no_public_manual_scenario_trigger_methods():
    assert not hasattr(Floor6BuxumScenario, "trigger_betrayal")
    assert not hasattr(Floor6BuxumScenario, "resolve_buxum_retreat")
    assert not hasattr(Floor6StachionScenario, "trigger_morte_joe_ambush")
    assert not hasattr(Floor6StachionScenario, "advance_to_paralysis_release")
    assert not hasattr(Floor6StachionScenario, "resolve_ambusher_retreat")
    assert hasattr(Floor6StachionScenario, "wait_for_paralysis_release")


def test_migrated_conditional_events_are_not_exposed_as_manual_mcp_tools():
    floor6 = (ROOT / "src/sao_mcp/server_floor6.py").read_text(encoding="utf-8")
    buxum = (ROOT / "src/sao_mcp/server_floor6_buxum.py").read_text(encoding="utf-8")
    forbidden = (
        "trigger_floor6_morte_joe_ambush",
        "advance_floor6_to_paralysis_release",
        "resolve_floor6_ambusher_retreat",
        "trigger_floor6_buxum_betrayal",
        "resolve_floor6_buxum_retreat",
    )
    joined = floor6 + "\\n" + buxum
    assert all(name not in joined for name in forbidden)
    assert "wait_floor6_for_paralysis_release" in floor6
''',
    encoding="utf-8",
)
