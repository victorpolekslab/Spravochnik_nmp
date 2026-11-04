import re, sys
DOSE = re.compile(r"\d[\d.,]*(?:\s*[-–—]\s*[\d.,]+)?\s*(?:мг|мкг|г\b|мл|ЕД|МЕ|ммоль|капл|доз[аыу]?\b|вдох|мг/кг|мкг/кг|мл/кг)", re.I)
cid, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "dose")
lim = int(sys.argv[3]) if len(sys.argv) > 3 else 330
sec = ""
seen = set()
for line in open(f"extract/{cid}.txt", encoding="utf-8"):
    line = line.rstrip()
    if line.startswith("#### "):
        sec = line; continue
    if line.startswith("## ") or line.startswith("### "): continue
    want = (mode == "dose" and DOSE.search(line) and "doc_criteria" not in sec) or (mode == "crit" and "doc_criteria" in sec) \
        or (mode == "urg" and re.search(r"(?i)неотложн|скор\w+ медиц|догоспит|криз|обострен|бригад", line))
    if not want: continue
    t = re.sub(r"\s+", " ", line)[:lim]
    k = t[:80]
    if k in seen: continue
    seen.add(k)
    print(f"[{sec[6:20].split(']')[0]}] {t}")
