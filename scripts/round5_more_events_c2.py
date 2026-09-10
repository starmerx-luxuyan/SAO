from __future__ import annotations

from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    write(path, text.replace(old, new, 1))


def method_bounds(text: str, method_name: str) -> tuple[int, int]:
    marker = f"    def {method_name}("
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"method {method_name} not found")
    decorator_start = text.rfind("\n    @", 0, start)
    previous_method = text.rfind("\n    def ", 0, start)
    if decorator_start > previous_method:
        start = decorator_start + 1
    end = text.find("\n    def ", start + 1)
    next_decorator = text.find("\n    @", start + 1)
    candidates = [value for value in (end, next_decorator) if value >= 0]
    end = min(candidates) if candidates else len(text)
    return start, end


def replace_method(path: str, method_name: str, new_block: str) -> None:
    text = read(path)
    start, end = method_bounds(text, method_name)
    write(path, text[:start] + new_block.rstrip() + "\n" + text[end:])


def insert_before_method(path: str, method_name: str, block: str) -> None:
    text = read(path)
    start, _ = method_bounds(text, method_name)
    write(path, text[:start] + block.rstrip() + "\n\n" + text[start:])


# Player-side defeat events wait through SAO's revival End Phase. Evaluate once more after expired
# deaths are finalized so permanent-death conditions become observable without a GM resolve call.
replace_once(
    "src/sao_mcp/runtime/world_event_runtime.py",
    '''    def travel_actor(self, actor_id: str, destination_id: str):\n''',
    '''    def _finalize_expired_deaths(self, encounter) -> None:\n        super()._finalize_expired_deaths(encounter)\n        self.evaluate_world_events()\n\n    def travel_actor(self, actor_id: str, destination_id: str):\n''',
)

