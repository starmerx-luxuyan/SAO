from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Put the scheduler in the single-inheritance runtime chain.
replace_once(
    "src/sao_mcp/runtime/guild_autonomy_runtime.py",
    "from sao_mcp.runtime.npc_autonomy_runtime import NPCAutonomyAincradRuntime\n",
    "from sao_mcp.runtime.npc_scheduler_runtime import NPCSchedulerAincradRuntime\n",
)
replace_once(
    "src/sao_mcp/runtime/guild_autonomy_runtime.py",
    "class GuildAutonomyAincradRuntime(NPCAutonomyAincradRuntime):\n",
    "class GuildAutonomyAincradRuntime(NPCSchedulerAincradRuntime):\n",
)

# Generalized actor-core/agenda persistence still lives in the NPC autonomy SSOT.
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    "from sao_mcp.rules.npc_autonomy import NPCAgendaState\n",
    "from sao_mcp.rules.npc_autonomy import NPCAgendaState\nfrom sao_mcp.rules.npc_scheduler import NPCPlanActionKind\n",
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    'NPC_AUTONOMY_SCHEMA = "npc-autonomy.v3"\n',
    'NPC_AUTONOMY_SCHEMA = "npc-autonomy.v4"\n',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''    def npc_location_id(self, npc_id: str) -> str | None:\n        agenda = self.npc_agendas.get(npc_id)\n        if agenda is not None and agenda.active:\n            return None\n        return super().npc_location_id(npc_id)\n''',
    '''    def npc_location_id(self, npc_id: str) -> str | None:\n        agenda = self.npc_agendas.get(npc_id)\n        if agenda is not None and agenda.in_transit:\n            return None\n        return super().npc_location_id(npc_id)\n''',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''            if agenda.plan_step_id is not None:\n                step = core.current_plan_step\n                if step is None or step.step_id != agenda.plan_step_id:\n                    raise RuntimeError(f"NPC {npc_id} active agenda is not executing the current actor-core plan step")\n                if step.target_location_id != agenda.target_location_id:\n                    raise RuntimeError(f"NPC {npc_id} agenda target disagrees with actor-core plan step")\n''',
    '''            if agenda.plan_step_id is not None:\n                step = core.current_plan_step\n                if step is None or step.step_id != agenda.plan_step_id:\n                    raise RuntimeError(f"NPC {npc_id} active agenda is not executing the current actor-core plan step")\n                if step.action_kind.value != agenda.activity_kind:\n                    raise RuntimeError(f"NPC {npc_id} agenda kind disagrees with actor-core plan step")\n                if agenda.in_transit:\n                    if step.target_location_id != agenda.target_location_id:\n                        raise RuntimeError(f"NPC {npc_id} agenda target disagrees with actor-core plan step")\n                elif agenda.stationary_location_id != self._stationary_npc_location_id(npc_id):\n                    raise RuntimeError(f"NPC {npc_id} stationary agenda lost its settled location")\n''',
)
replace_once(
    "src/sao_mcp/runtime/npc_autonomy_runtime.py",
    '''            agenda = NPCAgendaState(\n                npc_id=npc_id,\n                activity_kind=row.get("activity_kind"),\n                from_location_id=row.get("from_location_id"),\n                target_location_id=row.get("target_location_id"),\n                started_at_ms=row.get("started_at_ms"),\n                due_at_ms=row.get("due_at_ms"),\n                traversal_tags=tuple(row.get("traversal_tags", ())),\n                plan_step_id=row.get("plan_step_id"),\n            )\n            if agenda.active and (agenda.due_at_ms is None or agenda.due_at_ms <= self.world.now_ms):\n                raise ValueError(f"NPC autonomy save contains overdue active travel: {npc_id}")\n''',
    '''            agenda = NPCAgendaState(\n                npc_id=npc_id,\n                activity_kind=row.get("activity_kind"),\n                from_location_id=row.get("from_location_id"),\n                target_location_id=row.get("target_location_id"),\n                stationary_location_id=row.get("stationary_location_id"),\n                started_at_ms=row.get("started_at_ms"),\n                due_at_ms=row.get("due_at_ms"),\n                traversal_tags=tuple(row.get("traversal_tags", ())),\n                plan_step_id=row.get("plan_step_id"),\n                payload=dict(row.get("payload", {})),\n                interruptible=bool(row.get("interruptible", False)),\n            )\n            if agenda.active and (agenda.due_at_ms is None or agenda.due_at_ms <= self.world.now_ms):\n                raise ValueError(f"NPC autonomy save contains overdue active activity: {npc_id}")\n''',
)

