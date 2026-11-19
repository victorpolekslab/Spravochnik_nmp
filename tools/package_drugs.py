#!/usr/bin/env python3
"""Build a reproducible, compressed SQLite snapshot of the drugs branch.

Usage: python tools/package_drugs.py --source /path/to/drugs/app --out dist
Requires only Python 3.12 stdlib. Does NOT publish or sign the package.
"""
import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build(source, out):
    source, out = Path(source), Path(out)
    index = json.loads((source / "search.json").read_text(encoding="utf-8"))
    interactions = json.loads((source / "ix.json").read_text(encoding="utf-8"))
    version = json.loads((source / "version.json").read_text(encoding="utf-8"))
    ids = sorted({str(row[0]) for row in index["docs"] if row and row[0]})
    if not ids:
        raise ValueError("Empty instruction index")
    out.mkdir(parents=True, exist_ok=True)
    final = out / "drugs.db.gz"
    with tempfile.TemporaryDirectory(prefix="drugs-build-") as tmp:
        db_path = Path(tmp) / "drugs.db"
        con = sqlite3.connect(db_path)
        try:
            con.execute("PRAGMA journal_mode=DELETE")
            con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            con.execute("CREATE TABLE docs (id TEXT PRIMARY KEY, json TEXT NOT NULL)")
            con.execute("INSERT INTO meta VALUES (?, ?)", ("version", str(version["v"])))
            con.execute("INSERT INTO meta VALUES (?, ?)", ("search", json.dumps(index, ensure_ascii=False, separators=(",", ":"))))
            con.execute("INSERT INTO meta VALUES (?, ?)", ("ix", json.dumps(interactions, ensure_ascii=False, separators=(",", ":"))))
            for doc_id in ids:
                path = source / "doc" / (doc_id + ".json")
                if not path.is_file():
                    raise FileNotFoundError("Missing indexed instruction: " + doc_id)
                raw = path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("Invalid instruction: " + doc_id)
                con.execute("INSERT INTO docs VALUES (?, ?)", (doc_id, json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
            con.commit()
            check = con.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise ValueError("SQLite integrity check failed: " + check)
            count = con.execute("SELECT count(*) FROM docs").fetchone()[0]
            if count != len(ids):
                raise ValueError("Instruction count mismatch")
        finally:
            con.close()
        staging = out / "drugs.db.gz.tmp"
        try:
            with db_path.open("rb") as src, staging.open("wb") as dst:
                with gzip.GzipFile(filename="", mode="wb", fileobj=dst, compresslevel=9, mtime=0) as gz:
                    for block in iter(lambda: src.read(1024 * 1024), b""):
                        gz.write(block)
            os.replace(staging, final)
        finally:
            staging.unlink(missing_ok=True)
    manifest = {
        "schema": 1, "version": str(version["v"]),
        "format": "sqlite3+gzip", "file": final.name,
        "sha256": sha256(final), "size": final.stat().st_size,
        "documents": len(ids),
    }
    tmp_manifest = out / "drugs-manifest.json.tmp"
    tmp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_manifest, out / "drugs-manifest.json")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", default="dist/drugs")
    args = parser.parse_args()
    build(args.source, args.out)
