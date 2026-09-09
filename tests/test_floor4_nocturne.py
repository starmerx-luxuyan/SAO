from sao_mcp.corpus.floor4_nocturne import (
    FALLEN_HIDEOUT,
    LAKE_YOFEL,
    RIVER_ULL,
    YOFEL_CASTLE,
    YOFILIS_ID,
)
from sao_mcp.corpus.floor6_elfwar import SACRED_KEY_BAG_ID
from sao_mcp.corpus.floor7_elfwar import LAVIK_ID
from sao_mcp.corpus.floor7_pursuit import RUBY_KEY_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor4_nocturne import (
    ROVIA,
    USCO,
    install_floor4_nocturne_scenario,
)


class _ValidatedFloor7Campaign:
    def __init__(self, runtime, handoff):
        self.runtime = runtime
        self._handoff = handoff

    def handoff(self, harin_instance_id: str, aghyellr_instance_id: str) -> dict:
        assert harin_instance_id == "harin7_nocturne_fixture"
        assert aghyellr_instance_id == "aghyellr7_nocturne_fixture"
        return dict(self._handoff)


def _npc_actor(actor_id, name, npc_definition_id, location_id):
    return CombatantState(
        actor_id=actor_id,
        name=name,
        kind=EntityKind.NPC,
        level=28,
        max_hp=7600,
        hp=7600,
        strength=64,
        agility=62,
        cursor=CursorColor.YELLOW,
        location_id=location_id,
        metadata={"npc_definition_id": npc_definition_id},
    )


def _setup_nocturne_runtime():
    runtime = HousingAincradRuntime(seed=151)
    runtime.world.floors[4].unlocked = True
    runtime.world.floors[4].main_town_gate_active = True

    a = runtime.create_character("NocturneA", level=28)
    b = runtime.create_character("NocturneB", level=28)
    kizmel = _npc_actor("nocturne_kizmel", "Kizmel", "npc_kizmel", "floor_7_boss_room")
    lavik = _npc_actor("nocturne_lavik", "Lavik Fen Cortassios", LAVIK_ID, "floor_7_field")
    runtime.actors[kizmel.actor_id] = kizmel
    runtime.actors[lavik.actor_id] = lavik
    runtime.npcs.states[LAVIK_ID].location_id = lavik.location_id

    kysarah = _npc_actor("nocturne_kysarah", "Kysarah", "npc_floor6_kysarah", "floor_7_field")
    runtime.actors[kysarah.actor_id] = kysarah
    bag = ItemInstance(
        instance_id="nocturne_four_key_bag",
        template_id=SACRED_KEY_BAG_ID,
        owner_id=kysarah.actor_id,
        metadata={"stolen_by_kysarah": True},
    )
    add_item(kysarah, bag, runtime.catalog, allow_overweight=True)

    fallen = _npc_actor("nocturne_ruby_holder", "Fallen Elf Ruby Holder", "fallen_fixture", "floor_7_labyrinth")
    fallen.metadata["fallen_elf"] = True
    runtime.actors[fallen.actor_id] = fallen
    ruby = ItemInstance(
        instance_id="nocturne_ruby_key",
        template_id=RUBY_KEY_ID,
        owner_id=fallen.actor_id,
        metadata={"fallen_control": True},
    )
    add_item(fallen, ruby, runtime.catalog, allow_overweight=True)

    runtime.world.global_flags["floor7_harin_escape_instances"] = {
        "harin7_nocturne_fixture": {
            "instance_id": "harin7_nocturne_fixture",
            "stage": "boss_room_reached",
            "player_ids": [a.actor_id, b.actor_id],
            "kizmel_actor_id": kizmel.actor_id,
            "pursuit": {
                "target_key_bag_instance_id": bag.instance_id,
                "target_key_bag_holder_id": kysarah.actor_id,
                "ruby_key_instance_id": ruby.instance_id,
                "ruby_key_fallen_holder_id": fallen.actor_id,
            },
        }
    }
    handoff = {
        "fallenSacredKeyCount": 5,
        "fiveKeyPursuitContinues": True,
        "civisActorId": a.actor_id,
        "dolefulNocturneInstanceId": "doleful_floor7_fixture",
    }
    campaign = _ValidatedFloor7Campaign(runtime, handoff)
    nocturne = install_floor4_nocturne_scenario(runtime, campaign)
    return runtime, nocturne, campaign, a, b, kizmel, lavik, kysarah, bag, fallen, ruby


