from __future__ import annotations

import ast
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src" / "sao_mcp"

# These modules are the only places allowed to commit world-location mutation.
# Scenario/services must call one of these authorities rather than editing location_id directly.
LOCATION_AUTHORITY_FILES = {
    Path("rules/travel.py"),
    Path("rules/group_travel.py"),
    Path("rules/transport.py"),
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
    rows: list[int] = []
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        if any(_stored_location_target(target) for target in targets):
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
        "Direct world-location mutation bypasses travel/transport authority:\n"
        + "\n".join(violations)
    )
