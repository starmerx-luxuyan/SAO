from __future__ import annotations

import sao_mcp.server as core_server
from sao_mcp.corpus.social_seed import apply_social_catalog_seed
from sao_mcp.runtime.community_hooks import attach_community_economy
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.property_economy import make_runtime_economy
from sao_mcp.scenarios.floor2_martial_arts import install_floor2_martial_arts_scenario
from sao_mcp.scenarios.floor2_taurus_raid import install_floor2_taurus_raid_scenario
from sao_mcp.scenarios.floor3_spiders import install_floor3_spider_scenario
from sao_mcp.scenarios.floor4_biceps import install_floor4_biceps_scenario
from sao_mcp.scenarios.floor4_shipwright import install_floor4_shipwright_scenario
from sao_mcp.scenarios.floor5_fuscus import install_floor5_fuscus_scenario
from sao_mcp.scenarios.floor5_karluin import install_floor5_karluin_scenario
from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario
from sao_mcp.server_adventure import register_adventure_tools
from sao_mcp.server_communications import register_communication_tools
from sao_mcp.server_duels import register_duel_tools
from sao_mcp.server_economy import register_economy_tools
from sao_mcp.server_family import register_family_tools
from sao_mcp.server_floor2 import register_floor2_tools
from sao_mcp.server_floor3 import register_floor3_tools
from sao_mcp.server_floor4 import register_floor4_tools
from sao_mcp.server_floor5 import register_floor5_tools
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
floor2_martial_arts = install_floor2_martial_arts_scenario(runtime)
floor2_taurus_raid = install_floor2_taurus_raid_scenario(runtime)
floor3_spiders = install_floor3_spider_scenario(runtime)
floor4_biceps = install_floor4_biceps_scenario(runtime)
floor4_shipwright = install_floor4_shipwright_scenario(runtime)
floor5_fuscus = install_floor5_fuscus_scenario(runtime)
floor5_karluin = install_floor5_karluin_scenario(runtime)
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
register_floor2_tools(mcp, floor2_taurus_raid, floor2_martial_arts)
register_floor3_tools(mcp, floor3_spiders)
register_floor4_tools(mcp, floor4_shipwright, floor4_biceps)
register_floor5_tools(mcp, floor5_karluin, floor5_fuscus)
register_floor22_tools(mcp, floor22_witch)

from sao_mcp.server_bosses import register_boss_tools  # noqa: E402

register_boss_tools(mcp, runtime)

from sao_mcp import server_ui as _server_ui  # noqa: E402,F401
from sao_mcp import server_boss_ui as _server_boss_ui  # noqa: E402,F401

__all__ = [
    "mcp",
    "runtime",
    "floor2_martial_arts",
    "floor2_taurus_raid",
    "floor3_spiders",
    "floor4_biceps",
    "floor4_shipwright",
    "floor5_fuscus",
    "floor5_karluin",
    "floor22_witch",
]
