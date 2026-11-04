import sqlite3, zlib, re, sys
from bs4 import BeautifulSoup
c = sqlite3.connect('/home/claude/cr/build/cr.db')
cid, key, before, after = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
nth = int(sys.argv[5]) if len(sys.argv) > 5 else 0
t = ' '.join(BeautifulSoup(zlib.decompress(h).decode(), 'lxml').get_text(' ') for (h,) in c.execute("select html from sec where cr=? and html is not null and sid not in ('doc_bible','doc_a1','doc_a2') order by ord", (cid,)))
t = re.sub(r'\s+', ' ', t)
t = re.sub(r'\s*\[[\d\s,;–—-]+\]', '', t)
ms = list(re.finditer(key, t, re.I))
print(f'({len(ms)} matches)')
if ms:
    m = ms[min(nth, len(ms) - 1)]
    print(t[max(0, m.start() - before):m.start() + after])
