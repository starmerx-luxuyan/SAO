from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Elapsed travel time is already emitted through advance_world. World events that depend
# on the committed destination need one separate arrival-state evaluation after location commit.
replace_once(
    "src/sao_mcp/runtime/world_event_runtime.py",
    '''    def travel_actor(self, actor_id: str, destination_id: str):\n        # Ordinary travel routes elapsed time through self.advance_world(), so world-event\n        # and NPC-scheduler boundaries are emitted exactly once during the travel window.\n        return super().travel_actor(actor_id, destination_id)\n''',
    '''    def travel_actor(self, actor_id: str, destination_id: str):\n        # Elapsed travel time is emitted through self.advance_world(). Evaluate once more\n        # after the destination commit for arrival-dependent rules, without replaying time hooks.\n        resolution = super().travel_actor(actor_id, destination_id)\n        self.evaluate_world_events()\n        return resolution\n''',
)

# Output 8 locked the then-current rich-goal contract exactly. Output 10 adds one scheduler field.
path = Path("tests/test_npc_actor_core_authority.py")
text = path.read_text(encoding="utf-8")
old = '''        "resource_requirements",\n    }\n'''
new = '''        "resource_requirements",\n        "scheduled_actions",\n    }\n'''
if text.count(old) != 1:
    raise RuntimeError("expected one actor-core GM contract assertion")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
