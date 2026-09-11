import pytest

from sao_mcp.rules.npc_actor_core import NPCGoalSource
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.npc_autonomy_runtime import LOCATION_UNAVAILABLE_FACT_PREFIX, SHOP_RETURN_GOAL_ID
from sao_mcp.runtime.persistence import export_runtime, import_runtime


AGIL = "pc_agil"
AGIL_SHOP = "floor_50_agil_shop"
ALGADE = "floor_50_algade"
FLOOR50_FIELD = "floor_50_field"
SHOP_TO_ALGADE_MS = 2 * 60_000
ALGADE_TO_FIELD_MS = 18 * 60_000


def test_nonmaterialized_npc_actor_core_plans_route_and_survives_save_load():
    runtime = HousingAincradRuntime(seed=97)
    runtime.world.floors[50].unlocked = True
    player = runtime.create_character("Observer", level=10)
    player.location_id = AGIL_SHOP

    assert runtime.npc_location_id(AGIL) == AGIL_SHOP
    before = runtime.world.now_ms
    core = runtime.set_npc_goal(AGIL, "inspect_frontline_route", FLOOR50_FIELD)
    assert runtime.world.now_ms == before
    assert core.current_goal_id == "inspect_frontline_route"
    assert core.current_business_id == "pursue:inspect_frontline_route"
    assert [step.target_location_id for step in core.short_term_plan] == [ALGADE, FLOOR50_FIELD]
    assert core.current_plan_step.target_location_id == ALGADE

    agenda = runtime.npc_agenda_state(AGIL)
    assert agenda["goal_target_location_id"] == FLOOR50_FIELD
    assert agenda["target_location_id"] == ALGADE
    assert agenda["started_at_ms"] == before
    assert agenda["due_at_ms"] == before + SHOP_TO_ALGADE_MS
    assert agenda["plan_step_id"] == core.current_plan_step.step_id
    assert runtime.npc_location_id(AGIL) is None
    with pytest.raises(ValueError, match="same location"):
        runtime.interact_npc(player.actor_id, AGIL)

    runtime.advance_world(60_000)
    assert runtime.npc_agenda_state(AGIL)["active"] is True

    restored = import_runtime(export_runtime(runtime))
    restored_core = restored.npc_actor_core_state(AGIL)
    assert restored.world.now_ms == 60_000
    assert restored_core["current_goal_id"] == "inspect_frontline_route"
    assert restored_core["current_business_id"] == "pursue:inspect_frontline_route"
    assert restored_core["active"] is True
    assert restored.npc_location_id(AGIL) is None

    restored.advance_world(19 * 60_000)
    final = restored.npc_actor_core_state(AGIL)
    assert final["active"] is False
    assert final["current_goal_id"] == "inspect_frontline_route"
    assert final["goal_target_location_id"] == FLOOR50_FIELD
    assert final["goal_reached"] is True
    assert final["location_id"] == FLOOR50_FIELD
    assert restored.npcs.states[AGIL].location_id == FLOOR50_FIELD
    assert [row["to_location_id"] for row in restored.npc_activity_history] == [ALGADE, FLOOR50_FIELD]
    assert all(row["goal_id"] == "inspect_frontline_route" for row in restored.npc_activity_history)
    assert all(row["business_id"] == "pursue:inspect_frontline_route" for row in restored.npc_activity_history)
    assert all(row["plan_step_id"] for row in restored.npc_activity_history)


