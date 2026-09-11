from pathlib import Path

path = Path("tests/test_world_event_runtime.py")
text = path.read_text(encoding="utf-8")
old = '''    runtime.register_world_event_rule(\n        "test.interruptible",\n        lambda: ["test:interruptible:1"],\n        lambda occurrence_id: WorldEventResult(\n            WorldEventStatus.ACTIVE,\n            {"occurrence_id": occurrence_id, "phase": "started"},\n        ),\n    )\n    runtime.plan_world_event(\n'''
new = '''    def discover_interruptible():\n        occurrence = runtime.world_events.occurrences.get("test:interruptible:1")\n        return (\n            ["test:interruptible:1"]\n            if occurrence is not None and occurrence.status is WorldEventStatus.PENDING\n            else []\n        )\n\n    runtime.register_world_event_rule(\n        "test.interruptible",\n        discover_interruptible,\n        lambda occurrence_id: WorldEventResult(\n            WorldEventStatus.ACTIVE,\n            {"occurrence_id": occurrence_id, "phase": "started"},\n        ),\n    )\n    runtime.plan_world_event(\n'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f"expected one interruptible test anchor, found {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
