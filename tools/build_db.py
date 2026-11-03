"""Build the offline SQLite database for the app.

Inputs (under /home/claude/cr):
  raw/list.json                       - registry of current guidelines (API GetJsonClinrecs)
  json/<id>.json.gz                   - structured guideline texts (API GetClinrec2)
  mkb_src/.../1.2.643.5.1.13.13.11.1005_2.27.csv - MKB-10 (NSI Minzdrav)
Output: build/cr.db
"""
import csv, gzip, json, os, re, sqlite3, sys, zlib, datetime
from bs4 import BeautifulSoup, Comment, NavigableString

BASE = "/home/claude/cr"
OUT = os.path.join(BASE, "build", "cr.db")
MKB_CSV = os.path.join(BASE, "mkb_src/mkb10/resources/1.2.643.5.1.13.13.11.1005_2.27.csv")

AGE = {1: "Взрослые", 2: "Дети", 3: "Взрослые и дети"}

# Typos found in the NSI export (v2.27) and checked against independent editions of MKB-10
# (RLS encyclopedia, gesund.bund.de Russian ICD-10). Original text is kept for search and shown as a note.
MKB_FIX = {
    "J46": ("Астматическое статус", "Астматический статус"),
    "N85.4": ("Неправильное положения матки", "Неправильное положение матки"),
    "A17.8": ("другой локализаций", "других локализаций"),
    "V81.9": ("железнодорожном транспортом средстве", "железнодорожном транспортном средстве"),
    "B21.3": ("кроветветворной", "кроветворной"),
    "B67.6": ("вызыванные", "вызванные"),
    "G41.1": ("Зпилептический", "Эпилептический"),
    "G94.0": ("инфекцоннных", "инфекционных"),
    "K23.0": ("Туберкалезный", "Туберкулезный"),
    "F99-F99": ("НЕУТОЧННЕННЫЕ", "НЕУТОЧНЕННЫЕ"),
}


def norm(s):
    s = (s or "").lower().replace("ё", "е")
    return re.sub(r"\s+", " ", s).strip()


# ---------------- HTML cleaning ----------------
KEEP = {"p", "br", "strong", "b", "em", "i", "u", "sup", "sub", "ul", "ol", "li",
        "table", "thead", "tbody", "tfoot", "tr", "td", "th", "a", "h1", "h2", "h3", "h4",
        "h5", "h6", "blockquote", "caption", "hr"}
DROP = {"script", "style", "meta", "link", "xml", "head", "title", "object", "embed", "iframe", "svg"}
IMG_PH = '<div class="imgph">Иллюстрация — см. оригинал (кнопка «Сайт» или «PDF»)</div>'


