"""Add hybrid summaries to cr.db: verbatim fragments from the guideline, trimmed (no paraphrasing).

  cls   - section 1.5 (classification), HTML, citations removed
  diag  - mandatory examinations: quality criteria items that are examinations
          (fallback: recommendation theses from sections 2.3/2.4)
  treat - treatment: quality criteria items about treatment + recommendation theses of section 3,
          grouped by subheadings, each with its grade (УУР/УДД)
"""
import difflib, json, re, sqlite3, sys, zlib
from bs4 import BeautifulSoup

DB = "/home/claude/cr/build/cr.db"

CIT = re.compile(r"\s*\[(?:\d+(?:\s*[-–—]\s*\d+)?\s*[,;]?\s*)+\]")
THESIS = re.compile(r"^(?:не\s+)?рекоменд(?:уется|уются|овано|ованы|ован|ована|уем)\b", re.I)
GRADE = re.compile(r"уровень\s+убедительности|\bУУР\b|\bУДД\b", re.I)
DIAG_RE = re.compile(
    r"исследован|анализ|определени|рентген|томограф|\bузи\b|ультразвук|экг|электрокардиограф|осмотр|консультац|"
    r"\bприем\b|биопси|эндоскопи|пульсоксиметр|спирометр|измерени|оценк|диагност|микроскоп|посев|пцр|тест|"
    r"мониторинг|скрининг|цитолог|гистолог|маммограф|колоноскоп|гастроскоп|сцинтиграф|денситометр|аудиометр|"
    r"\bкт\b|\bмрт\b|\bпэт|бронхоскоп|цистоскоп|допплер|эхокардиограф|регистрац|расшифровк|взяти|обследовани|"
    r"верификац|выявлени|подсчет|ангиограф|морфологическ|иммуногистохим|кариотип|генетическ", re.I)
TREAT_START = re.compile(r"^(?:выполнен[оаы]?|проведен[оаы]?|осуществлен[оаы]?)\s+(?:назначени|терапи|лечени|"
                         r"введени|операц|хирургич|оперативн|трансфуз|оксигенотерап|ингаляц|вакцинац|"
                         r"инфузи|удалени|резекци|иммобилизац|репозиц|дренир|пункци|санаци|коррекци)", re.I)


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def clean_text(s):
    s = CIT.sub("", norm(s))
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    return s.strip()


def shorten(s, limit=220):
    """Trim a verbatim thesis: cut off the 'с целью …' rationale and overly long tails."""
    out = s
    m = re.search(r",?\s+с целью\s", out)
    if m and m.start() >= 40:
        out = out[:m.start()].rstrip(" ,;") + "…"
    if len(out) > limit:
        cut = max(out.rfind(";", 0, limit), out.rfind(",", 0, limit))
        if cut < limit * 0.5:
            cut = out.rfind(" ", 0, limit)
        out = out[:cut].rstrip(" ,;") + "…"
    return out


INLINE_GRADE = re.compile(r"\s*\(?\s*(?:УДД|УУР)\s*[–—\-:]?\s*[ABCАВС1-5]\s*[,;]?\s*(?:(?:УДД|УУР)\s*[–—\-:]?\s*[ABCАВС1-5])?\s*\)?\.?", re.I)


def grade(s):
    s = s.replace("А", "A").replace("В", "B").replace("С", "C")
    a = re.search(r"(?:рекомендаций|УУР)\s*[–—\-:]?\s*([ABC])\b", s, re.I)
    b = re.search(r"(?:доказательств|УДД)\s*[–—\-:]?\s*([1-5])", s, re.I)
    return (a.group(1).upper() if a else "") + (b.group(1) if b else "")


