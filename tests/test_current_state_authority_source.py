from __future__ import annotations

import ast
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src" / "sao_mcp"
NPC_LOCATION_AUTHORITY_FILES = {
    Path("rules/npcs.py"),
    Path("runtime/knowledge_runtime.py"),
    Path("runtime/npc_autonomy_runtime.py"),
}


def _is_runtime_npc_states(node: ast.AST) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    states = node.value
    return (
        isinstance(states, ast.Attribute)
        and states.attr == "states"
        and isinstance(states.value, ast.Attribute)
        and states.value.attr == "npcs"
    )


def _direct_npc_state_location_reads(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr != "location_id":
            continue
        if not isinstance(node.ctx, ast.Load):
            continue
        if _is_runtime_npc_states(node.value):
            rows.append(node.lineno)
    return sorted(rows)


def _imports_legacy_actor_only_item_locator(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != "sao_mcp.rules.inventory":
            continue
        if any(alias.name == "locate_item_container" for alias in node.names):
            rows.append(node.lineno)
    return sorted(rows)


def _direct_faction_metadata_reads(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if (
                isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "metadata"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "faction_ids"
            ):
                rows.append(node.lineno)
        elif isinstance(node, ast.Subscript):
            if not (isinstance(node.value, ast.Attribute) and node.value.attr == "metadata"):
                continue
            key = node.slice
            if isinstance(key, ast.Constant) and key.value == "faction_ids" and isinstance(node.ctx, ast.Load):
                rows.append(node.lineno)
    return sorted(set(rows))


def _scenario_actor_guild_projection_reads(path: Path) -> list[int]:
    if Path("scenarios") not in path.relative_to(SRC).parents:
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "guild_id"
        and isinstance(node.ctx, ast.Load)
    )


def test_scenarios_do_not_bypass_current_state_authorities():
    violations: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative not in NPC_LOCATION_AUTHORITY_FILES:
            for line in _direct_npc_state_location_reads(path):
                violations.append(f"npc-location {relative.as_posix()}:{line}")
        if relative.parts and relative.parts[0] in {"scenarios", "runtime"}:
            for line in _imports_legacy_actor_only_item_locator(path):
                violations.append(f"item-container {relative.as_posix()}:{line}")
        if relative != Path("rules/access.py"):
            for line in _direct_faction_metadata_reads(path):
                violations.append(f"faction {relative.as_posix()}:{line}")
        for line in _scenario_actor_guild_projection_reads(path):
            violations.append(f"guild-membership {relative.as_posix()}:{line}")

    assert violations == [], (
        "Current-state decisions bypass authoritative query paths:\n" + "\n".join(violations)
    )
