def test_full_server_bootstrap_imports_all_tool_and_ui_groups():
    from sao_mcp import server_bootstrap

    assert server_bootstrap.mcp is not None
    assert server_bootstrap.runtime is not None
    assert hasattr(server_bootstrap.runtime, "economy")


def test_full_server_uses_living_quest_ecology_over_monster_and_economy_layers():
    from sao_mcp import server_bootstrap
    from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime
    from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime
    from sao_mcp.runtime.quest_ecology_runtime import QuestEcologyAincradRuntime

    assert isinstance(server_bootstrap.runtime, QuestEcologyAincradRuntime)
    assert isinstance(server_bootstrap.runtime, MonsterEcologyAincradRuntime)
    assert isinstance(server_bootstrap.runtime, EconomyLoopAincradRuntime)
    assert server_bootstrap.runtime.economy.next_tick_at_ms > server_bootstrap.runtime.world.now_ms
    assert server_bootstrap.runtime.next_ecology_tick_at_ms > server_bootstrap.runtime.world.now_ms
    assert server_bootstrap.runtime.next_quest_ecology_tick_at_ms > server_bootstrap.runtime.world.now_ms
