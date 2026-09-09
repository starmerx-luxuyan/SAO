import pytest

from sao_mcp.corpus.floor4 import YOFILIS_ID
from sao_mcp.corpus.floor4_nocturne import (
    CETRANN_ID,
    FALLEN_HIDEOUT,
    KELPIE_ID,
    LAKE_YOFEL,
    LAKE_YOFEL_FOG_BOUNDARY,
    LAKE_YOFEL_NORTH_BEACH,
    LAKE_YOFEL_WEST_SHORE,
    YOFEL_CASTLE,
)
from sao_mcp.corpus.floor6_elfwar import KYSARAH_ID, SACRED_KEY_BAG_ID
from sao_mcp.corpus.floor7_elfwar import LAVIK_ID
from sao_mcp.corpus.floor7_pursuit import RUBY_KEY_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.nightfolk import become_civis_nocte
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor4_nocturne import ROVIA, USCO, install_floor4_nocturne_scenario


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
    become_civis_nocte(a, master_actor_id="nirrnir_floor7_fixture", now_ms=runtime.world.now_ms)
    kizmel = _npc_actor("nocturne_kizmel", "Kizmel", "npc_kizmel", "floor_7_boss_room")
    lavik = _npc_actor("nocturne_lavik", "Lavik Fen Cortassios", LAVIK_ID, "floor_7_field")
    runtime.actors[kizmel.actor_id] = kizmel
    runtime.actors[lavik.actor_id] = lavik
    runtime.npcs.states[LAVIK_ID].location_id = lavik.location_id

    kysarah = _npc_actor("nocturne_kysarah", "Kysarah the Ransacker", KYSARAH_ID, "floor_7_field")
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


def _move_group_from_rovia_to_lavik(runtime, group_ids):
    for actor_id in group_ids:
        runtime.actors[actor_id].location_id = ROVIA
    travel_together(runtime, group_ids, "floor_4_caldera_lake")
    travel_together(runtime, group_ids, USCO)
    travel_together(runtime, group_ids, LAKE_YOFEL_WEST_SHORE)


def _move_group_from_lavik_to_yofel(runtime, group_ids):
    travel_together(runtime, group_ids, LAKE_YOFEL)
    travel_together(runtime, group_ids, YOFEL_CASTLE)


