"""Static regression checks for Android OTA recovery safeguards.

These are source-level invariants, not runtime/device behavioral tests.
"""
from pathlib import Path

source = (Path(__file__).resolve().parent.parent /
          "android/app/src/main/java/ru/klinrek/app/Ota.java").read_text(encoding="utf-8")

checks = {
    "single active OTA worker": "busy.compareAndSet(false, true)",
    "staging cleanup on failure": "if (staging != null) deleteTree(staging);",
    "completed release checked before download": "boolean alreadyComplete = dir.exists() && matchesManifest(dir, files);",
    "invalid existing release rejected": 'throw new SecurityException("Existing OTA version is incomplete or invalid");',
    "completed release skips downloading": "if (!alreadyComplete) {",
    "rename before version activation": 'if (!tmp.renameTo(dir)) throw new Exception("rename");',
    "manifest hash checked": "hash.equals(sha256(readFile(file, size)))",
    "manifest size checked": "file.length() != size",
    "index page required": 'return new File(dir, "index.html").isFile();',
    "bounded download": "readLimited(in, maxBytes)",
    "version persisted after installation": 'p.edit().putLong("ver", v)',
}
for name, snippet in checks.items():
    assert snippet in source, f"Missing OTA recovery safeguard: {name}"

assert "deleteTree(dir);" not in source, "Existing completed OTA releases must not be deleted"
assert source.index("boolean alreadyComplete") < source.index("if (!alreadyComplete)")
assert source.index('if (!tmp.renameTo(dir))') < source.index('p.edit().putLong("ver", v)')
assert source.index("if (staging != null) deleteTree(staging);") < source.index("busy.set(false);")
print("Android OTA recovery source invariants passed (not a runtime test)")
