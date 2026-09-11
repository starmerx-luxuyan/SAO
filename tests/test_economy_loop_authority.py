from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.economy_loop import RegionalMarketState, VendorStockState
from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime
from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime
from sao_mcp.runtime.quest_ecology_runtime import QuestEcologyAincradRuntime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime
from sao_mcp.runtime.population_runtime import PopulationAincradRuntime


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_economy_loop_is_one_more_single_inheritance_layer_above_population():
    assert EconomyLoopAincradRuntime.__bases__ == (PopulationAincradRuntime,)


def test_market_state_does_not_duplicate_actor_guild_or_population_balances():
    regional_fields = set(RegionalMarketState.__dataclass_fields__)
    vendor_fields = set(VendorStockState.__dataclass_fields__)
    assert "headcount" not in regional_fields
    assert "actor_col" not in regional_fields
    assert "guild_vault_col" not in regional_fields
    assert "seller_col" not in vendor_fields
    assert "guild_storage" not in vendor_fields


def test_scenarios_cannot_mutate_living_economy_ledgers_directly():
    forbidden = {
        "vendor_stocks",
        "regional_markets",
        "market_history",
        "next_tick_at_ms",
        "advance_living_market_tick",
        "_commit_vendor_purchase",
        "_commit_vendor_sale",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []


def test_server_bootstrap_preserves_economy_loop_under_the_new_authoritative_top_runtime():
    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")
    assert MonsterEcologyAincradRuntime.__bases__ == (EconomyLoopAincradRuntime,)
    assert QuestEcologyAincradRuntime.__bases__ == (MonsterEcologyAincradRuntime,)
    assert SocialCommunicationAincradRuntime.__bases__ == (QuestEcologyAincradRuntime,)
    assert "SocialCommunicationAincradRuntime" in source
    assert "PopulationAincradRuntime(seed=0xA1C0)" not in source
    assert "EconomyLoopAincradRuntime(seed=0xA1C0)" not in source
    assert "MonsterEcologyAincradRuntime(seed=0xA1C0)" not in source
    assert "make_runtime_economy(runtime)" not in source


def test_economy_server_exposes_state_quote_and_history_without_another_mutation_surface():
    source = (ROOT / "src/sao_mcp/server_economy.py").read_text(encoding="utf-8")
    assert "def get_aincrad_economy_state" in source
    assert "def quote_vendor_item" in source
    assert "def get_economy_history" in source
