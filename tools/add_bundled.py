"""Adds full texts of guidelines to the bundled database (sec + fts), from GetClinrec2 JSON (json/<id>.json.gz).

   python3 add_bundled.py <cr.db> <json dir> <id> [<id> ...]
"""
import gzip, json, os, re, sqlite3, sys, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_db import clean_html, norm  # noqa: E402


def main(db_path, jdir, ids):
    db = sqlite3.connect(db_path)
    for cid in ids:
        if not db.execute("SELECT 1 FROM cr WHERE id=?", (cid,)).fetchone():
            print("not in list:", cid); continue
        old = [r[0] for r in db.execute("SELECT id FROM sec WHERE cr=?", (cid,))]
        for r in old:
            db.execute("DELETE FROM fts WHERE rowid=?", (r,))
        db.execute("DELETE FROM sec WHERE cr=?", (cid,))
        d = json.loads(gzip.open(os.path.join(jdir, cid + ".json.gz")).read().decode("utf-8"))
        n = 0
        for s in d["obj"]["sections"]:
            sid = s.get("id") or ""
            if sid in ("doc_whole", "doc_title"):
                continue
            title = (s.get("title") or "").strip()
            html, text = clean_html(s.get("content") or "")
            lv = 2 if re.match(r"^\d+\.\d+", title) else 1
            db.execute("INSERT INTO sec(cr,ord,sid,title,lvl,len,html) VALUES(?,?,?,?,?,?,?)",
                       (cid, n, sid, title, lv, len(html), zlib.compress(html.encode("utf-8"), 9) if html else None))
            rid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            if text:
                db.execute("INSERT INTO fts(rowid, body) VALUES(?,?)", (rid, norm(title) + " " + text))
            n += 1
        print(cid, n, "sections")
    db.commit()
    db.execute("VACUUM")
    db.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
