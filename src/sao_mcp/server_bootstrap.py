from __future__ import annotations

import sao_mcp.server as core_server
from sao_mcp.corpus.social_seed import apply_social_catalog_seed
from sao_mcp.runtime.gm_turn import GMTurnExecutor
from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime
from sao_mcp.scenarios.floor2_martial_arts import install_floor2_martial_arts_scenario
from sao_mcp.scenarios.floor2_taurus_raid import install_floor2_taurus_raid_scenario
from sao_mcp.scenarios.floor3_spiders import install_floor3_spider_scenario
from sao_mcp.scenarios.floor4_biceps import install_floor4_biceps_scenario
from sao_mcp.scenarios.floor4_nocturne import install_floor4_nocturne_scenario
from sao_mcp.scenarios.floor4_shipwright import install_floor4_shipwright_scenario
from sao_mcp.scenarios.floor5_fuscus import install_floor5_fuscus_scenario
from sao_mcp.scenarios.floor5_karluin import install_floor5_karluin_scenario
from sao_mcp.scenarios.floor5_shortcut import install_floor5_shortcut_scenario
from sao_mcp.scenarios.floor6_buxum import install_floor6_buxum_scenario
from sao_mcp.scenarios.floor6_elfwar import install_floor6_elfwar_scenario
from sao_mcp.scenarios.floor6_irrational_cube import install_floor6_irrational_cube_scenario
from sao_mcp.scenarios.floor6_south import install_floor6_south_scenario
from sao_mcp.scenarios.floor6_stachion import install_floor6_stachion_scenario
from sao_mcp.scenarios.floor6_trials import install_floor6_trials_scenario
from sao_mcp.scenarios.floor7_aghyellr import install_floor7_aghyellr_scenario
from sao_mcp.scenarios.floor7_campaign import install_floor7_campaign_scenario
from sao_mcp.scenarios.floor7_elfwar import install_floor7_elfwar_scenario
from sao_mcp.scenarios.floor7_intrigue import install_floor7_casino_intrigue_scenario
from sao_mcp.scenarios.floor7_pursuit import install_floor7_pursuit_scenario
from sao_mcp.scenarios.floor7_volupta import install_floor7_volupta_scenario
from sao_mcp.scenarios.floor8_emergency import install_floor8_forest_emergency_scenario
from sao_mcp.scenarios.floor8_sluva import install_floor8_sluva_justice_scenario
from sao_mcp.scenarios.floor8_standoff import install_floor8_cave_standoff_scenario
from sao_mcp.scenarios.floor22_witch import install_floor22_witch_scenario
from sao_mcp.server_adventure import register_adventure_tools
from sao_mcp.server_communications import register_communication_tools
from sao_mcp.server_duels import register_duel_tools
from sao_mcp.server_economy import register_economy_tools
from sao_mcp.server_family import register_family_tools
from sao_mcp.server_floor2 import register_floor2_tools
from sao_mcp.server_floor3 import register_floor3_tools
from sao_mcp.server_floor4 import register_floor4_tools
from sao_mcp.server_floor4_nocturne import register_floor4_nocturne_tools
from sao_mcp.server_floor5 import register_floor5_tools
from sao_mcp.server_floor6 import register_floor6_tools
from sao_mcp.server_floor6_buxum import register_floor6_buxum_tools
from sao_mcp.server_floor6_elfwar import register_floor6_elfwar_tools
from sao_mcp.server_floor7 import register_floor7_tools
from sao_mcp.server_floor7_campaign import register_floor7_campaign_tools
from sao_mcp.server_floor8 import register_floor8_tools
from sao_mcp.server_floor22 import register_floor22_tools
from sao_mcp.server_gm import register_gm_tools
from sao_mcp.server_housing import register_housing_tools
from sao_mcp.server_inventory import register_inventory_tools
from sao_mcp.server_ecology import register_monster_ecology_tools
from sao_mcp.server_population import register_population_tools
from sao_mcp.server_progression import register_progression_tools
from sao_mcp.server_relationships import register_relationship_tools
from sao_mcp.server_spatial import register_spatial_tools
from sao_mcp.server_timeline import register_timeline_tools

