import pytest

from sao_mcp.corpus.floor8_world import (
    ARBOREAL_ROUTE_TAGS,
    FOREST_ELF_ESCAPE_CAVE,
    FOREST_ELF_ESCAPE_CAVE_MOUTH,
    FOREST_ELF_SACRED_WOODS,
    FRIEBEN,
    SLUVA,
)
from sao_mcp.domain.models import CursorColor, DefenseMode, ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.travel import AUTONOMOUS_TRAVEL_RESTRICTION_KEY
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor8_emergency import install_floor8_forest_emergency_scenario
from sao_mcp.scenarios.floor8_standoff import (
    FOREST_ELF_CUSTODY_RESTRICTION,
    install_floor8_cave_standoff_scenario,
)


class _NocturneStub:
    def __init__(self, runtime, player_ids):
        self.runtime = runtime
        self.player_ids = list(player_ids)
        self.stage = "five_key_hideout_recon_on_lake"
        self.emergency_instance_id = None
        self.message_id = None

    def status(self, instance_id):
        assert instance_id == "nocturne_standoff_fixture"
        return {"stage": self.stage, "player_ids": list(self.player_ids)}

    def link_floor8_emergency(self, instance_id, emergency_instance_id, message_id):
        assert instance_id == "nocturne_standoff_fixture"
        assert self.stage == "five_key_hideout_recon_on_lake"
        self.emergency_instance_id = emergency_instance_id
        self.message_id = message_id
        self.stage = "floor8_emergency_received"
        return {"stage": self.stage}

    def assign_floor8_emergency_split(self, instance_id, floor8_actor_ids, hideout_actor_ids):
        assert instance_id == "nocturne_standoff_fixture"
        assert self.stage == "floor8_emergency_received"
        assert set(floor8_actor_ids) | set(hideout_actor_ids) == set(self.player_ids)
        assert not (set(floor8_actor_ids) & set(hideout_actor_ids))
        self.stage = "parallel_nocturne_branches"
        return {
            "floor8_actor_ids": list(floor8_actor_ids),
            "hideout_actor_ids": list(hideout_actor_ids),
        }


def _teleport_to_frieben(runtime, actor):
    crystal = ItemInstance(
        instance_id=f"standoff_crystal_{actor.actor_id}",
        template_id="teleport_crystal",
        owner_id=actor.actor_id,
        quantity=1,
    )
    add_item(actor, crystal, runtime.catalog, allow_overweight=True)
    runtime.teleport_actor(actor.actor_id, crystal.instance_id, FRIEBEN)


def _make_live_standoff(seed=211):
    runtime = HousingAincradRuntime(seed=seed)
    runtime.world.floors[8].unlocked = True
    runtime.world.floors[8].main_town_gate_active = True
    responder = runtime.create_character("StandoffMediator", level=28)
    responder.skill_proficiencies["one_hand_sword"] = 1000.0
    nocturne = _NocturneStub(runtime, [responder.actor_id])
    emergency = install_floor8_forest_emergency_scenario(runtime, nocturne)
    notice = emergency.trigger_from_nocturne("nocturne_standoff_fixture", responder.actor_id)
    instance_id = notice["instance_id"]
    emergency.assign_response_split(instance_id, [responder.actor_id], [])
    _teleport_to_frieben(runtime, responder)
    emergency.arrive_frieben(instance_id)
    emergency.meet_argo_and_klein(instance_id)
    emergency.depart_acorn_shop_to_sacred_woods(instance_id)
    emergency.inspect_sacred_woods_incident(instance_id)
    emergency.follow_to_escape_cave_mouth(instance_id)
    emergency.enter_escape_cave(instance_id)
    assert emergency.status(instance_id)["stage"] == "responders_inside_cave_standoff"
    standoff = install_floor8_cave_standoff_scenario(runtime, emergency)
    return runtime, nocturne, emergency, standoff, instance_id, responder


