from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor missing in {path}: {old[:180]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "tests/test_guild_autonomy_integration.py"
replace_once(
    path,
    '''    assigned = executor.execute([\n        {\n            "op": "assign_guild_goal",\n            "guild_id": guild.guild_id,\n            "leader_id": leader.actor_id,\n            "goal_id": "scout_tolbana",\n            "target_location_id": TOLBANA,\n            "assigned_member_ids": [member.actor_id],\n        }\n    ])\n    agenda = assigned["guild_agendas"][guild.guild_id]\n''',
    '''    assigned = executor.execute(\n        [{\n            "op": "assign_guild_goal",\n            "guild_id": guild.guild_id,\n            "leader_id": leader.actor_id,\n            "goal_id": "scout_tolbana",\n            "target_location_id": TOLBANA,\n            "assigned_member_ids": [member.actor_id],\n        }],\n        observer_actor_ids=[leader.actor_id],\n    )\n    assert "guild_agendas" not in assigned\n    agenda = runtime.guild_agenda_state(guild.guild_id)\n''',
)
replace_once(
    path,
    '''    cleared = restored_executor.execute([\n        {\n            "op": "clear_guild_goal",\n            "guild_id": guild.guild_id,\n            "leader_id": leader.actor_id,\n            "goal_id": "scout_tolbana",\n        }\n    ])\n    assert cleared["guild_agendas"][guild.guild_id]["goal_id"] is None\n''',
    '''    cleared = restored_executor.execute(\n        [{\n            "op": "clear_guild_goal",\n            "guild_id": guild.guild_id,\n            "leader_id": leader.actor_id,\n            "goal_id": "scout_tolbana",\n        }],\n        observer_actor_ids=[leader.actor_id],\n    )\n    assert "guild_agendas" not in cleared\n    assert restored.guild_agenda_state(guild.guild_id)["goal_id"] is None\n''',
)

path = "tests/test_npc_actor_core_authority.py"
replace_once(
    path,
    '''def test_gm_exposes_actor_core_inspection_surface():\n    server = (ROOT / "src/sao_mcp/server_gm.py").read_text(encoding="utf-8")\n    assert "def get_npc_actor_core" in server\n    assert "npc_actor_core_state(npc_id)" in server\n\n\n''',
    '''def test_npc_actor_core_remains_runtime_authority_but_is_not_a_gm_observation_surface():\n    runtime_source = (ROOT / "src/sao_mcp/runtime/npc_autonomy_runtime.py").read_text(encoding="utf-8")\n    server = (ROOT / "src/sao_mcp/server_gm.py").read_text(encoding="utf-8")\n    assert "def npc_actor_core_state" in runtime_source\n    assert "def get_npc_actor_core" not in server\n    assert "npc_actor_core_state(npc_id)" not in server\n    assert "def get_gm_observation" in server\n\n\n''',
)
