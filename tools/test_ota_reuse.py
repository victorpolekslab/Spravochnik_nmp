"""Behavioral checks for OTA manifest reuse without network or signing secrets."""
import ast
import json
from pathlib import Path
from types import ModuleType
import sys

root = Path(__file__).resolve().parent.parent
source = (root / "tools/ci_ota.py").read_text(encoding="utf-8")
tree = ast.parse(source)
func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "reusable")
module = ast.Module(body=[func], type_ignores=[])
sys.path.insert(0, str(root / "tools"))
import build_ota
namespace = {"json": json, "verify": lambda m, s: s == b"valid"}
exec(compile(ast.fix_missing_locations(module), "<ota-reuse-test>", "exec"), namespace)
reusable = namespace["reusable"]

files = [["index.html", "abc", 10], ["app.js", "def", 20]]
def manifest(native=build_ota.MIN_NATIVE, items=files):
    return json.dumps({"v": 123, "minNative": native, "files": items}).encode()

assert reusable(manifest(), b"valid", files)
assert not reusable(manifest(), b"invalid", files), "Bad signature must be rejected"
assert not reusable(manifest(native=38), b"valid", files), "Old APK floor must be rejected"
assert not reusable(manifest(native=40), b"valid", files), "Different native floor must be rejected"
assert not reusable(manifest(items=[files[0]]), b"valid", files), "Missing file must be rejected"
assert not reusable(manifest(items=[files[1], files[0]]), b"valid", files), "Different file order must be rejected"
assert not reusable(manifest(items=[files[0], ["app.js", "def", 21]]), b"valid", files), "Different file size must be rejected"
assert not reusable(manifest(items=[files[0], ["app.js", "changed", 20]]), b"valid", files), "Different file hash must be rejected"
print("OTA manifest reuse behavior passed")
