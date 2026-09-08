from sao_mcp.corpus.floor7 import SWORD_OF_VOLUPTA_ID
from sao_mcp.corpus.floor7_intrigue import (
    LYKAON_DECOLORANT_ID,
    NARSOS_FRUIT_ID,
    WURTZ_STONE_ID,
)
from sao_mcp.domain.models import StatusEffectState, StatusType
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor7_intrigue import (
    KORLOY_STABLES,
    LOOSEROCK_FOREST,
    WEST_RIVERBANK,
    install_floor7_casino_intrigue_scenario,
)
from sao_mcp.scenarios.floor7_volupta import CASINO, MONSTER_ARENA, install_floor7_volupta_scenario


def test_volupta_cheating_investigation_casino_and_sword_passives_form_one_playable_loop():
    runtime = HousingAincradRuntime(seed=53)
    volupta = install_floor7_volupta_scenario(runtime)
    intrigue = install_floor7_casino_intrigue_scenario(runtime, volupta)
    player = runtime.create_character("VoluptaPlayer", level=24)
    runtime.world.floors[7].unlocked = True

    assert "floor_7_lectio" in runtime.world_map.locations
    assert "floor_7_volupta" in runtime.world_map.locations
    assert CASINO in runtime.world_map.locations
    assert KORLOY_STABLES in runtime.world_map.locations
    assert WEST_RIVERBANK in runtime.world_map.locations
    assert "floor_7_main_town" not in runtime.world_map.locations

    player.location_id = CASINO
    player.col = 10_100_000
    wallet = volupta.buy_volcoins(player.actor_id, 101_000)
    assert wallet["volcoin"] == 101_000
    assert wallet["cor"] == 0
    assert wallet["exchange_rate"] == {"volcoin": 1, "cor": 100}

    runtime.travel_actor(player.actor_id, MONSTER_ARENA)
    suspicious = volupta.open_arena_match("rusty_lykaon_vs_bouncy_slater")
    assert suspicious["arena_rank"] == {"rusty_lykaon": 6, "bouncy_slater": 6}
    assert suspicious["payout_multipliers"] == {"rusty_lykaon": 2.39, "bouncy_slater": 1.64}
    suspicious = volupta.resolve_arena_match(suspicious["instance_id"], seed=2)
    evidence = intrigue.inspect_first_match_cage(player.actor_id, suspicious["instance_id"])
    assert evidence["stage"] == "arena_dye_evidence_found"

    runtime.travel_actor(player.actor_id, CASINO)
    state = intrigue.report_evidence_to_nirrnir(player.actor_id)
    assert state["material_request"] == {NARSOS_FRUIT_ID: 20, WURTZ_STONE_ID: 50}

    runtime.travel_actor(player.actor_id, "floor_7_volupta")
    runtime.travel_actor(player.actor_id, LOOSEROCK_FOREST)
    state = intrigue.gather_narsos_fruit(player.actor_id)
    assert state["narsos_in_inventory"] == 20

    runtime.travel_actor(player.actor_id, "floor_7_volupta")
    runtime.travel_actor(player.actor_id, WEST_RIVERBANK)
    before_wurtz = runtime.world.now_ms
    state = intrigue.gather_wurtz_stones(player.actor_id)
    assert runtime.world.now_ms == before_wurtz + 5 * 60 * 60 * 1000
    assert state["wurtz_in_inventory"] == 50

    runtime.travel_actor(player.actor_id, "floor_7_volupta")
    runtime.travel_actor(player.actor_id, CASINO)
    before_brew = runtime.world.now_ms
    state = intrigue.brew_decolorant(player.actor_id)
    assert runtime.world.now_ms == before_brew + 3 * 60 * 60 * 1000
    assert state["stage"] == "decolorant_ready_infiltrate_stables"
    assert state["narsos_in_inventory"] == 0
    assert state["wurtz_in_inventory"] == 0
    assert any(item.template_id == LYKAON_DECOLORANT_ID for item in player.inventory.values())

    runtime.travel_actor(player.actor_id, KORLOY_STABLES)
    disguised = intrigue.discover_dyed_lykaon(player.actor_id)
    lykaon = runtime.actors[disguised["disguised_lykaon_actor_id"]]
    assert disguised["visible_lykaon_species"] == "Rusty Lykaon"
    assert lykaon.metadata["monster_id"] == "rusty_lykaon"
    assert lykaon.metadata["rubrabium_dyed"] is True

    revealed = intrigue.apply_decolorant(player.actor_id)
    assert revealed["stage"] == "storm_lykaon_revealed"
    assert revealed["visible_lykaon_species"] == "Storm Lykaon"
    assert lykaon.metadata["monster_id"] == "storm_lykaon"
    assert lykaon.metadata["rubrabium_dyed"] is False

    runtime.travel_actor(player.actor_id, CASINO)
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
    assert runtime.catalog.weapons[SWORD_OF_VOLUPTA_ID].name == "Sword of Volupta"
    assert player.inventory[sword_id].metadata["true_identity_known_to_actor"] is False
    assert runtime.world.global_flags["floor7_sword_of_volupta_instance_id"] == sword_id

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
