from sao_mcp.rules.raids import assign_raid_role
from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.runtime.aincrad_runtime import AincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def test_standalone_import_restores_boss_aware_runtime_and_boss_phase_state():
    runtime = AincradRuntime(seed=4)
    runtime.economy = EconomyRuntime()
    player = runtime.create_character("Saver", level=8)
    encounter, boss = runtime.start_floor_boss_encounter([player.actor_id], enforce_location=False)
    boss.metadata["boss_depleted_bars"] = 2
    boss.hp = 3_601
    runtime.attack(encounter.encounter_id, player.actor_id, boss.actor_id, defense="none", seed=1)
    assert runtime.boss_phase(boss).phase_id == "nodachi"
    assign_raid_role(runtime.world, encounter.encounter_id, player.actor_id, "attacker")

    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, AincradRuntime)
    loaded_boss = restored.actors[boss.actor_id]
    assert restored.boss_phase(loaded_boss).phase_id == "nodachi"
    assert restored.boss_bar_state(loaded_boss)["hpBars"] == 4
    assert restored.world.global_flags["raid_command_states"][encounter.encounter_id]["roles"][player.actor_id] == "attacker"
    assert restored.encounters[encounter.encounter_id].participants[boss.actor_id] is loaded_boss
