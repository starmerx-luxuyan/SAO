from __future__ import annotations

import sao_mcp.server as core_server
from sao_mcp.corpus.social_seed import apply_social_catalog_seed
from sao_mcp.rules.economy import EconomyRuntime
from sao_mcp.runtime.community_hooks import attach_community_economy
from sao_mcp.runtime.family_runtime import FamilyCommunityAincradRuntime
from sao_mcp.server_adventure import register_adventure_tools
from sao_mcp.server_duels import register_duel_tools
from sao_mcp.server_economy import register_economy_tools
from sao_mcp.server_family import register_family_tools
from sao_mcp.server_inventory import register_inventory_tools
from sao_mcp.server_progression import register_progression_tools
from sao_mcp.server_relationships import register_relationship_tools
from sao_mcp.server_spatial import register_spatial_tools
from sao_mcp.server_timeline import register_timeline_tools

# One authoritative state retains Boss, raid-spatial, timeline, duel, death, community and family layers.
if not isinstance(core_server.runtime, FamilyCommunityAincradRuntime):
    core_server.runtime = FamilyCommunityAincradRuntime(seed=0xA1C0)

mcp = core_server.mcp
runtime = core_server.runtime
apply_social_catalog_seed(runtime.catalog)

if not hasattr(runtime, "economy"):
    runtime.economy = EconomyRuntime()
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

from sao_mcp.server_bosses import register_boss_tools  # noqa: E402

register_boss_tools(mcp, runtime)

# Import after all state/tool groups exist so UI views can expose every panel and Boss state.
from sao_mcp import server_ui as _server_ui  # noqa: E402,F401
from sao_mcp import server_boss_ui as _server_boss_ui  # noqa: E402,F401

__all__ = ["mcp", "runtime"]
