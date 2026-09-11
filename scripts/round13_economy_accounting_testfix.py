from pathlib import Path

path = Path("tests/test_economy_loop.py")
text = path.read_text(encoding="utf-8")
old = '''        "field_bread",\n        20,\n        runtime.catalog,\n'''
new = '''        "field_bread",\n        10,\n        runtime.catalog,\n'''
if old not in text:
    raise RuntimeError("bulk-purchase accounting test anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
