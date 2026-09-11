from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.monster_ecology import MonsterSpeciesEcologyState
from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime
from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime
from sao_mcp.runtime.quest_ecology_runtime import QuestEcologyAincradRuntime


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_monster_ecology_is_one_single_inheritance_layer_above_economy():
    assert MonsterEcologyAincradRuntime.__bases__ == (EconomyLoopAincradRuntime,)


def test_ecology_species_state_does_not_duplicate_materialized_actor_state_or_population():
    fields = set(MonsterSpeciesEcologyState.__dataclass_fields__)
    assert "reserved_units" not in fields
    assert "actor_id" not in fields
    assert "hp" not in fields
    assert "headcount" not in fields
    assert "inventory" not in fields


def test_scenarios_cannot_mutate_ecology_or_background_commodity_authorities_directly():
    forbidden = {
        "monster_ecology",
        "monster_risk_debt",
        "next_ecology_tick_at_ms",
        "advance_monster_ecology_tick",
        "materialize_ecological_monster",
        "background_commodity_stock",
        "record_external_supply",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []


def test_server_bootstrap_uses_monster_ecology_as_authoritative_top_runtime():
    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")
    assert QuestEcologyAincradRuntime.__bases__ == (MonsterEcologyAincradRuntime,)
    assert "QuestEcologyAincradRuntime" in source
    assert "MonsterEcologyAincradRuntime(seed=0xA1C0)" not in source
    assert "EconomyLoopAincradRuntime(seed=0xA1C0)" not in source
    assert "register_monster_ecology_tools" in source


def test_ecology_server_exposes_inspection_and_authoritative_materialization_only():
    source = (ROOT / "src/sao_mcp/server_ecology.py").read_text(encoding="utf-8")
    assert "def get_monster_ecology_state" in source
    assert "def get_monster_ecology_history" in source
    assert "def materialize_wild_monster" in source
    assert "def release_wild_monster" in source
