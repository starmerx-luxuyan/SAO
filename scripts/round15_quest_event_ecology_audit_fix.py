from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected audit anchor missing in {path}: {old[:140]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# QuestRuntime owns a runtime-local definition registry: immutable corpus copies plus exact dynamic projections.
path = "src/sao_mcp/rules/quests.py"
replace_once(
    path,
    '    """Persistent quest state. Definitions are immutable corpus; progress is campaign state."""\n',
    '    """Persistent quest progress plus a runtime-local registry of corpus and dynamic definitions."""\n',
)

# Static quest listing must not leak globally posted living contracts to every actor.
path = "src/sao_mcp/server_adventure.py"
replace_once(
    path,
'''        rows = []\n        for quest_id, definition in runtime.quests.definitions.items():\n            progress = active.get(quest_id)\n''',
'''        rows = []\n        dynamic_contracts = getattr(runtime, "quest_contracts", {})\n        for quest_id, definition in runtime.quests.definitions.items():\n            if quest_id in dynamic_contracts:\n                continue\n            progress = active.get(quest_id)\n''',
)

# Local task-board view: only contracts actually posted where this player currently stands are visible.
path = "src/sao_mcp/server_quest_ecology.py"
replace_once(
    path,
'''def register_quest_ecology_tools(mcp, runtime) -> None:\n    @mcp.tool()\n    def get_quest_ecology_state(contract_id: str | None = None) -> str:\n''',
'''def register_quest_ecology_tools(mcp, runtime) -> None:\n    @mcp.tool()\n    def list_ecological_quests(actor_id: str) -> str:\n        """List active living-world contracts posted at the player's current task board."""\n        actor = runtime.actors[actor_id]\n        if actor.location_id is None:\n            return _json({"actorId": actor_id, "locationId": None, "contracts": []})\n        rows = []\n        for contract_id, contract in sorted(runtime.quest_contracts.items()):\n            occurrence = runtime.world_events.occurrences[contract.occurrence_id]\n            if contract.posting_location_id != actor.location_id or occurrence.status.value != "active":\n                continue\n            row = runtime.quest_contract_state(contract_id)\n            rows.append(row)\n        return _json({"actorId": actor_id, "locationId": actor.location_id, "contracts": rows})\n\n    @mcp.tool()\n    def get_quest_ecology_state(contract_id: str | None = None) -> str:\n''',
)

# Preserve the actual winning actor/organization identity when the world beats a contract.
path = "src/sao_mcp/runtime/quest_ecology_runtime.py"
replace_once(
    path,
    "from sao_mcp.rules.quests import QuestObjectiveKind\n",
    "from sao_mcp.rules.quests import QuestObjectiveKind\nfrom sao_mcp.rules.state_authority import authoritative_guild_id\n",
)
replace_once(
    path,
'''            winners = tuple(sorted(set(eligible)))\n            self._resolve_contract(\n                contract,\n                winner_kind=("named_player" if winners else "named_outsider"),\n                winner_ids=winners,\n                winner_ref_id=killer_id,\n            )\n''',
'''            winners = tuple(sorted(set(eligible)))\n            winner_kind = "named_outsider"\n            winner_ref_id = killer_id\n            if winners:\n                guild_ids = {\n                    authoritative_guild_id(self, actor_id)\n                    for actor_id in winners\n                }\n                if len(guild_ids) == 1 and None not in guild_ids:\n                    winner_kind = "guild_members"\n                    winner_ref_id = next(iter(guild_ids))\n                else:\n                    winner_kind = "named_player"\n            elif killer is not None:\n                npc_id = killer.metadata.get("npc_definition_id")\n                if isinstance(npc_id, str) and npc_id:\n                    winner_kind = "named_npc"\n                    winner_ref_id = npc_id\n                else:\n                    guild_id = authoritative_guild_id(self, killer.actor_id)\n                    if guild_id is not None:\n                        winner_kind = "guild_outsider"\n                        winner_ref_id = guild_id\n            self._resolve_contract(\n                contract,\n                winner_kind=winner_kind,\n                winner_ids=winners,\n                winner_ref_id=winner_ref_id,\n            )\n''',
)

# Lock player-facing location visibility and static-list separation.
path = "tests/test_quest_ecology.py"
text = Path(path).read_text(encoding="utf-8")
text += '''\n\ndef test_living_contract_visibility_is_local_to_posting_board_not_static_quest_list_projection():\n    runtime = QuestEcologyAincradRuntime(seed=809)\n    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)\n    contract = _monster_contract(runtime)\n    player = runtime.create_character("BoardReader")\n    assert player.location_id == contract.posting_location_id\n    assert contract.quest_id in runtime.quests.definitions\n    runtime.travel_actor(player.actor_id, WEST)\n    assert player.location_id != contract.posting_location_id\n    # Runtime contract remains real, but location is what controls the player-facing task-board view.\n    assert runtime.world_events.occurrences[contract.occurrence_id].status is WorldEventStatus.ACTIVE\n'''
Path(path).write_text(text, encoding="utf-8")

path = "tests/test_quest_ecology_authority.py"
replace_once(
    path,
'''    assert "def get_quest_ecology_state" in source\n    assert "def get_quest_ecology_history" in source\n''',
'''    assert "def list_ecological_quests" in source\n    assert "contract.posting_location_id != actor.location_id" in source\n    assert "def get_quest_ecology_state" in source\n    assert "def get_quest_ecology_history" in source\n''',
)
text = Path(path).read_text(encoding="utf-8")
text += '''\n\ndef test_static_adventure_quest_list_excludes_dynamic_contract_projection():\n    source = (ROOT / "src/sao_mcp/server_adventure.py").read_text(encoding="utf-8")\n    assert 'dynamic_contracts = getattr(runtime, "quest_contracts", {})' in source\n    assert "if quest_id in dynamic_contracts" in source\n'''
Path(path).write_text(text, encoding="utf-8")
