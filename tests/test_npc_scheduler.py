from __future__ import annotations

from sao_mcp.domain.models import EntityKind
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.property_economy import make_runtime_economy


AGIL = "pc_agil"
AGIL_SHOP = "floor_50_agil_shop"
TUTOR = "npc_tutorial_instructor"
TOWN = "floor_1_town_of_beginnings"
WEST = "floor_1_west_field"


def _materialize(runtime, npc_id: str, name: str, location_id: str, level: int = 10):
    actor = runtime.create_character(name, level=level)
    actor.kind = EntityKind.NPC
    actor.metadata["npc_definition_id"] = npc_id
    actor.location_id = location_id
    return actor


def test_scheduler_resolves_investigation_at_exact_due_time_inside_large_world_advance():
    runtime = HousingAincradRuntime(seed=1001)
    runtime.world.floors[50].unlocked = True
    runtime.set_npc_goal(
        AGIL,
        "inspect_shop_books",
        AGIL_SHOP,
        scheduled_actions=[{
            "action_kind": "investigate",
            "duration_ms": 120_000,
            "payload": {"fact_id": "shop_books_checked", "value": True},
            "interruptible": True,
        }],
    )
    state = runtime.npc_scheduler_state(AGIL)
    assert state["activity"]["activity_kind"] == "investigate"
    assert state["location_id"] == AGIL_SHOP
    assert state["activity"]["due_at_ms"] == 120_000

    runtime.advance_world(600_000)
    belief = runtime.belief(AGIL, "shop_books_checked")
    assert belief is not None
    assert belief.learned_at_ms == 120_000
    assert runtime.world.now_ms == 600_000
    history = [row for row in runtime.npc_activity_history if row.get("activity_kind") == "investigate"]
    assert history[-1]["completed_at_ms"] == 120_000
    assert history[-1]["status"] == "completed"


def test_scheduler_contact_uses_real_knowledge_transfer_chain():
    runtime = HousingAincradRuntime(seed=1002)
    runtime.world.floors[50].unlocked = True
    listener = runtime.create_character("Listener", level=5)
    listener.location_id = AGIL_SHOP
    source = runtime.record_observation(
        AGIL,
        "ore_shortage",
        True,
        observation_location_id=AGIL_SHOP,
        source_id="market_board",
        confidence=0.9,
    )
    runtime.set_npc_goal(
        AGIL,
        "brief_listener",
        AGIL_SHOP,
        scheduled_actions=[{
            "action_kind": "contact",
            "duration_ms": 30_000,
            "payload": {"recipient_id": listener.actor_id, "fact_ids": ["ore_shortage"]},
        }],
    )
    runtime.advance_world(30_000)
    received = runtime.belief(listener.actor_id, "ore_shortage")
    assert received is not None
    assert received.source_id == AGIL
    assert received.evidence_event_ids == (source.event_id,)
    assert received.learned_at_ms == 30_000


def test_scheduler_vendor_trade_uses_authoritative_economy_and_materialized_inventory():
    runtime = HousingAincradRuntime(seed=1003)
    runtime.economy = make_runtime_economy(runtime)
    actor = _materialize(runtime, TUTOR, "Instructor", TOWN)
    actor.col = 100
    runtime.set_npc_goal(
        TUTOR,
        "buy_field_supplies",
        TOWN,
        scheduled_actions=[{
            "action_kind": "trade_vendor",
            "duration_ms": 10_000,
            "payload": {
                "operation": "buy",
                "vendor_id": "npc_vendor_town_of_beginnings",
                "template_id": "field_bread",
                "quantity": 2,
            },
        }],
    )
    runtime.advance_world(10_000)
    assert actor.col == 90
    assert sum(item.quantity for item in actor.inventory.values() if item.template_id == "field_bread") == 2
    row = [r for r in runtime.npc_activity_history if r.get("activity_kind") == "trade_vendor"][-1]
    assert row["result"]["total_col"] == 10


def test_scheduler_engage_then_attack_resolves_through_combat_timeline():
    runtime = HousingAincradRuntime(seed=1004)
    actor = _materialize(runtime, TUTOR, "Instructor", WEST, level=5)
    monster = runtime.create_training_monster(level=1)
    monster.location_id = WEST
    hp_before = monster.hp
    runtime.set_npc_goal(
        TUTOR,
        "fight_boar",
        WEST,
        scheduled_actions=[
            {
                "action_kind": "engage",
                "duration_ms": 1_000,
                "payload": {"target_actor_id": monster.actor_id},
                "interruptible": False,
            },
            {
                "action_kind": "attack",
                "duration_ms": 0,
                "payload": {"target_actor_id": monster.actor_id, "seed": 7},
                "interruptible": True,
            },
        ],
    )
    runtime.advance_world(5_000)
    rows = [r for r in runtime.npc_activity_history if r.get("goal_id") == "fight_boar"]
    assert [row["activity_kind"] for row in rows] == ["engage", "attack"]
    assert rows[0]["result"]["encounter_id"] in runtime.encounters
    assert rows[1]["result"]["event"] == "player_attack"
    assert monster.hp <= hp_before
    assert runtime.world.now_ms == 5_000
    assert actor.location_id == WEST


