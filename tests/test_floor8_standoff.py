from sao_mcp.corpus.floor8_world import (
    FOREST_ELF_ESCAPE_CAVE,
    FOREST_ELF_ESCAPE_CAVE_MOUTH,
    FOREST_ELF_SACRED_WOODS,
    FRIEBEN,
    SLUVA,
)
from sao_mcp.domain.models import CursorColor, DefenseMode, ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor8_emergency import install_floor8_forest_emergency_scenario
from sao_mcp.scenarios.floor8_standoff import install_floor8_cave_standoff_scenario


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
    emergency.depart_frieben_to_sacred_woods(instance_id)
    emergency.inspect_sacred_woods_incident(instance_id)
    emergency.follow_to_escape_cave_mouth(instance_id)
    emergency.enter_escape_cave(instance_id)
    assert emergency.status(instance_id)["stage"] == "responders_inside_cave_standoff"
    standoff = install_floor8_cave_standoff_scenario(runtime, emergency)
    return runtime, nocturne, emergency, standoff, instance_id, responder


def test_cave_standoff_restitution_requires_explicit_offer_and_forest_elf_leader_acceptance():
    runtime, nocturne, emergency, standoff, instance_id, responder = _make_live_standoff()
    state = emergency._state(instance_id)
    forest_leader_id = runtime.world.parties[state["incident"]["forest_elf_party_id"]].leader_id
    forest_leader = runtime.actors[forest_leader_id]
    responder.col = 5_000
    leader_before = forest_leader.col

    offered = standoff.offer_restitution(instance_id, responder.actor_id, responder.actor_id, 1_200)
    assert offered["stage"] == "restitution_offered"
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
    assert responder.col == 3_500
    assert forest_leader.col == leader_before + 1_500
    assert all(
        runtime.actors[actor_id].location_id == FOREST_ELF_SACRED_WOODS
        for actor_id in state["incident"]["forest_elf_actor_ids"]
    )
    assert all(
        runtime.actors[actor_id].location_id == FOREST_ELF_ESCAPE_CAVE
        for actor_id in state["incident"]["frontline_actor_ids"]
    )

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    restored_nocturne = _NocturneStub(restored, [responder.actor_id])
    restored_emergency = install_floor8_forest_emergency_scenario(restored, restored_nocturne)
    restored_standoff = install_floor8_cave_standoff_scenario(restored, restored_emergency)
    persisted = restored_standoff.status(instance_id)
    assert persisted["stage"] == "standoff_resolved_restitution"
    assert persisted["accepted_restitution"]["col_amount"] == 1_500
    assert restored.actors[responder.actor_id].col == 3_500


def test_cave_standoff_can_resolve_by_real_frontline_custody_transfer_to_sluva():
    runtime, nocturne, emergency, standoff, instance_id, responder = _make_live_standoff(seed=223)
    state = emergency._state(instance_id)
    frontline_ids = list(state["incident"]["frontline_actor_ids"])
    forest_ids = list(state["incident"]["forest_elf_actor_ids"])
    started = runtime.world.now_ms

    result = standoff.surrender_incident_players_to_custody(instance_id, responder.actor_id)

    assert result["stage"] == "standoff_resolved_custody"
    assert runtime.world.now_ms - started == 24 * 60_000
    assert set(result["custody_actor_ids"]) == set(frontline_ids)
    assert all(runtime.actors[actor_id].location_id == SLUVA for actor_id in frontline_ids + forest_ids)
    assert all(runtime.actors[actor_id].metadata["forest_elf_custody"] is True for actor_id in frontline_ids)
    assert responder.location_id == FOREST_ELF_ESCAPE_CAVE


def test_cave_standoff_can_escalate_into_ordinary_combat_and_resolve_only_after_real_defeat():
    runtime, nocturne, emergency, standoff, instance_id, responder = _make_live_standoff(seed=227)
    state = emergency._state(instance_id)
    forest_ids = list(state["incident"]["forest_elf_actor_ids"])
    before_combat = runtime.world.now_ms

    combat = standoff.start_cave_mouth_combat(instance_id, [responder.actor_id])
    encounter_id = combat["cave_combat_encounter_id"]
    encounter = runtime.encounters[encounter_id]
    assert runtime.world.now_ms - before_combat == 2 * 60_000
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
    assert all(runtime.actors[actor_id].alive is False for actor_id in forest_ids)
    assert responder.cursor is CursorColor.GREEN