# -------------------- Floor 6 Elf War: Castle assault + immediate Kysarah theft --------------------
replace_once(
    "src/sao_mcp/scenarios/floor6_elfwar.py",
    '''KYSARAH_KNOCKBACK_MS = 1500\n''',
    '''KYSARAH_KNOCKBACK_MS = 1500\nCASTLE_GALEY_ATTACK_EVENT_RULE_ID = "floor6.castle_galey_attack"\nKYSARAH_KEY_THEFT_EVENT_RULE_ID = "floor6.kysarah_key_theft"\n''',
)
replace_method(
    "src/sao_mcp/scenarios/floor6_elfwar.py",
    "__init__",
    '''    def __init__(self, runtime) -> None:\n        self.runtime = runtime\n        runtime.register_world_event_rule(\n            CASTLE_GALEY_ATTACK_EVENT_RULE_ID,\n            self._discover_castle_galey_attack_events,\n            self._resolve_castle_galey_attack_event,\n        )\n        runtime.register_world_event_rule(\n            KYSARAH_KEY_THEFT_EVENT_RULE_ID,\n            self._discover_kysarah_key_theft_events,\n            self._resolve_kysarah_key_theft_event,\n        )\n        runtime.evaluate_world_events()''',
)
insert_before_method(
    "src/sao_mcp/scenarios/floor6_elfwar.py",
    "_create_gindo_actor",
    '''    @staticmethod\n    def _event_actor_id(occurrence_id: str, rule_id: str) -> str:\n        prefix = f"{rule_id}:"\n        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):\n            raise RuntimeError(f"invalid {rule_id} occurrence id: {occurrence_id}")\n        return occurrence_id[len(prefix):]\n\n    def _discover_castle_galey_attack_events(self) -> list[str]:\n        states = self.runtime.world.global_flags.get("floor6_elfwar_states", {})\n        ready: list[str] = []\n        for actor_id, state in states.items():\n            actor = self.runtime.actors.get(actor_id)\n            if (\n                state["stage"] == "castle_galey_attack_pending"\n                and actor is not None\n                and actor.alive\n                and actor.location_id == CASTLE_GALEY\n            ):\n                ready.append(f"{CASTLE_GALEY_ATTACK_EVENT_RULE_ID}:{actor_id}")\n        return ready\n\n    def _resolve_castle_galey_attack_event(self, occurrence_id: str) -> dict:\n        actor_id = self._event_actor_id(occurrence_id, CASTLE_GALEY_ATTACK_EVENT_RULE_ID)\n        state = self._trigger_castle_galey_attack(actor_id)\n        return {\n            "actor_id": actor_id,\n            "gindo_actor_id": state["gindo_actor_id"],\n            "stage": state["stage"],\n            "spirit_tree_poisoned": state["spirit_tree_poisoned"],\n        }\n\n    def _discover_kysarah_key_theft_events(self) -> list[str]:\n        states = self.runtime.world.global_flags.get("floor6_elfwar_states", {})\n        stachion_states = self.runtime.world.global_flags.get("floor6_stachion_quest_states", {})\n        ready: list[str] = []\n        for actor_id, state in states.items():\n            if state["stage"] != "qusack_released_kysarah_pending":\n                continue\n            actor = self.runtime.actors.get(actor_id)\n            if actor is None or not actor.alive or actor.location_id != QUSACK_RESCUE_CAVE:\n                continue\n            bag_id = state.get("sacred_key_bag_instance_id")\n            if not bag_id or bag_id not in actor.inventory:\n                continue\n            if actor.inventory[bag_id].template_id != SACRED_KEY_BAG_ID:\n                raise RuntimeError("Floor 6 sacred-key bag state points to the wrong item template")\n            if not any(item.template_id == IRON_KEY_ID for item in actor.inventory.values()):\n                continue\n            stachion_state = stachion_states.get(actor_id)\n            if stachion_state is None or stachion_state.get("myia_met_at_ms") is None:\n                continue\n            myia_id = stachion_state.get("myia_actor_id")\n            myia = self.runtime.actors.get(myia_id) if myia_id else None\n            if myia is None or not myia.alive:\n                continue\n            if not any(item.template_id == THEANO_IRON_KEY_ID for item in myia.inventory.values()):\n                continue\n            if any(\n                not state.get(key) or state[key] not in self.runtime.actors\n                for key in ("gindo_actor_id", "kizmel_actor_id")\n            ):\n                continue\n            ready.append(f"{KYSARAH_KEY_THEFT_EVENT_RULE_ID}:{actor_id}")\n        return ready\n\n    def _resolve_kysarah_key_theft_event(self, occurrence_id: str) -> dict:\n        actor_id = self._event_actor_id(occurrence_id, KYSARAH_KEY_THEFT_EVENT_RULE_ID)\n        state = self._trigger_kysarah_key_theft(actor_id)\n        return {\n            "actor_id": actor_id,\n            "kysarah_actor_id": state["kysarah_actor_id"],\n            "combined_iron_key_instance_id": state["combined_iron_key_instance_id"],\n            "stage": state["stage"],\n        }''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_elfwar.py",
    '''    def trigger_castle_galey_attack(self, actor_id: str) -> dict:\n''',
    '''    def _trigger_castle_galey_attack(self, actor_id: str) -> dict:\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_elfwar.py",
    '''    def trigger_kysarah_key_theft(self, actor_id: str) -> dict:\n''',
    '''    def _trigger_kysarah_key_theft(self, actor_id: str) -> dict:\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_elfwar.py",
    '''        state["stage"] = "qusack_released_kysarah_pending"\n        state["qusack_hostages_released"] = True\n        return self.status(actor_id)\n''',
    '''        state["stage"] = "qusack_released_kysarah_pending"\n        state["qusack_hostages_released"] = True\n        self.runtime.evaluate_world_events()\n        return self.status(actor_id)\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_elfwar.py",
    '''    return Floor6ElfWarScenario(runtime)\n''',
    '''    service = runtime.install_world_event_service(\n        "floor6.elfwar", lambda: Floor6ElfWarScenario(runtime)\n    )\n    if not isinstance(service, Floor6ElfWarScenario):\n        raise RuntimeError("floor6.elfwar service registry contains the wrong service type")\n    return service\n''',
)
replace_once(
    "src/sao_mcp/server_floor6_elfwar.py",
    '''    @mcp.tool()\n    def trigger_floor6_castle_galey_attack(actor_id: str) -> str:\n        """Start the Fallen Elf assault and Gindo's coerced poisoning of Castle Galey's spirit-tree spring."""\n        return _json(elfwar.trigger_castle_galey_attack(actor_id))\n\n''',
    "",
)
replace_once(
    "src/sao_mcp/server_floor6_elfwar.py",
    '''    @mcp.tool()\n    def trigger_floor6_kysarah_key_theft(actor_id: str) -> str:\n        """Run Kysarah's Tsumujiguruma theft: she takes the sacred-key bag and crushes Cylon's/Theano's repelling iron keys into one real Combined Iron Key instance."""\n        return _json(elfwar.trigger_kysarah_key_theft(actor_id))\n\n''',
    "",
)

