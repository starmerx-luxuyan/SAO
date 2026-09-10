from __future__ import annotations

from pathlib import Path

source_path = Path("scripts/round4_live_state_core.py")
source = source_path.read_text(encoding="utf-8")
old = '        attach_community_economy(runtime, economy)\\n    return runtime\\n\'\'\''
new = '        attach_community_economy(runtime, economy)\\n    assert_runtime_state_authority(runtime)\\n    return runtime\\n\'\'\''
if source.count(old) != 1:
    raise RuntimeError("round4 core persistence anchor no longer has the expected source shape")
source = source.replace(old, new, 1)
exec(compile(source, str(source_path), "exec"), {"__name__": "__main__"})
