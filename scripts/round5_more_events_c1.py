from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# World-event evaluation must happen after the complete defeat transaction, not merely after
# the world-clock movement embedded inside combat resolution.
replace_once(
    "src/sao_mcp/runtime/world_event_runtime.py",
    '''    def advance_world(self, elapsed_ms: int) -> list[int]:\n        before_ms = self.world.now_ms\n        activated = super().advance_world(elapsed_ms)\n        self._emit_world_advance(before_ms)\n        return activated\n\n    def travel_actor(self, actor_id: str, destination_id: str):\n''',
    '''    def advance_world(self, elapsed_ms: int) -> list[int]:\n        before_ms = self.world.now_ms\n        activated = super().advance_world(elapsed_ms)\n        self._emit_world_advance(before_ms)\n        return activated\n\n    def _resolve_defeat(self, encounter, target, killer_id: str | None) -> None:\n        super()._resolve_defeat(encounter, target, killer_id)\n        self.evaluate_world_events()\n\n    def travel_actor(self, actor_id: str, destination_id: str):\n''',
)

# Death-based discovery must see the committed defeat marker. Low-HP / broken-weapon retreats
# remain live-actor conditions.
replace_once(
    "src/sao_mcp/scenarios/floor6_buxum.py",
    '''            if not buxum.alive or low_hp or weapon_broken:\n                ready.append(f"{BUXUM_RETREAT_EVENT_RULE_ID}:{cube_instance_id}")\n''',
    '''            defeat_committed = not buxum.alive and buxum.metadata.get("defeat_resolved") is True\n            if defeat_committed or (buxum.alive and (low_hp or weapon_broken)):\n                ready.append(f"{BUXUM_RETREAT_EVENT_RULE_ID}:{cube_instance_id}")\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''            trigger = any(not hostile.alive for hostile in hostiles) or any(\n                hostile.alive and hostile.max_hp > 0 and hostile.hp / hostile.max_hp <= AMBUSH_RETREAT_HP_RATIO\n                for hostile in hostiles\n            )\n''',
    '''            trigger = any(\n                not hostile.alive and hostile.metadata.get("defeat_resolved") is True\n                for hostile in hostiles\n            ) or any(\n                hostile.alive and hostile.max_hp > 0 and hostile.hp / hostile.max_hp <= AMBUSH_RETREAT_HP_RATIO\n                for hostile in hostiles\n            )\n''',
)
# The private resolver has the same precondition as discovery.
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''        trigger = any(not hostile.alive for hostile in hostiles) or any(\n            hostile.alive and hostile.max_hp > 0 and hostile.hp / hostile.max_hp <= AMBUSH_RETREAT_HP_RATIO\n            for hostile in hostiles\n        )\n''',
    '''        trigger = any(\n            not hostile.alive and hostile.metadata.get("defeat_resolved") is True\n            for hostile in hostiles\n        ) or any(\n            hostile.alive and hostile.max_hp > 0 and hostile.hp / hostile.max_hp <= AMBUSH_RETREAT_HP_RATIO\n            for hostile in hostiles\n        )\n''',
)

# -------------------- Floor 5: Fuscus hidden personal flag --------------------
replace_once(
    "src/sao_mcp/scenarios/floor5_fuscus.py",
    '''FLAG_STAT_BONUS = 0.08  # Simulation magnitude applied to the existing all-stat combat path.\n''',
    '''FLAG_STAT_BONUS = 0.08  # Simulation magnitude applied to the existing all-stat combat path.\nFUSCUS_FLAG_DROP_EVENT_RULE_ID = "floor5.fuscus_hidden_flag_drop"\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor5_fuscus.py",
    '''    def __init__(self, runtime) -> None:\n        self.runtime = runtime\n''',
    '''    def __init__(self, runtime) -> None:\n        self.runtime = runtime\n        runtime.register_world_event_rule(\n            FUSCUS_FLAG_DROP_EVENT_RULE_ID,\n            self._discover_hidden_flag_drop_events,\n            self._resolve_hidden_flag_drop_event,\n        )\n        runtime.evaluate_world_events()\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor5_fuscus.py",
    '''    def resolve_hidden_flag_drop(self, instance_id: str) -> dict:\n        state = self._instance(instance_id)\n        boss = self.runtime.actors[state["boss_id"]]\n        if boss.alive:\n            raise ValueError("Fuscus must be defeated before the Flag of Valor drop resolves")\n        if state["flag_drop_resolved"]:\n            return {"instance_id": instance_id, "resolved": True, "drop_created": True}\n\n        encounter = self.runtime.encounters[state["encounter_id"]]\n        candidates = sorted(\n            actor.actor_id\n            for actor in encounter.participants.values()\n            if actor.kind is EntityKind.PLAYER and actor.alive\n        )\n        if not candidates:\n            candidates = sorted(state["player_ids"])\n        recipient_id = self.runtime.rng.choice(candidates)\n        item = ItemInstance(\n            instance_id=f"flag_{uuid.uuid4().hex[:12]}",\n            template_id=FLAG_OF_VALOR,\n            owner_id=recipient_id,\n            quantity=1,\n            metadata={\n                "fuscus_instance_id": instance_id,\n                "hidden_personal_drop": True,\n                "allocation": "random_raid_participant_simulation",\n            },\n        )\n        add_item(self.runtime.actors[recipient_id], item, self.runtime.catalog, allow_overweight=True)\n        state["flag_drop_resolved"] = True\n        state["flag_recipient_id"] = recipient_id\n        state["flag_instance_id"] = item.instance_id\n        state["stage"] = "post_boss_secret_drop"\n        if encounter.active:\n            self.runtime.end_encounter(encounter.encounter_id, reason="fuscus_defeated")\n        return {"instance_id": instance_id, "resolved": True, "drop_created": True}\n''',
    '''    @staticmethod\n    def _event_instance_id(occurrence_id: str) -> str:\n        prefix = f"{FUSCUS_FLAG_DROP_EVENT_RULE_ID}:"\n        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):\n            raise RuntimeError(f"invalid Fuscus flag-drop occurrence id: {occurrence_id}")\n        return occurrence_id[len(prefix):]\n\n    def _discover_hidden_flag_drop_events(self) -> list[str]:\n        ready: list[str] = []\n        for instance_id, state in self._instances().items():\n            if state["stage"] != "battle" or state["flag_drop_resolved"]:\n                continue\n            boss = self.runtime.actors[state["boss_id"]]\n            if not boss.alive and boss.metadata.get("defeat_resolved") is True:\n                ready.append(f"{FUSCUS_FLAG_DROP_EVENT_RULE_ID}:{instance_id}")\n        return ready\n\n    def _resolve_hidden_flag_drop_event(self, occurrence_id: str) -> dict:\n        instance_id = self._event_instance_id(occurrence_id)\n        result = self._resolve_hidden_flag_drop(instance_id)\n        state = self._instance(instance_id)\n        return {\n            **result,\n            "flag_instance_id": state["flag_instance_id"],\n            "recipient_hidden_from_public_status": True,\n        }\n\n    def _resolve_hidden_flag_drop(self, instance_id: str) -> dict:\n        state = self._instance(instance_id)\n        boss = self.runtime.actors[state["boss_id"]]\n        if boss.alive or boss.metadata.get("defeat_resolved") is not True:\n            raise ValueError("Fuscus defeat must be fully resolved before the Flag of Valor drop resolves")\n        if state["flag_drop_resolved"]:\n            raise RuntimeError("Fuscus hidden flag-drop occurrence attempted to resolve twice")\n\n        encounter = self.runtime.encounters[state["encounter_id"]]\n        candidates = sorted(\n            actor.actor_id\n            for actor in encounter.participants.values()\n            if actor.kind is EntityKind.PLAYER and actor.alive\n        )\n        if not candidates:\n            candidates = sorted(state["player_ids"])\n        recipient_id = self.runtime.rng.choice(candidates)\n        item = ItemInstance(\n            instance_id=f"flag_{uuid.uuid4().hex[:12]}",\n            template_id=FLAG_OF_VALOR,\n            owner_id=recipient_id,\n            quantity=1,\n            metadata={\n                "fuscus_instance_id": instance_id,\n                "hidden_personal_drop": True,\n                "allocation": "random_raid_participant_simulation",\n            },\n        )\n        add_item(self.runtime.actors[recipient_id], item, self.runtime.catalog, allow_overweight=True)\n        state["flag_drop_resolved"] = True\n        state["flag_recipient_id"] = recipient_id\n        state["flag_instance_id"] = item.instance_id\n        state["stage"] = "post_boss_secret_drop"\n        if encounter.active:\n            self.runtime.end_encounter(encounter.encounter_id, reason="fuscus_defeated")\n        return {"instance_id": instance_id, "resolved": True, "drop_created": True}\n''',
)
replace_once(
    "src/sao_mcp/server_floor5.py",
    '''    @mcp.tool()\n    def resolve_floor5_hidden_flag_drop(instance_id: str) -> str:\n        """After Fuscus dies, resolve the hidden personal Flag of Valor drop without revealing its recipient."""\n        return _json(fuscus.resolve_hidden_flag_drop(instance_id))\n\n''',
    "",
)
replace_once(
    "tests/test_floor5_fuscus_flag.py",
    '''    runtime._resolve_defeat(encounter, boss, players[0].actor_id)\n\n    public = fuscus.resolve_hidden_flag_drop(state["instance_id"])\n    assert public == {"instance_id": state["instance_id"], "resolved": True, "drop_created": True}\n''',
    '''    runtime._resolve_defeat(encounter, boss, players[0].actor_id)\n\n    assert fuscus.status(state["instance_id"])["flag_drop_resolved"] is True\n    occurrence = runtime.world_event_state(\n        f"floor5.fuscus_hidden_flag_drop:{state['instance_id']}"\n    )\n    assert occurrence["status"] == "resolved"\n    assert occurrence["payload"]["recipient_hidden_from_public_status"] is True\n''',
)