def _move_group_from_rovia_to_yofel(runtime, group_ids):
    for actor_id in group_ids:
        runtime.actors[actor_id].location_id = ROVIA
    travel_together(runtime, group_ids, "floor_4_caldera_lake")
    travel_together(runtime, group_ids, USCO)
    travel_together(runtime, group_ids, YOFEL_CASTLE)


def test_progressive9_entry_backtracks_to_floor4_and_survives_save_load_on_lake_yofel():
    runtime, nocturne, campaign, a, b, kizmel, lavik, kysarah, bag, fallen, ruby = _setup_nocturne_runtime()
    opened = nocturne.open_five_key_backtrack(
        "harin7_nocturne_fixture",
        "aghyellr7_nocturne_fixture",
    )
    instance_id = opened["instance_id"]

    assert opened["stage"] == "five_key_trail_points_to_floor4"
    assert opened["five_key_count"] == 5
    assert opened["five_key_assets_intact"] is True
    assert opened["lavik_actor_id"] == lavik.actor_id
    assert runtime.actors[lavik.actor_id].location_id == YOFEL_CASTLE
    assert runtime.npcs.states[LAVIK_ID].location_id == YOFEL_CASTLE
    assert runtime.npcs.states[YOFILIS_ID].location_id == YOFEL_CASTLE
    assert LAKE_YOFEL in runtime.world_map.locations
    assert RIVER_ULL in runtime.world_map.locations

    group_ids = [a.actor_id, b.actor_id, kizmel.actor_id]
    _move_group_from_rovia_to_yofel(runtime, group_ids)
    arrived = nocturne.arrive_yofel_castle(instance_id)
    assert arrived["stage"] == "lavik_request_offered"
    assert set(arrived["group_locations"].values()) == {YOFEL_CASTLE}

    accepted = nocturne.accept_lavik_request(instance_id, a.actor_id)
    assert accepted["stage"] == "meet_viscount_yofilis"
    met = nocturne.meet_yofilis(instance_id, a.actor_id)
    assert met["stage"] == "lake_yofel_recon_ready"
    assert met["ancient_elven_dispute_opened"] is True
    assert "lake_yofel" in met["yofilis_knowledge_tags"]

    lake = nocturne.embark_lake_yofel(instance_id)
    assert lake["stage"] == "lake_yofel_recon"
    assert lake["castle_to_lake_ms"] == 4 * 60_000
    assert set(lake["group_locations"].values()) == {LAKE_YOFEL}

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    restored_campaign = _ValidatedFloor7Campaign(restored, campaign._handoff)
    restored_nocturne = install_floor4_nocturne_scenario(restored, restored_campaign)
    restored_state = restored_nocturne.status(instance_id)
    assert restored_state["stage"] == "lake_yofel_recon"
    assert set(restored_state["group_locations"].values()) == {LAKE_YOFEL}
    assert restored.actors[kysarah.actor_id].inventory[bag.instance_id].template_id == SACRED_KEY_BAG_ID
    assert restored.actors[fallen.actor_id].inventory[ruby.instance_id].template_id == RUBY_KEY_ID
    assert restored.actors[lavik.actor_id].actor_id == lavik.actor_id
    assert restored.npcs.states[YOFILIS_ID].location_id == YOFEL_CASTLE

    started = restored.world.now_ms
    final = restored_nocturne.follow_river_ull_to_fallen_hideout(instance_id)
    assert final["stage"] == "floor4_fallen_hideout_reached"
    assert final["lake_to_hideout_ms"] == 60 * 60_000
    assert restored.world.now_ms - started == 60 * 60_000
    assert final["river_route_segments_ms"] == {
        "lake_yofel_to_river_ull": 10 * 60_000,
        "river_ull_to_caldera_lake": 10 * 60_000,
        "caldera_lake_to_bear_forest": 18 * 60_000,
        "bear_forest_to_fallen_hideout": 22 * 60_000,
    }
    assert set(final["group_locations"].values()) == {FALLEN_HIDEOUT}
    assert final["five_key_assets_intact"] is True
