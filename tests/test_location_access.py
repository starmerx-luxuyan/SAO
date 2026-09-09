import pytest

from sao_mcp.corpus.floor6_elfwar import KIZMEL_ID
from sao_mcp.corpus.floor8_world import FOREST_ELF_SACRED_WOODS, FRIEBEN, SLUVA
from sao_mcp.corpus.location_access import DARK_ELVES, LOCATION_ACCESS_RULES, LocationAccessRule
from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind, ItemInstance
from sao_mcp.rules.access import actor_faction_ids
from sao_mcp.rules.group_travel import travel_together
from sao_mcp.rules.inventory import add_item
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


def _kizmel(actor_id: str, location_id: str) -> CombatantState:
    return CombatantState(
        actor_id=actor_id,
        name="Kizmel",
        kind=EntityKind.NPC,
        level=28,
        max_hp=8000,
        hp=8000,
        strength=68,
        agility=70,
        cursor=CursorColor.YELLOW,
        location_id=location_id,
        metadata={"npc_definition_id": KIZMEL_ID},
    )


def test_sluva_access_rule_blocks_dark_elf_definition_before_group_time_or_movement():
    runtime = HousingAincradRuntime(seed=281)
    runtime.world.floors[8].unlocked = True
    player = runtime.create_character("SluvaVisitor", level=28)
    player.location_id = FOREST_ELF_SACRED_WOODS
    kizmel = _kizmel("kizmel_access_fixture", FOREST_ELF_SACRED_WOODS)
    runtime.actors[kizmel.actor_id] = kizmel

    assert actor_faction_ids(kizmel) == (DARK_ELVES,)
    started = runtime.world.now_ms
    with pytest.raises(ValueError, match=DARK_ELVES):
        travel_together(runtime, [player.actor_id, kizmel.actor_id], SLUVA)
    assert runtime.world.now_ms == started
    assert player.location_id == FOREST_ELF_SACRED_WOODS
    assert kizmel.location_id == FOREST_ELF_SACRED_WOODS

    with pytest.raises(ValueError, match=DARK_ELVES):
        runtime.travel_actor(kizmel.actor_id, SLUVA)
    assert runtime.world.now_ms == started
    assert kizmel.location_id == FOREST_ELF_SACRED_WOODS

    moved = runtime.travel_actor(player.actor_id, SLUVA)
    assert moved.to_location_id == SLUVA
    assert player.location_id == SLUVA
    assert kizmel.location_id == FOREST_ELF_SACRED_WOODS


def test_restricted_teleport_gate_rejects_before_crystal_is_consumed(monkeypatch):
    runtime = HousingAincradRuntime(seed=283)
    runtime.world.floors[8].unlocked = True
    runtime.world.floors[8].main_town_gate_active = True
    kizmel = _kizmel("kizmel_teleport_fixture", "floor_7_volupta")
    runtime.actors[kizmel.actor_id] = kizmel
    crystal = ItemInstance(
        instance_id="restricted_gate_crystal",
        template_id="teleport_crystal",
        owner_id=kizmel.actor_id,
        quantity=1,
    )
    add_item(kizmel, crystal, runtime.catalog, allow_overweight=True)
    monkeypatch.setitem(
        LOCATION_ACCESS_RULES,
        FRIEBEN,
        LocationAccessRule(FRIEBEN, forbidden_faction_ids=(DARK_ELVES,)),
    )

    with pytest.raises(ValueError, match=DARK_ELVES):
        runtime.teleport_actor(kizmel.actor_id, crystal.instance_id, FRIEBEN)

    assert kizmel.location_id == "floor_7_volupta"
    assert crystal.instance_id in kizmel.inventory
    assert kizmel.inventory[crystal.instance_id].quantity == 1
