from sao_mcp.corpus.floor5 import RING_OF_LUMINESCENCE
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor5_karluin import (
    BLINK_AND_BRINK,
    CATACOMBS_L1,
    CATACOMBS_LOWER,
    KARLUIN,
    RELIC_BONUS_MS,
    RUINED_TEMPLE,
    install_floor5_karluin_scenario,
)


def test_karluin_relic_bonus_and_shrewman_robbing_use_real_item_instances():
    runtime = HousingAincradRuntime(seed=37)
    karluin = install_floor5_karluin_scenario(runtime)
    player = runtime.create_character("RelicHunter", level=24)
    runtime.world.floors[5].unlocked = True
    player.location_id = KARLUIN

    runtime.travel_actor(player.actor_id, BLINK_AND_BRINK)
    buff = karluin.order_blue_blueberry_tart(player.actor_id)
    assert buff["active"]
    assert buff["remaining_ms"] == RELIC_BONUS_MS

    runtime.travel_actor(player.actor_id, KARLUIN)
    runtime.travel_actor(player.actor_id, RUINED_TEMPLE)
    ring = karluin.search_relic(player.actor_id)
    assert ring.template_id == RING_OF_LUMINESCENCE
    glow = karluin.breathe_on_luminescence_ring(player.actor_id, ring.instance_id)
    assert glow["luminescent"] is True
    assert player.inventory[ring.instance_id].metadata["luminescent"] is True

    runtime.travel_actor(player.actor_id, KARLUIN)
    runtime.travel_actor(player.actor_id, CATACOMBS_L1)
    runtime.travel_actor(player.actor_id, CATACOMBS_LOWER)

    potion = next(item for item in player.inventory.values() if item.template_id == "healing_potion_basic")
    original_id = potion.instance_id
    original_quantity = potion.quantity
    encounter, thief, stolen = karluin.trigger_shrewman_robbery(player.actor_id, original_id)
    assert original_id not in player.inventory
    assert stolen.instance_id == original_id
    assert stolen.owner_id == thief.actor_id
    assert thief.inventory[original_id].quantity == original_quantity

    thief.hp = 0
    thief.alive = False
    runtime._resolve_defeat(encounter, thief, player.actor_id)
    recovered = karluin.recover_shrewman_stolen_items(player.actor_id, thief.actor_id)
    assert recovered == [original_id]
    assert player.inventory[original_id].owner_id == player.actor_id
    assert player.inventory[original_id].quantity == original_quantity

    wraith_encounter, wraith = karluin.create_mournful_wraith_encounter(player.actor_id)
    assert wraith.metadata["monster_id"] == "mournful_wraith"
    assert wraith.actor_id in wraith_encounter.participants
