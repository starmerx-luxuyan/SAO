from sao_mcp.corpus.floor4_nocturne import (
    ICHTHYOID_CULTIVATOR_ID,
    ICHTHYOID_TUBER_ID,
    KYSARAH_TRANSFER_ROOM,
    LAKE_YOFEL,
    YOFEL_CASTLE,
)
from sao_mcp.corpus.floor6_elfwar import KYSARAH_ID, SACRED_KEY_BAG_ID
from sao_mcp.corpus.floor7 import SWORD_OF_VOLUPTA_ID
from sao_mcp.corpus.floor7_elfwar import LAVIK_ID
from sao_mcp.corpus.floor7_pursuit import RUBY_KEY_ID
from sao_mcp.corpus.floor8_world import FOREST_ELF_ESCAPE_CAVE, FRIEBEN, SLUVA
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS
from sao_mcp.domain.models import CombatantState, CursorColor, DefenseMode, EntityKind, ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.nightfolk import become_civis_nocte
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor4_nocturne import install_floor4_nocturne_scenario
from sao_mcp.scenarios.floor8_emergency import install_floor8_forest_emergency_scenario


class _Campaign:
    def __init__(self, runtime, handoff):
        self.runtime = runtime
        self.handoff_state = handoff

    def handoff(self, harin_instance_id, aghyellr_instance_id):
        assert harin_instance_id == "harin8_fixture"
        assert aghyellr_instance_id == "aghyellr8_fixture"
        return dict(self.handoff_state)


def _npc(actor_id, name, npc_definition_id, location_id, *, level=28):
    return CombatantState(
        actor_id=actor_id,
        name=name,
        kind=EntityKind.NPC,
        level=level,
        max_hp=8000 if level < 40 else 15000,
        hp=8000 if level < 40 else 15000,
        strength=64 if level < 40 else 115,
        agility=62 if level < 40 else 88,
        armor=150 if level < 40 else 360,
        evasion=12 if level < 40 else 20,
        cursor=CursorColor.YELLOW,
        location_id=location_id,
        metadata={"npc_definition_id": npc_definition_id},
    )


