import pytest

from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.npc_autonomy_runtime import LOCATION_UNAVAILABLE_FACT_PREFIX, SHOP_RETURN_GOAL_ID
from sao_mcp.runtime.persistence import export_runtime, import_runtime


AGIL = "pc_agil"
AGIL_SHOP = "floor_50_agil_shop"
ALGADE = "floor_50_algade"
FLOOR50_FIELD = "floor_50_field"
SHOP_TO_ALGADE_MS = 2 * 60_000
ALGADE_TO_FIELD_MS = 18 * 60_000


def test_nonmaterialized_npc_goal_routes_concurrently_and_survives_save_load():
    runtime = HousingAincradRuntime(seed=97)
    runtime.world.floors[50].unlocked = True
    player = runtime.create_character("Observer", level=10)
    player.location_id = AGIL_SHOP

    assert runtime.npc_location_id(AGIL) == AGIL_SHOP
    before = runtime.world.now_ms
    agenda = runtime.set_npc_goal(AGIL, "inspect_frontline_route", FLOOR50_FIELD)
    assert runtime.world.now_ms == before
    assert agenda.goal_target_location_id == FLOOR50_FIELD
    assert agenda.target_location_id == ALGADE
    assert agenda.started_at_ms == before
    assert agenda.due_at_ms == before + SHOP_TO_ALGADE_MS
    assert runtime.npc_location_id(AGIL) is None
    with pytest.raises(ValueError, match="same location"):
        runtime.interact_npc(player.actor_id, AGIL)

    runtime.advance_world(60_000)
    assert runtime.npc_agenda_state(AGIL)["active"] is True
    assert runtime.npc_location_id(AGIL) is None

    restored = import_runtime(export_runtime(runtime))
    assert restored.world.now_ms == 60_000
    assert restored.npc_agenda_state(AGIL)["active"] is True
    assert restored.npc_location_id(AGIL) is None

    # One large world-time jump completes the first leg at t=2m, automatically plans
    # Algade -> Floor 50 Field from that historical arrival time, then completes it at t=20m.
    restored.advance_world(19 * 60_000)
    final = restored.npc_agenda_state(AGIL)
    assert final["active"] is False
    assert final["goal_id"] == "inspect_frontline_route"
    assert final["goal_target_location_id"] == FLOOR50_FIELD
    assert final["goal_reached"] is True
    assert final["location_id"] == FLOOR50_FIELD
    assert restored.npcs.states[AGIL].location_id == FLOOR50_FIELD
    assert restored.npc_activity_history == [
        {
            "npc_id": AGIL,
            "goal_id": "inspect_frontline_route",
            "activity_kind": "travel",
            "from_location_id": AGIL_SHOP,
            "to_location_id": ALGADE,
            "started_at_ms": 0,
            "completed_at_ms": SHOP_TO_ALGADE_MS,
            "traversal_tags": [],
        },
        {
            "npc_id": AGIL,
            "goal_id": "inspect_frontline_route",
            "activity_kind": "travel",
            "from_location_id": ALGADE,
            "to_location_id": FLOOR50_FIELD,
            "started_at_ms": SHOP_TO_ALGADE_MS,
            "completed_at_ms": SHOP_TO_ALGADE_MS + ALGADE_TO_FIELD_MS,
            "traversal_tags": [],
        },
    ]


def test_materialized_shop_owner_returns_home_after_manual_displacement():
    runtime = HousingAincradRuntime(seed=101)
    runtime.world.floors[50].unlocked = True
    agil_actor = runtime.create_character("Agil", level=30)
    agil_actor.metadata["npc_definition_id"] = AGIL
    agil_actor.location_id = AGIL_SHOP

    dormant_npc_state_location = runtime.npcs.states[AGIL].location_id
    runtime.schedule_npc_travel(AGIL, ALGADE)

    assert agil_actor.location_id is None
    assert runtime.npc_location_id(AGIL) is None
    assert runtime.npcs.states[AGIL].location_id == dormant_npc_state_location

    runtime.advance_world(SHOP_TO_ALGADE_MS)

    # The manual displacement completes at t=2m. At that historical arrival time the
    # shop-owner role immediately forms a routine goal and starts the return leg.
    routine = runtime.npc_agenda_state(AGIL)
    assert routine["goal_id"] == SHOP_RETURN_GOAL_ID
    assert routine["goal_target_location_id"] == AGIL_SHOP
    assert routine["active"] is True
    assert routine["from_location_id"] == ALGADE
    assert routine["target_location_id"] == AGIL_SHOP
    assert agil_actor.location_id is None
    assert runtime.npcs.states[AGIL].location_id == dormant_npc_state_location

    runtime.advance_world(SHOP_TO_ALGADE_MS)
    assert agil_actor.location_id == AGIL_SHOP
    assert runtime.npc_agenda_state(AGIL)["goal_reached"] is True
    assert runtime.npcs.states[AGIL].location_id == dormant_npc_state_location


def test_shop_owner_routine_depends_on_its_current_belief_about_home():
    runtime = HousingAincradRuntime(seed=103)
    runtime.world.floors[50].unlocked = True
    runtime.npcs.states[AGIL].location_id = ALGADE
    unavailable_fact = f"{LOCATION_UNAVAILABLE_FACT_PREFIX}{AGIL_SHOP}"

    runtime.record_inference(AGIL, unavailable_fact, True, source_id="market_rumor")
    runtime.advance_world(10 * 60_000)

    blocked = runtime.npc_agenda_state(AGIL)
    assert blocked["active"] is False
    assert blocked["goal_id"] is None
    assert blocked["location_id"] == ALGADE

    # The world did not change; only Agil's belief did. The corrected belief changes the
    # next autonomous decision and causes the shop-owner routine to form on the next tick.
    runtime.record_observation(AGIL, unavailable_fact, False, source_id="verified_shop_status")
    runtime.advance_world(1)
    returning = runtime.npc_agenda_state(AGIL)
    assert returning["goal_id"] == SHOP_RETURN_GOAL_ID
    assert returning["goal_target_location_id"] == AGIL_SHOP
    assert returning["active"] is True
    assert returning["location_id"] is None

    runtime.advance_world(SHOP_TO_ALGADE_MS)
    arrived = runtime.npc_agenda_state(AGIL)
    assert arrived["goal_reached"] is True
    assert arrived["location_id"] == AGIL_SHOP
