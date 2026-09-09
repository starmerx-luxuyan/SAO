from sao_mcp.corpus.floor8_world import (
    ACORN_SHOP,
    ARBOREAL_ROUTE_TAGS,
    FOREST_ELF_ESCAPE_CAVE,
    FOREST_ELF_ESCAPE_CAVE_MOUTH,
    FOREST_ELF_SACRED_WOODS,
    FRIEBEN,
    MANAGED_FOREST_OUTER,
)
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor8_emergency import install_floor8_forest_emergency_scenario


class _NocturneStub:
    def __init__(self, runtime, player_id):
        self.runtime = runtime
        self.player_id = player_id
        self.stage = "five_key_hideout_recon_on_lake"

    def status(self, instance_id):
        assert instance_id == "floor8_route_nocturne"
        return {"stage": self.stage, "player_ids": [self.player_id]}

    def link_floor8_emergency(self, instance_id, emergency_instance_id, message_id):
        assert instance_id == "floor8_route_nocturne"
        self.stage = "floor8_emergency_received"
        return {"stage": self.stage}

    def assign_floor8_emergency_split(self, instance_id, floor8_actor_ids, hideout_actor_ids):
        assert instance_id == "floor8_route_nocturne"
        assert floor8_actor_ids == [self.player_id]
        assert hideout_actor_ids == []
        self.stage = "parallel_nocturne_branches"
        return {
            "floor8_actor_ids": list(floor8_actor_ids),
            "hideout_actor_ids": list(hideout_actor_ids),
        }


def test_floor8_scenario_persists_executed_route_segments_with_actual_traversal_tags():
    runtime = HousingAincradRuntime(seed=317)
    runtime.world.floors[8].unlocked = True
    runtime.world.floors[8].main_town_gate_active = True
    responder = runtime.create_character("RouteResponder", level=28)
    nocturne = _NocturneStub(runtime, responder.actor_id)
    emergency = install_floor8_forest_emergency_scenario(runtime, nocturne)

    opened = emergency.trigger_from_nocturne("floor8_route_nocturne", responder.actor_id)
    instance_id = opened["instance_id"]
    emergency.assign_response_split(instance_id, [responder.actor_id], [])
    responder.location_id = FRIEBEN
    emergency.arrive_frieben(instance_id)

    met = emergency.meet_argo_and_klein(instance_id)
    assert met["frieben_to_acorn_shop_route"] == [
        {
            "from_location_id": FRIEBEN,
            "to_location_id": ACORN_SHOP,
            "elapsed_ms": 5 * 60_000,
            "newly_discovered": True,
            "traversal_tags": ["safe_town_route", "multi_level_access"],
        }
    ]
    assert met["frieben_to_acorn_shop_ms"] == 5 * 60_000

    woods = emergency.depart_acorn_shop_to_sacred_woods(instance_id)
    route = woods["acorn_shop_to_sacred_woods_route"]
    assert [(row["from_location_id"], row["to_location_id"]) for row in route] == [
        (ACORN_SHOP, FRIEBEN),
        (FRIEBEN, MANAGED_FOREST_OUTER),
        (MANAGED_FOREST_OUTER, FOREST_ELF_SACRED_WOODS),
    ]
    assert route[0]["traversal_tags"] == ["safe_town_route", "multi_level_access"]
    assert route[1]["traversal_tags"] == list(ARBOREAL_ROUTE_TAGS)
    assert route[2]["traversal_tags"] == list(ARBOREAL_ROUTE_TAGS)
    assert woods["acorn_shop_to_sacred_woods_ms"] == sum(row["elapsed_ms"] for row in route)
    assert woods["acorn_shop_to_sacred_woods_ms"] == 35 * 60_000

    emergency.inspect_sacred_woods_incident(instance_id)
    mouth = emergency.follow_to_escape_cave_mouth(instance_id)
    assert mouth["incident"]["sacred_woods_to_cave_mouth_route"] == [
        {
            "from_location_id": FOREST_ELF_SACRED_WOODS,
            "to_location_id": FOREST_ELF_ESCAPE_CAVE_MOUTH,
            "elapsed_ms": 6 * 60_000,
            "newly_discovered": True,
            "traversal_tags": list(ARBOREAL_ROUTE_TAGS),
        }
    ]

    inside = emergency.enter_escape_cave(instance_id)
    assert inside["incident"]["cave_mouth_to_cave_route"] == [
        {
            "from_location_id": FOREST_ELF_ESCAPE_CAVE_MOUTH,
            "to_location_id": FOREST_ELF_ESCAPE_CAVE,
            "elapsed_ms": 2 * 60_000,
            "newly_discovered": True,
            "traversal_tags": ["cave_entry"],
        }
    ]

    restored = import_runtime(export_runtime(runtime))
    restored_emergency = install_floor8_forest_emergency_scenario(
        restored,
        _NocturneStub(restored, responder.actor_id),
    )
    persisted = restored_emergency.status(instance_id)
    assert persisted["frieben_to_acorn_shop_route"] == met["frieben_to_acorn_shop_route"]
    assert persisted["acorn_shop_to_sacred_woods_route"] == route
    assert persisted["incident"]["sacred_woods_to_cave_mouth_route"] == mouth["incident"]["sacred_woods_to_cave_mouth_route"]
    assert persisted["incident"]["cave_mouth_to_cave_route"] == inside["incident"]["cave_mouth_to_cave_route"]
