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


replace(
    "src/sao_mcp/scenarios/floor22_witch.py",
    '''        runtime.quests.definitions.setdefault(QUEST_ID, floor22_quest_definition())\n        install_floor22_npc(runtime)\n        runtime.register_world_event_rule(''',
    '''        runtime.quests.definitions.setdefault(QUEST_ID, floor22_quest_definition())\n        runtime.register_world_event_rule(''',
)

replace(
    "src/sao_mcp/scenarios/floor22_witch.py",
    '''        runtime.evaluate_world_events()\n\n    def instances(self) -> dict:''',
    '''        runtime.evaluate_world_events()\n\n    def _ensure_toto_state(self) -> None:\n        """Materialize Toto only once Floor 22 gameplay actually needs him."""\n        install_floor22_npc(self.runtime)\n        ensure_core = getattr(self.runtime, "_ensure_actor_core", None)\n        if ensure_core is not None:\n            ensure_core(TOTO_ID)\n\n    def prepare_import(self, payload: dict) -> None:\n        """Restore dynamic Toto state only for saves that already contain it."""\n        npc_state = payload.get("npc_state", {})\n        autonomy = payload.get("npc_autonomy_state", {})\n        if (\n            TOTO_ID in npc_state\n            or TOTO_ID in autonomy.get("actor_cores", {})\n            or TOTO_ID in autonomy.get("agendas", {})\n        ):\n            self._ensure_toto_state()\n\n    def instances(self) -> dict:''',
)

replace(
    "src/sao_mcp/scenarios/floor22_witch.py",
    '''        for actor_id in players:\n            actor = runtime.actors[actor_id]\n            if actor.kind is not EntityKind.PLAYER or not actor.alive:\n                raise ValueError("quest participants must be living players")\n            if actor.location_id != FOREST_SITE:\n                raise ValueError(f"all quest participants must be at {FOREST_SITE}")\n            runtime.quests.accept(actor_id, QUEST_ID, now_ms=runtime.world.now_ms)\n\n        instance_id = f"witch22_{uuid.uuid4().hex[:12]}"''',
    '''        for actor_id in players:\n            actor = runtime.actors[actor_id]\n            if actor.kind is not EntityKind.PLAYER or not actor.alive:\n                raise ValueError("quest participants must be living players")\n            if actor.location_id != FOREST_SITE:\n                raise ValueError(f"all quest participants must be at {FOREST_SITE}")\n\n        self._ensure_toto_state()\n        for actor_id in players:\n            runtime.quests.accept(actor_id, QUEST_ID, now_ms=runtime.world.now_ms)\n\n        instance_id = f"witch22_{uuid.uuid4().hex[:12]}"''',
)

replace(
    "src/sao_mcp/runtime/persistence.py",
    '''    if into is None:\n        from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime\n        from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario\n\n        runtime: GameRuntime = SocialCommunicationAincradRuntime()\n        install_floor22_witch_scenario(runtime)\n    else:\n        runtime = into\n    load_campaign_setup_state(runtime, payload.get("campaign_setup_state"))''',
    '''    if into is None:\n        from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime\n\n        runtime: GameRuntime = SocialCommunicationAincradRuntime()\n    else:\n        runtime = into\n\n    # Scenario installers may seed static corpus/rules, but dynamic actors are restored lazily\n    # from the save through the scenario import hook below.\n    from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario\n\n    install_floor22_witch_scenario(runtime)\n    load_campaign_setup_state(runtime, payload.get("campaign_setup_state"))''',
)

replace(
    "src/sao_mcp/runtime/persistence.py",
    '''    if "rng_state" in payload:\n        runtime.rng.setstate(_tuplify(payload["rng_state"]))\n    runtime.quests.load_state(payload.get("quest_state", {}))\n    runtime.npcs.load_state(payload.get("npc_state", {}))''',
    '''    if "rng_state" in payload:\n        runtime.rng.setstate(_tuplify(payload["rng_state"]))\n    for scenario in getattr(runtime, "scenarios", {}).values():\n        prepare_import = getattr(scenario, "prepare_import", None)\n        if prepare_import is not None:\n            prepare_import(payload)\n    runtime.quests.load_state(payload.get("quest_state", {}))\n    runtime.npcs.load_state(payload.get("npc_state", {}))''',
)

(ROOT / "tests/test_floor22_lazy_materialization.py").write_text(r'''from __future__ import annotations

from sao_mcp.corpus.floor22 import FOREST_SITE, TOTO_ID
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


def test_floor22_progress_save_restores_dynamic_toto_state():
    runtime = HousingAincradRuntime(seed=34)
    scenario = install_floor22_witch_scenario(runtime)
    player = runtime.create_character("Floor22Persist", level=30)
    runtime.world.floors[22].unlocked = True
    player.location_id = FOREST_SITE
    scenario.start([player.actor_id])
    save_json = export_runtime(runtime)

    restored = import_runtime(save_json)
    assert TOTO_ID in restored.npcs.states
    assert TOTO_ID in restored.npc_actor_cores
    assert export_runtime(restored) == save_json
''', encoding="utf-8")

print("applied lazy Floor 22 dynamic NPC patch")
