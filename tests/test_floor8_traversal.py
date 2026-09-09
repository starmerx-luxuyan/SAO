from sao_mcp.corpus.floor8_world import (
    ARBOREAL_ROUTE_TAGS,
    FOREST_ELF_SACRED_WOODS,
    FRIEBEN,
    MANAGED_FOREST_OUTER,
)
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


def test_floor8_arboreal_routes_are_authoritative_on_solo_group_and_reverse_travel():
    runtime = HousingAincradRuntime(seed=311)
    runtime.world.floors[8].unlocked = True
    a = runtime.create_character("ArborealA", level=28)
    b = runtime.create_character("ArborealB", level=28)
    a.location_id = FRIEBEN

    outward = runtime.travel_actor(a.actor_id, MANAGED_FOREST_OUTER)
    assert outward.traversal_tags == ARBOREAL_ROUTE_TAGS
    assert a.location_id == MANAGED_FOREST_OUTER

    b.location_id = MANAGED_FOREST_OUTER
    deeper = travel_together(runtime, [a.actor_id, b.actor_id], FOREST_ELF_SACRED_WOODS)
    assert deeper.traversal_tags == ARBOREAL_ROUTE_TAGS
    assert {a.location_id, b.location_id} == {FOREST_ELF_SACRED_WOODS}

    reverse = travel_together(runtime, [a.actor_id, b.actor_id], MANAGED_FOREST_OUTER)
    assert reverse.traversal_tags == ARBOREAL_ROUTE_TAGS
    assert {a.location_id, b.location_id} == {MANAGED_FOREST_OUTER}


def test_non_floor8_default_connection_keeps_empty_traversal_tags():
    runtime = HousingAincradRuntime(seed=313)
    actor = runtime.create_character("PlainRoute", level=1)
    result = runtime.travel_actor(actor.actor_id, "floor_1_west_field")
    assert result.traversal_tags == ()
