def test_full_server_bootstrap_imports_all_tool_and_ui_groups():
    from sao_mcp import server_bootstrap

    assert server_bootstrap.mcp is not None
    assert server_bootstrap.runtime is not None
    assert hasattr(server_bootstrap.runtime, "economy")