# -------------------- Floor 8 cave-mouth combat outcome --------------------
replace_once(
    "src/sao_mcp/scenarios/floor8_standoff.py",
    '''FOREST_ELF_CUSTODY_RESTRICTION = "forest_elf_custody"\n''',
    '''FOREST_ELF_CUSTODY_RESTRICTION = "forest_elf_custody"\nCAVE_MOUTH_COMBAT_EVENT_RULE_ID = "floor8.cave_mouth_combat_resolution"\n''',
)
replace_method(
    "src/sao_mcp/scenarios/floor8_standoff.py",
    "__init__",
    '''    def __init__(self, runtime, emergency) -> None:\n        if emergency.runtime is not runtime:\n            raise RuntimeError("Floor 8 standoff and emergency services must share one runtime")\n        self.runtime = runtime\n        self.emergency = emergency\n        runtime.register_world_event_rule(\n            CAVE_MOUTH_COMBAT_EVENT_RULE_ID,\n            self._discover_cave_mouth_combat_events,\n            self._resolve_cave_mouth_combat_event,\n        )\n        runtime.evaluate_world_events()''',
)
insert_before_method(
    "src/sao_mcp/scenarios/floor8_standoff.py",
    "resolve_cave_mouth_combat",
    '''    @staticmethod\n    def _combat_event_instance_id(occurrence_id: str) -> str:\n        prefix = f"{CAVE_MOUTH_COMBAT_EVENT_RULE_ID}:"\n        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):\n            raise RuntimeError(f"invalid cave-mouth combat occurrence id: {occurrence_id}")\n        return occurrence_id[len(prefix):]\n\n    def _discover_cave_mouth_combat_events(self) -> list[str]:\n        states = self.runtime.world.global_flags.get("floor8_forest_emergency_instances", {})\n        ready: list[str] = []\n        for instance_id, state in states.items():\n            if state["stage"] != "cave_mouth_combat":\n                continue\n            forest = [self.runtime.actors[actor_id] for actor_id in self._forest_ids(state)]\n            players = [self.runtime.actors[actor_id] for actor_id in state["cave_combat_player_ids"]]\n            forest_defeated = bool(forest) and all(\n                not actor.alive\n                and actor.hp <= 0\n                and actor.metadata.get("defeat_resolved") is True\n                for actor in forest\n            )\n            player_defeated = bool(players) and all(\n                not actor.alive\n                and actor.hp <= 0\n                and actor.metadata.get("death_state") == "permanent"\n                for actor in players\n            )\n            if forest_defeated or player_defeated:\n                ready.append(f"{CAVE_MOUTH_COMBAT_EVENT_RULE_ID}:{instance_id}")\n        return ready\n\n    def _resolve_cave_mouth_combat_event(self, occurrence_id: str) -> dict:\n        instance_id = self._combat_event_instance_id(occurrence_id)\n        state = self._resolve_cave_mouth_combat(instance_id)\n        return {\n            "instance_id": instance_id,\n            "outcome": state["cave_combat_outcome"],\n            "stage": state["stage"],\n        }''',
)
replace_method(
    "src/sao_mcp/scenarios/floor8_standoff.py",
    "resolve_cave_mouth_combat",
    '''    def _resolve_cave_mouth_combat(self, instance_id: str) -> dict:\n        state = self._state(instance_id)\n        if state["stage"] != "cave_mouth_combat":\n            raise ValueError("there is no active cave-mouth combat branch to resolve")\n        encounter = self.runtime.encounters[state["cave_combat_encounter_id"]]\n        forest = [self.runtime.actors[actor_id] for actor_id in self._forest_ids(state)]\n        players = [self.runtime.actors[actor_id] for actor_id in state["cave_combat_player_ids"]]\n        forest_defeated = bool(forest) and all(\n            not actor.alive\n            and actor.hp <= 0\n            and actor.metadata.get("defeat_resolved") is True\n            for actor in forest\n        )\n        player_defeated = bool(players) and all(\n            not actor.alive\n            and actor.hp <= 0\n            and actor.metadata.get("death_state") == "permanent"\n            for actor in players\n        )\n        if forest_defeated:\n            state["cave_combat_outcome"] = "forest_elf_pursuit_party_defeated"\n            state["cave_combat_resolved_at_ms"] = self.runtime.world.now_ms\n            state["stage"] = "standoff_resolved_forest_elves_defeated"\n            if encounter.active:\n                self.runtime.end_encounter(encounter.encounter_id, reason="forest_elf_pursuit_party_defeated")\n            return self.status(instance_id)\n        if player_defeated:\n            state["cave_combat_outcome"] = "selected_player_combatants_defeated"\n            state["cave_combat_resolved_at_ms"] = self.runtime.world.now_ms\n            state["stage"] = "cave_mouth_combat_player_side_defeated"\n            if encounter.active:\n                self.runtime.end_encounter(encounter.encounter_id, reason="selected_player_combatants_defeated")\n            return self.status(instance_id)\n        raise ValueError("the cave-mouth encounter still has an unresolved living or revivable side")''',
)
replace_once(
    "src/sao_mcp/scenarios/floor8_standoff.py",
    '''        elif stage == "cave_mouth_combat":\n            actions = ["ordinary_combat", "resolve_cave_mouth_combat"]\n''',
    '''        elif stage == "cave_mouth_combat":\n            actions = ["ordinary_combat"]\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor8_standoff.py",
    '''    return Floor8CaveStandoffScenario(runtime, emergency)\n''',
    '''    service = runtime.install_world_event_service(\n        "floor8.cave_standoff", lambda: Floor8CaveStandoffScenario(runtime, emergency)\n    )\n    if not isinstance(service, Floor8CaveStandoffScenario):\n        raise RuntimeError("floor8.cave_standoff service registry contains the wrong service type")\n    if service.emergency is not emergency:\n        raise RuntimeError("floor8.cave_standoff is already bound to a different emergency service")\n    return service\n''',
)
replace_once(
    "src/sao_mcp/server_floor8.py",
    '''    @mcp.tool()\n    def resolve_progressive9_cave_mouth_combat(instance_id: str) -> str:\n        """After ordinary combat, resolve the local encounter only when the real Forest Elf pursuit party or all selected player combatants are actually defeated."""\n        return _json(standoff.resolve_cave_mouth_combat(instance_id))\n\n''',
    "",
)

# -------------------- Floor 8 Sluva sentence expiry --------------------
replace_once(
    "src/sao_mcp/scenarios/floor8_sluva.py",
    '''RESTORATIVE_SERVICE_MS = 2 * 60 * 60_000\n''',
    '''RESTORATIVE_SERVICE_MS = 2 * 60 * 60_000\nSLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID = "floor8.sluva_imprisonment_complete"\n''',
)
replace_method(
    "src/sao_mcp/scenarios/floor8_sluva.py",
    "__init__",
    '''    def __init__(self, runtime, emergency) -> None:\n        if emergency.runtime is not runtime:\n            raise RuntimeError("Sluva justice and Floor 8 emergency services must share one runtime")\n        self.runtime = runtime\n        self.emergency = emergency\n        runtime.register_world_event_rule(\n            SLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID,\n            self._discover_imprisonment_completion_events,\n            self._resolve_imprisonment_completion_event,\n        )\n        runtime.evaluate_world_events()''',
)
insert_before_method(
    "src/sao_mcp/scenarios/floor8_sluva.py",
    "complete_imprisonment_enforcement",
    '''    @staticmethod\n    def _sentence_event_instance_id(occurrence_id: str) -> str:\n        prefix = f"{SLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID}:"\n        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):\n            raise RuntimeError(f"invalid Sluva imprisonment occurrence id: {occurrence_id}")\n        return occurrence_id[len(prefix):]\n\n    def _discover_imprisonment_completion_events(self) -> list[str]:\n        states = self.runtime.world.global_flags.get("floor8_forest_emergency_instances", {})\n        ready: list[str] = []\n        for instance_id, state in states.items():\n            if state["stage"] != "sluva_sentence_enforcement_active":\n                continue\n            docket = state["sluva_justice"]\n            enforcement = docket["sentence_enforcement"]\n            expected_ids = list(enforcement["imprisonment_actor_ids"])\n            if not expected_ids:\n                raise RuntimeError("active Sluva sentence enforcement has no imprisonment actors")\n            release_times: list[int] = []\n            for actor_id in expected_ids:\n                sentence = self.runtime.legal.sentence_for(actor_id)\n                if (\n                    sentence is None\n                    or sentence.case_id != docket["case_id"]\n                    or sentence.kind is not SentenceKind.IMPRISONMENT\n                    or sentence.status is not SentenceStatus.ACTIVE\n                    or sentence.release_at_ms is None\n                ):\n                    raise RuntimeError(\n                        f"active Sluva docket disagrees with authoritative sentence state for {actor_id}"\n                    )\n                release_times.append(int(sentence.release_at_ms))\n            if self.runtime.world.now_ms >= max(release_times):\n                ready.append(f"{SLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID}:{instance_id}")\n        return ready\n\n    def _resolve_imprisonment_completion_event(self, occurrence_id: str) -> dict:\n        instance_id = self._sentence_event_instance_id(occurrence_id)\n        state = self._complete_imprisonment_enforcement(instance_id)\n        return {\n            "instance_id": instance_id,\n            "stage": state["stage"],\n            "completed_at_ms": state["sluva_justice"]["sentence_enforcement"][\n                "imprisonment_completed_at_ms"\n            ],\n        }''',
)
replace_method(
    "src/sao_mcp/scenarios/floor8_sluva.py",
    "complete_imprisonment_enforcement",
    '''    def _complete_imprisonment_enforcement(self, instance_id: str) -> dict:\n        state = self._state(instance_id)\n        if state["stage"] != "sluva_sentence_enforcement_active":\n            raise ValueError("there is no active Sluva imprisonment term to complete")\n        docket = state["sluva_justice"]\n        enforcement = docket["sentence_enforcement"]\n        imprisonment_actor_ids = list(enforcement["imprisonment_actor_ids"])\n        release_times: list[int] = []\n        for actor_id in imprisonment_actor_ids:\n            sentence = self.runtime.legal.sentence_for(actor_id)\n            if (\n                sentence is None\n                or sentence.case_id != docket["case_id"]\n                or sentence.kind is not SentenceKind.IMPRISONMENT\n                or sentence.status is not SentenceStatus.ACTIVE\n                or sentence.release_at_ms is None\n            ):\n                raise RuntimeError(\n                    f"active Sluva docket disagrees with authoritative sentence state for {actor_id}"\n                )\n            release_times.append(int(sentence.release_at_ms))\n        if not release_times or self.runtime.world.now_ms < max(release_times):\n            raise ValueError("the active imprisonment term has not reached its release time")\n        self._require_ids_at(imprisonment_actor_ids, SLUVA)\n        self._require_custody(imprisonment_actor_ids)\n        for actor_id in imprisonment_actor_ids:\n            self.runtime.complete_imprisonment_sentence(\n                actor_id, resolution="sluva_imprisonment_completed"\n            )\n\n        enforcement["status"] = "imprisonment_completed"\n        enforcement["imprisonment_completed_at_ms"] = self.runtime.world.now_ms\n        if enforcement["execution_order_actor_ids"]:\n            docket["status"] = "imprisonment_completed_execution_pending"\n            state["stage"] = "sluva_imprisonment_completed_execution_pending"\n        else:\n            docket["status"] = "sentence_enforcement_completed"\n            state["stage"] = "sluva_sentence_enforcement_completed"\n        return self.status(instance_id)''',
)
replace_once(
    "src/sao_mcp/scenarios/floor8_sluva.py",
    '''    return Floor8SluvaJusticeScenario(runtime, emergency)\n''',
    '''    service = runtime.install_world_event_service(\n        "floor8.sluva_justice", lambda: Floor8SluvaJusticeScenario(runtime, emergency)\n    )\n    if not isinstance(service, Floor8SluvaJusticeScenario):\n        raise RuntimeError("floor8.sluva_justice service registry contains the wrong service type")\n    if service.emergency is not emergency:\n        raise RuntimeError("floor8.sluva_justice is already bound to a different emergency service")\n    return service\n''',
)
replace_once(
    "src/sao_mcp/server_floor8.py",
    '''    @mcp.tool()\n    def complete_progressive9_sluva_imprisonment_enforcement(\n        instance_id: str,\n        arbiter_actor_id: str,\n    ) -> str:\n        """Complete the active local Sluva imprisonment term only after the shared world clock reaches its recorded release time. Imprisoned actors are released from custody; any strict execution order remains pending and is not auto-resolved."""\n        return _json(sluva.complete_imprisonment_enforcement(instance_id, arbiter_actor_id))\n\n''',
    "",
)

# -------------------- Integration tests --------------------
replace_once(
    "tests/test_floor6_stachion.py",
    '''    runtime.travel_actor(player.actor_id, CASTLE_GALEY)\n\n    elf_state = elfwar.trigger_castle_galey_attack(player.actor_id)\n    assert elf_state["spirit_tree_poisoned"] is True\n''',
    '''    runtime.travel_actor(player.actor_id, CASTLE_GALEY)\n\n    elf_state = elfwar.status(player.actor_id)\n    assert runtime.world_event_state(\n        f"floor6.castle_galey_attack:{player.actor_id}"\n    )["status"] == "resolved"\n    assert elf_state["spirit_tree_poisoned"] is True\n''',
)
replace_once(
    "tests/test_floor6_stachion.py",
    '''    runtime.travel_actor(player.actor_id, QUSACK_RESCUE_CAVE)\n    elfwar.start_qusack_rescue(player.actor_id)\n    elf_state = elfwar.trigger_kysarah_key_theft(player.actor_id)\n\n    assert elf_state["stage"] == "kysarah_stole_and_combined_keys"\n''',
    '''    runtime.travel_actor(player.actor_id, QUSACK_RESCUE_CAVE)\n    elf_state = elfwar.start_qusack_rescue(player.actor_id)\n    assert runtime.world_event_state(\n        f"floor6.kysarah_key_theft:{player.actor_id}"\n    )["status"] == "resolved"\n\n    assert elf_state["stage"] == "kysarah_stole_and_combined_keys"\n''',
)
replace_once(
    "tests/test_floor8_standoff.py",
    '''    resolved = standoff.resolve_cave_mouth_combat(instance_id)\n    assert resolved["stage"] == "standoff_resolved_forest_elves_defeated"\n''',
    '''    resolved = standoff.status(instance_id)\n    assert runtime.world_event_state(\n        f"floor8.cave_mouth_combat_resolution:{instance_id}"\n    )["status"] == "resolved"\n    assert encounter.active is False\n    assert resolved["stage"] == "standoff_resolved_forest_elves_defeated"\n''',
)
replace_once(
    "tests/test_floor8_sluva.py",
    '''    with pytest.raises(ValueError, match="has not reached its release time"):\n        sluva.complete_imprisonment_enforcement(INSTANCE_ID, arbiter_id)\n    runtime.advance_world(term_ms - 1)\n    assert sluva.status(INSTANCE_ID)["sentence_enforcement_remaining_ms"] == 1\n    with pytest.raises(ValueError, match="has not reached its release time"):\n        sluva.complete_imprisonment_enforcement(INSTANCE_ID, arbiter_id)\n    runtime.advance_world(1)\n\n    completed = sluva.complete_imprisonment_enforcement(INSTANCE_ID, arbiter_id)\n''',
    '''    occurrence_id = f"floor8.sluva_imprisonment_complete:{INSTANCE_ID}"\n    assert occurrence_id not in runtime.world_events.occurrences\n    runtime.advance_world(term_ms - 1)\n    assert sluva.status(INSTANCE_ID)["sentence_enforcement_remaining_ms"] == 1\n    assert occurrence_id not in runtime.world_events.occurrences\n    runtime.advance_world(1)\n\n    completed = sluva.status(INSTANCE_ID)\n    assert runtime.world_event_state(occurrence_id)["status"] == "resolved"\n''',
)
replace_once(
    "tests/test_floor8_sluva.py",
    '''    runtime.advance_world(term_ms)\n    completed = sluva.complete_imprisonment_enforcement(INSTANCE_ID, arbiter_id)\n    assert completed["stage"] == "sluva_sentence_enforcement_completed"\n''',
    '''    runtime.advance_world(term_ms)\n    completed = sluva.status(INSTANCE_ID)\n    assert runtime.world_event_state(\n        f"floor8.sluva_imprisonment_complete:{INSTANCE_ID}"\n    )["status"] == "resolved"\n    assert completed["stage"] == "sluva_sentence_enforcement_completed"\n''',
)

# Rewrite the permanent authority contract to include every migrated event service and every server
# surface where a manual trigger used to exist.
Path("tests/test_world_event_authority.py").write_text(
    '''from pathlib import Path\n\nfrom sao_mcp.runtime.housing_runtime import HousingAincradRuntime\nfrom sao_mcp.scenarios.floor5_fuscus import (\n    FUSCUS_FLAG_DROP_EVENT_RULE_ID,\n    Floor5FuscusScenario,\n    install_floor5_fuscus_scenario,\n)\nfrom sao_mcp.scenarios.floor6_buxum import (\n    BUXUM_BETRAYAL_EVENT_RULE_ID,\n    BUXUM_RETREAT_EVENT_RULE_ID,\n    Floor6BuxumScenario,\n    install_floor6_buxum_scenario,\n)\nfrom sao_mcp.scenarios.floor6_elfwar import (\n    CASTLE_GALEY_ATTACK_EVENT_RULE_ID,\n    KYSARAH_KEY_THEFT_EVENT_RULE_ID,\n    Floor6ElfWarScenario,\n    install_floor6_elfwar_scenario,\n)\nfrom sao_mcp.scenarios.floor6_irrational_cube import install_floor6_irrational_cube_scenario\nfrom sao_mcp.scenarios.floor6_stachion import (\n    AMBUSHER_RETREAT_EVENT_RULE_ID,\n    MORTE_JOE_AMBUSH_EVENT_RULE_ID,\n    PARALYSIS_RELEASE_EVENT_RULE_ID,\n    Floor6StachionScenario,\n    install_floor6_stachion_scenario,\n)\nfrom sao_mcp.scenarios.floor7_pursuit import (\n    LABYRINTH_PURSUIT_EVENT_RULE_ID,\n    Floor7PursuitScenario,\n    install_floor7_pursuit_scenario,\n)\nfrom sao_mcp.scenarios.floor8_sluva import (\n    SLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID,\n    Floor8SluvaJusticeScenario,\n    install_floor8_sluva_justice_scenario,\n)\nfrom sao_mcp.scenarios.floor8_standoff import (\n    CAVE_MOUTH_COMBAT_EVENT_RULE_ID,\n    Floor8CaveStandoffScenario,\n    install_floor8_cave_standoff_scenario,\n)\n\n\nROOT = Path(__file__).resolve().parents[1]\n\n\nclass _EmergencyNoState:\n    def __init__(self, runtime):\n        self.runtime = runtime\n\n\ndef test_conditional_scene_transitions_are_registered_world_event_rules():\n    runtime = HousingAincradRuntime(seed=811)\n    cube = install_floor6_irrational_cube_scenario(runtime)\n    buxum = install_floor6_buxum_scenario(runtime, cube)\n    stachion = install_floor6_stachion_scenario(runtime)\n    fuscus = install_floor5_fuscus_scenario(runtime)\n    pursuit = install_floor7_pursuit_scenario(runtime)\n    elfwar = install_floor6_elfwar_scenario(runtime)\n    emergency = _EmergencyNoState(runtime)\n    standoff = install_floor8_cave_standoff_scenario(runtime, emergency)\n    sluva = install_floor8_sluva_justice_scenario(runtime, emergency)\n\n    assert install_floor6_buxum_scenario(runtime, cube) is buxum\n    assert install_floor6_stachion_scenario(runtime) is stachion\n    assert install_floor5_fuscus_scenario(runtime) is fuscus\n    assert install_floor7_pursuit_scenario(runtime) is pursuit\n    assert install_floor6_elfwar_scenario(runtime) is elfwar\n    assert install_floor8_cave_standoff_scenario(runtime, emergency) is standoff\n    assert install_floor8_sluva_justice_scenario(runtime, emergency) is sluva\n\n    assert set(runtime.world_event_rules).issuperset(\n        {\n            BUXUM_BETRAYAL_EVENT_RULE_ID,\n            BUXUM_RETREAT_EVENT_RULE_ID,\n            MORTE_JOE_AMBUSH_EVENT_RULE_ID,\n            PARALYSIS_RELEASE_EVENT_RULE_ID,\n            AMBUSHER_RETREAT_EVENT_RULE_ID,\n            FUSCUS_FLAG_DROP_EVENT_RULE_ID,\n            LABYRINTH_PURSUIT_EVENT_RULE_ID,\n            CASTLE_GALEY_ATTACK_EVENT_RULE_ID,\n            KYSARAH_KEY_THEFT_EVENT_RULE_ID,\n            CAVE_MOUTH_COMBAT_EVENT_RULE_ID,\n            SLUVA_IMPRISONMENT_COMPLETE_EVENT_RULE_ID,\n        }\n    )\n\n\ndef test_migrated_conditional_events_have_no_public_manual_scenario_trigger_methods():\n    assert not hasattr(Floor6BuxumScenario, "trigger_betrayal")\n    assert not hasattr(Floor6BuxumScenario, "resolve_buxum_retreat")\n    assert not hasattr(Floor6StachionScenario, "trigger_morte_joe_ambush")\n    assert not hasattr(Floor6StachionScenario, "advance_to_paralysis_release")\n    assert not hasattr(Floor6StachionScenario, "resolve_ambusher_retreat")\n    assert hasattr(Floor6StachionScenario, "wait_for_paralysis_release")\n    assert not hasattr(Floor5FuscusScenario, "resolve_hidden_flag_drop")\n    assert not hasattr(Floor7PursuitScenario, "resolve_labyrinth_pursuit")\n    assert not hasattr(Floor6ElfWarScenario, "trigger_castle_galey_attack")\n    assert not hasattr(Floor6ElfWarScenario, "trigger_kysarah_key_theft")\n    assert not hasattr(Floor8CaveStandoffScenario, "resolve_cave_mouth_combat")\n    assert not hasattr(Floor8SluvaJusticeScenario, "complete_imprisonment_enforcement")\n\n\ndef test_migrated_conditional_events_are_not_exposed_as_manual_mcp_tools():\n    server_paths = (\n        "src/sao_mcp/server_floor5.py",\n        "src/sao_mcp/server_floor6.py",\n        "src/sao_mcp/server_floor6_buxum.py",\n        "src/sao_mcp/server_floor6_elfwar.py",\n        "src/sao_mcp/server_floor7.py",\n        "src/sao_mcp/server_floor8.py",\n    )\n    joined = "\\n".join((ROOT / path).read_text(encoding="utf-8") for path in server_paths)\n    forbidden = (\n        "trigger_floor6_morte_joe_ambush",\n        "advance_floor6_to_paralysis_release",\n        "resolve_floor6_ambusher_retreat",\n        "trigger_floor6_buxum_betrayal",\n        "resolve_floor6_buxum_retreat",\n        "resolve_floor5_hidden_flag_drop",\n        "resolve_floor7_labyrinth_pursuit",\n        "trigger_floor6_castle_galey_attack",\n        "trigger_floor6_kysarah_key_theft",\n        "resolve_progressive9_cave_mouth_combat",\n        "complete_progressive9_sluva_imprisonment_enforcement",\n    )\n    assert all(name not in joined for name in forbidden)\n    assert "wait_floor6_for_paralysis_release" in joined\n''',
    encoding="utf-8",
)
