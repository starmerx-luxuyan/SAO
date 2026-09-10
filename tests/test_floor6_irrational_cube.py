from sao_mcp.corpus.floor6_elfwar import MEDITATION_SKILL_ID
from sao_mcp.corpus.floor6_finale import COMBINED_IRON_KEY_ID, GOLDEN_CUBE_ID
from sao_mcp.domain.models import CursorColor, ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor6_buxum import install_floor6_buxum_scenario
from sao_mcp.scenarios.floor6_elfwar import install_floor6_elfwar_scenario
from sao_mcp.scenarios.floor6_irrational_cube import install_floor6_irrational_cube_scenario


def test_floor6_release_finale_preserves_cube_and_combined_key_instances_through_buxum():
    runtime = HousingAincradRuntime(seed=43)
    cube = install_floor6_irrational_cube_scenario(runtime)
    elfwar = install_floor6_elfwar_scenario(runtime)
    buxum_scene = install_floor6_buxum_scenario(runtime, cube)
    player = runtime.create_character("CubeSolver", level=42)
    runtime.world.floors[6].unlocked = True
    player.location_id = "floor_6_boss_room"
    player.skill_proficiencies[MEDITATION_SKILL_ID] = 500.0
    player.metadata.setdefault("skill_mods", {})[MEDITATION_SKILL_ID] = ["awakening"]

    golden_cube = ItemInstance("test_golden_cube", GOLDEN_CUBE_ID, player.actor_id)
    add_item(player, golden_cube, runtime.catalog, allow_overweight=True)

    # The same steel-key instance created from Cylon/Theano's paired keys has already been stolen by Kysarah.
    kysarah = elfwar._create_kysarah_actor()
    combined_key = ItemInstance(
        "test_combined_iron_key",
        COMBINED_IRON_KEY_ID,
        kysarah.actor_id,
        metadata={"component_instance_ids": ["cylon_key_original", "theano_key_original"]},
    )
    add_item(kysarah, combined_key, runtime.catalog, allow_overweight=True)
    runtime.world.global_flags["floor6_kysarah_combined_iron_key_created"] = True
    runtime.world.global_flags["floor6_combined_iron_key_instance_id"] = combined_key.instance_id
    assert "floor6_combined_iron_key_holder_id" not in runtime.world.global_flags

    state = cube.activate_guardian(
        [player.actor_id],
        player.actor_id,
        golden_cube.instance_id,
    )
    boss = runtime.actors[state["boss_id"]]
    encounter = runtime.encounters[state["encounter_id"]]
    assert state["stage"] == "number_face_puzzle"
    assert state["target_code"] == "834159672"
    assert state["numbered_armor_active"] is True
    assert state["hp_floor"] == boss.max_hp
    assert golden_cube.instance_id not in player.inventory
    assert boss.inventory[golden_cube.instance_id].template_id == GOLDEN_CUBE_ID

    state = cube.rotate_row(state["instance_id"], 2, "left")
    state = cube.rotate_column(state["instance_id"], 2, "up")
    state = cube.rotate_row(state["instance_id"], 0, "right")
    assert state["puzzle_solved"]
    assert state["face"] == [[8, 3, 4], [1, 5, 9], [6, 7, 2]]
    assert state["stage"] == "black_core_battle"
    assert state["black_core_exposed"] is True
    assert state["hp_floor"] == 1

    # Generic combat reaches the last pixel; the finale mechanic decides what happens next.
    boss.hp = 1
    boss.alive = True
    betrayal = buxum_scene.trigger_betrayal(state["instance_id"])
    buxum = runtime.actors[betrayal["buxum_actor_id"]]

    assert combined_key.instance_id not in kysarah.inventory
    assert combined_key.instance_id in boss.inventory
    assert boss.inventory[combined_key.instance_id].owner_id == boss.actor_id
    assert betrayal["combined_key_holder_id"] == boss.actor_id
    assert "floor6_combined_iron_key_holder_id" not in runtime.world.global_flags
    assert betrayal["cube_state"]["combined_key_in_reverse_keyhole"] is True
    assert golden_cube.instance_id in buxum.inventory
    assert buxum.cursor is CursorColor.ORANGE
    assert player.actor_id in betrayal["bound_actor_ids"]

    released = buxum_scene.break_bind_with_awakening(state["instance_id"], player.actor_id)
    assert released["stage"] == "awakening_counterattack"
    assert player.actor_id not in released["bound_actor_ids"]
    assert player.metadata["floor6_awakening_broke_bind"] is True

    # The actual duel can use ordinary PvP. This test only crosses the simulation retreat threshold.
    buxum.hp = max(1, int(buxum.max_hp * 0.20))
    buxum.alive = True
    retreat = buxum_scene.resolve_buxum_retreat(state["instance_id"])
    assert retreat["stage"] == "golden_cube_dropped"
    assert buxum.actor_id not in encounter.participants

    recovered = buxum_scene.recover_golden_cube(state["instance_id"], player.actor_id)
    assert recovered["stage"] == "golden_cube_recovered"
    assert golden_cube.instance_id in player.inventory
    assert player.inventory[golden_cube.instance_id].owner_id == player.actor_id

    cleared = cube.reinsert_cube_and_destroy_core(state["instance_id"], player.actor_id)
    assert cleared["stage"] == "cleared"
    assert cleared["golden_cube_destroyed"] is True
    assert golden_cube.instance_id not in player.inventory
    assert combined_key.instance_id not in player.inventory
    assert combined_key.instance_id not in boss.inventory
    assert cleared["combined_key_grounded"] is True
    assert not boss.alive and boss.hp == 0
    assert runtime.world.floors[6].floor_boss_defeated

    # The boss defeat hook advances Buxum's branch before any Buxum status read.
    assert buxum_scene._state(state["instance_id"])["stage"] == "floor_cleared"
    grounded = buxum_scene.status(state["instance_id"])
    assert grounded["combined_key_holder_id"] is None

    key_recovery = cube.recover_surviving_combined_key(state["instance_id"], player.actor_id)
    assert key_recovery["combined_key_instance_id"] == combined_key.instance_id
    assert combined_key.instance_id in player.inventory
    assert player.inventory[combined_key.instance_id].owner_id == player.actor_id
    assert buxum_scene.status(state["instance_id"])["combined_key_holder_id"] == player.actor_id
