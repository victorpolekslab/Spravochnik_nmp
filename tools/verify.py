"""For every item marked as taken from a guideline (src КР<id>), check that all numbers of the dose
appear in that guideline's text within a window around the drug name."""
import json, re, sqlite3, zlib, sys
from bs4 import BeautifulSoup

db = sqlite3.connect("/home/claude/cr/build/cr.db")
cache = {}


def text(cid):
    if cid not in cache:
        t = " ".join(BeautifulSoup(zlib.decompress(h).decode(), "lxml").get_text(" ")
                     for (h,) in db.execute("select html from sec where cr=? and html is not null", (cid,)))
        t = re.sub(r"\s+", " ", t).lower().replace("ё", "е")
        cache[cid] = t
    return cache[cid]


def nums(s):
    s = s.replace(" 000", "000")
    out = re.findall(r"\d+(?:[.,]\d+)?", s)
    return [n.replace(".", ",") for n in out if n not in ("1", "2", "3", "4")]  # frequencies are too common to check


GENERIC = {"или", "без", "есть", "альтернатива", "при", "до", "старт", "тяжёлое", "тяжелое", "лёгкое"}

items = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/cr/feld/items.json"))
bad = []
for it in items:
    m = re.match(r"КР(\d+_\d+)", it["src"])
    if not m:
        continue
    t = text(m.group(1))
    ns = nums(it["d"])
    if not ns:
        continue
    words = [w for w in re.findall(r"[а-яёa-z]{4,}", (it["n"] + " " + it["d"]).lower().replace("ё", "е")) if w not in GENERIC]
    stems = [w[:6] for w in words[:4]] or [""]
    ok = False
    for st in stems:
        for mm in re.finditer(re.escape(st), t):
            win = t[max(0, mm.start() - 500): mm.start() + 900]
            if all(re.search(r"(?<![\d,])" + re.escape(n) + r"(?![\d])", win) for n in ns):
                ok = True
                break
        if ok:
            break
    if not ok:
        missing = [n for n in ns if not re.search(r"(?<![\d,])" + re.escape(n) + r"(?![\d])", t)]
        bad.append((it["dis"], it["src"], it["n"], it["d"], missing))

print(f"checked {sum(1 for i in items if i['src'].startswith('КР'))}, not confirmed: {len(bad)}")
for b in bad:
    print(" | ".join(str(x) for x in b))
