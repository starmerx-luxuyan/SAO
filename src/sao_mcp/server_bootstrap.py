from __future__ import annotations

import sao_mcp.server as core_server
from sao_mcp.corpus.social_seed import apply_social_catalog_seed
from sao_mcp.runtime.community_hooks import attach_community_economy
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.property_economy import make_runtime_economy
from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario
from sao_mcp.server_adventure import register_adventure_tools
from sao_mcp.server_communications import register_communication_tools
from sao_mcp.server_duels import register_duel_tools
from sao_mcp.server_economy import register_economy_tools
from sao_mcp.server_family import register_family_tools
from sao_mcp.server_floor22 import register_floor22_tools
from sao_mcp.server_housing import register_housing_tools
from sao_mcp.server_inventory import register_inventory_tools
from sao_mcp.server_progression import register_progression_tools
from sao_mcp.server_relationships import register_relationship_tools
from sao_mcp.server_spatial import register_spatial_tools
from sao_mcp.server_timeline import register_timeline_tools

# One authoritative game runtime. Floor-specific content is installed as scenario services,
# not by adding another runtime subclass for every quest or floor.
if not isinstance(core_server.runtime, HousingAincradRuntime):
    core_server.runtime = HousingAincradRuntime(seed=0xA1C0)

mcp = core_server.mcp
runtime = core_server.runtime
apply_social_catalog_seed(runtime.catalog)
floor22_witch = install_floor22_witch_scenario(runtime)

if not hasattr(runtime, "economy"):
    runtime.economy = make_runtime_economy(runtime)
attach_community_economy(runtime, runtime.economy)

register_adventure_tools(mcp, runtime)
register_inventory_tools(mcp, runtime)
register_progression_tools(mcp, runtime)
register_economy_tools(mcp, runtime, runtime.economy)
register_spatial_tools(mcp, runtime)
register_timeline_tools(mcp, runtime)
register_duel_tools(mcp, runtime)
register_relationship_tools(mcp, runtime)
register_family_tools(mcp, runtime)
register_communication_tools(mcp, runtime)
register_housing_tools(mcp, runtime)
register_floor22_tools(mcp, floor22_witch)

from sao_mcp.server_bosses import register_boss_tools  # noqa: E402

register_boss_tools(mcp, runtime)

from sao_mcp import server_ui as _server_ui  # noqa: E402,F401
from sao_mcp import server_boss_ui as _server_boss_ui  # noqa: E402,F401

__all__ = ["mcp", "runtime", "floor22_witch"]
