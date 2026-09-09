import pytest

from sao_mcp.corpus.floor6_elfwar import KIZMEL_ID
from sao_mcp.corpus.floor8_world import FOREST_ELF_SACRED_WOODS, SLUVA
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind
from sao_mcp.rules.access import actor_faction_ids
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


def test_sluva_access_rule_blocks_dark_elf_definition_before_group_time_or_movement():
    runtime = HousingAincradRuntime(seed=281)
    runtime.world.floors[8].unlocked = True
    player = runtime.create_character("SluvaVisitor", level=28)
    player.location_id = FOREST_ELF_SACRED_WOODS
    kizmel = CombatantState(
        actor_id="kizmel_access_fixture",
        name="Kizmel",
        kind=EntityKind.NPC,
        level=28,
        max_hp=8000,
        hp=8000,
        strength=68,
        agility=70,
        cursor=CursorColor.YELLOW,
        location_id=FOREST_ELF_SACRED_WOODS,
        metadata={"npc_definition_id": KIZMEL_ID},
    )
    runtime.actors[kizmel.actor_id] = kizmel

    assert actor_faction_ids(kizmel) == ("dark_elves",)
    started = runtime.world.now_ms
    with pytest.raises(ValueError, match="dark_elves"):
        travel_together(runtime, [player.actor_id, kizmel.actor_id], SLUVA)
    assert runtime.world.now_ms == started
    assert player.location_id == FOREST_ELF_SACRED_WOODS
    assert kizmel.location_id == FOREST_ELF_SACRED_WOODS

    with pytest.raises(ValueError, match="dark_elves"):
        runtime.travel_actor(kizmel.actor_id, SLUVA)
    assert runtime.world.now_ms == started
    assert kizmel.location_id == FOREST_ELF_SACRED_WOODS

    moved = runtime.travel_actor(player.actor_id, SLUVA)
    assert moved.to_location_id == SLUVA
    assert player.location_id == SLUVA
    assert kizmel.location_id == FOREST_ELF_SACRED_WOODS