# Current-route authority only treats actual graph travel as a route. Stationary scheduler work stays settled.
replace_once(
    "src/sao_mcp/rules/live_state.py",
    "        if agenda is not None and agenda.active:\n",
    "        if agenda is not None and agenda.active and agenda.activity_kind == \"travel\":\n",
)
replace_once(
    "src/sao_mcp/rules/live_state.py",
    '''    now = runtime.world.now_ms\n    if not isinstance(now, int) or isinstance(now, bool) or now < 0:\n        raise RuntimeError("world clock must be a non-negative integer")\n\n''',
    '''    now = runtime.world.now_ms\n    if not isinstance(now, int) or isinstance(now, bool) or now < 0:\n        raise RuntimeError("world clock must be a non-negative integer")\n    scheduler_assert = getattr(runtime, "_assert_npc_scheduler_authority", None)\n    if scheduler_assert is not None:\n        scheduler_assert()\n\n''',
)
replace_once(
    "src/sao_mcp/rules/live_state.py",
    '''        if agenda.activity_kind != "travel":\n            raise RuntimeError(f"NPC {npc_id} has unsupported active activity {agenda.activity_kind!r}")\n''',
    '''        if agenda.activity_kind != "travel":\n            if agenda.stationary_location_id not in runtime.world_map.locations:\n                raise RuntimeError(f"NPC {npc_id} stationary activity references an unknown location")\n            if agenda.started_at_ms is None or agenda.due_at_ms is None or not (agenda.started_at_ms <= now < agenda.due_at_ms):\n                raise RuntimeError(f"NPC {npc_id} has invalid stationary-activity timing")\n            resolver = getattr(runtime, "_materialized_npc_actor", None)\n            materialized = resolver(npc_id) if resolver is not None else None\n            if materialized is not None and materialized.location_id != agenda.stationary_location_id:\n                raise RuntimeError(f"NPC {npc_id} stationary activity actor is not at its settled location")\n            continue\n''',
)

# Route ordinary travel time through runtime.advance_world so scheduler boundaries are not skipped.
replace_once(
    "src/sao_mcp/rules/travel.py",
    "from dataclasses import dataclass\n",
    "from collections.abc import Callable\nfrom dataclasses import dataclass\n",
)
replace_once(
    "src/sao_mcp/rules/travel.py",
    '''def travel(\n    world: WorldState,\n    actor: CombatantState,\n    destination_id: str,\n    catalog: WorldMapCatalog,\n) -> TravelResolution:\n''',
    '''def travel(\n    world: WorldState,\n    actor: CombatantState,\n    destination_id: str,\n    catalog: WorldMapCatalog,\n    *,\n    advance_time: Callable[[int], object] | None = None,\n) -> TravelResolution:\n''',
)
replace_once(
    "src/sao_mcp/rules/travel.py",
    '''    origin = actor.location_id\n    world.now_ms += edge.travel_ms\n    newly_discovered = discover_location(world, actor, destination)\n''',
    '''    origin = actor.location_id\n    if advance_time is None:\n        world.now_ms += edge.travel_ms\n    else:\n        actor.location_id = None\n        advance_time(edge.travel_ms)\n        if actor.location_id is not None:\n            raise RuntimeError("travelling actor acquired a settled location before travel commit")\n    newly_discovered = discover_location(world, actor, destination)\n''',
)
replace_once(
    "src/sao_mcp/runtime/engine.py",
    "        resolution = travel(self.world, actor, destination_id, self.world_map)\n",
    "        resolution = travel(self.world, actor, destination_id, self.world_map, advance_time=self.advance_world)\n",
)
replace_once(
    "src/sao_mcp/runtime/world_event_runtime.py",
    '''    def travel_actor(self, actor_id: str, destination_id: str):\n        # GameRuntime.travel_actor delegates to the data-only travel rule, which advances\n        # WorldState directly. Emit the same authoritative time event after that commit.\n        before_ms = self.world.now_ms\n        resolution = super().travel_actor(actor_id, destination_id)\n        self._emit_world_advance(before_ms)\n        return resolution\n''',
    '''    def travel_actor(self, actor_id: str, destination_id: str):\n        # Ordinary travel routes elapsed time through self.advance_world(), so world-event\n        # and NPC-scheduler boundaries are emitted exactly once during the travel window.\n        return super().travel_actor(actor_id, destination_id)\n''',
)

