from sao_mcp.corpus.floor6_elfwar import KYSARAH_ID, SACRED_KEY_BAG_ID
from sao_mcp.corpus.floor7_pursuit import RUBY_KEY_ID
from sao_mcp.corpus.location_access import FALLEN_ELVES
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.rules.inventory import add_item, transfer_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor7_elfwar import PALACE, VOLUPTA, install_floor7_elfwar_scenario
from sao_mcp.scenarios.floor7_pursuit import (
    ANT_TUNNEL_VALLEY,
    BOSS_ROOM,
    CASINO,
    DRAGON_BONE,
    FIELD_OF_BONES,
    LABYRINTH,
    PLATEAU,
    RENDEZVOUS_PREPARATION_MS,
    TRAIL_MARGIN_MS,
    WATCH_HILL,
    install_floor7_pursuit_scenario,
)


LEGACY_ROUTE_MS_FIELDS = {
    "volupta_to_field_ms",
    "field_to_watch_ms",
    "watch_to_dragon_ms",
    "dragon_to_ant_ms",
    "ant_to_plateau_ms",
    "plateau_to_labyrinth_ms",
    "boss_room_travel_ms",
}


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


def _assert_route(route, actor_ids, expected_segments):
    assert [
        (row["from_location_id"], row["to_location_id"], row["elapsed_ms"])
        for row in route
    ] == expected_segments
    assert all(row["actor_ids"] == actor_ids for row in route)
    assert all("newly_discovered" in row and "traversal_tags" in row for row in route)


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
    raw_pursuit = pursuit._state(instance_id)["pursuit"]

    assert state["instance_id"] == instance_id
    assert elfwar._state(instance_id)["stage"] == "scyia_counteroffer_accepted"
    assert a.location_id == VOLUPTA
    assert b.location_id == VOLUPTA
    assert kizmel.location_id == VOLUPTA
    assert bag.instance_id in kysarah.inventory
    assert state["ruby_key_status"] == "dark_elf_retrieval_team"
    assert state["fallen_sacred_key_count"] == 4
    assert "target_key_bag_holder_id" not in raw_pursuit
    assert "ruby_key_fallen_holder_id" not in raw_pursuit
    assert raw_pursuit["ruby_key_ambusher_actor_id"] is None
    assert LEGACY_ROUTE_MS_FIELDS.isdisjoint(raw_pursuit)
    assert raw_pursuit["rendezvous_route"] == []
    assert raw_pursuit["tail_to_ant_route"] == []
    assert raw_pursuit["labyrinth_entry_route"] == []
    assert raw_pursuit["boss_room_route"] == []
    return runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag


def _reach_blocker_encounter(seed=83):
    runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag = _setup(seed)
    actor_ids = [a.actor_id, b.actor_id, kizmel.actor_id]
    before_depart = runtime.world.now_ms
    state = pursuit.rest_and_reach_dragon_bone_watch(instance_id)
    rendezvous = state["pursuit"]["rendezvous_route"]
    assert runtime.world.now_ms - before_depart == RENDEZVOUS_PREPARATION_MS + sum(
        row["elapsed_ms"] for row in rendezvous
    )
    assert len(rendezvous) == 2
    assert rendezvous[0]["from_location_id"] == VOLUPTA
    assert rendezvous[0]["to_location_id"] == FIELD_OF_BONES
    assert rendezvous[1]["from_location_id"] == FIELD_OF_BONES
    assert rendezvous[1]["to_location_id"] == WATCH_HILL
    assert all(row["actor_ids"] == actor_ids for row in rendezvous)
    assert LEGACY_ROUTE_MS_FIELDS.isdisjoint(state["pursuit"])
    assert {a.location_id, b.location_id, kizmel.location_id} == {WATCH_HILL}

    state = pursuit.observe_fallen_departure(instance_id)
    assert set(state["fallen_scout_locations"].values()) == {DRAGON_BONE}
    state = pursuit.pursue_to_ant_tunnel_valley(instance_id)
    _assert_route(
        state["pursuit"]["tail_to_ant_route"],
        actor_ids,
        [
            (WATCH_HILL, DRAGON_BONE, 10 * 60_000),
            (DRAGON_BONE, ANT_TUNNEL_VALLEY, 75 * 60_000),
        ],
    )
    assert LEGACY_ROUTE_MS_FIELDS.isdisjoint(state["pursuit"])
    assert {a.location_id, b.location_id, kizmel.location_id} == {ANT_TUNNEL_VALLEY}

    state = pursuit.follow_through_valley_into_labyrinth(instance_id)
    _assert_route(
        state["pursuit"]["labyrinth_entry_route"],
        actor_ids,
        [
            (ANT_TUNNEL_VALLEY, PLATEAU, 35 * 60_000),
            (PLATEAU, LABYRINTH, 25 * 60_000),
        ],
    )
    assert LEGACY_ROUTE_MS_FIELDS.isdisjoint(state["pursuit"])
    assert {a.location_id, b.location_id, kizmel.location_id} == {LABYRINTH}
    assert len(state["blockers"]) == 2
    assert state["ruby_key_status"] == "fallen_control"
    assert state["fallen_sacred_key_count"] == 5
    assert state["ruby_key_owner_is_fallen"] is True
    raw_pursuit = pursuit._state(instance_id)["pursuit"]
    assert "target_key_bag_holder_id" not in raw_pursuit
    assert "ruby_key_fallen_holder_id" not in raw_pursuit
    assert raw_pursuit["ruby_key_ambusher_actor_id"] == state["ruby_key_owner_id"]
    ruby_holder = runtime.actors[state["ruby_key_owner_id"]]
    assert ruby_holder.inventory[state["ruby_key_instance_id"]].template_id == RUBY_KEY_ID
    assert bag.instance_id in kysarah.inventory
    return runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag, state["blocker_encounter_id"]


