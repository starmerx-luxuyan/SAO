from sao_mcp.corpus.floor6_elfwar import KIZMEL_ID
from sao_mcp.corpus.floor7_elfwar import KIZMEL_SABER_ID, LAVIK_ID, QUEST_ID
from sao_mcp.corpus.floor7_intrigue import NARSOS_FRUIT_ID, NARSOS_REQUIRED
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.scenarios.floor7_elfwar import (
    BLACKOUT_AND_DESCENT_MS,
    KIZMEL_CONVINCE_MS,
    LAVIK_CELL,
    LAVIK_SEARCH_MS,
    LOOSEROCK_FOREST,
    PALACE,
    POST_ESCAPE_NARSOS_GATHER_MS,
    RETURN_TO_VOLUPTA_MS,
    SEVENTH_PRISON,
    VOLUPTA,
    WEAPON_RECOVERY_MS,
    ARREST_PROCESSING_MS,
    ASCENT_AND_GUARD_SUBDUAL_MS,
    CELL_LOCK_BURN_MS,
    install_floor7_elfwar_scenario,
)


def test_harin_tree_palace_escape_preserves_player_and_existing_kizmel_weapons():
    runtime = HousingAincradRuntime(seed=59)
    elfwar = install_floor7_elfwar_scenario(runtime)
    player = runtime.create_character("HarinPrisoner", level=27)
    runtime.world.floors[7].unlocked = True
    player.location_id = PALACE
    original_weapon_id = player.equipment["weapon"]
    original_weapon_template = player.inventory[original_weapon_id].template_id
    kizmel_npc_state_location = runtime.npcs.states[KIZMEL_ID].location_id
    lavik_npc_state_location = runtime.npcs.states[LAVIK_ID].location_id

    # Simulate continuity from the prior Elf War floors: Kizmel already exists in the campaign
    # and already owns an equipped weapon instance before Harin's arrest.
    saber_template = runtime.catalog.weapons[KIZMEL_SABER_ID]
    kizmel_weapon = ItemInstance(
        instance_id="existing_kizmel_saber",
        template_id=KIZMEL_SABER_ID,
        owner_id="existing_kizmel",
        durability=saber_template.base_durability,
        max_durability=saber_template.base_durability,
    )
    preexisting_kizmel = CombatantState(
        actor_id="existing_kizmel",
        name="Kizmel",
        kind=EntityKind.NPC,
        level=43,
        max_hp=9000,
        hp=9000,
        strength=72,
        agility=70,
        armor=285,
        evasion=15,
        cursor=CursorColor.YELLOW,
        location_id=PALACE,
        inventory={kizmel_weapon.instance_id: kizmel_weapon},
        equipment={"weapon": kizmel_weapon.instance_id},
        skill_proficiencies={"one_hand_curved_sword": 760.0, "parry": 590.0},
        metadata={"npc_definition_id": KIZMEL_ID, "dark_elf_royal_guard": True},
    )
    runtime.actors[preexisting_kizmel.actor_id] = preexisting_kizmel
    started_at = runtime.world.now_ms

    state = elfwar.arrive_and_be_arrested([player.actor_id])
    assert state["stage"] == "imprisoned_b2"
    assert state["kizmel_preexisting_actor_id"] == preexisting_kizmel.actor_id
    assert state["kizmel_confiscated_item_ids"] == [kizmel_weapon.instance_id]
    assert original_weapon_id not in player.inventory
    assert player.equipment.get("weapon") is None
    assert kizmel_weapon.instance_id not in preexisting_kizmel.inventory
    assert preexisting_kizmel.equipment.get("weapon") is None
    assert preexisting_kizmel.location_id == SEVENTH_PRISON
    assert runtime.npcs.states[KIZMEL_ID].location_id == kizmel_npc_state_location
    assert runtime.npc_location_id(KIZMEL_ID) == SEVENTH_PRISON
    storage = runtime.actors[state["storage_actor_id"]]
    assert storage.inventory[original_weapon_id].template_id == original_weapon_template
    assert storage.inventory[original_weapon_id].owner_id == storage.actor_id
    assert storage.inventory[kizmel_weapon.instance_id].template_id == KIZMEL_SABER_ID
    assert storage.inventory[kizmel_weapon.instance_id].owner_id == storage.actor_id

    state = elfwar.burn_cell_lock(state["instance_id"])
    assert state["cell_lock_burns"] == 7
    state = elfwar.recover_confiscated_weapons(state["instance_id"])
    assert player.equipment["weapon"] == original_weapon_id
    assert player.inventory[original_weapon_id].template_id == original_weapon_template
    assert player.inventory[original_weapon_id].owner_id == player.actor_id

    state = elfwar.meet_lavik(state["instance_id"])
    lavik = runtime.actors[state["lavik_actor_id"]]
    assert lavik.name == "Lavik Fen Cortassios"
    assert lavik.metadata["harin_status"] == "fugitive"
    assert lavik.equipment.get("weapon") is not None
    assert lavik.location_id == LAVIK_CELL
    assert runtime.npcs.states[LAVIK_ID].location_id == lavik_npc_state_location
    assert runtime.npc_location_id(LAVIK_ID) == LAVIK_CELL

    state = elfwar.lavik_subdues_guard_post(state["instance_id"])
    assert state["guards_subdued_nonlethally"] == 2
    state = elfwar.rejoin_kizmel(state["instance_id"])
    kizmel = runtime.actors[state["kizmel_actor_id"]]
    assert kizmel.actor_id == preexisting_kizmel.actor_id
    assert kizmel.metadata["harin_status"] == "prisoner_refusing_escape"
    assert kizmel.equipment["weapon"] == kizmel_weapon.instance_id
    assert kizmel.inventory[kizmel_weapon.instance_id].owner_id == kizmel.actor_id
    assert runtime.npcs.states[KIZMEL_ID].location_id == kizmel_npc_state_location
    assert runtime.npc_location_id(KIZMEL_ID) == SEVENTH_PRISON

    state = elfwar.convince_kizmel_to_escape(state["instance_id"])
    assert state["kizmel_status"] == "fugitive_clearing_own_name"
    state = elfwar.blackout_and_escape(state["instance_id"])
    assert state["palace_blackout"] is True
    assert player.location_id == LOOSEROCK_FOREST
    assert state["kizmel_location_id"] == LOOSEROCK_FOREST
    assert state["lavik_location_id"] == LOOSEROCK_FOREST
    assert runtime.npcs.states[KIZMEL_ID].location_id == kizmel_npc_state_location
    assert runtime.npc_location_id(KIZMEL_ID) == LOOSEROCK_FOREST
    assert runtime.npcs.states[LAVIK_ID].location_id == lavik_npc_state_location
    assert runtime.npc_location_id(LAVIK_ID) == LOOSEROCK_FOREST
    assert state["players"][player.actor_id]["quest_completed"] is True
    assert QUEST_ID in runtime.quests.completed_by_actor[player.actor_id]

    state = elfwar.gather_narsos_and_part_with_lavik(state["instance_id"], player.actor_id)
    narsos_count = sum(
        item.quantity for item in player.inventory.values() if item.template_id == NARSOS_FRUIT_ID
    )
    assert narsos_count == NARSOS_REQUIRED
    assert state["lavik_departed"] is True
    assert state["kizmel_location_id"] == LOOSEROCK_FOREST
    assert runtime.npcs.states[LAVIK_ID].location_id == lavik_npc_state_location
    assert runtime.npc_location_id(LAVIK_ID) == "floor_7_field"

    state = elfwar.return_to_volupta_with_kizmel(state["instance_id"])
    assert state["stage"] == "returned_to_volupta_with_kizmel"
    assert player.location_id == VOLUPTA
    assert state["kizmel_location_id"] == VOLUPTA
    assert kizmel.equipment["weapon"] == kizmel_weapon.instance_id
    assert runtime.npcs.states[KIZMEL_ID].location_id == kizmel_npc_state_location
    assert runtime.npc_location_id(KIZMEL_ID) == VOLUPTA

    elapsed = runtime.world.now_ms - started_at
    expected = (
        ARREST_PROCESSING_MS
        + CELL_LOCK_BURN_MS
        + WEAPON_RECOVERY_MS
        + LAVIK_SEARCH_MS
        + ASCENT_AND_GUARD_SUBDUAL_MS
        + KIZMEL_CONVINCE_MS
        + BLACKOUT_AND_DESCENT_MS
        + POST_ESCAPE_NARSOS_GATHER_MS
        + RETURN_TO_VOLUPTA_MS
    )
    assert elapsed == expected
