from sao_mcp.corpus.floor7 import SWORD_OF_VOLUPTA_ID
from sao_mcp.domain.models import StatusEffectState, StatusType
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor7_volupta import CASINO, MONSTER_ARENA, install_floor7_volupta_scenario


def test_volupta_casino_redeems_real_sword_with_canon_passives():
    runtime = HousingAincradRuntime(seed=53)
    volupta = install_floor7_volupta_scenario(runtime)
    player = runtime.create_character("VoluptaPlayer", level=24)
    runtime.world.floors[7].unlocked = True

    assert "floor_7_lectio" in runtime.world_map.locations
    assert "floor_7_volupta" in runtime.world_map.locations
    assert "floor_7_volupta_grand_casino" in runtime.world_map.locations
    assert "floor_7_main_town" not in runtime.world_map.locations

    player.location_id = CASINO
    player.col = 10_100_000
    wallet = volupta.buy_volcoins(player.actor_id, 101_000)
    assert wallet["volcoin"] == 101_000
    assert wallet["cor"] == 0
    assert wallet["exchange_rate"] == {"volcoin": 1, "cor": 100}

    runtime.travel_actor(player.actor_id, MONSTER_ARENA)
    match = volupta.open_arena_match("tiny_glyptodont_vs_verdian_bighorn")
    bet = volupta.place_arena_bet(
        player.actor_id,
        match["instance_id"],
        "verdian_bighorn",
        1_000,
    )
    assert bet["wallet"]["volcoin"] == 100_000
    resolved = volupta.resolve_arena_match(match["instance_id"], seed=4)
    assert resolved["status"] == "resolved"
    assert resolved["winner_id"] in {"tiny_glyptodont", "verdian_bighorn"}

    runtime.travel_actor(player.actor_id, CASINO)
    redemption = volupta.redeem_sword_of_volupta(player.actor_id)
    sword_id = redemption["sword_instance_id"]
    assert redemption["price_volcoin"] == 100_000
    assert player.inventory[sword_id].template_id == SWORD_OF_VOLUPTA_ID
    assert runtime.world.global_flags["floor7_sword_of_volupta_instance_id"] == sword_id

    # Equipping the prize immediately removes poison and enables its tagged passives.
    player.statuses.append(
        StatusEffectState(
            effect_id="test_poison_before_equip",
            status_type=StatusType.POISON,
            source_id=None,
            remaining_ms=30_000,
            magnitude=100,
        )
    )
    runtime.equip_item(player.actor_id, sword_id)
    assert all(status.status_type is not StatusType.POISON for status in player.statuses)
    assert player.metadata["equipment_hp_regeneration_instance_id"] == sword_id
    assert player.metadata["equipment_poison_nullification_instance_id"] == sword_id

    monster = runtime.create_training_monster("Volupta Target", level=5)
    monster.location_id = "floor_7_field"
    player.location_id = "floor_7_field"
    encounter = runtime.start_encounter([player.actor_id, monster.actor_id], zone_id="floor_7_field")

    player.hp = player.max_hp // 2
    before_regen = player.hp
    runtime.advance_encounter(encounter.encounter_id, 10_000)
    assert player.hp > before_regen

    # Poison applied after the weapon is equipped is nullified before it can tick.
    player.statuses.append(
        StatusEffectState(
            effect_id="test_poison_after_equip",
            status_type=StatusType.POISON,
            source_id=monster.actor_id,
            remaining_ms=10_000,
            magnitude=500,
        )
    )
    before_poison_tick = player.hp
    runtime.advance_encounter(encounter.encounter_id, 1_000)
    assert all(status.status_type is not StatusType.POISON for status in player.statuses)
    assert player.hp >= before_poison_tick

    strike = runtime.attack(encounter.encounter_id, player.actor_id, monster.actor_id, seed=999)
    assert strike.legal and strike.hit
    assert strike.critical is True
    assert strike.crit_chance == 1.0
