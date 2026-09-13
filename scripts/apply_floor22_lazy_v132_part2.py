from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise RuntimeError(f"{path}: expected {count} occurrences, found {found}: {old[:100]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Every runtime owns its NPC definition registry. Scenario-local registration must never
# mutate module-level CORE_NPCS or leak into later campaigns in the same Python process.
replace(
    "src/sao_mcp/rules/npcs.py",
    '''    def __init__(self, definitions: dict[str, NPCDefinition] | None = None) -> None:\n        self.definitions = definitions or CORE_NPCS\n        self.states = {''',
    '''    def __init__(self, definitions: dict[str, NPCDefinition] | None = None) -> None:\n        self.definitions = dict(CORE_NPCS if definitions is None else definitions)\n        self.states = {''',
)

# The first patch writes this regression file. Strengthen it with cross-runtime isolation
# and restore Floor 22 saves into the same runtime class that produced them.
test_path = ROOT / "tests/test_floor22_lazy_materialization.py"
text = test_path.read_text(encoding="utf-8")
text = text.replace(
    '''from sao_mcp.corpus.floor22 import FOREST_SITE, TOTO_ID\n''',
    '''from sao_mcp.corpus.floor22 import FOREST_SITE, TOTO_ID\nfrom sao_mcp.rules.npcs import CORE_NPCS\n''',
    1,
)
old = '''def test_floor22_progress_save_restores_dynamic_toto_state():\n    runtime = HousingAincradRuntime(seed=34)\n    scenario = install_floor22_witch_scenario(runtime)\n    player = runtime.create_character("Floor22Persist", level=30)\n    runtime.world.floors[22].unlocked = True\n    player.location_id = FOREST_SITE\n    scenario.start([player.actor_id])\n    save_json = export_runtime(runtime)\n\n    restored = import_runtime(save_json)\n    assert TOTO_ID in restored.npcs.states\n    assert TOTO_ID in restored.npc_actor_cores\n    assert export_runtime(restored) == save_json\n'''
new = '''def test_floor22_registration_is_isolated_between_runtime_instances():\n    first = HousingAincradRuntime(seed=34)\n    scenario = install_floor22_witch_scenario(first)\n    player = first.create_character("Floor22Isolation", level=30)\n    first.world.floors[22].unlocked = True\n    player.location_id = FOREST_SITE\n    scenario.start([player.actor_id])\n    assert TOTO_ID in first.npcs.definitions\n    assert TOTO_ID in first.npcs.states\n\n    second = HousingAincradRuntime(seed=35)\n    assert TOTO_ID not in second.npcs.definitions\n    assert TOTO_ID not in second.npcs.states\n    assert TOTO_ID not in CORE_NPCS\n\n\ndef test_floor22_progress_save_restores_dynamic_toto_state():\n    runtime = HousingAincradRuntime(seed=36)\n    scenario = install_floor22_witch_scenario(runtime)\n    player = runtime.create_character("Floor22Persist", level=30)\n    runtime.world.floors[22].unlocked = True\n    player.location_id = FOREST_SITE\n    scenario.start([player.actor_id])\n    save_json = export_runtime(runtime)\n\n    restored = HousingAincradRuntime(seed=37)\n    install_floor22_witch_scenario(restored)\n    import_runtime(save_json, into=restored)\n    assert TOTO_ID in restored.npcs.states\n    assert TOTO_ID in restored.npc_actor_cores\n    assert export_runtime(restored) == save_json\n'''
if text.count(old) != 1:
    raise RuntimeError("generated Floor 22 persistence regression changed unexpectedly")
test_path.write_text(text.replace(old, new), encoding="utf-8")

print("applied per-runtime NPC registry isolation patch")
