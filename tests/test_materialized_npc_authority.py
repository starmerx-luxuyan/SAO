import pytest

from sao_mcp.corpus.floor4_nocturne import LAKE_YOFEL_WEST_SHORE
from sao_mcp.corpus.floor7_elfwar import LAVIK_ID
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def _materialized_lavik(actor_id: str, location_id: str) -> CombatantState:
    return CombatantState(
        actor_id=actor_id,
        name="Lavik Fen Cortassios",
        kind=EntityKind.NPC,
        level=28,
        max_hp=7600,
        hp=7600,
        strength=64,
        agility=62,
        cursor=CursorColor.YELLOW,
        location_id=location_id,
        metadata={"npc_definition_id": LAVIK_ID},
    )


def test_materialized_npc_actor_controls_interaction_location_across_save_load():
    runtime = HousingAincradRuntime(seed=271)
    player = runtime.create_character("Materialized NPC Witness", level=28)
    dormant_state_location = runtime.npcs.states[LAVIK_ID].location_id
    assert dormant_state_location != LAKE_YOFEL_WEST_SHORE

    lavik = _materialized_lavik("materialized_lavik_fixture", LAKE_YOFEL_WEST_SHORE)
    runtime.actors[lavik.actor_id] = lavik
    player.location_id = LAKE_YOFEL_WEST_SHORE

    interaction = runtime.interact_npc(player.actor_id, LAVIK_ID)
    assert interaction.location_id == LAKE_YOFEL_WEST_SHORE
    assert runtime.npc_location_id(LAVIK_ID) == LAKE_YOFEL_WEST_SHORE
    assert runtime.npcs.states[LAVIK_ID].location_id == dormant_state_location

    player.location_id = dormant_state_location
    with pytest.raises(ValueError, match="actor and NPC are not at the same location"):
        runtime.interact_npc(player.actor_id, LAVIK_ID)

    player.location_id = LAKE_YOFEL_WEST_SHORE
    saved = export_runtime(runtime)
    restored = import_runtime(saved)
    assert restored.npcs.states[LAVIK_ID].location_id == dormant_state_location
    assert restored.npc_location_id(LAVIK_ID) == LAKE_YOFEL_WEST_SHORE
    restored_interaction = restored.interact_npc(player.actor_id, LAVIK_ID)
    assert restored_interaction.location_id == LAKE_YOFEL_WEST_SHORE

    restored.actors[lavik.actor_id].alive = False
    with pytest.raises(ValueError, match="materialized NPC is not alive"):
        restored.interact_npc(player.actor_id, LAVIK_ID)


def test_duplicate_materialized_npc_identity_is_rejected():
    runtime = HousingAincradRuntime(seed=277)
    runtime.actors["lavik_one"] = _materialized_lavik("lavik_one", LAKE_YOFEL_WEST_SHORE)
    runtime.actors["lavik_two"] = _materialized_lavik("lavik_two", LAKE_YOFEL_WEST_SHORE)

    with pytest.raises(RuntimeError, match="multiple materialized actors exist"):
        runtime.npc_location_id(LAVIK_ID)