def test_cave_standoff_restitution_requires_explicit_offer_and_forest_elf_leader_acceptance():
    runtime, nocturne, emergency, standoff, instance_id, responder = _make_live_standoff()
    state = emergency._state(instance_id)
    representative_ids = list(state["incident"]["frontline_actor_ids"])
    forest_leader_id = runtime.world.parties[state["incident"]["forest_elf_party_id"]].leader_id
    forest_leader = runtime.actors[forest_leader_id]
    responder.col = 5_000
    leader_before = forest_leader.col

    offered = standoff.offer_restitution(instance_id, responder.actor_id, responder.actor_id, 1_200)
    assert offered["stage"] == "restitution_offered"
    assert offered["local_standoff_resolution"] == {
        "scope": "materialized_local_standoff_only",
        "outcome": None,
    }
    assert responder.col == 5_000
    assert forest_leader.col == leader_before
    assert offered["pending_restitution"]["col_amount"] == 1_200

    rejected = standoff.reject_restitution(instance_id, forest_leader_id)
    assert rejected["stage"] == "responders_inside_cave_standoff"
    assert responder.col == 5_000
    assert forest_leader.col == leader_before
    assert rejected["last_rejected_restitution"]["col_amount"] == 1_200

    standoff.offer_restitution(instance_id, responder.actor_id, responder.actor_id, 1_500)
    accepted = standoff.accept_restitution(instance_id, forest_leader_id)
    assert accepted["stage"] == "standoff_resolved_restitution"
    assert accepted["local_standoff_resolution"] == {
        "scope": "materialized_local_standoff_only",
        "outcome": "restitution_accepted_by_local_pursuit_party",
    }
    assert accepted["guild_crisis_report"]["affected_member_scope"] == "majority_of_each_guild"
    withdrawal = accepted["accepted_restitution"]["withdrawal_route"]
    assert len(withdrawal) == 1
    assert withdrawal[0]["actor_ids"] == list(state["incident"]["forest_elf_actor_ids"])
    assert withdrawal[0]["from_location_id"] == FOREST_ELF_ESCAPE_CAVE_MOUTH
    assert withdrawal[0]["to_location_id"] == FOREST_ELF_SACRED_WOODS
    assert withdrawal[0]["elapsed_ms"] == 6 * 60_000
    assert withdrawal[0]["traversal_tags"] == list(ARBOREAL_ROUTE_TAGS)
    assert responder.col == 3_500
    assert forest_leader.col == leader_before + 1_500
    assert all(
        runtime.actors[actor_id].location_id == FOREST_ELF_SACRED_WOODS
        for actor_id in state["incident"]["forest_elf_actor_ids"]
    )
    assert all(
        runtime.actors[actor_id].location_id == FOREST_ELF_ESCAPE_CAVE
        for actor_id in representative_ids
    )
    assert all(
        runtime.actors[actor_id].metadata["floor8_local_standoff_resolution"] == "restitution"
        for actor_id in representative_ids
    )
    assert all(
        "floor8_forest_elf_claim_settled" not in runtime.actors[actor_id].metadata
        for actor_id in representative_ids
    )

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    restored_nocturne = _NocturneStub(restored, [responder.actor_id])
    restored_emergency = install_floor8_forest_emergency_scenario(restored, restored_nocturne)
    restored_standoff = install_floor8_cave_standoff_scenario(restored, restored_emergency)
    persisted = restored_standoff.status(instance_id)
    assert persisted["stage"] == "standoff_resolved_restitution"
    assert persisted["accepted_restitution"]["col_amount"] == 1_500
    assert persisted["accepted_restitution"]["withdrawal_route"] == withdrawal
    assert persisted["local_standoff_resolution"]["scope"] == "materialized_local_standoff_only"
    assert restored.actors[responder.actor_id].col == 3_500