def test_materialized_shop_owner_role_goal_returns_home_after_manual_displacement():
    runtime = HousingAincradRuntime(seed=101)
    runtime.world.floors[50].unlocked = True
    agil_actor = runtime.create_character("Agil", level=30)
    agil_actor.metadata["npc_definition_id"] = AGIL
    agil_actor.location_id = AGIL_SHOP

    role_goal = runtime.npc_actor_cores[AGIL].long_term_goals[SHOP_RETURN_GOAL_ID]
    assert role_goal.source is NPCGoalSource.ROLE
    assert role_goal.business_id == "operate_shop"

    dormant_npc_state_location = runtime.npcs.states[AGIL].location_id
    runtime.schedule_npc_travel(AGIL, ALGADE)
    assert agil_actor.location_id is None
    assert runtime.npc_location_id(AGIL) is None

    runtime.advance_world(SHOP_TO_ALGADE_MS)
    routine = runtime.npc_actor_core_state(AGIL)
    assert routine["current_goal_id"] == SHOP_RETURN_GOAL_ID
    assert routine["current_business_id"] == "operate_shop"
    assert routine["goal_target_location_id"] == AGIL_SHOP
    assert routine["active"] is True
    assert routine["activity"]["from_location_id"] == ALGADE
    assert routine["activity"]["target_location_id"] == AGIL_SHOP
    assert agil_actor.location_id is None
    assert runtime.npcs.states[AGIL].location_id == dormant_npc_state_location

    runtime.advance_world(SHOP_TO_ALGADE_MS)
    arrived = runtime.npc_actor_core_state(AGIL)
    assert agil_actor.location_id == AGIL_SHOP
    assert arrived["goal_reached"] is True
    assert arrived["current_business_id"] == "operate_shop"


def test_actor_core_goal_can_be_gated_by_current_npc_belief():
    runtime = HousingAincradRuntime(seed=103)
    runtime.world.floors[50].unlocked = True
    fact_id = "frontline_route_verified"

    runtime.set_npc_goal(
        AGIL,
        "inspect_verified_frontline",
        FLOOR50_FIELD,
        required_fact_id=fact_id,
        required_fact_value=True,
    )
    blocked = runtime.npc_actor_core_state(AGIL)
    assert blocked["long_term_goals"]["inspect_verified_frontline"]["eligible"] is False
    assert blocked["current_goal_id"] == SHOP_RETURN_GOAL_ID
    assert blocked["active"] is False

    observed = runtime.record_observation(
        AGIL,
        fact_id,
        True,
        observation_location_id=AGIL_SHOP,
        source_id="verified_route_report",
    )
    runtime.advance_world(1)
    selected = runtime.npc_actor_core_state(AGIL)
    assert selected["current_goal_id"] == "inspect_verified_frontline"
    assert selected["decision_basis_fact_ids"] == [fact_id]
    assert selected["decision_basis_event_ids"] == [observed.event_id]
    assert selected["decision_beliefs"][fact_id]["event_id"] == observed.event_id
    assert selected["decision_beliefs"][fact_id]["value"] is True
    assert selected["active"] is True


def test_actor_core_goal_can_be_gated_by_relationship_score():
    runtime = HousingAincradRuntime(seed=105)
    runtime.world.floors[50].unlocked = True
    player = runtime.create_character("Trusted Scout", level=10)

    runtime.set_npc_goal(
        AGIL,
        "meet_trusted_scout_route",
        ALGADE,
        relationship_actor_id=player.actor_id,
        min_relationship=100,
    )
    blocked = runtime.npc_actor_core_state(AGIL)
    assert blocked["long_term_goals"]["meet_trusted_scout_route"]["eligible"] is False
    assert blocked["current_goal_id"] == SHOP_RETURN_GOAL_ID

    runtime.npcs.adjust_relationship(player.actor_id, AGIL, 140)
    runtime.advance_world(1)
    selected = runtime.npc_actor_core_state(AGIL)
    assert selected["current_goal_id"] == "meet_trusted_scout_route"
    assert selected["decision_relation_actor_ids"] == [player.actor_id]
    assert selected["decision_relationships"][player.actor_id] == 140
    assert selected["active"] is True


