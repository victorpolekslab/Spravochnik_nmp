"""Дозагрузка инструкций из ГРЛС для групп «МНН + путь», у которых нет ОХЛП в открытых данных ЕАЭС.

python3 grls_fetch.py out/index.json out/missing.json grls_out [--limit N] [--workers 3]
Для каждой группы перебирает её РУ (сначала оригинальные): поиск по номеру РУ в ГРЛС →
карточка → список файлов инструкции → самый свежий PDF.
Выход: grls_out/pdf/<guid>.pdf, grls_out/found.jsonl
"""
import json, os, re, sys, time, argparse, threading, concurrent.futures as cf
import requests
from bs4 import BeautifulSoup

B = 'https://grls.rosminzdrav.ru/'
ap = argparse.ArgumentParser()
ap.add_argument('index'); ap.add_argument('missing'); ap.add_argument('out')
ap.add_argument('--limit', type=int, default=0); ap.add_argument('--workers', type=int, default=3)
a = ap.parse_args()
os.makedirs(os.path.join(a.out, 'pdf'), exist_ok=True)

idx = json.load(open(a.index, encoding='utf-8'))
by_group = {}
for i in idx:
    by_group.setdefault((' + '.join(i['inn']), i['route']), []).append(i)
miss = json.load(open(a.missing, encoding='utf-8'))
if a.limit:
    miss = miss[:a.limit]

local = threading.local()
def sess():
    if not hasattr(local, 's'):
        s = requests.Session(); s.headers['User-Agent'] = 'Mozilla/5.0 (spravochnik-nmp)'
        r = get(s, B + 'GRLS.aspx')
        soup = BeautifulSoup(r.text, 'html.parser')
        local.form = {i.get('name'): i.get('value', '') for i in soup.select('input')
                      if i.get('name') and i.get('type') not in ('submit', 'radio')}
        local.s = s
    return local.s

def get(s, url, **kw):
    for t in range(4):
        try:
            r = s.get(url, timeout=90, **kw); r.raise_for_status(); return r
        except Exception:
            if t == 3: raise
            time.sleep(3 * (t + 1))

def post(s, url, **kw):
    for t in range(4):
        try:
            r = s.post(url, timeout=90, **kw); r.raise_for_status(); return r
        except Exception:
            if t == 3: raise
            time.sleep(3 * (t + 1))

def grls_regnum(ru):   # ЛП-№012305-(РГ-RU) → ЛП-№(012305)-(РГ-RU)
    m = re.match(r'ЛП-№(\d+)-\(РГ-RU\)', ru)
    return f'ЛП-№({m.group(1)})-(РГ-RU)' if m else ru

def find_guid(regnum):
    s = sess()
    f = dict(local.form, **{'ctl00$plate$isFS': '0', 'ctl00$plate$txtRegNm': regnum, 'ctl00$plate$bSeek': 'Найти'})
    r = post(s, B + 'GRLS.aspx', data=f)
    m = re.search(r"det\(&#39;([0-9a-f-]{36})&#39;,0\)", r.text)
    return m.group(1) if m else None

def instr_files(guid):
    s = sess()
    card = get(s, B + 'Grls_View_v2.aspx?routingGuid=' + guid).text
    reg = re.search(r'id="ctl00_plate_RegNr"[^>]*value="([^"]*)"|value="([^"]*)"[^>]*id="ctl00_plate_RegNr"', card)
    idr = re.search(r'id="ctl00_plate_hfIdReg"[^>]*value="([^"]*)"|value="([^"]*)"[^>]*id="ctl00_plate_hfIdReg"', card)
    if not (reg and idr):
        return []
    reg, idr = reg.group(1) or reg.group(2), idr.group(1) or idr.group(2)
    body = json.dumps({'regNumber': reg, 'idReg': idr}, ensure_ascii=False).encode('utf-8')
    r = post(s, B + 'GRLS_View_V2.aspx/AddInstrImg', data=body, headers={'Content-Type': 'application/json; charset=utf-8'})
    data = json.loads(r.json()['d'] or '{}')
    files = []
    for src in data.get('Sources') or []:
        for ins in src.get('Instructions') or []:
            for im in ins.get('Images') or []:
                u = (im.get('Url') or '').replace('\\', '/')
                m = re.search(r'/InstrImg/(\d{4})/(\d\d)/(\d\d)/', u)
                files.append({'url': u, 'label': im.get('Label'), 'date': '-'.join(m.groups()) if m else '', 'pdf': u.lower().endswith('.pdf')})
    return files

def work(g):
    key = (g['inn'], g['route'])
    cands = sorted(by_group.get(key, []), key=lambda x: x['kind'] == '01', reverse=True)
    res = {'inn': g['inn'], 'route': g['route']}
    tried = 0
    for c in cands[:5]:
        try:
            tried += 1
            guid = find_guid(grls_regnum(c['ru']))
            if not guid:
                continue
            files = [f for f in instr_files(guid) if f['pdf']]
            if not files:
                continue
            f = sorted(files, key=lambda x: x['date'])[-1]
            pdf = os.path.join(a.out, 'pdf', guid + '.pdf')
            if not os.path.exists(pdf):
                b = get(sess(), B + f['url'].lstrip('/')).content
                if not b.startswith(b'%PDF'):
                    continue
                open(pdf, 'wb').write(b)
            res.update(guid=guid, ru=c['ru'], tn=c['tn'], form=c['form'], atc=c['atc'], date=f['date'],
                       url=f['url'], pdf=os.path.basename(pdf), tried=tried)
            return res
        except Exception as e:
            res['last_error'] = repr(e)[:200]
    res['tried'] = tried
    return res

jl = os.path.join(a.out, 'found.jsonl')
done = set()
if os.path.exists(jl):
    for l in open(jl, encoding='utf-8'):
        r = json.loads(l); done.add((r['inn'], r['route']))
todo = [g for g in miss if (g['inn'], g['route']) not in done]
print('готово ранее', len(done), 'осталось', len(todo), flush=True)
with cf.ThreadPoolExecutor(a.workers) as ex, open(jl, 'a', encoding='utf-8') as jf:
    for r in ex.map(work, todo):
        jf.write(json.dumps(r, ensure_ascii=False) + '\n'); jf.flush()
        print(('ok  ' if r.get('pdf') else 'нет ') + r['inn'][:50], r['route'], r.get('date', ''), r.get('last_error', '')[:80], flush=True)
