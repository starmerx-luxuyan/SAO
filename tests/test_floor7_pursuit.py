from sao_mcp.corpus.floor6_elfwar import KYSARAH_ID, SACRED_KEY_BAG_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor7_elfwar import PALACE, VOLUPTA, install_floor7_elfwar_scenario
from sao_mcp.scenarios.floor7_pursuit import (
    BOSS_ROOM,
    CASINO,
    FIELD_OF_BONES,
    LABYRINTH,
    TRAIL_MARGIN_MS,
    install_floor7_pursuit_scenario,
)


def _finish_harin_escape(runtime, elfwar, player_ids):
    state = elfwar.arrive_and_be_arrested(player_ids)
    instance_id = state["instance_id"]
    elfwar.burn_cell_lock(instance_id)
    elfwar.recover_confiscated_weapons(instance_id)
    elfwar.meet_lavik(instance_id)
    elfwar.lavik_subdues_guard_post(instance_id)
    elfwar.rejoin_kizmel(instance_id)
    elfwar.convince_kizmel_to_escape(instance_id)
    elfwar.blackout_and_escape(instance_id)
    elfwar.gather_narsos_and_part_with_lavik(instance_id, player_ids[0])
    return elfwar.return_to_volupta_with_kizmel(instance_id)


def _seed_kysarah_key_bag(runtime):
    kysarah = CombatantState(
        actor_id="fixture_kysarah_floor7",
        name="Kysarah",
        kind=EntityKind.NPC,
        level=30,
        max_hp=8000,
        hp=8000,
        strength=70,
        agility=72,
        cursor=CursorColor.YELLOW,
        location_id="floor_7_field",
        metadata={"npc_definition_id": KYSARAH_ID},
    )
    runtime.actors[kysarah.actor_id] = kysarah
    bag = ItemInstance(
        instance_id="fixture_four_sacred_keys",
        template_id=SACRED_KEY_BAG_ID,
        owner_id=kysarah.actor_id,
        metadata={"stolen_by_kysarah": True},
    )
    add_item(kysarah, bag, runtime.catalog, allow_overweight=True)
    return kysarah, bag


def _setup(seed=83):
    runtime = HousingAincradRuntime(seed=seed)
    runtime.world.floors[7].unlocked = True
    elfwar = install_floor7_elfwar_scenario(runtime)
    pursuit = install_floor7_pursuit_scenario(runtime)

    a = runtime.create_character("PursuerA", level=27)
    b = runtime.create_character("PursuerB", level=27)
    a.location_id = PALACE
    b.location_id = PALACE
    harin = _finish_harin_escape(runtime, elfwar, [a.actor_id, b.actor_id])
    instance_id = harin["instance_id"]
    kizmel = runtime.actors[elfwar._state(instance_id)["kizmel_actor_id"]]

    kysarah, bag = _seed_kysarah_key_bag(runtime)
    runtime.world.global_flags.setdefault("floor7_casino_intrigue_states", {})[a.actor_id] = {
        "true_species_revealed": True,
    }

    travel_together(runtime, [a.actor_id, b.actor_id], CASINO)
    state = pursuit.negotiate_scyia_counteroffer(a.actor_id, b.actor_id)

    assert state["instance_id"] == instance_id
    assert elfwar._state(instance_id)["stage"] == "scyia_counteroffer_accepted"
    assert a.location_id == VOLUPTA
    assert b.location_id == VOLUPTA
    assert kizmel.location_id == VOLUPTA
    assert bag.instance_id in kysarah.inventory
    return runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag


def _reach_blocker_encounter(seed=83):
    runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag = _setup(seed)
    before_depart = runtime.world.now_ms
    state = pursuit.rest_and_reach_dragon_bone_watch(instance_id)
    expected = state["pursuit"]["field_of_bones_travel_ms"] + 30 * 60_000
    assert runtime.world.now_ms - before_depart == expected
    assert {a.location_id, b.location_id, kizmel.location_id} == {FIELD_OF_BONES}

    pursuit.observe_fallen_departure(instance_id)
    pursuit.pursue_to_ant_tunnel_valley(instance_id)
    state = pursuit.follow_through_valley_into_labyrinth(instance_id)
    assert {a.location_id, b.location_id, kizmel.location_id} == {LABYRINTH}
    assert len(state["blockers"]) == 2
    return runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag, state["blocker_encounter_id"]


def _defeat_blockers(runtime, pursuit, instance_id, encounter_id, elapsed_ms):
    encounter = runtime.encounters[encounter_id]
    state = pursuit.status(instance_id)
    for blocker_id in state["pursuit"]["blocker_actor_ids"]:
        blocker = encounter.participants[blocker_id]
        blocker.hp = 0
        blocker.alive = False
    runtime.advance_encounter(encounter_id, elapsed_ms)
    return pursuit.resolve_labyrinth_pursuit(instance_id)


def test_floor7_pursuit_uses_harin_state_real_key_bag_and_shared_travel_time():
    runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag, encounter_id = _reach_blocker_encounter()
    before_resolution = runtime.world.now_ms
    state = _defeat_blockers(runtime, pursuit, instance_id, encounter_id, TRAIL_MARGIN_MS - 1)

    assert state["trail_outcome"] == "maintained"
    assert runtime.world.now_ms - before_resolution == TRAIL_MARGIN_MS - 1
    assert bag.instance_id in kysarah.inventory
    assert state["target_key_bag_matches"] == [
        {
            "owner_id": kysarah.actor_id,
            "owner_npc_definition_id": KYSARAH_ID,
            "stolen_by_kysarah": True,
        }
    ]

    state = pursuit.advance_to_boss_room(instance_id)
    assert state["ready_for_aghyellr"] is True
    assert {a.location_id, b.location_id, kizmel.location_id} == {BOSS_ROOM}


def test_floor7_pursuit_can_lose_fallen_trail_from_actual_combat_delay():
    runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag, encounter_id = _reach_blocker_encounter(seed=97)
    state = _defeat_blockers(runtime, pursuit, instance_id, encounter_id, TRAIL_MARGIN_MS + 1)

    assert state["trail_outcome"] == "lost"
    assert state["stage"] == "trail_lost_in_labyrinth"
    assert bag.instance_id in kysarah.inventory


def test_group_travel_advances_one_edge_for_a_colocated_party():
    runtime = HousingAincradRuntime(seed=101)
    runtime.world.floors[7].unlocked = True
    a = runtime.create_character("GroupA", level=20)
    b = runtime.create_character("GroupB", level=20)
    a.location_id = VOLUPTA
    b.location_id = VOLUPTA

    started = runtime.world.now_ms
    resolution = travel_together(runtime, [a.actor_id, b.actor_id], FIELD_OF_BONES)

    assert runtime.world.now_ms - started == resolution.elapsed_ms
    assert a.location_id == FIELD_OF_BONES
    assert b.location_id == FIELD_OF_BONES
