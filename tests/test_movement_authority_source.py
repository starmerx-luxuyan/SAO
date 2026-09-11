from __future__ import annotations

import ast
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src" / "sao_mcp"

# These modules are the only places allowed to commit live world-location mutation.
# Scenario/services must call one of these authorities rather than editing location_id directly.
# rules/population.py owns only anonymous PopulationCohortState settlement/transit state.
LOCATION_AUTHORITY_FILES = {
    Path("rules/travel.py"),
    Path("rules/population.py"),
    Path("rules/group_travel.py"),
    Path("rules/transport.py"),
    Path("rules/spawn.py"),
    Path("runtime/npc_autonomy_runtime.py"),
    Path("runtime/guild_autonomy_runtime.py"),
}


def _stored_location_target(target: ast.expr) -> bool:
    if isinstance(target, ast.Attribute):
        return target.attr == "location_id"
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_stored_location_target(item) for item in target.elts)
    return False


def _direct_location_writes(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    parent: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    rows: list[int] = []
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        if not any(_stored_location_target(target) for target in targets):
            continue

        owner = parent.get(node)
        while owner is not None and not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = parent.get(owner)
        if isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)) and owner.name.startswith("load"):
            # Save restoration rehydrates already-committed state; it is not a live movement path.
            continue
        rows.append(node.lineno)
    return sorted(rows)


def test_runtime_location_mutation_is_confined_to_movement_authorities():
    violations: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative in LOCATION_AUTHORITY_FILES:
            continue
        for line in _direct_location_writes(path):
            violations.append(f"{relative.as_posix()}:{line}")

    assert violations == [], (
        "Direct live world-location mutation bypasses travel/transport/spawn authority:\n"
        + "\n".join(violations)
    )
