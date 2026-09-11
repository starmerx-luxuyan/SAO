def test_full_server_bootstrap_imports_all_tool_and_ui_groups():
    from sao_mcp import server_bootstrap

    assert server_bootstrap.mcp is not None
    assert server_bootstrap.runtime is not None
    assert hasattr(server_bootstrap.runtime, "economy")


def test_full_server_uses_living_economy_loop_runtime():
    from sao_mcp import server_bootstrap
    from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime

    assert isinstance(server_bootstrap.runtime, EconomyLoopAincradRuntime)
    assert server_bootstrap.runtime.economy.next_tick_at_ms > server_bootstrap.runtime.world.now_ms
