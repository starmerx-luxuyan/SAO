from sao_mcp.corpus.floor6_elfwar import KYSARAH_ID, SACRED_KEY_BAG_ID
from sao_mcp.corpus.floor7 import SWORD_OF_VOLUPTA_ID
from sao_mcp.corpus.floor7_pursuit import RUBY_KEY_ID
from sao_mcp.corpus.location_access import FALLEN_ELVES
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor7_campaign import install_floor7_campaign_scenario


class _StatusService:
    def __init__(self, runtime, payload):
        self.runtime = runtime
        self.payload = payload

    def status(self, instance_id):
        assert instance_id == "harin7_fixture"
        return self.payload


class _RaidService:
    def __init__(self, runtime, payload):
        self.runtime = runtime
        self.payload = payload

    def raid_status(self, instance_id):
        assert instance_id == "aghyellr7_fixture"
        return self.payload


def test_floor7_campaign_handoff_validates_real_assets_and_next_floor_schedule():
    runtime = HousingAincradRuntime(seed=107)
    floor7 = runtime.world.floors[7]
    floor7.unlocked = True
    floor7.floor_boss_defeated = True
    floor7.floor_boss_defeated_at_ms = runtime.world.now_ms
    floor7.scheduled_gate_activation_at_ms = runtime.world.now_ms + 2 * 60 * 60 * 1000

    kysarah = CombatantState(
        actor_id="handoff_kysarah",
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
    key_bag = ItemInstance(
        instance_id="handoff_four_keys",
        template_id=SACRED_KEY_BAG_ID,
        owner_id=kysarah.actor_id,
        metadata={"stolen_by_kysarah": True},
    )
    add_item(kysarah, key_bag, runtime.catalog, allow_overweight=True)

    ruby_holder = CombatantState(
        actor_id="handoff_fallen_ruby_holder",
        name="Fallen Elf Ruby Holder",
        kind=EntityKind.NPC,
        level=25,
        max_hp=6500,
        hp=6500,
        strength=60,
        agility=68,
        cursor=CursorColor.YELLOW,
        location_id="floor_7_labyrinth",
        metadata={"faction_ids": (FALLEN_ELVES,)},
    )
    runtime.actors[ruby_holder.actor_id] = ruby_holder
    ruby = ItemInstance(
        instance_id="handoff_ruby_key",
        template_id=RUBY_KEY_ID,
        owner_id=ruby_holder.actor_id,
        metadata={"fallen_control": True},
    )
    add_item(ruby_holder, ruby, runtime.catalog, allow_overweight=True)

    nirrnir = CombatantState(
        actor_id="handoff_nirrnir",
        name="Nirrnir Nachtoy",
        kind=EntityKind.NPC,
        level=30,
        max_hp=7200,
        hp=7200,
        strength=46,
        agility=62,
        cursor=CursorColor.YELLOW,
        location_id="floor_7_boss_room",
        metadata={"night_rank": "dominus_nocte"},
    )
    runtime.actors[nirrnir.actor_id] = nirrnir

    civis = runtime.create_character("HandoffCivis", level=24)
    civis.metadata.update(
        {
            "night_rank": "civis_nocte",
            "night_master_actor_id": nirrnir.actor_id,
        }
    )
    sword_template = runtime.catalog.weapons[SWORD_OF_VOLUPTA_ID]
    sword = ItemInstance(
        instance_id="handoff_doleful",
        template_id=SWORD_OF_VOLUPTA_ID,
        owner_id=civis.actor_id,
        durability=sword_template.base_durability,
        max_durability=sword_template.base_durability,
        metadata={"true_identity_revealed": True, "true_name": "Doleful Nocturne"},
    )
    add_item(civis, sword, runtime.catalog, allow_overweight=True)

    blood_ids = [f"handoff_blood_{index}" for index in range(17)]
    cure_id = blood_ids[0]
    for blood_id in blood_ids[1:]:
        item = ItemInstance(
            instance_id=blood_id,
            template_id="fresh_aghyellr_dragon_blood",
            owner_id=civis.actor_id,
        )
        add_item(civis, item, runtime.catalog, allow_overweight=True)

    pursuit_payload = {
        "stage": "boss_room_reached",
        "fallen_sacred_key_count": 5,
        "ruby_key_status": "fallen_control",
        "ruby_key_instance_id": ruby.instance_id,
        "ruby_key_owner_id": ruby_holder.actor_id,
        "target_key_bag_matches": [
            {
                "owner_id": kysarah.actor_id,
                "owner_npc_definition_id": KYSARAH_ID,
                "stolen_by_kysarah": True,
            }
        ],
    }
    raid_payload = {
        "boss_alive": False,
        "nirrnir_actor_id": nirrnir.actor_id,
        "nirrnir": {
            "stage": "cured",
            "nirrnir_actor_id": nirrnir.actor_id,
            "cure_blood_instance_id": cure_id,
        },
        "civis_actor_ids": [civis.actor_id],
        "doleful_nocturne_revealed_instance_ids": [sword.instance_id],
        "blood_jars_collected": 17,
        "blood_jar_instance_ids": blood_ids,
        "blood_jars_remaining_in_campaign": 16,
    }

    campaign = install_floor7_campaign_scenario(
        runtime,
        _StatusService(runtime, pursuit_payload),
        _RaidService(runtime, raid_payload),
    )
    state = campaign.handoff("harin7_fixture", "aghyellr7_fixture")

    assert state["floor7Cleared"] is True
    assert state["fallenSacredKeyCount"] == 5
    assert state["rubyKeyInstanceId"] == ruby.instance_id
    assert state["rubyKeyOwnerId"] == ruby_holder.actor_id
    assert state["civisActorId"] == civis.actor_id
    assert state["dolefulNocturneInstanceId"] == sword.instance_id
    assert state["aghyellrBloodJarCount"] == 17
    assert state["aghyellrBloodJarsRemaining"] == 16
    assert state["floor8Unlocked"] is False
    assert state["floor8GateScheduledAtMs"] == floor7.scheduled_gate_activation_at_ms
    assert state["fiveKeyPursuitContinues"] is True
