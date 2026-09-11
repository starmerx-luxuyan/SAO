from pathlib import Path

path = Path(__file__).with_name("round16_social_communication_autonomy_patch.py")
text = path.read_text(encoding="utf-8")
start = text.index('path = "tests/test_economy_loop_authority.py"')
end = text.index('\nwrite(\n    "tests/test_server_bootstrap.py"', start)
replacement = '''path = "tests/test_economy_loop_authority.py"\nreplace_once(\n    path,\n    "from sao_mcp.runtime.quest_ecology_runtime import QuestEcologyAincradRuntime\\n",\n    "from sao_mcp.runtime.quest_ecology_runtime import QuestEcologyAincradRuntime\\n"\n    "from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime\\n",\n)\nreplace_once(\n    path,\n    "    assert \\\"QuestEcologyAincradRuntime\\\" in source\\n",\n    "    assert SocialCommunicationAincradRuntime.__bases__ == (QuestEcologyAincradRuntime,)\\n"\n    "    assert \\\"SocialCommunicationAincradRuntime\\\" in source\\n",\n)\n'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