def blocks(html):
    """Ordered (kind, text) items: headings and leaf text blocks."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for el in soup.find_all(["h2", "h3", "h4", "li", "p"]):
        if el.name == "p" and el.find_parent("li"):
            continue
        if el.name == "li" and el.find("li"):
            continue
        if el.find_parent("table"):
            continue
        t = norm(el.get_text(" "))
        if not t:
            continue
        kind = "h" if el.name in ("h2", "h3", "h4") else "t"
        out.append((kind, t))
    return out


def theses(html, ord_):
    groups, cur, seen = [], None, set()
    items = blocks(html)
    for i, (kind, t) in enumerate(items):
        if kind == "h":
            if len(t) < 150:
                cur = {"h": re.sub(r"\s+", " ", t), "items": []}
                groups.append(cur)
            continue
        if not THESIS.match(t):
            continue
        g = grade(t) if re.search(r"УДД|УУР", t) else ""
        if g:
            t = INLINE_GRADE.sub(" ", t)
        for k2, t2 in ([] if g else items[i + 1:i + 25]):
            if GRADE.search(t2):
                g = grade(t2)
                break
            if THESIS.match(t2):
                break
        full = clean_text(t)
        key = full.lower()[:200]
        if key in seen:
            continue
        seen.add(key)
        if cur is None:
            cur = {"h": "", "items": []}
            groups.append(cur)
        words = re.findall(r"[\wА-Яа-яЁё-]+", full)
        # skip the leading "(Не) рекомендуется" (often bold, i.e. a separate text node) for in-text highlighting
        k = 0
        while k < len(words) and k < 3 and re.match(r"(?i)^(не|рекоменд\w*)$", words[k]):
            k += 1
        cur["items"].append({"t": shorten(full), "g": g, "o": ord_, "q": " ".join(words[k:k + 6])})
    return [g for g in groups if g["items"]]


def criteria(html):
    soup = BeautifulSoup(html, "lxml")
    diag, treat, seen = [], [], set()
    for tr in soup.find_all("tr"):
        cells = [norm(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c and not re.fullmatch(r"(?:\d+\.?|да\s*/\s*нет|да|нет|№.*|критери.*|оценка.*)", c, re.I)]
        if not cells:
            continue
        t = clean_text(max(cells, key=len))
        if len(t) < 12:
            continue
        # repeated criteria from tables for different care settings: compare without parentheses/spaces
        core = re.sub(r"\([^)]*\)", "", t.lower())
        core = re.sub(r"[^а-яёa-z0-9]+", "", core)
        if core in seen or any(difflib.SequenceMatcher(None, core, x).ratio() > 0.93 for x in seen if abs(len(x) - len(core)) < 8):
            continue
        seen.add(core)
        # drop the formal "Выполнено/Выполнен/Проведено" prefix (verbatim otherwise)
        short = re.sub(r"^(?:выполнен[оаы]?|проведен[оаы]?|осуществлен[оаы]?)\s+", "", t, flags=re.I)
        short = short[:1].upper() + short[1:]
        if TREAT_START.match(t) or not DIAG_RE.search(t):
            treat.append(short)
        else:
            diag.append(short)
    return diag, treat


def main():
    db = sqlite3.connect(DB)
    db.execute("DROP TABLE IF EXISTS summ")
    db.execute("CREATE TABLE summ(cr TEXT PRIMARY KEY, data BLOB)")
    stats = {"cls": 0, "diag_crit": 0, "diag_thes": 0, "treat": 0, "none": 0}
    for (cr,) in db.execute("SELECT id FROM cr").fetchall():
        secs = {}
        for sid, ord_, title, h in db.execute("SELECT sid, ord, title, html FROM sec WHERE cr=?", (cr,)):
            secs[sid] = (ord_, title, zlib.decompress(h).decode() if h else "")
        s = {}
        o, _, h = secs.get("doc_crat_info_1_5", (None, "", ""))
        if len(BeautifulSoup(h, "lxml").get_text(strip=True)) > 40:
            s["cls"] = CIT.sub("", h)
            s["cls_o"] = o
            stats["cls"] += 1
        o, _, h = secs.get("doc_criteria", (None, "", ""))
        d, tr = criteria(h) if h else ([], [])
        if d:
            s["diag"] = {"src": "crit", "o": o, "items": d}
            stats["diag_crit"] += 1
        else:
            groups = []
            for sid in ("doc_diag_2_3", "doc_diag_2_4"):
                o2, t2, h2 = secs.get(sid, (None, "", ""))
                if h2:
                    g = theses(h2, o2)
                    items = [x for gg in g for x in gg["items"]]
                    if items:
                        groups.append({"h": t2, "items": items})
            if groups:
                s["diag"] = {"src": "thes", "groups": groups}
                stats["diag_thes"] += 1
        o, _, h = secs.get("doc_3", (None, "", ""))
        tg = theses(h, o) if h else []
        if tr or tg:
            s["treat"] = {"crit": tr, "crit_o": secs.get("doc_criteria", (None,))[0], "groups": tg}
            stats["treat"] += 1
        if not s:
            stats["none"] += 1
        db.execute("INSERT INTO summ VALUES(?,?)",
                   (cr, zlib.compress(json.dumps(s, ensure_ascii=False).encode("utf-8"), 9)))
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(stats)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        DB = sys.argv[1]
    main()
