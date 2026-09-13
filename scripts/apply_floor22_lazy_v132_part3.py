from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise RuntimeError(f"{path}: expected {count} occurrences, found {found}: {old[:100]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


replace(
    "src/sao_mcp/rules/world.py",
    '''def _dynamic_connection_ids(world: WorldState) -> list[str]:\n    value = world.global_flags.get(DYNAMIC_CONNECTION_IDS_FLAG)\n    if value is None:\n        value = []\n        world.global_flags[DYNAMIC_CONNECTION_IDS_FLAG] = value\n    if not isinstance(value, list) or any(not isinstance(connection_id, str) for connection_id in value):\n        raise RuntimeError("dynamic_world_connection_ids must be a list of connection IDs")\n    unknown = [connection_id for connection_id in value if connection_id not in DYNAMIC_TRAVEL_CONNECTIONS]\n    if unknown:\n        raise RuntimeError(f"unknown dynamic world connection IDs: {unknown}")\n    return value\n''',
    '''def _dynamic_connection_ids(world: WorldState) -> list[str]:\n    # Reading/restoring a world with no unlocked dynamic connection must be side-effect free.\n    # Otherwise a plain import/export grows an empty persistence field.\n    value = world.global_flags.get(DYNAMIC_CONNECTION_IDS_FLAG, [])\n    if not isinstance(value, list) or any(not isinstance(connection_id, str) for connection_id in value):\n        raise RuntimeError("dynamic_world_connection_ids must be a list of connection IDs")\n    unknown = [connection_id for connection_id in value if connection_id not in DYNAMIC_TRAVEL_CONNECTIONS]\n    if unknown:\n        raise RuntimeError(f"unknown dynamic world connection IDs: {unknown}")\n    return value\n''',
)

replace(
    "src/sao_mcp/rules/world.py",
    '''    ids = _dynamic_connection_ids(world)\n    if connection_id not in ids:\n        ids.append(connection_id)\n    _install_dynamic_connection(world_map, connection_id)''',
    '''    ids = _dynamic_connection_ids(world)\n    if DYNAMIC_CONNECTION_IDS_FLAG not in world.global_flags:\n        ids = list(ids)\n        world.global_flags[DYNAMIC_CONNECTION_IDS_FLAG] = ids\n    if connection_id not in ids:\n        ids.append(connection_id)\n    _install_dynamic_connection(world_map, connection_id)''',
)

# Add a direct regression to the dynamic-world test module if present.
test = ROOT / "tests/test_floor5_karluin.py"
text = test.read_text(encoding="utf-8")
if "test_restoring_world_without_dynamic_connections_does_not_grow_empty_flag" not in text:
    text += '''\n\ndef test_restoring_world_without_dynamic_connections_does_not_grow_empty_flag():\n    from sao_mcp.corpus.world import build_world_map_catalog\n    from sao_mcp.rules.world import DYNAMIC_CONNECTION_IDS_FLAG, make_aincrad_world, restore_dynamic_world_connections\n\n    world = make_aincrad_world()\n    world_map = build_world_map_catalog()\n    assert DYNAMIC_CONNECTION_IDS_FLAG not in world.global_flags\n    restore_dynamic_world_connections(world, world_map)\n    assert DYNAMIC_CONNECTION_IDS_FLAG not in world.global_flags\n'''
    test.write_text(text, encoding="utf-8")

print("applied side-effect-free dynamic world connection restore patch")
