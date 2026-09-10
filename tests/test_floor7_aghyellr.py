from copy import deepcopy

from sao_mcp.corpus.floor7 import SWORD_OF_VOLUPTA_ID
from sao_mcp.domain.models import ItemInstance, StatusType
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor7_aghyellr import (
    AGHYELLR_BLOOD_JAR_COUNT,
    BOSS_ROOM,
    CASINO,
    HUMAN_BLOOD_BRIDGE_MS,
    KORLOY_STABLES,
    NIRRNIR_STABILIZED_SURVIVAL_MS,
    install_floor7_aghyellr_scenario,
)


def _give_sword_of_volupta(runtime, actor):
    template = runtime.catalog.weapons[SWORD_OF_VOLUPTA_ID]
    item = ItemInstance(
        instance_id="test_sword_of_volupta",
        template_id=SWORD_OF_VOLUPTA_ID,
        owner_id=actor.actor_id,
        durability=template.base_durability,
        max_durability=template.base_durability,
    )
    add_item(actor, item, runtime.catalog, allow_overweight=True)
    runtime.equip_item(actor.actor_id, item.instance_id)
    return item


def test_floor7_nirrnir_civis_doleful_and_aghyellr_blood_drop_are_real_state():
    runtime = HousingAincradRuntime(seed=59)
    aghyellr = install_floor7_aghyellr_scenario(runtime)
    lead = runtime.create_character("DragonHunter", level=24)
    rookie = runtime.create_character("GazeRookie", level=19)
    runtime.world.floors[7].unlocked = True
    sword = _give_sword_of_volupta(runtime, lead)

    # Reading the dormant scenario does not materialize mutable story state.
    assert "floor7_nirrnir_poison_story" not in runtime.world.global_flags
    dormant = aghyellr.nirrnir_status()
    assert dormant["stage"] == "not_started"
    assert "floor7_nirrnir_poison_story" not in runtime.world.global_flags

    lead.location_id = CASINO
    runtime.travel_actor(lead.actor_id, KORLOY_STABLES)
    poison = aghyellr.trigger_nirrnir_poisoning(lead.actor_id)
    assert poison["stage"] == "stabilised_silver_poison"
    assert poison["remaining_ms"] == NIRRNIR_STABILIZED_SURVIVAL_MS
    assert poison["ordinary_antidote_effective"] is False
    assert poison["nightfolk"]["night_rank"] == "dominus_nocte"

    nirrnir = runtime.actors[poison["nirrnir_actor_id"]]
    runtime.advance_world(47 * 60 * 60 * 1000)

    # The authoritative clock event has already mutated the poison state before any read API runs.
    raw_story = runtime.world.global_flags["floor7_nirrnir_poison_story"]
    assert raw_story["stage"] == "stabilised_silver_poison"
    assert nirrnir.alive is True
    assert nirrnir.hp <= int(nirrnir.max_hp * 0.05)
    poison_status = next(status for status in nirrnir.statuses if status.stack_key == "argent_serpent_silver_poison")
    assert 59 * 60 * 1000 <= poison_status.remaining_ms <= 60 * 60 * 1000

    story_before_read = deepcopy(raw_story)
    hp_before_read = nirrnir.hp
    poison = aghyellr.nirrnir_status()
    assert runtime.world.global_flags["floor7_nirrnir_poison_story"] == story_before_read
    assert nirrnir.hp == hp_before_read
    assert poison["alive"] is True
    assert 59 * 60 * 1000 <= poison["remaining_ms"] <= 60 * 60 * 1000

    lead.location_id = BOSS_ROOM
    rookie.location_id = BOSS_ROOM
    raid = aghyellr.start_aghyellr_raid([lead.actor_id, rookie.actor_id], bring_nirrnir=True)
    encounter = runtime.encounters[raid["encounter_id"]]
    boss = runtime.actors[raid["boss_id"]]
    assert nirrnir.actor_id in encounter.participants
    assert nirrnir.location_id == BOSS_ROOM
    assert raid["boss"]["definitionId"] == "aghyellr_the_igneous_wyrm"

    world_before_battle_minute = runtime.world.now_ms
    remaining_before_battle_minute = raid["nirrnir"]["remaining_ms"]
    runtime.advance_encounter(encounter.encounter_id, 60_000)
    poison_status = next(status for status in nirrnir.statuses if status.stack_key == "argent_serpent_silver_poison")
    assert poison_status.remaining_ms == remaining_before_battle_minute - 60_000
    synced = aghyellr.raid_status(raid["instance_id"])
    assert runtime.world.now_ms - world_before_battle_minute == 60_000
    assert runtime.encounter_world_time_ms(encounter.encounter_id) == runtime.world.now_ms
    assert "world_synced_encounter_ms" not in synced
    assert synced["nirrnir"]["remaining_ms"] == remaining_before_battle_minute - 60_000

    hp_before_bridge = lead.hp
    bridge = aghyellr.sustain_nirrnir_with_human_blood(raid["instance_id"], lead.actor_id)
    assert lead.hp < hp_before_bridge
    assert bridge["transformation"]["night_rank"] == "civis_nocte"
    assert bridge["transformation"]["direct_sunlight_weakness"] == "lethal"
    assert bridge["transformation"]["can_create_night_followers"] is False
    assert nirrnir.hp >= int(nirrnir.max_hp * 0.30)

    runtime.advance_encounter(encounter.encounter_id, HUMAN_BLOOD_BRIDGE_MS)
    assert runtime.world.global_flags["floor7_nirrnir_poison_story"]["human_blood_bridge_active"] is False
    assert nirrnir.metadata["human_blood_bridge_active"] is False

    reveal = aghyellr.reveal_doleful_nocturne(raid["instance_id"], lead.actor_id, sword.instance_id)
    assert reveal["true_name"] == "Doleful Nocturne"
    assert sword.metadata["true_identity_revealed"] is True
    assert runtime.catalog.weapons[SWORD_OF_VOLUPTA_ID].name == "Sword of Volupta"

    aghyellr.telegraph_intimidating_gaze(raid["instance_id"])
    gaze = aghyellr.resolve_intimidating_gaze(raid["instance_id"])
    assert rookie.actor_id in gaze["stunned_actor_ids"]
    assert lead.actor_id in gaze["level_20_plus_unaffected_actor_ids"]
    assert any(
        status.status_type is StatusType.STUN and status.stack_key == "aghyellr_intimidating_gaze"
        for status in rookie.statuses
    )
    assert not any(status.stack_key == "aghyellr_intimidating_gaze" for status in lead.statuses)

    boss.hp = 0
    boss.alive = False
    runtime._resolve_defeat(encounter, boss, lead.actor_id)
    assert runtime.world.floors[7].floor_boss_defeated
    assert aghyellr._raids()[raid["instance_id"]]["stage"] == "aghyellr_defeated"

    blood = aghyellr.collect_fresh_dragon_blood(raid["instance_id"], lead.actor_id)
    blood_ids = blood["blood_instance_ids"]
    assert len(blood_ids) == AGHYELLR_BLOOD_JAR_COUNT == 17
    assert all(blood_id in lead.inventory for blood_id in blood_ids)
    assert all(lead.inventory[blood_id].metadata["diluted"] is False for blood_id in blood_ids)
    assert all(lead.inventory[blood_id].metadata["preserved"] is False for blood_id in blood_ids)

    cured = aghyellr.administer_dragon_blood(raid["instance_id"], lead.actor_id, blood_ids[0])
    assert cured["stage"] == "cured"
    assert cured["alive"] is True
    assert cured["hp"] == cured["max_hp"]
    assert blood_ids[0] not in lead.inventory
    assert all(status.stack_key != "argent_serpent_silver_poison" for status in nirrnir.statuses)

    final = aghyellr.raid_status(raid["instance_id"])
    assert final["blood_jars_remaining_in_campaign"] == 16
    assert final["civis_actor_ids"] == [lead.actor_id]
    assert final["doleful_nocturne_revealed_instance_ids"] == [sword.instance_id]