def _setup_branch_state():
    runtime = HousingAincradRuntime(seed=181)
    runtime.world.floors[4].unlocked = True
    runtime.world.floors[4].main_town_gate_active = True
    runtime.world.floors[8].unlocked = True
    runtime.world.floors[8].main_town_gate_active = True

    a = runtime.create_character("Floor8Responder", level=28)
    b = runtime.create_character("HideoutResponder", level=28)
    a.skill_proficiencies["one_hand_sword"] = 1000.0
    become_civis_nocte(a, master_actor_id="nirrnir_fixture", now_ms=0)

    sword_template = runtime.catalog.weapons[SWORD_OF_VOLUPTA_ID]
    doleful = ItemInstance(
        instance_id="doleful_branch_fixture",
        template_id=SWORD_OF_VOLUPTA_ID,
        owner_id=a.actor_id,
        durability=sword_template.base_durability,
        max_durability=sword_template.base_durability,
        metadata={"true_identity_revealed": True, "true_name": "Doleful Nocturne"},
    )
    add_item(a, doleful, runtime.catalog, allow_overweight=True)
    runtime.equip_item(a.actor_id, doleful.instance_id)

    kizmel = _npc("branch_kizmel", "Kizmel", "npc_kizmel", "floor_7_boss_room")
    lavik = _npc("branch_lavik", "Lavik Fen Cortassios", LAVIK_ID, "floor_7_field")
    kysarah = _npc("branch_kysarah", "Kysarah the Ransacker", KYSARAH_ID, "floor_7_field", level=55)
    fallen = _npc("branch_ruby_holder", "Fallen Elf Ruby Holder", "fallen_fixture", "floor_7_labyrinth")
    fallen.metadata["fallen_elf"] = True
    for actor in (kizmel, lavik, kysarah, fallen):
        runtime.actors[actor.actor_id] = actor
    runtime.npcs.states[LAVIK_ID].location_id = lavik.location_id

    bag = ItemInstance(
        instance_id="branch_four_key_bag",
        template_id=SACRED_KEY_BAG_ID,
        owner_id=kysarah.actor_id,
        metadata={"stolen_by_kysarah": True},
    )
    ruby = ItemInstance(
        instance_id="branch_ruby_key",
        template_id=RUBY_KEY_ID,
        owner_id=fallen.actor_id,
        metadata={"fallen_control": True},
    )
    add_item(kysarah, bag, runtime.catalog, allow_overweight=True)
    add_item(fallen, ruby, runtime.catalog, allow_overweight=True)

    runtime.world.global_flags["floor7_harin_escape_instances"] = {
        "harin8_fixture": {
            "instance_id": "harin8_fixture",
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
        "dolefulNocturneInstanceId": doleful.instance_id,
    }
    campaign = _Campaign(runtime, handoff)
    nocturne = install_floor4_nocturne_scenario(runtime, campaign)
    opened = nocturne.open_five_key_backtrack("harin8_fixture", "aghyellr8_fixture")
    instance_id = opened["instance_id"]
    state = nocturne._state(instance_id)
    state["stage"] = "five_key_hideout_recon_on_lake"
    for actor_id in (a.actor_id, b.actor_id, kizmel.actor_id):
        runtime.actors[actor_id].location_id = LAKE_YOFEL
    return runtime, campaign, nocturne, instance_id, a, b, kizmel, kysarah, bag, fallen, ruby


def _move_to_floor4_labyrinth(runtime, actor):
    runtime.travel_actor(actor.actor_id, YOFEL_CASTLE)
    runtime.travel_actor(actor.actor_id, "floor_4_usco")
    runtime.travel_actor(actor.actor_id, "floor_4_labyrinth")


def test_floor8_emergency_real_message_split_kysarah_truce_tuber_and_persistence():
    runtime, campaign, nocturne, instance_id, a, b, kizmel, kysarah, bag, fallen, ruby = _setup_branch_state()
    emergency = install_floor8_forest_emergency_scenario(runtime, nocturne)

    assert FRIEBEN in runtime.world_map.locations
    assert SLUVA in runtime.world_map.locations
    assert FOREST_ELF_ESCAPE_CAVE in runtime.world_map.locations
    assert "floor_8_main_town" not in runtime.world_map.locations
    assert runtime.world_map.locations[FRIEBEN].teleport_gate is True

    notice = emergency.trigger_from_nocturne(instance_id, a.actor_id)
    emergency_id = notice["instance_id"]
    argo_id = notice["argo_actor_id"]
    assert runtime.relationships.are_friends(argo_id, a.actor_id)
    assert notice["message"]["channel"] == "friend"
    assert runtime.communications.messages[notice["message_id"]].text == notice["message"]["text"]
    assert nocturne.status(instance_id)["stage"] == "floor8_emergency_received"

    split = emergency.assign_response_split(emergency_id, [a.actor_id], [b.actor_id])
    assert split["floor8_actor_ids"] == [a.actor_id]
    assert split["hideout_actor_ids"] == [b.actor_id]
    assert nocturne.status(instance_id)["stage"] == "parallel_nocturne_branches"

    hideout = nocturne.follow_river_ull_to_fallen_hideout(instance_id)
    assert hideout["hideout_branch_stage"] == "floor4_fallen_hideout_reached"
    assert runtime.actors[b.actor_id].location_id == "floor_4_fallen_elf_hideout"
    assert runtime.actors[kizmel.actor_id].location_id == "floor_4_fallen_elf_hideout"
    assert runtime.actors[a.actor_id].location_id == LAKE_YOFEL

    _move_to_floor4_labyrinth(runtime, a)
    intercepted = nocturne.trigger_kysarah_interception(instance_id, a.actor_id)
    encounter_id = intercepted["kysarah_interception_encounter_id"]
    encounter = runtime.encounters[encounter_id]
    assert kysarah.actor_id in encounter.participants
    assert bag.instance_id in kysarah.inventory

    truce = nocturne.resolve_kysarah_falhari_truce(instance_id, a.actor_id)
    assert truce["kysarah_interception_outcome"] == "falhari_truce"
    assert truce["kysarah"]["location_id"] == KYSARAH_TRANSFER_ROOM
    assert truce["kysarah_requested_item_template_id"] == ICHTHYOID_TUBER_ID
    assert set(encounter.participants) == {a.actor_id, kysarah.actor_id}
    assert runtime._in_live_encounter(a.actor_id) is False

    definition = AINCRAD_MONSTERS[ICHTHYOID_CULTIVATOR_ID]
    cultivator = runtime._create_monster(
        name=definition.name,
        level=definition.level,
        location_id=definition.location_id,
        hp_factor=definition.hp_factor,
        loot_table_id=definition.loot_table_id,
        quest_kill_id=definition.quest_kill_id,
    )
    cultivator.metadata["monster_id"] = definition.monster_id
    cultivator.hp = 1
    cultivator.max_hp = max(cultivator.max_hp, 1)
    cultivator.evasion = 0
    farm = runtime.start_encounter([a.actor_id, cultivator.actor_id], zone_id="floor_4_labyrinth")
    result = runtime.attack(
        farm.encounter_id,
        a.actor_id,
        cultivator.actor_id,
        defense=DefenseMode.NONE,
        seed=1,
    )
    assert result.hit
    assert cultivator.alive is False
    tubers = [item for item in a.inventory.values() if item.template_id == ICHTHYOID_TUBER_ID]
    assert len(tubers) == 1

    runtime.travel_actor(a.actor_id, KYSARAH_TRANSFER_ROOM)
    delivered = nocturne.deliver_ichthyoid_tuber_to_kysarah(instance_id, a.actor_id, tubers[0].instance_id)
    assert delivered["kysarah_tuber_delivered_at_ms"] is not None
    assert tubers[0].instance_id in kysarah.inventory
    assert bag.instance_id in kysarah.inventory

    crystal = ItemInstance(
        instance_id="branch_teleport_crystal",
        template_id="teleport_crystal",
        owner_id=a.actor_id,
        quantity=1,
    )
    add_item(a, crystal, runtime.catalog, allow_overweight=True)
    runtime.teleport_actor(a.actor_id, crystal.instance_id, FRIEBEN)
    arrived = emergency.arrive_frieben(emergency_id)
    assert arrived["stage"] == "responders_at_frieben"
    assert arrived["argo_location_id"] == FRIEBEN
    assert arrived["floor8_responder_locations"] == {a.actor_id: FRIEBEN}

    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    restored_campaign = _Campaign(restored, campaign.handoff_state)
    restored_nocturne = install_floor4_nocturne_scenario(restored, restored_campaign)
    restored_emergency = install_floor8_forest_emergency_scenario(restored, restored_nocturne)
    assert restored_emergency.status(emergency_id)["stage"] == "responders_at_frieben"
    assert restored.relationships.are_friends(argo_id, a.actor_id)
    assert restored_nocturne.status(instance_id)["kysarah_interception_outcome"] == "falhari_truce"
    assert restored.actors[kysarah.actor_id].inventory[bag.instance_id].template_id == SACRED_KEY_BAG_ID
    assert restored.actors[fallen.actor_id].inventory[ruby.instance_id].template_id == RUBY_KEY_ID


def test_kysarah_can_be_defeated_and_real_four_key_bag_recovered_instead_of_forced_truce():
    runtime, campaign, nocturne, instance_id, a, b, kizmel, kysarah, bag, fallen, ruby = _setup_branch_state()
    state = nocturne._state(instance_id)
    state["stage"] = "parallel_nocturne_branches"
    state["floor8_actor_ids"] = [a.actor_id]
    state["hideout_actor_ids"] = [b.actor_id]
    state["floor8_branch_stage"] = "departing_floor4"
    state["hideout_branch_stage"] = "on_lake"

    _move_to_floor4_labyrinth(runtime, a)
    intercepted = nocturne.trigger_kysarah_interception(instance_id, a.actor_id)
    encounter = runtime.encounters[intercepted["kysarah_interception_encounter_id"]]
    kysarah.hp = 0
    kysarah.alive = False
    runtime._resolve_defeat(encounter, kysarah, a.actor_id)

    recovered = nocturne.claim_four_key_bag_after_kysarah_defeat(instance_id, a.actor_id)
    assert recovered["kysarah_interception_outcome"] == "kysarah_defeated_four_keys_recovered"
    assert recovered["four_key_bag_owner_id"] == a.actor_id
    assert bag.instance_id in a.inventory
    assert bag.instance_id not in kysarah.inventory
    assert recovered["ruby_key_owner_id"] == fallen.actor_id
