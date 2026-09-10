from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "src/sao_mcp/scenarios/floor6_buxum.py"
replace_once(
    path,
    'from sao_mcp.rules.state_authority import require_sole_actor_item_holder\n',
    'from sao_mcp.rules.state_authority import locate_runtime_item\n',
)
replace_once(
    path,
    '''        try:
            holder, key = require_sole_actor_item_holder(self.runtime, key_id)
        except KeyError:
            return None
        if key.template_id != COMBINED_IRON_KEY_ID:
            raise RuntimeError("Floor 6 combined-key instance ID points to the wrong item template")
        return holder, key
''',
    '''        located = locate_runtime_item(self.runtime, key_id)
        if located is None:
            return None
        if located.item.template_id != COMBINED_IRON_KEY_ID:
            raise RuntimeError("Floor 6 combined-key instance ID points to the wrong item template")
        return located
''',
)
replace_once(
    path,
    '''        holder, key = located
        if holder.metadata.get("npc_definition_id") != KYSARAH_ID:
            raise ValueError("the canonical Buxum betrayal requires the combined key previously stolen by Kysarah")
        holder.inventory.pop(key.instance_id)
        return holder, key
''',
    '''        holder_id = located.sole_actor_id
        if holder_id is None:
            raise ValueError("the canonical Buxum betrayal requires Kysarah to be the combined key's current actor holder")
        holder = self.runtime.actors[holder_id]
        key = located.item
        if holder.metadata.get("npc_definition_id") != KYSARAH_ID:
            raise ValueError("the canonical Buxum betrayal requires the combined key previously stolen by Kysarah")
        holder.inventory.pop(key.instance_id)
        return holder, key
''',
)
replace_once(
    path,
    '        combined_key_holder_id = located[1].owner_id if located is not None else None\n',
    '        combined_key_holder_id = located.sole_actor_id if located is not None else None\n',
)