def _defeat_blockers(runtime, pursuit, instance_id, encounter_id, elapsed_ms):
    encounter = runtime.encounters[encounter_id]
    state = pursuit.status(instance_id)
    runtime.advance_encounter(encounter_id, elapsed_ms)
    blocker_ids = list(state["pursuit"]["blocker_actor_ids"])
    for blocker_id in blocker_ids:
        blocker = encounter.participants[blocker_id]
        blocker.hp = 0
        blocker.alive = False
        runtime._resolve_defeat(encounter, blocker, state["pursuit"]["travelling_actor_ids"][0])
    resolved = pursuit.status(instance_id)
    assert runtime.world_event_state(
        f"floor7.labyrinth_pursuit_resolution:{instance_id}"
    )["status"] == "resolved"
    return resolved


def test_floor7_pursuit_uses_corpus_route_real_keys_and_shared_travel_time():
    runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag, encounter_id = _reach_blocker_encounter()
    actor_ids = [a.actor_id, b.actor_id, kizmel.actor_id]
    assert not any(
        edge.from_location_id == FIELD_OF_BONES and edge.to_location_id == ANT_TUNNEL_VALLEY
        for edge in runtime.world_map.connections
    )
    assert not any(
        edge.from_location_id == ANT_TUNNEL_VALLEY and edge.to_location_id == LABYRINTH
        for edge in runtime.world_map.connections
    )

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
    assert state["fallen_sacred_key_count"] == 5

    state = pursuit.advance_to_boss_room(instance_id)
    assert state["ready_for_aghyellr"] is True
    boss_route = state["pursuit"]["boss_room_route"]
    assert len(boss_route) == 1
    assert boss_route[0]["actor_ids"] == actor_ids
    assert boss_route[0]["from_location_id"] == LABYRINTH
    assert boss_route[0]["to_location_id"] == BOSS_ROOM
    assert boss_route[0]["elapsed_ms"] > 0
    assert LEGACY_ROUTE_MS_FIELDS.isdisjoint(state["pursuit"])
    assert {a.location_id, b.location_id, kizmel.location_id} == {BOSS_ROOM}