def test_interruptible_stationary_work_preempts_on_relevant_belief_change():
    runtime = HousingAincradRuntime(seed=1005)
    runtime.world.floors[50].unlocked = True
    low_fact = runtime.record_observation(
        AGIL, "routine_ok", True, observation_location_id=AGIL_SHOP
    )
    assert low_fact.value is True
    runtime.set_npc_goal(
        AGIL,
        "routine_wait",
        AGIL_SHOP,
        priority=20,
        required_fact_id="routine_ok",
        scheduled_actions=[{
            "action_kind": "wait",
            "duration_ms": 600_000,
            "payload": {},
            "interruptible": True,
        }],
    )
    runtime.set_npc_goal(
        AGIL,
        "urgent_check",
        AGIL_SHOP,
        priority=100,
        required_fact_id="urgent_signal",
        scheduled_actions=[{
            "action_kind": "investigate",
            "duration_ms": 5_000,
            "payload": {"fact_id": "urgent_checked", "value": True},
        }],
    )
    assert runtime.npc_scheduler_state(AGIL)["activity"]["activity_kind"] == "wait"
    runtime.record_observation(
        AGIL, "urgent_signal", True, observation_location_id=AGIL_SHOP
    )
    state = runtime.npc_scheduler_state(AGIL)
    assert state["current_goal_id"] == "urgent_check"
    assert state["activity"]["activity_kind"] == "investigate"
    interrupted = [r for r in runtime.npc_activity_history if r.get("status") == "interrupted"]
    assert interrupted[-1]["goal_id"] == "routine_wait"


def test_noninterruptible_travel_replans_only_after_reaching_route_node():
    runtime = HousingAincradRuntime(seed=1006)
    runtime.world.floors[50].unlocked = True
    runtime.set_npc_goal(AGIL, "field_trip", "floor_50_field", priority=20)
    assert runtime.npc_scheduler_state(AGIL)["activity"]["activity_kind"] == "travel"
    runtime.set_npc_goal(AGIL, "urgent_algade", "floor_50_algade", priority=100)
    travelling = runtime.npc_scheduler_state(AGIL)
    assert travelling["current_goal_id"] == "field_trip"
    runtime.advance_world(2 * 60_000)
    after_node = runtime.npc_scheduler_state(AGIL)
    assert after_node["current_goal_id"] == "urgent_algade"
    assert after_node["location_id"] == "floor_50_algade"


def test_scheduler_state_and_mid_activity_due_time_survive_save_load():
    runtime = HousingAincradRuntime(seed=1007)
    runtime.world.floors[50].unlocked = True
    runtime.set_npc_goal(
        AGIL,
        "long_inventory_check",
        AGIL_SHOP,
        scheduled_actions=[{
            "action_kind": "investigate",
            "duration_ms": 100_000,
            "payload": {"fact_id": "inventory_checked", "value": True},
        }],
    )
    runtime.advance_world(40_000)
    restored = import_runtime(export_runtime(runtime))
    state = restored.npc_scheduler_state(AGIL)
    assert state["activity"]["due_at_ms"] == 100_000
    assert state["operations"]["long_inventory_check"]["actions"][0]["action_kind"] == "investigate"
    restored.advance_world(60_000)
    belief = restored.belief(AGIL, "inventory_checked")
    assert belief is not None and belief.learned_at_ms == 100_000


def test_ordinary_player_travel_processes_scheduler_due_point_inside_travel_window():
    runtime = HousingAincradRuntime(seed=1008)
    runtime.set_npc_goal(
        TUTOR,
        "brief_pause",
        TOWN,
        scheduled_actions=[{
            "action_kind": "investigate",
            "duration_ms": 30_000,
            "payload": {"fact_id": "half_minute_check", "value": True},
        }],
    )
    player = runtime.create_character("Walker", level=2)
    resolution = runtime.travel_actor(player.actor_id, WEST)
    assert resolution.elapsed_ms > 30_000
    belief = runtime.belief(TUTOR, "half_minute_check")
    assert belief is not None
    assert belief.learned_at_ms == 30_000
    assert runtime.world.now_ms == resolution.elapsed_ms