# -------------------- Floor 7: Labyrinth blocker pursuit outcome --------------------
replace_once(
    "src/sao_mcp/scenarios/floor7_pursuit.py",
    '''TRAIL_MARGIN_MS = 3 * 60_000\n''',
    '''TRAIL_MARGIN_MS = 3 * 60_000\nLABYRINTH_PURSUIT_EVENT_RULE_ID = "floor7.labyrinth_pursuit_resolution"\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor7_pursuit.py",
    '''    def __init__(self, runtime) -> None:\n        self.runtime = runtime\n''',
    '''    def __init__(self, runtime) -> None:\n        self.runtime = runtime\n        runtime.register_world_event_rule(\n            LABYRINTH_PURSUIT_EVENT_RULE_ID,\n            self._discover_labyrinth_pursuit_events,\n            self._resolve_labyrinth_pursuit_event,\n        )\n        runtime.evaluate_world_events()\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor7_pursuit.py",
    '''    def resolve_labyrinth_pursuit(self, instance_id: str) -> dict:\n        state = self._state(instance_id)\n        if state["stage"] != "labyrinth_blocker_battle":\n            raise ValueError("the pursuit is not waiting on the Labyrinth blocker encounter")\n        pursuit = state["pursuit"]\n        encounter = self.runtime.encounters[pursuit["blocker_encounter_id"]]\n\n        if any(\n            encounter.participants[actor_id].alive or encounter.participants[actor_id].hp > 0\n            for actor_id in pursuit["blocker_actor_ids"]\n        ):\n            raise ValueError("the Labyrinth blockers are still alive")\n        if any(\n            not self.runtime.actors[actor_id].alive\n            for actor_id in pursuit["travelling_actor_ids"]\n        ):\n            raise ValueError("the pursuit group cannot continue with a defeated traveller")\n\n        combat_elapsed_ms = encounter.time_ms - pursuit["blocker_encounter_started_at_ms"]\n        if combat_elapsed_ms < 0:\n            raise RuntimeError("Labyrinth encounter time moved backwards")\n        pursuit["blocker_combat_elapsed_ms"] = combat_elapsed_ms\n        pursuit["trail_margin_ms"] = TRAIL_MARGIN_MS\n        pursuit["trail_outcome"] = "maintained" if combat_elapsed_ms <= TRAIL_MARGIN_MS else "lost"\n        if encounter.active:\n            self.runtime.end_encounter(encounter.encounter_id, reason="labyrinth_blockers_defeated")\n\n        for scout_id in pursuit["fallen_scout_ids"]:\n            self.runtime.actors[scout_id].metadata["pursuit_trail_outcome"] = pursuit["trail_outcome"]\n        state["stage"] = (\n            "trail_maintained_in_labyrinth"\n            if pursuit["trail_outcome"] == "maintained"\n            else "trail_lost_in_labyrinth"\n        )\n        return self.status(instance_id)\n''',
    '''    @staticmethod\n    def _pursuit_event_instance_id(occurrence_id: str) -> str:\n        prefix = f"{LABYRINTH_PURSUIT_EVENT_RULE_ID}:"\n        if not occurrence_id.startswith(prefix) or len(occurrence_id) == len(prefix):\n            raise RuntimeError(f"invalid Labyrinth pursuit occurrence id: {occurrence_id}")\n        return occurrence_id[len(prefix):]\n\n    def _discover_labyrinth_pursuit_events(self) -> list[str]:\n        ready: list[str] = []\n        for instance_id, state in self._harin_states().items():\n            if state["stage"] != "labyrinth_blocker_battle":\n                continue\n            pursuit = state["pursuit"]\n            blockers = [self.runtime.actors[actor_id] for actor_id in pursuit["blocker_actor_ids"]]\n            if not blockers or any(\n                blocker.alive or blocker.hp > 0 or blocker.metadata.get("defeat_resolved") is not True\n                for blocker in blockers\n            ):\n                continue\n            if any(not self.runtime.actors[actor_id].alive for actor_id in pursuit["travelling_actor_ids"]):\n                continue\n            ready.append(f"{LABYRINTH_PURSUIT_EVENT_RULE_ID}:{instance_id}")\n        return ready\n\n    def _resolve_labyrinth_pursuit_event(self, occurrence_id: str) -> dict:\n        instance_id = self._pursuit_event_instance_id(occurrence_id)\n        state = self._resolve_labyrinth_pursuit(instance_id)\n        return {\n            "instance_id": instance_id,\n            "trail_outcome": state["trail_outcome"],\n            "stage": state["stage"],\n        }\n\n    def _resolve_labyrinth_pursuit(self, instance_id: str) -> dict:\n        state = self._state(instance_id)\n        if state["stage"] != "labyrinth_blocker_battle":\n            raise ValueError("the pursuit is not waiting on the Labyrinth blocker encounter")\n        pursuit = state["pursuit"]\n        encounter = self.runtime.encounters[pursuit["blocker_encounter_id"]]\n\n        blockers = [self.runtime.actors[actor_id] for actor_id in pursuit["blocker_actor_ids"]]\n        if any(\n            blocker.alive or blocker.hp > 0 or blocker.metadata.get("defeat_resolved") is not True\n            for blocker in blockers\n        ):\n            raise ValueError("the Labyrinth blockers have not completed defeat resolution")\n        if any(\n            not self.runtime.actors[actor_id].alive\n            for actor_id in pursuit["travelling_actor_ids"]\n        ):\n            raise ValueError("the pursuit group cannot continue with a defeated traveller")\n\n        combat_elapsed_ms = encounter.time_ms - pursuit["blocker_encounter_started_at_ms"]\n        if combat_elapsed_ms < 0:\n            raise RuntimeError("Labyrinth encounter time moved backwards")\n        pursuit["blocker_combat_elapsed_ms"] = combat_elapsed_ms\n        pursuit["trail_margin_ms"] = TRAIL_MARGIN_MS\n        pursuit["trail_outcome"] = "maintained" if combat_elapsed_ms <= TRAIL_MARGIN_MS else "lost"\n        if encounter.active:\n            self.runtime.end_encounter(encounter.encounter_id, reason="labyrinth_blockers_defeated")\n\n        for scout_id in pursuit["fallen_scout_ids"]:\n            self.runtime.actors[scout_id].metadata["pursuit_trail_outcome"] = pursuit["trail_outcome"]\n        state["stage"] = (\n            "trail_maintained_in_labyrinth"\n            if pursuit["trail_outcome"] == "maintained"\n            else "trail_lost_in_labyrinth"\n        )\n        return self.status(instance_id)\n''',
)
replace_once(
    "src/sao_mcp/server_floor7.py",
    '''    @mcp.tool()\n    def resolve_floor7_labyrinth_pursuit(instance_id: str) -> str:\n        """After ordinary combat kills the Labyrinth blockers, synchronize actual encounter time and determine whether the Fallen trail was maintained or lost."""\n        return _json(pursuit.resolve_labyrinth_pursuit(instance_id))\n\n''',
    "",
)
replace_once(
    "tests/test_floor7_pursuit.py",
    '''def _defeat_blockers(runtime, pursuit, instance_id, encounter_id, elapsed_ms):\n    encounter = runtime.encounters[encounter_id]\n    state = pursuit.status(instance_id)\n    for blocker_id in state["pursuit"]["blocker_actor_ids"]:\n        blocker = encounter.participants[blocker_id]\n        blocker.hp = 0\n        blocker.alive = False\n    runtime.advance_encounter(encounter_id, elapsed_ms)\n    return pursuit.resolve_labyrinth_pursuit(instance_id)\n''',
    '''def _defeat_blockers(runtime, pursuit, instance_id, encounter_id, elapsed_ms):\n    encounter = runtime.encounters[encounter_id]\n    state = pursuit.status(instance_id)\n    runtime.advance_encounter(encounter_id, elapsed_ms)\n    blocker_ids = list(state["pursuit"]["blocker_actor_ids"])\n    for blocker_id in blocker_ids:\n        blocker = encounter.participants[blocker_id]\n        blocker.hp = 0\n        blocker.alive = False\n        runtime._resolve_defeat(encounter, blocker, state["pursuit"]["travelling_actor_ids"][0])\n    resolved = pursuit.status(instance_id)\n    assert runtime.world_event_state(\n        f"floor7.labyrinth_pursuit_resolution:{instance_id}"\n    )["status"] == "resolved"\n    return resolved\n''',
)