def test_progressive9_lavik_yofilis_kelpie_and_hideout_are_one_persistent_state_chain():
    runtime, nocturne, campaign, a, b, kizmel, lavik, kysarah, bag, fallen, ruby = _setup_nocturne_runtime()
    assert YOFILIS_ID == "npc_floor4_yofilis"
    assert "npc_floor4_viscount_yofilis" not in runtime.npcs.definitions
    assert CETRANN_ID in runtime.npcs.definitions

    opened = nocturne.open_five_key_backtrack("harin7_nocturne_fixture", "aghyellr7_nocturne_fixture")
    instance_id = opened["instance_id"]
    assert opened["stage"] == "five_key_trail_points_to_floor4"
    assert opened["five_key_count"] == 5
    assert opened["five_key_assets_intact"] is True
    assert runtime.actors[lavik.actor_id].location_id == LAKE_YOFEL_WEST_SHORE
    assert runtime.npcs.states[LAVIK_ID].location_id == LAKE_YOFEL_WEST_SHORE
    assert runtime.npcs.states[YOFILIS_ID].location_id == YOFEL_CASTLE

    group_ids = [a.actor_id, b.actor_id, kizmel.actor_id]
    _move_group_from_rovia_to_lavik(runtime, group_ids)
    met_lavik = nocturne.arrive_lavik_west_shore(instance_id)
    assert met_lavik["stage"] == "lavik_request_offered"
    accepted = nocturne.accept_lavik_request(instance_id, a.actor_id)
    assert accepted["stage"] == "reach_yofel_castle_without_lavik"

    _move_group_from_lavik_to_yofel(runtime, group_ids)
    castle = nocturne.arrive_yofel_castle(instance_id)
    assert castle["stage"] == "request_secret_yofilis_meeting"
    assert castle["lavik_location_id"] == LAKE_YOFEL_WEST_SHORE
    agreed = nocturne.request_yofilis_secret_meeting(instance_id, a.actor_id)
    assert agreed["stage"] == "kelpie_search_ready"

    original_equipment = {
        a.actor_id: dict(a.equipment),
        b.actor_id: dict(b.equipment),
    }
    prepared = nocturne.prepare_kelpie_search(instance_id, [a.actor_id, b.actor_id])
    assert prepared["stage"] == "kelpie_search_prepared"
    assert not a.equipment and not b.equipment
    assert {a.location_id, b.location_id} == {LAKE_YOFEL_FOG_BOUNDARY}
    assert kizmel.location_id == YOFEL_CASTLE

    present = nocturne.call_kelpie_from_fog(instance_id)
    kelpie_id = present["kelpie"]["actor_id"]
    kelpie = runtime.actors[kelpie_id]
    assert kelpie.metadata["monster_id"] == KELPIE_ID
    assert kelpie.cursor is CursorColor.RED
    assert kelpie.location_id == LAKE_YOFEL_FOG_BOUNDARY
    with pytest.raises(ValueError):
        nocturne.tame_kelpie(instance_id, b.actor_id, "Not Yours")

    tamed = nocturne.tame_kelpie(instance_id, a.actor_id, "Moo")
    assert tamed["taming"]["tamer_actor_id"] == a.actor_id
    assert tamed["taming"]["monster_level"] < tamed["taming"]["tamer_level"]
    assert kelpie.cursor is CursorColor.YELLOW
    assert kelpie.metadata["night_tamed_by_actor_id"] == a.actor_id
    assert kelpie.metadata["nickname"] == "Moo"

    restored_equipment = nocturne.restore_kelpie_search_equipment(instance_id)
    assert restored_equipment["stage"] == "escort_yofilis_to_north_beach"
    assert dict(a.equipment) == original_equipment[a.actor_id]
    assert dict(b.equipment) == original_equipment[b.actor_id]

    beach = nocturne.escort_yofilis_to_north_beach(instance_id)
    assert beach["stage"] == "ride_kelpie_to_yofilis"
    assert kizmel.location_id == LAKE_YOFEL_NORTH_BEACH
    assert runtime.npcs.states[YOFILIS_ID].location_id == LAKE_YOFEL_NORTH_BEACH

    ridden = nocturne.ride_kelpie_to_yofilis(instance_id)
    assert ridden["stage"] == "kelpie_at_yofilis_rendezvous"
    assert {a.location_id, b.location_id, kelpie.location_id} == {LAKE_YOFEL_NORTH_BEACH}

    reunion = nocturne.carry_yofilis_to_lavik(instance_id)
    assert reunion["stage"] == "lavik_yofilis_reunited"
    assert runtime.npcs.states[YOFILIS_ID].location_id == LAKE_YOFEL_WEST_SHORE
    assert {a.location_id, b.location_id, kizmel.location_id, kelpie.location_id} == {LAKE_YOFEL_WEST_SHORE}

    promised = nocturne.record_lavik_yofilis_duel_promise(instance_id, a.actor_id)
    assert promised["lavik_yofilis_duel_promised"] is True
    returned = nocturne.return_yofilis_and_open_past(instance_id, a.actor_id)
    assert returned["stage"] == "five_key_hideout_recon_ready"
    assert returned["yofilis_past_opened"] is True
    assert len(returned["yofilis_past_facts"]) == 3
    assert set(returned["group_locations"].values()) == {YOFEL_CASTLE}
    assert returned["kelpie"]["location_id"] == LAKE_YOFEL

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    restored_campaign = _ValidatedFloor7Campaign(restored, campaign._handoff)
    restored_nocturne = install_floor4_nocturne_scenario(restored, restored_campaign)
    restored_state = restored_nocturne.status(instance_id)
    assert restored_state["stage"] == "five_key_hideout_recon_ready"
    assert restored_state["kelpie"]["actor_id"] == kelpie_id
    assert restored_state["kelpie"]["night_tamed_by_actor_id"] == a.actor_id
    assert restored_state["kelpie"]["nickname"] == "Moo"
    assert restored.actors[kysarah.actor_id].inventory[bag.instance_id].template_id == SACRED_KEY_BAG_ID
    assert restored.actors[fallen.actor_id].inventory[ruby.instance_id].template_id == RUBY_KEY_ID
    assert restored.actors[lavik.actor_id].location_id == LAKE_YOFEL_WEST_SHORE
    assert restored.npcs.states[YOFILIS_ID].location_id == YOFEL_CASTLE

    lake = restored_nocturne.embark_five_key_hideout_recon(instance_id)
    assert lake["stage"] == "five_key_hideout_recon_on_lake"
    assert lake["castle_to_lake_ms"] == 4 * 60_000
    assert set(lake["group_locations"].values()) == {LAKE_YOFEL}

    started = restored.world.now_ms
    final = restored_nocturne.follow_river_ull_to_fallen_hideout(instance_id)
    assert final["stage"] == "floor4_fallen_hideout_reached"
    assert final["lake_to_hideout_ms"] == 60 * 60_000
    assert restored.world.now_ms - started == 60 * 60_000
    assert set(final["group_locations"].values()) == {FALLEN_HIDEOUT}
    assert final["five_key_assets_intact"] is True