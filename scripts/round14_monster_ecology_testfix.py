from pathlib import Path

path = Path("tests/test_economy_loop_authority.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime\nfrom sao_mcp.runtime.population_runtime import PopulationAincradRuntime\n",
    "from sao_mcp.runtime.economy_loop_runtime import EconomyLoopAincradRuntime\nfrom sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime\nfrom sao_mcp.runtime.population_runtime import PopulationAincradRuntime\n",
    1,
)
old = '''def test_server_bootstrap_uses_economy_loop_as_the_authoritative_top_runtime():\n    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")\n    assert "EconomyLoopAincradRuntime" in source\n    assert "PopulationAincradRuntime(seed=0xA1C0)" not in source\n    assert "make_runtime_economy(runtime)" not in source\n'''
new = '''def test_server_bootstrap_preserves_economy_loop_under_the_new_authoritative_top_runtime():\n    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")\n    assert MonsterEcologyAincradRuntime.__bases__ == (EconomyLoopAincradRuntime,)\n    assert "MonsterEcologyAincradRuntime" in source\n    assert "PopulationAincradRuntime(seed=0xA1C0)" not in source\n    assert "EconomyLoopAincradRuntime(seed=0xA1C0)" not in source\n    assert "make_runtime_economy(runtime)" not in source\n'''
if old not in text:
    raise RuntimeError("old economy bootstrap authority test anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
