from sao_mcp.runtime.engine import GameRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def _go_to_horunka(rt: GameRuntime, actor_id: str) -> None:
    rt.travel_actor(actor_id, "floor_1_west_field")
    rt.travel_actor(actor_id, "floor_1_horunka")


def test_secret_medicine_canon_quest_produces_anneal_blade_with_eight_attempts():
    rt = GameRuntime(seed=9)
    actor = rt.create_character("QuestPlayer", level=3)
    _go_to_horunka(rt, actor.actor_id)
    progress = rt.accept_quest(actor.actor_id, "secret_medicine_of_the_forest")
    assert progress.quest_id == "secret_medicine_of_the_forest"

    rt.travel_actor(actor.actor_id, "floor_1_west_field")
    monster = rt.create_little_nepenthes(flowerhead=True)
    monster.hp = 1
    monster.max_hp = 1
    monster.agility = -100
    enc = rt.start_encounter([actor.actor_id, monster.actor_id], zone_id="floor_1_west_field")
    result = rt.attack(enc.encounter_id, actor.actor_id, monster.actor_id, defense="none", seed=5)
    assert result.hit
    assert any(item.template_id == "little_nepenthes_ovule" for item in actor.inventory.values())

    # The resolved encounter remains in history, but ordinary travel should be allowed once no enemy is alive.
    rt.travel_actor(actor.actor_id, "floor_1_horunka")
    claim = rt.claim_quest(actor.actor_id, "secret_medicine_of_the_forest")
    assert claim.quest_id == "secret_medicine_of_the_forest"
    anneal = [actor.inventory[item_id] for item_id in claim.item_instance_ids]
    assert len(anneal) == 1
    assert anneal[0].template_id == "anneal_blade"
    assert anneal[0].max_enhancement_attempts == 8
    assert not any(item.template_id == "little_nepenthes_ovule" for item in actor.inventory.values())


def test_secret_medicine_global_accept_cooldown_blocks_other_player():
    rt = GameRuntime(seed=1)
    a = rt.create_character("A")
    b = rt.create_character("B")
    _go_to_horunka(rt, a.actor_id)
    _go_to_horunka(rt, b.actor_id)
    rt.accept_quest(a.actor_id, "secret_medicine_of_the_forest")
    interaction = rt.interact_npc(b.actor_id, "npc_horunka_mother")
    assert "secret_medicine_of_the_forest" not in interaction.available_quests


def test_save_roundtrip_preserves_shared_actor_identity_world_quests_and_rng():
    rt = GameRuntime(seed=123)
    actor = rt.create_character("SavePlayer", level=4)
    monster = rt.create_training_monster(level=2)
    actor.location_id = monster.location_id
    enc = rt.start_encounter([actor.actor_id, monster.actor_id])
    rt.npcs.adjust_relationship(actor.actor_id, "npc_tutorial_instructor", 17)
    payload = export_runtime(rt)
    loaded = import_runtime(payload)

    assert loaded.world.now_ms == rt.world.now_ms
    assert loaded.actors[actor.actor_id].name == "SavePlayer"
    assert loaded.encounters[enc.encounter_id].participants[actor.actor_id] is loaded.actors[actor.actor_id]
    assert loaded.npcs.states["npc_tutorial_instructor"].relationship_by_actor[actor.actor_id] == 17
    assert loaded.rng.random() == rt.rng.random()
