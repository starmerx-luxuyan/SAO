from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.quest_ecology import QuestContractState
from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime
from sao_mcp.runtime.quest_ecology_runtime import QuestEcologyAincradRuntime


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_quest_ecology_is_one_single_inheritance_layer_above_monster_ecology():
    assert QuestEcologyAincradRuntime.__bases__ == (MonsterEcologyAincradRuntime,)


def test_contract_state_does_not_duplicate_world_event_status_actor_inventory_or_economy_balance():
    fields = set(QuestContractState.__dataclass_fields__)
    assert "status" not in fields
    assert "actor_col" not in fields
    assert "inventory" not in fields
    assert "guild_vault_col" not in fields
    assert "monster_population" not in fields


def test_dynamic_contract_definition_is_projection_not_process_global_corpus_mutation():
    from sao_mcp.corpus.quests import CORE_QUESTS

    runtime = QuestEcologyAincradRuntime(seed=811)
    before = set(CORE_QUESTS)
    runtime.advance_world(60 * 60 * 1000)
    assert set(CORE_QUESTS) == before
    assert any(contract.quest_id in runtime.quests.definitions for contract in runtime.quest_contracts.values())


def test_scenarios_cannot_mutate_quest_ecology_or_world_progress_directly():
    forbidden = {
        "quest_contracts",
        "quest_contract_sequence",
        "next_quest_ecology_tick_at_ms",
        "advance_quest_ecology_tick",
        "_publish_contract",
        "_resolve_contract",
        "_advance_contract_progress",
        "quest_ecology_ecology_cursor",
        "quest_ecology_market_cursor",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []


def test_server_bootstrap_uses_quest_ecology_as_authoritative_top_runtime():
    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")
    assert "QuestEcologyAincradRuntime" in source
    assert "MonsterEcologyAincradRuntime(seed=0xA1C0)" not in source
    assert "register_quest_ecology_tools" in source


def test_quest_ecology_server_has_no_manual_publish_or_resolve_surface():
    source = (ROOT / "src/sao_mcp/server_quest_ecology.py").read_text(encoding="utf-8")
    assert "def list_ecological_quests" in source
    assert "contract.posting_location_id != actor.location_id" in source
    assert "def get_quest_ecology_state" in source
    assert "def get_quest_ecology_history" in source
    assert "def accept_ecological_quest" in source
    assert "def claim_ecological_quest" in source
    assert "publish_contract" not in source
    assert "resolve_contract" not in source


def test_adventure_catalog_spawn_routes_through_living_ecology_authority():
    source = (ROOT / "src/sao_mcp/server_adventure.py").read_text(encoding="utf-8")
    assert "materialize_ecological_monster" in source
    assert "living ecology encounters cannot override catalog monster level" in source


def test_static_adventure_quest_list_excludes_dynamic_contract_projection():
    source = (ROOT / "src/sao_mcp/server_adventure.py").read_text(encoding="utf-8")
    assert 'dynamic_contracts = getattr(runtime, "quest_contracts", {})' in source
    assert "if quest_id in dynamic_contracts" in source