def test_actor_core_resource_requirements_read_materialized_authoritative_resources():
    runtime = HousingAincradRuntime(seed=107)
    runtime.world.floors[50].unlocked = True
    agil_actor = runtime.create_character("Agil", level=30)
    agil_actor.metadata["npc_definition_id"] = AGIL
    agil_actor.location_id = AGIL_SHOP
    agil_actor.col = 0

    runtime.set_npc_goal(
        AGIL,
        "fund_market_trip",
        ALGADE,
        resource_requirements={"col": 50},
    )
    blocked = runtime.npc_actor_core_state(AGIL)
    assert blocked["resources"]["materialized"] is True
    assert blocked["resources"]["col"] == 0
    assert blocked["long_term_goals"]["fund_market_trip"]["eligible"] is False
    assert blocked["current_goal_id"] == SHOP_RETURN_GOAL_ID

    agil_actor.col = 80
    runtime.advance_world(1)
    selected = runtime.npc_actor_core_state(AGIL)
    assert selected["resources"]["col"] == 80
    assert selected["current_goal_id"] == "fund_market_trip"
    assert selected["active"] is True


def test_shop_owner_routine_depends_on_current_belief_about_home():
    runtime = HousingAincradRuntime(seed=109)
    runtime.world.floors[50].unlocked = True
    runtime.npcs.states[AGIL].location_id = ALGADE
    unavailable_fact = f"{LOCATION_UNAVAILABLE_FACT_PREFIX}{AGIL_SHOP}"

    rumor = runtime.record_observation(
        AGIL,
        "market_rumor:shop_unavailable",
        True,
        observation_location_id=ALGADE,
        source_id="market_rumor",
        confidence=0.6,
    )
    runtime.record_inference(
        AGIL,
        unavailable_fact,
        True,
        evidence_fact_ids=[rumor.fact_id],
        source_id="merchant_judgment",
    )
    runtime.advance_world(10 * 60_000)
    blocked = runtime.npc_actor_core_state(AGIL)
    assert blocked["active"] is False
    assert blocked["current_goal_id"] is None
    assert blocked["location_id"] == ALGADE

    runtime.record_observation(
        AGIL,
        unavailable_fact,
        False,
        observation_location_id=ALGADE,
        source_id="verified_shop_status",
    )
    runtime.advance_world(1)
    returning = runtime.npc_actor_core_state(AGIL)
    assert returning["current_goal_id"] == SHOP_RETURN_GOAL_ID
    assert returning["current_business_id"] == "operate_shop"
    assert returning["active"] is True
    assert returning["location_id"] is None

    runtime.advance_world(SHOP_TO_ALGADE_MS)
    arrived = runtime.npc_actor_core_state(AGIL)
    assert arrived["goal_reached"] is True
    assert arrived["location_id"] == AGIL_SHOP


def test_agenda_is_execution_only_and_cannot_own_goal_state():
    runtime = HousingAincradRuntime(seed=111)
    runtime.world.floors[50].unlocked = True
    runtime.set_npc_goal(AGIL, "inspect_frontline_route", FLOOR50_FIELD)

    agenda = runtime.npc_agendas[AGIL]
    assert not hasattr(agenda, "goal_id")
    assert not hasattr(agenda, "goal_target_location_id")
    projected = runtime.npc_agenda_state(AGIL)
    assert projected["goal_id"] == "inspect_frontline_route"
    assert projected["goal_target_location_id"] == FLOOR50_FIELD


def test_reached_goal_does_not_rebuild_identical_plan_every_world_tick():
    runtime = HousingAincradRuntime(seed=113)
    runtime.world.floors[50].unlocked = True
    runtime.set_npc_goal(AGIL, "visit_algade_once", ALGADE)
    runtime.advance_world(SHOP_TO_ALGADE_MS)
    core = runtime.npc_actor_cores[AGIL]
    assert runtime.npc_actor_core_state(AGIL)["goal_reached"] is True
    revision = core.revision
    runtime.advance_world(60_000)
    assert core.revision == revision