# One authoritative game runtime. Floor-specific content is installed as scenario services,
# not by adding another runtime subclass for every quest or floor.
if not isinstance(core_server.runtime, MonsterEcologyAincradRuntime):
    core_server.runtime = MonsterEcologyAincradRuntime(seed=0xA1C0)

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
floor5_shortcut = install_floor5_shortcut_scenario(runtime)
floor6_irrational_cube = install_floor6_irrational_cube_scenario(runtime)
floor6_buxum = install_floor6_buxum_scenario(runtime, floor6_irrational_cube)
floor6_stachion = install_floor6_stachion_scenario(runtime)
floor6_trials = install_floor6_trials_scenario(runtime)
floor6_south = install_floor6_south_scenario(runtime)
floor6_elfwar = install_floor6_elfwar_scenario(runtime)
floor7_volupta = install_floor7_volupta_scenario(runtime)
floor7_aghyellr = install_floor7_aghyellr_scenario(runtime)
floor7_intrigue = install_floor7_casino_intrigue_scenario(runtime, floor7_volupta)
floor7_elfwar = install_floor7_elfwar_scenario(runtime)
floor7_pursuit = install_floor7_pursuit_scenario(runtime)
floor7_campaign = install_floor7_campaign_scenario(runtime, floor7_pursuit, floor7_aghyellr)
floor4_nocturne = install_floor4_nocturne_scenario(runtime, floor7_campaign)
floor8_emergency = install_floor8_forest_emergency_scenario(runtime, floor4_nocturne)
floor8_standoff = install_floor8_cave_standoff_scenario(runtime, floor8_emergency)
floor8_sluva = install_floor8_sluva_justice_scenario(runtime, floor8_emergency)
floor22_witch = install_floor22_witch_scenario(runtime)
gm_turn_executor = GMTurnExecutor(runtime)

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
register_population_tools(mcp, runtime)
register_monster_ecology_tools(mcp, runtime)
register_gm_tools(mcp, gm_turn_executor)
register_floor2_tools(mcp, floor2_taurus_raid, floor2_martial_arts)
register_floor3_tools(mcp, floor3_spiders)
register_floor4_tools(mcp, floor4_shipwright, floor4_biceps)
register_floor4_nocturne_tools(mcp, floor4_nocturne)
register_floor5_tools(mcp, floor5_karluin, floor5_fuscus, floor5_shortcut)
register_floor6_tools(mcp, floor6_irrational_cube, floor6_stachion, floor6_trials, floor6_south)
register_floor6_buxum_tools(mcp, floor6_buxum, floor6_irrational_cube)
register_floor6_elfwar_tools(mcp, floor6_elfwar)
register_floor7_tools(mcp, floor7_volupta, floor7_aghyellr, floor7_intrigue, floor7_elfwar, floor7_pursuit)
register_floor7_campaign_tools(mcp, floor7_campaign)
register_floor8_tools(mcp, floor8_emergency, floor8_standoff, floor8_sluva)
register_floor22_tools(mcp, floor22_witch)

from sao_mcp.server_bosses import register_boss_tools  # noqa: E402

register_boss_tools(mcp, runtime)

from sao_mcp import server_ui as _server_ui  # noqa: E402,F401
from sao_mcp import server_boss_ui as _server_boss_ui  # noqa: E402,F401

__all__ = [
    "mcp",
    "runtime",
    "gm_turn_executor",
    "floor2_martial_arts",
    "floor2_taurus_raid",
    "floor3_spiders",
    "floor4_biceps",
    "floor4_shipwright",
    "floor4_nocturne",
    "floor5_fuscus",
    "floor5_karluin",
    "floor5_shortcut",
    "floor6_irrational_cube",
    "floor6_buxum",
    "floor6_stachion",
    "floor6_trials",
    "floor6_south",
    "floor6_elfwar",
    "floor7_volupta",
    "floor7_aghyellr",
    "floor7_intrigue",
    "floor7_elfwar",
    "floor7_pursuit",
    "floor7_campaign",
    "floor8_emergency",
    "floor8_standoff",
    "floor8_sluva",
    "floor22_witch",
]
