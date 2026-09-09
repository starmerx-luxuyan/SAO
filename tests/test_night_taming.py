import pytest

from sao_mcp.domain.models import CursorColor
from sao_mcp.rules.nightfolk import become_civis_nocte, tame_lower_level_monster
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


def test_night_monster_control_uses_real_rank_level_and_monster_state():
    runtime = HousingAincradRuntime(seed=157)
    civis = runtime.create_character("NightTamer", level=20)
    civis.location_id = "floor_1_west_field"
    become_civis_nocte(civis, master_actor_id="dominus_fixture", now_ms=0)

    monster = runtime.create_training_monster("Tameable Beast", level=19)
    monster.location_id = civis.location_id
    monster.metadata["night_tameable"] = True

    result = tame_lower_level_monster(civis, monster, now_ms=1234)

    assert result.tamer_actor_id == civis.actor_id
    assert result.monster_actor_id == monster.actor_id
    assert result.monster_level == 19
    assert result.tamer_level == 20
    assert monster.metadata["night_tamed_by_actor_id"] == civis.actor_id
    assert monster.metadata["night_tamed_at_ms"] == 1234
    assert monster.cursor is CursorColor.YELLOW


def test_night_monster_control_rejects_non_night_and_equal_level_targets():
    runtime = HousingAincradRuntime(seed=163)
    mortal = runtime.create_character("Mortal", level=20)
    mortal.location_id = "floor_1_west_field"
    beast = runtime.create_training_monster("Beast", level=19)
    beast.location_id = mortal.location_id
    beast.metadata["night_tameable"] = True

    with pytest.raises(ValueError):
        tame_lower_level_monster(mortal, beast, now_ms=0)

    become_civis_nocte(mortal, master_actor_id="dominus_fixture", now_ms=0)
    equal = runtime.create_training_monster("Equal Beast", level=20)
    equal.location_id = mortal.location_id
    equal.metadata["night_tameable"] = True

    with pytest.raises(ValueError):
        tame_lower_level_monster(mortal, equal, now_ms=1)