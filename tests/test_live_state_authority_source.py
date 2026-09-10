from __future__ import annotations

import ast
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src" / "sao_mcp"

ENCOUNTER_MUTATION_AUTHORITIES = {
    Path("runtime/engine.py"),
    Path("runtime/persistence.py"),
}
ENCOUNTER_CURRENT_FIELDS = {
    "world_started_at_ms",
    "time_ms",
    "ended_at_world_ms",
    "end_reason",
}
PARTICIPANT_MUTATORS = {"pop", "clear", "update", "setdefault", "__setitem__"}
FLOOR8_LEGAL_SCENARIOS = {
    Path("scenarios/floor8_standoff.py"),
    Path("scenarios/floor8_sluva.py"),
}


def _attribute_name(node: ast.AST) -> str | None:
    return node.attr if isinstance(node, ast.Attribute) else None


def _is_participants_target(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "participants"
    if isinstance(node, ast.Subscript):
        return _is_participants_target(node.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_is_participants_target(item) for item in node.elts)
    return False


def _target_current_field(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute) and node.attr in ENCOUNTER_CURRENT_FIELDS:
        text = ast.unparse(node)
        if "encounter" in text or ".encounters[" in text or text.startswith("enc."):
            return node.attr
    if isinstance(node, ast.Subscript):
        return _target_current_field(node.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        for item in node.elts:
            field = _target_current_field(item)
            if field is not None:
                return field
    return None


def _assigned_targets(node: ast.AST) -> list[ast.expr]:
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, ast.AnnAssign):
        return [node.target]
    if isinstance(node, ast.AugAssign):
        return [node.target]
    return []


def _encounter_mutations(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        for target in _assigned_targets(node):
            if _is_participants_target(target):
                rows.append((node.lineno, "participants-write"))
            field = _target_current_field(target)
            if field is not None:
                rows.append((node.lineno, f"encounter-{field}-write"))
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in PARTICIPANT_MUTATORS:
            continue
        if _is_participants_target(node.func.value):
            rows.append((node.lineno, f"participants-{node.func.attr}"))
    return sorted(set(rows))


def _floor8_legal_metadata_access(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[tuple[int, str]] = []
    forbidden_names = {"AUTONOMOUS_TRAVEL_RESTRICTION_KEY"}
    forbidden_literals = {
        "autonomous_travel_restriction",
        "forest_elf_custody_started_at_ms",
        "forest_elf_custody_ended_at_ms",
        "forest_elf_custody_resolution",
        "forest_elf_custody_location_id",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in forbidden_names:
            rows.append((node.lineno, node.id))
        elif isinstance(node, ast.Constant) and node.value in forbidden_literals:
            rows.append((node.lineno, str(node.value)))
    return sorted(set(rows))


def _scenario_route_history_reads(path: Path) -> list[tuple[int, str]]:
    relative = path.relative_to(SRC)
    if not relative.parts or relative.parts[0] != "scenarios":
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            if node.attr in {"npc_activity_history", "guild_activity_history"}:
                rows.append((node.lineno, node.attr))
    return sorted(set(rows))


def _event_payload_clock_reads(path: Path) -> list[int]:
    relative = path.relative_to(SRC)
    if relative in {Path("runtime/persistence.py")}:
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "get" or not node.args:
            continue
        if not isinstance(node.args[0], ast.Constant) or node.args[0].value != "world_started_at_ms":
            continue
        text = ast.unparse(node.func.value)
        if "payload" in text:
            rows.append(node.lineno)
    return sorted(set(rows))


def test_live_state_mutations_and_decisions_use_authorities():
    violations: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative not in ENCOUNTER_MUTATION_AUTHORITIES:
            for line, kind in _encounter_mutations(path):
                violations.append(f"{kind} {relative.as_posix()}:{line}")
        if relative in FLOOR8_LEGAL_SCENARIOS:
            for line, key in _floor8_legal_metadata_access(path):
                violations.append(f"legal-metadata {relative.as_posix()}:{line} {key}")
        for line, field in _scenario_route_history_reads(path):
            violations.append(f"route-history-current-read {relative.as_posix()}:{line} {field}")
        for line in _event_payload_clock_reads(path):
            violations.append(f"event-payload-clock-read {relative.as_posix()}:{line}")

    assert violations == [], (
        "Live-state decisions or mutations bypass authoritative encounter/legal/route state:\n"
        + "\n".join(violations)
    )
