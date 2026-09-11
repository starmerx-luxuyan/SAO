from pathlib import Path

path = Path("src/sao_mcp/runtime/guild_autonomy_runtime.py")
text = path.read_text(encoding="utf-8")
old = '''        completed_at_ms = operation.due_at_ms\n        from_location_id = operation.from_location_id\n        destination_id = operation.next_location_id\n        traversal_tags = operation.traversal_tags\n        destination = self.world_map.locations[destination_id]\n'''
new = '''        completed_at_ms = operation.due_at_ms\n        started_at_ms = operation.started_at_ms\n        from_location_id = operation.from_location_id\n        destination_id = operation.next_location_id\n        traversal_tags = operation.traversal_tags\n        destination = self.world_map.locations[destination_id]\n'''
if text.count(old) != 1:
    raise RuntimeError(f"expected one guild leg capture anchor, found {text.count(old)}")
text = text.replace(old, new, 1)
old2 = '''            "started_at_ms": operation.started_at_ms,\n            "completed_at_ms": completed_at_ms,\n'''
new2 = '''            "started_at_ms": started_at_ms,\n            "completed_at_ms": completed_at_ms,\n'''
if text.count(old2) != 1:
    raise RuntimeError(f"expected one guild history start-time anchor, found {text.count(old2)}")
text = text.replace(old2, new2, 1)
old3 = '''        row = asdict(operation)\n        row["status"] = operation.status.value\n        row["active"] = operation.active\n'''
new3 = '''        row = asdict(operation)\n        row["assigned_member_ids"] = list(operation.assigned_member_ids)\n        row["traversal_tags"] = list(operation.traversal_tags)\n        row["status"] = operation.status.value\n        row["active"] = operation.active\n'''
if text.count(old3) != 1:
    raise RuntimeError(f"expected one guild operation projection anchor, found {text.count(old3)}")
path.write_text(text.replace(old3, new3, 1), encoding="utf-8")