def test_floor7_pursuit_keeps_ruby_ambusher_as_history_while_inventory_owner_changes():
    runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag, encounter_id = _reach_blocker_encounter(seed=89)
    before = pursuit.status(instance_id)
    ambusher_id = before["pursuit"]["ruby_key_ambusher_actor_id"]
    ambusher = runtime.actors[ambusher_id]
    new_holder = CombatantState(
        actor_id="fallen7_ruby_handoff_fixture",
        name="Fallen Elf Ruby Key Handoff",
        kind=EntityKind.NPC,
        level=24,
        max_hp=6200,
        hp=6200,
        strength=58,
        agility=66,
        cursor=CursorColor.YELLOW,
        location_id=LABYRINTH,
        metadata={"faction_ids": (FALLEN_ELVES,)},
    )
    runtime.actors[new_holder.actor_id] = new_holder
    transfer_item(
        ambusher,
        new_holder,
        before["ruby_key_instance_id"],
        runtime.catalog,
        allow_destination_overweight=True,
    )

    updated = pursuit.status(instance_id)
    assert updated["ruby_key_owner_id"] == new_holder.actor_id
    assert updated["ruby_key_owner_is_fallen"] is True
    assert updated["pursuit"]["ruby_key_ambusher_actor_id"] == ambusher_id
    assert "ruby_key_fallen_holder_id" not in updated["pursuit"]


def test_floor7_pursuit_can_lose_fallen_trail_from_actual_combat_delay_without_reversing_key_state():
    runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag, encounter_id = _reach_blocker_encounter(seed=97)
    state = _defeat_blockers(runtime, pursuit, instance_id, encounter_id, TRAIL_MARGIN_MS + 1)

    assert state["trail_outcome"] == "lost"
    assert state["stage"] == "trail_lost_in_labyrinth"
    assert bag.instance_id in kysarah.inventory
    assert state["fallen_sacred_key_count"] == 5
    assert state["ruby_key_status"] == "fallen_control"


def test_floor7_pursuit_survives_save_load_without_scenario_seeded_map_edges():
    runtime, pursuit, instance_id, a, b, kizmel, kysarah, bag = _setup(seed=103)
    pursuit.rest_and_reach_dragon_bone_watch(instance_id)
    before_save = pursuit.observe_fallen_departure(instance_id)
    scout_ids = list(before_save["pursuit"]["fallen_scout_ids"])
    actor_ids = [a.actor_id, b.actor_id, kizmel.actor_id]
    rendezvous_route = list(before_save["pursuit"]["rendezvous_route"])

    restored = import_runtime(export_runtime(runtime))
    restored_pursuit = install_floor7_pursuit_scenario(restored)
    restored_state = restored_pursuit.status(instance_id)

    assert restored_state["stage"] == "fallen_departed_begin_tail"
    assert restored_state["pursuit"]["rendezvous_route"] == rendezvous_route
    assert LEGACY_ROUTE_MS_FIELDS.isdisjoint(restored_state["pursuit"])
    assert {restored.actors[actor_id].location_id for actor_id in actor_ids} == {WATCH_HILL}
    assert {restored.actors[scout_id].location_id for scout_id in scout_ids} == {DRAGON_BONE}
    assert restored.actors[kysarah.actor_id].inventory[bag.instance_id].template_id == SACRED_KEY_BAG_ID
    assert "target_key_bag_holder_id" not in restored_state["pursuit"]
    assert "ruby_key_fallen_holder_id" not in restored_state["pursuit"]
    assert not any(
        edge.from_location_id == FIELD_OF_BONES and edge.to_location_id == ANT_TUNNEL_VALLEY
        for edge in restored.world_map.connections
    )

    restored_state = restored_pursuit.pursue_to_ant_tunnel_valley(instance_id)
    assert {restored.actors[actor_id].location_id for actor_id in actor_ids} == {ANT_TUNNEL_VALLEY}
    _assert_route(
        restored_state["pursuit"]["tail_to_ant_route"],
        actor_ids,
        [
            (WATCH_HILL, DRAGON_BONE, 10 * 60_000),
            (DRAGON_BONE, ANT_TUNNEL_VALLEY, 75 * 60_000),
        ],
    )

    restored_state = restored_pursuit.follow_through_valley_into_labyrinth(instance_id)
    assert {restored.actors[actor_id].location_id for actor_id in actor_ids} == {LABYRINTH}
    assert restored_state["ruby_key_status"] == "fallen_control"
    assert restored_state["fallen_sacred_key_count"] == 5
    assert restored_state["ruby_key_owner_is_fallen"] is True
    assert restored_state["pursuit"]["ruby_key_ambusher_actor_id"] == restored_state["ruby_key_owner_id"]
    assert LEGACY_ROUTE_MS_FIELDS.isdisjoint(restored_state["pursuit"])


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