def test_cave_standoff_can_transfer_only_local_representatives_to_sluva_custody():
    runtime, nocturne, emergency, standoff, instance_id, responder = _make_live_standoff(seed=223)
    state = emergency._state(instance_id)
    representative_ids = list(state["incident"]["frontline_actor_ids"])
    forest_ids = list(state["incident"]["forest_elf_actor_ids"])
    started = runtime.world.now_ms

    result = standoff.surrender_local_representatives_to_custody(instance_id, responder.actor_id)

    assert result["stage"] == "standoff_resolved_custody"
    assert result["local_standoff_resolution"] == {
        "scope": "materialized_local_standoff_only",
        "outcome": "materialized_representatives_in_sluva_custody",
    }
    assert result["guild_crisis_report"]["affected_member_scope"] == "majority_of_each_guild"
    route = result["custody_transfer_route"]
    assert [(segment["from_location_id"], segment["to_location_id"], segment["elapsed_ms"]) for segment in route] == [
        (FOREST_ELF_ESCAPE_CAVE, FOREST_ELF_ESCAPE_CAVE_MOUTH, 2 * 60_000),
        (FOREST_ELF_ESCAPE_CAVE_MOUTH, FOREST_ELF_SACRED_WOODS, 6 * 60_000),
        (FOREST_ELF_SACRED_WOODS, SLUVA, 16 * 60_000),
    ]
    assert route[0]["actor_ids"] == representative_ids
    assert route[1]["actor_ids"] == representative_ids + forest_ids
    assert route[2]["actor_ids"] == representative_ids + forest_ids
    assert route[0]["traversal_tags"] == ["cave_entry"]
    assert route[1]["traversal_tags"] == list(ARBOREAL_ROUTE_TAGS)
    assert route[2]["traversal_tags"] == list(ARBOREAL_ROUTE_TAGS + ("managed_inner_forest",))
    assert runtime.world.now_ms - started == sum(segment["elapsed_ms"] for segment in route) == 24 * 60_000
    assert set(result["custody_actor_ids"]) == set(representative_ids)
    assert all(runtime.actors[actor_id].location_id == SLUVA for actor_id in representative_ids + forest_ids)
    assert all(
        runtime.actor_custody_state(actor_id)["restriction_code"] == FOREST_ELF_CUSTODY_RESTRICTION
        and runtime.actor_custody_state(actor_id)["case_id"] == f"floor8_sluva:{instance_id}"
        for actor_id in representative_ids
    )
    assert all(
        AUTONOMOUS_TRAVEL_RESTRICTION_KEY not in runtime.actors[actor_id].metadata
        and "forest_elf_custody_location_id" not in runtime.actors[actor_id].metadata
        for actor_id in representative_ids
    )
    assert responder.location_id == FOREST_ELF_ESCAPE_CAVE

    detainee = runtime.actors[representative_ids[0]]
    blocked_at = runtime.world.now_ms
    with pytest.raises(ValueError, match="autonomous travel is restricted by forest_elf_custody"):
        runtime.travel_actor(detainee.actor_id, FOREST_ELF_SACRED_WOODS)
    assert runtime.world.now_ms == blocked_at
    assert detainee.location_id == SLUVA

    crystal = ItemInstance(
        instance_id=f"custody_crystal_{detainee.actor_id}",
        template_id="teleport_crystal",
        owner_id=detainee.actor_id,
        quantity=1,
    )
    add_item(detainee, crystal, runtime.catalog, allow_overweight=True)
    with pytest.raises(ValueError, match="autonomous travel is restricted by forest_elf_custody"):
        runtime.teleport_actor(detainee.actor_id, crystal.instance_id, FRIEBEN)
    assert detainee.location_id == SLUVA
    assert detainee.inventory[crystal.instance_id].quantity == 1


def test_cave_standoff_can_escalate_into_ordinary_combat_and_resolve_only_local_encounter():
    runtime, nocturne, emergency, standoff, instance_id, responder = _make_live_standoff(seed=227)
    state = emergency._state(instance_id)
    forest_ids = list(state["incident"]["forest_elf_actor_ids"])
    before_combat = runtime.world.now_ms

    combat = standoff.start_cave_mouth_combat(instance_id, [responder.actor_id])
    encounter_id = combat["cave_combat_encounter_id"]
    encounter = runtime.encounters[encounter_id]
    approach = combat["cave_combat_approach_route"]
    assert approach == [
        {
            "actor_ids": [responder.actor_id],
            "from_location_id": FOREST_ELF_ESCAPE_CAVE,
            "to_location_id": FOREST_ELF_ESCAPE_CAVE_MOUTH,
            "elapsed_ms": 2 * 60_000,
            "newly_discovered": False,
            "traversal_tags": ["cave_entry"],
        }
    ]
    assert runtime.world.now_ms - before_combat == sum(segment["elapsed_ms"] for segment in approach)
    assert responder.location_id == FOREST_ELF_ESCAPE_CAVE_MOUTH
    assert set(encounter.participants) == {responder.actor_id, *forest_ids}

    for index, forest_id in enumerate(forest_ids):
        target = runtime.actors[forest_id]
        target.hp = 1
        target.evasion = 0
        if index:
            wait_ms = max(0, responder.recovery_until_ms - encounter.time_ms)
            if wait_ms:
                runtime.advance_encounter(encounter_id, wait_ms)
        attack = runtime.attack(
            encounter_id,
            responder.actor_id,
            forest_id,
            defense=DefenseMode.NONE,
            seed=1,
        )
        assert attack.legal and attack.hit
        assert target.alive is False

    resolved = standoff.resolve_cave_mouth_combat(instance_id)
    assert resolved["stage"] == "standoff_resolved_forest_elves_defeated"
    assert resolved["cave_combat_outcome"] == "forest_elf_pursuit_party_defeated"
    assert resolved["local_standoff_resolution"] == {
        "scope": "materialized_local_standoff_only",
        "outcome": "local_forest_elf_pursuit_party_defeated",
    }
    assert resolved["guild_crisis_report"]["affected_member_scope"] == "majority_of_each_guild"
    assert all(runtime.actors[actor_id].alive is False for actor_id in forest_ids)
    assert responder.cursor is CursorColor.GREEN
