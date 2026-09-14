from __future__ import annotations

import ast
from pathlib import Path


def test_public_server_exposes_one_visual_surface_and_one_gameplay_mutation_line():
    path = Path(__file__).parents[1] / "src" / "sao_mcp" / "server_public.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    app_tools = []
    functions = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
            for decorator in node.decorator_list:
                call = decorator if isinstance(decorator, ast.Call) else None
                func = call.func if call is not None else decorator
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "apps"
                    and func.attr == "tool"
                ):
                    app_tools.append(node.name)

    assert app_tools == ["system_menu"]
    assert "character_hud" not in functions
    assert "boss_raid_hud" not in functions
    assert "buy_from_vendor" not in functions
    assert "sell_to_vendor" not in functions
    assert "create_party" not in functions
    assert "join_party" not in functions
    assert "register_gm_tools" not in source
    assert "register_player_runline_tools" in source
    assert "turn_execute" in source
