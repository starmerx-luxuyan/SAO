from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sao_mcp.corpus.floor22 import FOREST_SITE, TOTO_ID
from sao_mcp.rules.npcs import CORE_NPCS
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime
from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario
from scripts.build_kageaki_frontline_recovery_v132 import build_recovery


def test_floor22_install_does_not_materialize_future_toto():
    runtime = HousingAincradRuntime(seed=31)
    install_floor22_witch_scenario(runtime)
    assert TOTO_ID not in runtime.npcs.states
    assert TOTO_ID not in runtime.npc_actor_cores


def test_floor22_start_materializes_toto_after_participant_validation():
    runtime = HousingAincradRuntime(seed=32)
    scenario = install_floor22_witch_scenario(runtime)
    player = runtime.create_character("Floor22Start", level=30)
    runtime.world.floors[22].unlocked = True
    player.location_id = FOREST_SITE
    scenario.start([player.actor_id])
    assert TOTO_ID in runtime.npcs.states
    assert TOTO_ID in runtime.npc_actor_cores


def test_floor1_recovery_roundtrips_through_runtime_with_floor22_scenario_installed():
    save_json = build_recovery()
    runtime = SocialCommunicationAincradRuntime(seed=33)
    install_floor22_witch_scenario(runtime)
    assert TOTO_ID not in runtime.npcs.states
    import_runtime(save_json, into=runtime)
    assert TOTO_ID not in runtime.npcs.states
    assert TOTO_ID not in runtime.npc_actor_cores
    assert export_runtime(runtime) == save_json


def test_floor22_registration_is_isolated_between_runtime_instances():
    first = HousingAincradRuntime(seed=34)
    scenario = install_floor22_witch_scenario(first)
    player = first.create_character("Floor22Isolation", level=30)
    first.world.floors[22].unlocked = True
    player.location_id = FOREST_SITE
    scenario.start([player.actor_id])
    assert TOTO_ID in first.npcs.definitions
    assert TOTO_ID in first.npcs.states

    second = HousingAincradRuntime(seed=35)
    assert TOTO_ID not in second.npcs.definitions
    assert TOTO_ID not in second.npcs.states
    assert TOTO_ID not in CORE_NPCS


def test_floor22_progress_save_restores_dynamic_toto_state():
    runtime = SocialCommunicationAincradRuntime(seed=36)
    scenario = install_floor22_witch_scenario(runtime)
    player = runtime.create_character("Floor22Persist", level=30)
    runtime.world.floors[22].unlocked = True
    player.location_id = FOREST_SITE
    scenario.start([player.actor_id])
    save_json = export_runtime(runtime)

    restored = SocialCommunicationAincradRuntime(seed=37)
    install_floor22_witch_scenario(restored)
    import_runtime(save_json, into=restored)
    assert TOTO_ID in restored.npcs.states
    assert TOTO_ID in restored.npc_actor_cores
    assert export_runtime(restored) == save_json
