from __future__ import annotations

from sao_mcp.runtime.guild_autonomy_runtime import GuildAutonomyAincradRuntime
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime


class FullAincradRuntime(GuildAutonomyAincradRuntime, HousingAincradRuntime):
    """Production Aincrad runtime combining housing, NPC autonomy, knowledge and guild autonomy."""

    pass
