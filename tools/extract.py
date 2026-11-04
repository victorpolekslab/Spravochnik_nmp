"""Extract dose-bearing fragments, quality criteria and urgent-care passages from selected guidelines.
Output: feld/extract/<id>.txt (compact plain text with section markers)."""
import re, sqlite3, zlib, os, sys
from bs4 import BeautifulSoup

DB = "/home/claude/cr/build/cr.db"
OUT = "/home/claude/cr/feld/extract"
os.makedirs(OUT, exist_ok=True)
IDS = sys.argv[1:] or "62_3 154_4 157_5 778_1 616_1 359_3 603_3 724_2 25_3 313_3 306_3 654_2 714_2 156_2 155_2".split()

DOSE = re.compile(r"\d[\d.,]*(?:\s*[-–—]\s*[\d.,]+)?\s*(?:мг|мкг|г\b|мл|ЕД|МЕ|ммоль|капл|доз[аыу]?\b|вдох|ингаляц|таб|мг/кг|мкг/кг|мл/кг)", re.I)
URG = re.compile(r"неотложн|скор(?:ой|ая) медицинск|догоспитальн|на этапе СМП|бригад|экстренн|при обострени|гипертоническ\w+ криз|осложненн\w+ криз|транспортир|госпитализ", re.I)


def blocks(html):
    soup = BeautifulSoup(html, "lxml")
    out = []
    for el in soup.find_all(["h2", "h3", "h4", "li", "p", "tr"]):
        if el.name == "p" and (el.find_parent("li") or el.find_parent("tr")):
            continue
        if el.name == "li" and (el.find("li") or el.find_parent("tr")):
            continue
        if el.name == "tr":
            t = " | ".join(re.sub(r"\s+", " ", td.get_text(" ")).strip() for td in el.find_all(["td", "th"]))
        else:
            t = re.sub(r"\s+", " ", el.get_text(" ")).strip()
        t = re.sub(r"\s*\[[\d\s,;–—-]+\]", "", t)
        if t:
            out.append(("h" if el.name in ("h2", "h3", "h4") else "t", t))
    return out


db = sqlite3.connect(DB)
for cid in IDS:
    name = db.execute("SELECT name FROM cr WHERE id=?", (cid,)).fetchone()[0]
    lines = [f"### КР{cid} {name}"]
    for sid, title, h in db.execute("SELECT sid, title, html FROM sec WHERE cr=? ORDER BY ord", (cid,)):
        if not h or sid in ("doc_bible", "doc_a1", "doc_a2", "doc_abbreviation", "doc_terms", "doc_key_words"):
            continue
        html = zlib.decompress(h).decode()
        keep = []
        bl = blocks(html)
        for i, (k, t) in enumerate(bl):
            if k == "h":
                keep.append("## " + t[:150])
                continue
            take = False
            if sid == "doc_criteria":
                take = True
            elif sid in ("doc_3", "doc_a3", "doc_b", "doc_4", "doc_5", "doc_6") and DOSE.search(t):
                take = True
            elif sid in ("doc_3", "doc_diag_2", "doc_diag_2_1", "doc_diag_2_2", "doc_diag_2_3", "doc_diag_2_4", "doc_6") and URG.search(t) and re.match(r"(?i)(не\s+)?рекоменд", t):
                take = True
            if take:
                keep.append(t[:1500])
        # drop headings with nothing under them
        cleaned = []
        for j, x in enumerate(keep):
            if x.startswith("## ") and (j + 1 == len(keep) or keep[j + 1].startswith("## ")):
                continue
            cleaned.append(x)
        if cleaned:
            lines.append(f"\n#### [{sid}] {title}")
            lines += cleaned
    txt = "\n".join(lines)
    open(os.path.join(OUT, cid + ".txt"), "w", encoding="utf-8").write(txt)
    print(cid, len(txt), name[:60])