# Extend permanent authority gate: these transitions must not regress to public trigger methods/tools.
path = Path("tests/test_world_event_authority.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    '''from sao_mcp.runtime.housing_runtime import HousingAincradRuntime\n''',
    '''from sao_mcp.runtime.housing_runtime import HousingAincradRuntime\nfrom sao_mcp.scenarios.floor5_fuscus import FUSCUS_FLAG_DROP_EVENT_RULE_ID, Floor5FuscusScenario\nfrom sao_mcp.scenarios.floor7_pursuit import LABYRINTH_PURSUIT_EVENT_RULE_ID, Floor7PursuitScenario\n''',
    1,
)
text = text.replace(
    '''            AMBUSHER_RETREAT_EVENT_RULE_ID,\n        }\n''',
    '''            AMBUSHER_RETREAT_EVENT_RULE_ID,\n            FUSCUS_FLAG_DROP_EVENT_RULE_ID,\n            LABYRINTH_PURSUIT_EVENT_RULE_ID,\n        }\n''',
    1,
)
text = text.replace(
    '''    assert hasattr(Floor6StachionScenario, "wait_for_paralysis_release")\n''',
    '''    assert hasattr(Floor6StachionScenario, "wait_for_paralysis_release")\n    assert not hasattr(Floor5FuscusScenario, "resolve_hidden_flag_drop")\n    assert not hasattr(Floor7PursuitScenario, "resolve_labyrinth_pursuit")\n''',
    1,
)
text = text.replace(
    '''        "resolve_floor6_buxum_retreat",\n    )\n''',
    '''        "resolve_floor6_buxum_retreat",\n        "resolve_floor5_hidden_flag_drop",\n        "resolve_floor7_labyrinth_pursuit",\n    )\n''',
    1,
)
path.write_text(text, encoding="utf-8")