# Persist scheduler execution policy separately from Actor Core motivation/current plan.
replace_once(
    "src/sao_mcp/runtime/persistence.py",
    "    npc_autonomy_dump = getattr(runtime, \"dump_npc_autonomy_state\", None)\n",
    "    npc_autonomy_dump = getattr(runtime, \"dump_npc_autonomy_state\", None)\n    npc_scheduler_dump = getattr(runtime, \"dump_npc_scheduler_state\", None)\n",
)
replace_once(
    "src/sao_mcp/runtime/persistence.py",
    '        "npc_autonomy_state": npc_autonomy_dump() if npc_autonomy_dump is not None else {},\n',
    '        "npc_autonomy_state": npc_autonomy_dump() if npc_autonomy_dump is not None else {},\n        "npc_scheduler_state": npc_scheduler_dump() if npc_scheduler_dump is not None else {},\n',
)
replace_once(
    "src/sao_mcp/runtime/persistence.py",
    '''    autonomy_load = getattr(runtime, "load_npc_autonomy_state", None)\n    if autonomy_load is not None:\n        autonomy_load(payload.get("npc_autonomy_state", {}))\n\n    from sao_mcp.runtime.property_economy import make_runtime_economy\n''',
    '''    autonomy_load = getattr(runtime, "load_npc_autonomy_state", None)\n    if autonomy_load is not None:\n        autonomy_load(payload.get("npc_autonomy_state", {}))\n    scheduler_load = getattr(runtime, "load_npc_scheduler_state", None)\n    if scheduler_load is not None:\n        scheduler_load(payload.get("npc_scheduler_state", {}))\n\n    from sao_mcp.runtime.property_economy import make_runtime_economy\n''',
)

# GM structured action surface exposes scheduler steps and explicit interruption.
replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''            "resource_requirements",\n        }),\n    ),\n    "clear_npc_goal": (frozenset({"npc_id"}), frozenset()),\n''',
    '''            "resource_requirements",\n            "scheduled_actions",\n        }),\n    ),\n    "clear_npc_goal": (frozenset({"npc_id"}), frozenset()),\n    "interrupt_npc_activity": (\n        frozenset({"npc_id", "reason"}),\n        frozenset({"suspend_goal"}),\n    ),\n''',
)
replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''                resource_requirements=action.get("resource_requirements"),\n            )\n        if op == "clear_npc_goal":\n            return runtime.clear_npc_goal(action["npc_id"])\n''',
    '''                resource_requirements=action.get("resource_requirements"),\n                scheduled_actions=action.get("scheduled_actions"),\n            )\n        if op == "clear_npc_goal":\n            return runtime.clear_npc_goal(action["npc_id"])\n        if op == "interrupt_npc_activity":\n            return runtime.interrupt_npc_activity(\n                action["npc_id"],\n                reason=action["reason"],\n                suspend_goal=bool(action.get("suspend_goal", True)),\n            )\n''',
)
replace_once(
    "src/sao_mcp/runtime/gm_turn.py",
    '''            "npc_agendas": {\n                npc_id: runtime.npc_agenda_state(npc_id)\n                for npc_id in sorted(npc_ids)\n            },\n''',
    '''            "npc_agendas": {\n                npc_id: runtime.npc_agenda_state(npc_id)\n                for npc_id in sorted(npc_ids)\n            },\n            "npc_schedulers": {\n                npc_id: runtime.npc_scheduler_state(npc_id)\n                for npc_id in sorted(npc_ids)\n                if hasattr(runtime, "npc_scheduler_state")\n            },\n''',
)

replace_once(
    "src/sao_mcp/server_gm.py",
    '''    @mcp.tool()\n    def get_npc_actor_core(npc_id: str) -> str:\n        """Inspect one NPC's long-term goals, current business, short-term plan, decision inputs and authoritative resources."""\n        return _json(gm_turn_executor.runtime.npc_actor_core_state(npc_id))\n\n''',
    '''    @mcp.tool()\n    def get_npc_actor_core(npc_id: str) -> str:\n        """Inspect one NPC's long-term goals, current business, short-term plan, decision inputs and authoritative resources."""\n        return _json(gm_turn_executor.runtime.npc_actor_core_state(npc_id))\n\n    @mcp.tool()\n    def get_npc_scheduler(npc_id: str) -> str:\n        """Inspect one NPC's world-time execution step, due time, interruptibility and goal-bound scheduler operations."""\n        return _json(gm_turn_executor.runtime.npc_scheduler_state(npc_id))\n\n''',
)