def clean_html(html):
    if not html or not html.strip():
        return "", ""
    soup = BeautifulSoup(html, "lxml")
    root = soup.body or soup
    for c in root.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    for t in root.find_all(list(DROP)):
        t.decompose()
    for t in root.find_all("img"):
        t.replace_with(BeautifulSoup(IMG_PH, "html.parser"))
    for t in list(root.find_all(True)):
        name = t.name.lower()
        if ":" in name:  # o:p, v:shape, w:...
            t.unwrap() if t.get_text(strip=True) else t.decompose()
            continue
        if name == "div" and "imgph" in (t.get("class") or []):
            t.attrs = {"class": "imgph"}
            continue
        if name not in KEEP:
            t.unwrap()
            continue
        attrs = {}
        if name in ("td", "th"):
            for k in ("colspan", "rowspan"):
                v = t.get(k)
                if v and str(v).isdigit() and int(v) > 1:
                    attrs[k] = str(v)
        if name == "a":
            href = t.get("href") or ""
            if re.match(r"https?://", href):
                attrs["href"] = href
            else:
                t.unwrap()
                continue
        t.attrs = attrs
    # drop empty paragraphs / list items
    for t in list(root.find_all(["p", "li", "strong", "em", "b", "i", "u", "sup", "sub"])):
        if t.parent is None:
            continue
        if not t.get_text().replace("\xa0", " ").strip() and not t.find(["br", "table", "div"]):
            t.decompose()
    out = "".join(str(x) for x in root.contents)
    out = re.sub(r"(\s*<br/?>\s*){3,}", "<br/><br/>", out)
    out = re.sub(r"[ \t\r\n]+", " ", out).strip()
    text = norm(BeautifulSoup(out, "lxml").get_text(" "))
    return out, text


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.executescript("""
    PRAGMA page_size=4096;
    CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE mkb(id INTEGER PRIMARY KEY, code TEXT, name TEXT, parent INTEGER, lvl INTEGER,
                     sort INTEGER, nchild INTEGER DEFAULT 0, ncr INTEGER DEFAULT 0, q TEXT, orig TEXT);
    CREATE INDEX mkb_parent ON mkb(parent, sort);
    CREATE INDEX mkb_code ON mkb(code);
    CREATE TABLE cr(id TEXT PRIMARY KEY, code INTEGER, version INTEGER, name TEXT, age INTEGER,
                    ass TEXT, pub TEXT, mkb TEXT, cls INTEGER, q TEXT);
    CREATE TABLE cr_mkb(cr TEXT, code TEXT);
    CREATE INDEX cr_mkb_code ON cr_mkb(code);
    CREATE INDEX cr_mkb_cr ON cr_mkb(cr);
    CREATE TABLE sec(id INTEGER PRIMARY KEY, cr TEXT, ord INTEGER, sid TEXT, title TEXT,
                     lvl INTEGER, len INTEGER, html BLOB);
    CREATE INDEX sec_cr ON sec(cr, ord);
    CREATE VIRTUAL TABLE fts USING fts4(content="", body, tokenize=unicode61);
    """)

    # ---------- MKB-10 ----------
    rows = list(csv.DictReader(open(MKB_CSV, encoding="utf-8"), delimiter=";"))
    rows = [r for r in rows if r["ACTUAL"] == "1"]
    byid = {int(r["ID"]): r for r in rows}
    def lvl(r):
        n = 0
        while r["ID_PARENT"]:
            n += 1
            r = byid.get(int(r["ID_PARENT"]))
            if r is None:
                break
        return n
    def pretty(s):
        # class/block names are in CAPS in the source; convert to sentence case, keep abbreviations
        if s != s.upper() or not re.search("[А-Я]{3}", s):
            return s
        t = re.sub("[А-ЯЁ]+", lambda m: m.group().lower(), s)
        t = re.sub(r"\bin situ\b", "in situ", re.sub(r"\bIN SITU\b", "in situ", t))
        t = re.sub(r"\bвич\b", "ВИЧ", t)
        return t[:1].upper() + t[1:]

    rows.sort(key=lambda r: r["REC_CODE"])
    for i, r in enumerate(rows):
        code = r["MKB_CODE"].strip()
        raw = r["MKB_NAME"].strip()
        orig = None
        if code in MKB_FIX:
            bad, good = MKB_FIX.pop(code)
            assert bad in raw, (code, raw)
            orig = raw
            raw = raw.replace(bad, good)
        name = pretty(raw)
        if not r["ID_PARENT"]:  # class: show its range
            pass
        db.execute("INSERT INTO mkb(id,code,name,parent,lvl,sort,q,orig) VALUES(?,?,?,?,?,?,?,?)",
                   (int(r["ID"]), code, name, int(r["ID_PARENT"]) if r["ID_PARENT"] else None,
                    lvl(r), i, norm(code + " " + name + (" " + orig if orig else "")), orig))
    assert not MKB_FIX, MKB_FIX
    db.execute("UPDATE mkb SET nchild=(SELECT count(*) FROM mkb c WHERE c.parent=mkb.id)")
    # class ranges (class rows have roman numerals as code) -> compute range from children
    for (cid, code) in db.execute("SELECT id, code FROM mkb WHERE parent IS NULL").fetchall():
        ch = db.execute("SELECT code FROM mkb WHERE parent=? ORDER BY sort", (cid,)).fetchall()
        if ch:
            first = ch[0][0].split("-")[0]
            last = ch[-1][0].split("-")[-1]
            db.execute("UPDATE mkb SET name = name || ' (' || ? || ')' WHERE id=?",
                       (f"{first}-{last}", cid))

    # leaf/rubric code -> ids, and ancestors
    code2id = {}
    for (i, c) in db.execute("SELECT id, code FROM mkb"):
        code2id.setdefault(c, i)
    parent = dict(db.execute("SELECT id, parent FROM mkb").fetchall())
    cls_of = {}
    def top(i):
        while parent.get(i):
            i = parent[i]
        return i

    # ---------- Guidelines ----------
    items = json.load(open(os.path.join(BASE, "raw", "list.json"), encoding="utf-8"))
    missing = []
    ncr_nodes = {}
    total_secs = 0
    for n, x in enumerate(items):
        cid = x["id"]
        ms = re.search(r"\d+", x["publish_date"])
        pub = datetime.datetime.fromtimestamp(int(ms.group()) / 1000, datetime.timezone(datetime.timedelta(hours=3))).date().isoformat() if ms else ""
        codes = []
        for m in x["Mkb"]:
            m = m.strip().upper().replace(" ", "")
            if m and m not in codes:
                codes.append(m)
        codes.sort()
        # main class = most frequent class among codes
        cnt = {}
        for m in codes:
            i = code2id.get(m)
            if i:
                t = top(i)
                cnt[t] = cnt.get(t, 0) + 1
        cls = max(cnt, key=cnt.get) if cnt else None
        db.execute("INSERT INTO cr VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (cid, x["code"], x["version"], x["name"].strip(), x["age"], (x["ass"] or "").strip(),
                    pub, ", ".join(codes), cls, norm(x["name"] + " " + " ".join(codes) + f" кр{x['code']}")))
        nodes = set()
        for m in codes:
            db.execute("INSERT INTO cr_mkb VALUES(?,?)", (cid, m))
            i = code2id.get(m)
            while i:
                nodes.add(i)
                i = parent.get(i)
        for i in nodes:
            ncr_nodes[i] = ncr_nodes.get(i, 0) + 1

        p = os.path.join(BASE, "json", cid + ".json.gz")
        if not os.path.exists(p):
            missing.append(cid)
            continue
        d = json.loads(gzip.open(p).read().decode("utf-8"))
        secs = d["obj"]["sections"]
        ord_ = 0
        for s in secs:
            if s.get("id") == "doc_whole":
                continue
            title = (s.get("title") or "").strip()
            html, text = clean_html(s.get("content") or "")
            sid = s.get("id") or ""
            lv = 2 if re.match(r"^\d+\.\d+", title) else 1
            if sid == "doc_title":
                continue
            db.execute("INSERT INTO sec(cr,ord,sid,title,lvl,len,html) VALUES(?,?,?,?,?,?,?)",
                       (cid, ord_, sid, title, lv, len(html),
                        zlib.compress(html.encode("utf-8"), 9) if html else None))
            rid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            if text:
                db.execute("INSERT INTO fts(rowid, body) VALUES(?,?)", (rid, norm(title) + " " + text))
            ord_ += 1
            total_secs += 1
        if n % 50 == 0:
            print(n, cid, flush=True)
            db.commit()

    for i, c in ncr_nodes.items():
        db.execute("UPDATE mkb SET ncr=? WHERE id=?", (c, i))
    db.execute("INSERT INTO meta VALUES('built', ?)", (datetime.date.today().isoformat(),))
    db.execute("INSERT INTO meta VALUES('ncr', ?)", (str(len(items)),))
    db.execute("INSERT INTO meta VALUES('mkb_src', 'НСИ Минздрава России, OID 1.2.643.5.1.13.13.11.1005, версия 2.27')")
    db.execute("INSERT INTO meta VALUES('mkb_fixed', ?)", (str(db.execute("SELECT count(*) FROM mkb WHERE orig IS NOT NULL").fetchone()[0]),))
    db.execute("INSERT INTO meta VALUES('cr_src', 'Рубрикатор клинических рекомендаций cr.minzdrav.gov.ru, только действующие')")
    db.commit()
    db.execute("INSERT INTO fts(fts) VALUES('optimize')")
    db.commit()
    db.execute("VACUUM")
    db.close()
    print("missing texts:", missing)
    print("sections:", total_secs, "size MB:", os.path.getsize(OUT) / 1e6)


if __name__ == "__main__":
    main()
