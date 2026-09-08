from sao_mcp.domain.models import StatusType
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor7_aghyellr import (
    BOSS_ROOM,
    CASINO,
    KORLOY_STABLES,
    NIRRNIR_STABILIZED_SURVIVAL_MS,
    install_floor7_aghyellr_scenario,
)


def test_floor7_nirrnir_countdown_and_aghyellr_cure_are_real_world_state():
    runtime = HousingAincradRuntime(seed=59)
    aghyellr = install_floor7_aghyellr_scenario(runtime)
    lead = runtime.create_character("DragonHunter", level=24)
    rookie = runtime.create_character("GazeRookie", level=19)
    runtime.world.floors[7].unlocked = True

    lead.location_id = CASINO
    runtime.travel_actor(lead.actor_id, KORLOY_STABLES)
    poison = aghyellr.trigger_nirrnir_poisoning(lead.actor_id)
    assert poison["stage"] == "stabilised_silver_poison"
    assert poison["remaining_ms"] == NIRRNIR_STABILIZED_SURVIVAL_MS
    assert poison["ordinary_antidote_effective"] is False

    runtime.advance_world(47 * 60 * 60 * 1000)
    poison = aghyellr.nirrnir_status()
    assert poison["alive"] is True
    assert 59 * 60 * 1000 <= poison["remaining_ms"] <= 60 * 60 * 1000

    lead.location_id = BOSS_ROOM
    rookie.location_id = BOSS_ROOM
    raid = aghyellr.start_aghyellr_raid([lead.actor_id, rookie.actor_id], bring_nirrnir=True)
    encounter = runtime.encounters[raid["encounter_id"]]
    boss = runtime.actors[raid["boss_id"]]
    nirrnir = runtime.actors[raid["nirrnir_actor_id"]]
    assert nirrnir.actor_id in encounter.participants
    assert nirrnir.location_id == BOSS_ROOM
    assert raid["boss"]["definitionId"] == "aghyellr_the_igneous_wyrm"

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

    blood = aghyellr.collect_fresh_dragon_blood(raid["instance_id"], lead.actor_id)
    blood_id = blood["blood_instance_id"]
    assert blood_id in lead.inventory
    assert lead.inventory[blood_id].metadata["diluted"] is False
    assert lead.inventory[blood_id].metadata["preserved"] is False

    cured = aghyellr.administer_dragon_blood(lead.actor_id, blood_id)
    assert cured["stage"] == "cured"
    assert cured["alive"] is True
    assert cured["hp"] == cured["max_hp"]
    assert blood_id not in lead.inventory
    assert all(status.stack_key != "argent_serpent_silver_poison" for status in nirrnir.statuses)