# Preserve the pre-scheduler travel history contract; scheduler-only activities add lifecycle status.
replace_once(
    "src/sao_mcp/runtime/npc_scheduler_runtime.py",
    '''        if agenda.activity_kind == NPCPlanActionKind.TRAVEL.value:\n            completed_at_ms = super()._finish_travel_leg(npc_id, agenda)\n            if self.npc_activity_history:\n                self.npc_activity_history[-1].setdefault("status", "completed")\n            return completed_at_ms\n''',
    '''        if agenda.activity_kind == NPCPlanActionKind.TRAVEL.value:\n            return super()._finish_travel_leg(npc_id, agenda)\n''',
)

# Source-authority gate: scenario code cannot reach into scheduler state or call private execution helpers.
Path("tests/test_npc_scheduler_authority.py").write_text('''from __future__ import annotations\n\nimport ast\nfrom pathlib import Path\n\nfrom sao_mcp.rules.npc_scheduler import NPCPlanActionKind\nfrom sao_mcp.runtime.gm_turn import GMTurnExecutor\n\n\nROOT = Path(__file__).resolve().parents[1]\nSCENARIOS = ROOT / "src/sao_mcp/scenarios"\n\n\ndef test_scheduler_action_kinds_cover_world_time_npc_work_without_replacing_rule_engines():\n    assert {kind.value for kind in NPCPlanActionKind} == {\n        "travel", "wait", "investigate", "contact", "trade_vendor", "engage", "attack"\n    }\n\n\ndef test_gm_goal_contract_exposes_scheduler_actions_and_explicit_interruption():\n    contract = GMTurnExecutor.supported_actions()\n    assert "scheduled_actions" in contract["set_npc_goal"]["optional"]\n    assert set(contract["interrupt_npc_activity"]["required"]) == {"npc_id", "reason"}\n\n\ndef test_scenarios_cannot_bypass_scheduler_operation_authority():\n    forbidden = {\n        "npc_scheduler_goals",\n        "_begin_scheduler_step",\n        "_finish_travel_leg",\n        "_interrupt_current_activity",\n    }\n    violations = []\n    for path in SCENARIOS.glob("*.py"):\n        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))\n        for node in ast.walk(tree):\n            if isinstance(node, ast.Attribute) and node.attr in forbidden:\n                violations.append(f"{path.name}:{node.lineno}:{node.attr}")\n    assert violations == []\n''', encoding="utf-8")

Path("tests/test_npc_scheduler.py").write_text('''from __future__ import annotations\n\nfrom sao_mcp.domain.models import EntityKind\nfrom sao_mcp.runtime.housing_runtime import HousingAincradRuntime\nfrom sao_mcp.runtime.persistence import export_runtime, import_runtime\nfrom sao_mcp.runtime.property_economy import make_runtime_economy\n\n\nAGIL = "pc_agil"\nAGIL_SHOP = "floor_50_agil_shop"\nTUTOR = "npc_tutorial_instructor"\nTOWN = "floor_1_town_of_beginnings"\nWEST = "floor_1_west_field"\n\n\ndef _materialize(runtime, npc_id: str, name: str, location_id: str, level: int = 10):\n    actor = runtime.create_character(name, level=level)\n    actor.kind = EntityKind.NPC\n    actor.metadata["npc_definition_id"] = npc_id\n    actor.location_id = location_id\n    return actor\n\n\ndef test_scheduler_resolves_investigation_at_exact_due_time_inside_large_world_advance():\n    runtime = HousingAincradRuntime(seed=1001)\n    runtime.world.floors[50].unlocked = True\n    runtime.set_npc_goal(\n        AGIL,\n        "inspect_shop_books",\n        AGIL_SHOP,\n        scheduled_actions=[{\n            "action_kind": "investigate",\n            "duration_ms": 120_000,\n            "payload": {"fact_id": "shop_books_checked", "value": True},\n            "interruptible": True,\n        }],\n    )\n    state = runtime.npc_scheduler_state(AGIL)\n    assert state["activity"]["activity_kind"] == "investigate"\n    assert state["location_id"] == AGIL_SHOP\n    assert state["activity"]["due_at_ms"] == 120_000\n\n    runtime.advance_world(600_000)\n    belief = runtime.belief(AGIL, "shop_books_checked")\n    assert belief is not None\n    assert belief.learned_at_ms == 120_000\n    assert runtime.world.now_ms == 600_000\n    history = [row for row in runtime.npc_activity_history if row.get("activity_kind") == "investigate"]\n    assert history[-1]["completed_at_ms"] == 120_000\n    assert history[-1]["status"] == "completed"\n\n\ndef test_scheduler_contact_uses_real_knowledge_transfer_chain():\n    runtime = HousingAincradRuntime(seed=1002)\n    runtime.world.floors[50].unlocked = True\n    listener = runtime.create_character("Listener", level=5)\n    listener.location_id = AGIL_SHOP\n    source = runtime.record_observation(\n        AGIL,\n        "ore_shortage",\n        True,\n        observation_location_id=AGIL_SHOP,\n        source_id="market_board",\n        confidence=0.9,\n    )\n    runtime.set_npc_goal(\n        AGIL,\n        "brief_listener",\n        AGIL_SHOP,\n        scheduled_actions=[{\n            "action_kind": "contact",\n            "duration_ms": 30_000,\n            "payload": {"recipient_id": listener.actor_id, "fact_ids": ["ore_shortage"]},\n        }],\n    )\n    runtime.advance_world(30_000)\n    received = runtime.belief(listener.actor_id, "ore_shortage")\n    assert received is not None\n    assert received.source_id == AGIL\n    assert received.evidence_event_ids == (source.event_id,)\n    assert received.learned_at_ms == 30_000\n\n\ndef test_scheduler_vendor_trade_uses_authoritative_economy_and_materialized_inventory():\n    runtime = HousingAincradRuntime(seed=1003)\n    runtime.economy = make_runtime_economy(runtime)\n    actor = _materialize(runtime, TUTOR, "Instructor", TOWN)\n    actor.col = 100\n    runtime.set_npc_goal(\n        TUTOR,\n        "buy_field_supplies",\n        TOWN,\n        scheduled_actions=[{\n            "action_kind": "trade_vendor",\n            "duration_ms": 10_000,\n            "payload": {\n                "operation": "buy",\n                "vendor_id": "npc_vendor_town_of_beginnings",\n                "template_id": "field_bread",\n                "quantity": 2,\n            },\n        }],\n    )\n    runtime.advance_world(10_000)\n    assert actor.col == 90\n    assert sum(item.quantity for item in actor.inventory.values() if item.template_id == "field_bread") == 2\n    row = [r for r in runtime.npc_activity_history if r.get("activity_kind") == "trade_vendor"][-1]\n    assert row["result"]["total_col"] == 10\n\n\ndef test_scheduler_engage_then_attack_resolves_through_combat_timeline():\n    runtime = HousingAincradRuntime(seed=1004)\n    actor = _materialize(runtime, TUTOR, "Instructor", WEST, level=5)\n    monster = runtime.create_training_monster(level=1)\n    monster.location_id = WEST\n    hp_before = monster.hp\n    runtime.set_npc_goal(\n        TUTOR,\n        "fight_boar",\n        WEST,\n        scheduled_actions=[\n            {\n                "action_kind": "engage",\n                "duration_ms": 1_000,\n                "payload": {"target_actor_id": monster.actor_id},\n                "interruptible": False,\n            },\n            {\n                "action_kind": "attack",\n                "duration_ms": 0,\n                "payload": {"target_actor_id": monster.actor_id, "seed": 7},\n                "interruptible": True,\n            },\n        ],\n    )\n    runtime.advance_world(5_000)\n    rows = [r for r in runtime.npc_activity_history if r.get("goal_id") == "fight_boar"]\n    assert [row["activity_kind"] for row in rows] == ["engage", "attack"]\n    assert rows[0]["result"]["encounter_id"] in runtime.encounters\n    assert rows[1]["result"]["event"] == "player_attack"\n    assert monster.hp <= hp_before\n    assert runtime.world.now_ms == 5_000\n    assert actor.location_id == WEST\n\n\ndef test_interruptible_stationary_work_preempts_on_relevant_belief_change():\n    runtime = HousingAincradRuntime(seed=1005)\n    runtime.world.floors[50].unlocked = True\n    low_fact = runtime.record_observation(\n        AGIL, "routine_ok", True, observation_location_id=AGIL_SHOP\n    )\n    assert low_fact.value is True\n    runtime.set_npc_goal(\n        AGIL,\n        "routine_wait",\n        AGIL_SHOP,\n        priority=20,\n        required_fact_id="routine_ok",\n        scheduled_actions=[{\n            "action_kind": "wait",\n            "duration_ms": 600_000,\n            "payload": {},\n            "interruptible": True,\n        }],\n    )\n    runtime.set_npc_goal(\n        AGIL,\n        "urgent_check",\n        AGIL_SHOP,\n        priority=100,\n        required_fact_id="urgent_signal",\n        scheduled_actions=[{\n            "action_kind": "investigate",\n            "duration_ms": 5_000,\n            "payload": {"fact_id": "urgent_checked", "value": True},\n        }],\n    )\n    assert runtime.npc_scheduler_state(AGIL)["activity"]["activity_kind"] == "wait"\n    runtime.record_observation(\n        AGIL, "urgent_signal", True, observation_location_id=AGIL_SHOP\n    )\n    state = runtime.npc_scheduler_state(AGIL)\n    assert state["current_goal_id"] == "urgent_check"\n    assert state["activity"]["activity_kind"] == "investigate"\n    interrupted = [r for r in runtime.npc_activity_history if r.get("status") == "interrupted"]\n    assert interrupted[-1]["goal_id"] == "routine_wait"\n\n\ndef test_noninterruptible_travel_replans_only_after_reaching_route_node():\n    runtime = HousingAincradRuntime(seed=1006)\n    runtime.world.floors[50].unlocked = True\n    runtime.set_npc_goal(AGIL, "field_trip", "floor_50_field", priority=20)\n    assert runtime.npc_scheduler_state(AGIL)["activity"]["activity_kind"] == "travel"\n    runtime.set_npc_goal(AGIL, "urgent_algade", "floor_50_algade", priority=100)\n    travelling = runtime.npc_scheduler_state(AGIL)\n    assert travelling["current_goal_id"] == "field_trip"\n    runtime.advance_world(2 * 60_000)\n    after_node = runtime.npc_scheduler_state(AGIL)\n    assert after_node["current_goal_id"] == "urgent_algade"\n    assert after_node["location_id"] == "floor_50_algade"\n\n\ndef test_scheduler_state_and_mid_activity_due_time_survive_save_load():\n    runtime = HousingAincradRuntime(seed=1007)\n    runtime.world.floors[50].unlocked = True\n    runtime.set_npc_goal(\n        AGIL,\n        "long_inventory_check",\n        AGIL_SHOP,\n        scheduled_actions=[{\n            "action_kind": "investigate",\n            "duration_ms": 100_000,\n            "payload": {"fact_id": "inventory_checked", "value": True},\n        }],\n    )\n    runtime.advance_world(40_000)\n    restored = import_runtime(export_runtime(runtime))\n    state = restored.npc_scheduler_state(AGIL)\n    assert state["activity"]["due_at_ms"] == 100_000\n    assert state["operations"]["long_inventory_check"]["actions"][0]["action_kind"] == "investigate"\n    restored.advance_world(60_000)\n    belief = restored.belief(AGIL, "inventory_checked")\n    assert belief is not None and belief.learned_at_ms == 100_000\n\n\ndef test_ordinary_player_travel_processes_scheduler_due_point_inside_travel_window():\n    runtime = HousingAincradRuntime(seed=1008)\n    runtime.set_npc_goal(\n        TUTOR,\n        "brief_pause",\n        TOWN,\n        scheduled_actions=[{\n            "action_kind": "investigate",\n            "duration_ms": 30_000,\n            "payload": {"fact_id": "half_minute_check", "value": True},\n        }],\n    )\n    player = runtime.create_character("Walker", level=2)\n    resolution = runtime.travel_actor(player.actor_id, WEST)\n    assert resolution.elapsed_ms > 30_000\n    belief = runtime.belief(TUTOR, "half_minute_check")\n    assert belief is not None\n    assert belief.learned_at_ms == 30_000\n    assert runtime.world.now_ms == resolution.elapsed_ms\n''', encoding="utf-8")
