"""Замена листков-вкладышей на профессиональные документы: инструкция по медицинскому применению или ОХЛП.

python3 grls_upgrade.py grls_out [--workers 4] [--limit N]
Для каждой группы «МНН + путь», где сейчас листок-вкладыш (или документа нет), ищет в ГРЛС по МНН
все РУ вещества — действующие, изменённые, исключённые, истёкшие, — оставляет совпадающие по пути
введения и перебирает их инструкции от свежих к старым, пока не найдётся документ не листок-вкладыш.
Порядок: действующие РУ → РУ ЕАЭС (в т. ч. прошлые версии) → прежние национальные РУ.
Результат: grls_out/upgrade.jsonl; найденные PDF — в grls_out/pdf/.
"""
import json, os, re, sys, time, argparse, threading, concurrent.futures as cf
import requests, pymupdf
from bs4 import BeautifulSoup
sys.path.insert(0, os.path.dirname(__file__))
from textlib import route

B = 'https://grls.rosminzdrav.ru/'
ap = argparse.ArgumentParser(); ap.add_argument('out')
ap.add_argument('--workers', type=int, default=4); ap.add_argument('--limit', type=int, default=0)
ap.add_argument('--max-cards', type=int, default=12)
ap.add_argument('--extra', default='')
ap.add_argument('--jl', default='upgrade.jsonl')
a = ap.parse_args()

local = threading.local()
def req(method, url, **kw):
    for t in range(4):
        try:
            r = getattr(sess(), method)(url, timeout=90, **kw); r.raise_for_status(); return r
        except Exception:
            if t == 3: raise
            time.sleep(3 * (t + 1))

def sess():
    if not hasattr(local, 'form'):
        s = requests.Session(); s.headers['User-Agent'] = 'Mozilla/5.0 (spravochnik-nmp)'
        for t in range(4):
            try:
                soup = BeautifulSoup(s.get(B + 'GRLS.aspx', timeout=90).text, 'html.parser'); break
            except Exception:
                if t == 3: raise
                time.sleep(3 * (t + 1))
        local.s = s
        local.form = {i.get('name'): i.get('value', '') for i in soup.select('input')
                      if i.get('name') and i.get('type') not in ('submit', 'radio')}
    return local.s

STATUS_RANK = {'Д': 0, 'ПП': 1, 'ЕАЭС': 2, 'ИЗМ': 3, 'П': 3, 'ИСКЛ': 4, 'ИСТ': 4}

def date_key(d):
    m = re.match(r'(\d\d)\.(\d\d)\.(\d{4})', d or '')
    return f'{m.group(3)}{m.group(2)}{m.group(1)}' if m else '00000000'

LAT = str.maketrans('ABCEHKMOPTXaceopxy', 'АВСЕНКМОРТХасеорху')
SALT = (r'(гидрохлорид|гидробромид|дигидрохлорид|малеат|сульфат|тартрат|битартрат|сукцинат|мезилат|безилат|'
        r'ацетат|фосфат|цитрат|фумарат|лактат|бромид|хлорид|натрия|калия|кальция|магния|моногидрат|дигидрат|тригидрат|гидрат)')

def norm(s):
    s = s.lower().replace('ё', 'е')
    # латинская буква, перепутанная с кириллической («Cульбактам»)
    return re.sub(r'[a-z](?=[а-я])|(?<=[а-я])[a-z]', lambda m: m.group(0).translate(LAT), s)

STOP = {'для', 'профилактики', 'лечения', 'типа', 'вида', 'группы', 'содержащая', 'содержащий', 'экстракт', 'сухой',
        'густой', 'жидкий', 'раствор', 'в', 'и', 'с', 'на', 'из', 'по'}

def stem(x):
    x = re.sub(r'[^\w-]', '', x)
    return x[:-1] if len(x) > 6 and x[-1] in 'аыиеяу' else x

def comps(inn):
    """Компоненты МНН: для каждого — все значимые слова в виде основ (соли и служебные слова отброшены)."""
    out = []
    for p in re.split(r'\s*\+\s*', norm(inn)):
        w = [stem(x) for x in re.split(r'[\s,;()\[\]]+', p) if x and not re.fullmatch(SALT, x) and x not in STOP]
        w = [x for x in w if len(x) >= 3]
        if w:
            out.append(w)
    return out

def parts(inn):   # первые слова компонентов — для запроса в ГРЛС
    return [c[0] for c in comps(inn) if len(c[0]) >= 4]

def same_composition(inn, grls_mnn):
    """Состав совпадает, если каждое значимое слово каждого компонента есть в МНН из ГРЛС и число компонентов то же."""
    m = norm(grls_mnn)
    cs = comps(inn)
    return bool(cs) and all(all(w in m for w in c) for c in cs) and len(re.split(r'\+', m)) == len(cs)

def _grls_rows(field, q):
    f = dict(local.form, **{'ctl00$plate$isFS': '0', field: q[:60], 'ctl00$plate$hfRegType': '1,2,3,4,5,6,7,8',
                            'ctl00$plate$txtRecordOnPageCount': '99', 'ctl00$plate$bSeek': 'Найти'})
    soup = BeautifulSoup(req('post', B + 'GRLS.aspx', data=f).text, 'html.parser')
    rows = []
    for tr in soup.select('tr[onclick]'):
        m = re.search(r"det\('([0-9a-f-]{36})',0\)", tr['onclick'])
        c = [td.get_text(' ', strip=True) for td in tr.select('td')]
        if m and len(c) >= 12:
            rows.append({'guid': m.group(1), 'tn': c[1], 'mnn': c[2], 'form': c[3], 'ru': c[6],
                         'status': c[10], 'decision': c[11]})
    return rows

def search_inn(inn, tn=''):
    """РУ того же состава: поиск по МНН; если МНН в ГРЛС записано иначе (растительные, латиница) — по торговому названию."""
    sess()
    want = parts(inn)
    rows = []
    if want:
        q = max(want, key=len)   # самый длинный компонент — самый избирательный
        rows = [r for r in _grls_rows('ctl00$plate$txtMNN', q) if same_composition(inn, r['mnn'])]
    if not rows and tn:
        t = re.split(r'[®,(]', tn)[0].strip()
        if len(t) >= 3:
            key = lambda x: re.sub(r'[®™\s]+', ' ', norm(x)).strip()
            rows = [r for r in _grls_rows('ctl00$plate$txtTorg', t) if key(r['tn']) == key(tn.split(',')[0])]
            for r in rows:
                r['by_tn'] = True   # то же торговое наименование — тот же препарат
    return rows

def card_files(guid):
    card = req('get', B + 'Grls_View_v2.aspx?routingGuid=' + guid).text
    def val(i):
        m = re.search(r'<input[^>]*id="' + i + r'"[^>]*>', card)
        return re.search(r'value="([^"]*)"', m.group(0)).group(1) if m and 'value=' in m.group(0) else ''
    reg, idr = val('ctl00_plate_RegNr'), val('ctl00_plate_hfIdReg')
    if not reg or not idr:
        return []
    body = json.dumps({'regNumber': reg, 'idReg': idr}, ensure_ascii=False).encode('utf-8')
    d = json.loads(req('post', B + 'GRLS_View_V2.aspx/AddInstrImg', data=body,
                       headers={'Content-Type': 'application/json; charset=utf-8'}).json()['d'] or '{}')
    out = []
    for src in d.get('Sources') or []:
        for ins in src.get('Instructions') or []:
            for im in ins.get('Images') or []:
                u = (im.get('Url') or '').replace('\\', '/')
                if u.lower().endswith('.pdf'):
                    m = re.search(r'/InstrImg/(\d{4})/(\d\d)/(\d\d)/', u)
                    out.append({'url': u, 'date': '-'.join(m.groups()) if m else ''})
    return sorted(out, key=lambda x: x['date'], reverse=True)

def kind_of(b):
    try:
        d = pymupdf.open(stream=b, filetype='pdf')
        head = ' '.join(d[i].get_text() for i in range(min(2, len(d)))).lower()[:3000]
    except Exception:
        return 'битый'
    if len(head.strip()) < 100 and len(d):   # скан: распознаём первую страницу
        import subprocess
        png = d[0].get_pixmap(dpi=200, colorspace=pymupdf.csGRAY).tobytes('png')
        head = subprocess.run(['tesseract', 'stdin', 'stdout', '-l', 'rus', '--psm', '6'], input=png,
                              capture_output=True, timeout=120).stdout.decode('utf-8', 'replace').lower()[:3000]
        if len(head.strip()) < 100:
            return 'скан'
    if len(d) <= 3 and re.search(r'изменени[яе]|дата внесения', head):
        return 'лист изменений'   # не полная инструкция
    if 'листок-вкладыш' in head or 'листок - вкладыш' in head or 'информация для пациента' in head:
        return 'листок-вкладыш (ЕАЭС)'
    if 'общая характеристика' in head:
        return 'ОХЛП (ЕАЭС)'
    return 'инструкция по медицинскому применению'

def work(g):
    res = {'inn': g['inn'], 'route': g['route']}
    try:
        rows = [r for r in search_inn(g['inn'], g.get('tn', '')) if route(r['form']) == g['route']]
        res['rows'] = len(rows)
        def rank(r):   # действующие → прежние национальные РУ → прошлые версии РУ ЕАЭС; свежие раньше
            if r['status'] in ('Д', 'ПП'):
                grp = 0
            elif 'РГ-RU' not in r['ru']:
                grp = 1
            else:
                grp = 2
            return (grp, -int(date_key(r['decision'])))
        rows.sort(key=rank)
        seen, cards = set(), 0
        for r in rows:
            if r['guid'] in seen or cards >= a.max_cards:
                continue
            seen.add(r['guid']); cards += 1
            for f in card_files(r['guid'])[:5]:
                b = req('get', B + f['url'].lstrip('/')).content
                if not b.startswith(b'%PDF'):
                    continue
                k = kind_of(b)
                if k.startswith(('инструкция', 'ОХЛП')):
                    name = r['guid'] + '_' + os.path.basename(f['url'])
                    open(os.path.join(a.out, 'pdf', name), 'wb').write(b)
                    res.update(guid=r['guid'], ru=r['ru'], by_tn=r.get('by_tn', False), tn=r['tn'], form=r['form'], status=r['status'],
                               decision=r['decision'], date=f['date'], url=f['url'], pdf=name, kind=k, cards=cards)
                    return res
        res['cards'] = cards
    except Exception as e:
        res['error'] = repr(e)[:200]
    return res

# что улучшаем: листки-вкладыши и группы без документа
rep = {}
for l in open(os.path.join(a.out, 'report.jsonl'), encoding='utf-8'):
    x = json.loads(l); rep[(x['inn'], x['route'])] = x
found = {}
for l in open(os.path.join(a.out, 'found.jsonl'), encoding='utf-8'):
    x = json.loads(l); found[(x['inn'], x['route'])] = x
targets = [{'inn': k[0], 'route': k[1], 'tn': found.get(k, {}).get('tn', '')} for k, x in rep.items() if x.get('lv')]
tn_by_group = {}
_ix = os.path.join(os.path.dirname(a.out.rstrip('/')) or '.', 'out', 'index.json')
if os.path.exists(_ix):
    for i in json.load(open(_ix, encoding='utf-8')):
        tn_by_group.setdefault((' + '.join(i['inn']), i['route']), i['tn'])
targets += [{'inn': k[0], 'route': k[1], 'tn': tn_by_group.get(k, '')} for k, x in found.items() if not x.get('pdf')]
if a.limit:
    targets = targets[:a.limit]
jl = os.path.join(a.out, a.jl)
if a.extra:
    have = {(t['inn'], t['route']) for t in targets}
    targets += [t for t in json.load(open(a.extra, encoding='utf-8')) if (t['inn'], t['route']) not in have]
done = set()
if os.path.exists(jl):
    for l in open(jl, encoding='utf-8'):
        x = json.loads(l)
        if 'error' not in x: done.add((x['inn'], x['route']))
todo = [t for t in targets if (t['inn'], t['route']) not in done]
print('целей', len(targets), 'осталось', len(todo), flush=True)
with cf.ThreadPoolExecutor(a.workers) as ex, open(jl, 'a', encoding='utf-8') as jf:
    for x in ex.map(work, todo):
        jf.write(json.dumps(x, ensure_ascii=False) + '\n'); jf.flush()
        print(('ok  ' if x.get('pdf') else 'нет ') + x['inn'][:45], x['route'], x.get('status', ''), x.get('date', ''),
              'РУ:', x.get('rows'), 'карт:', x.get('cards'), x.get('error', '')[:60], flush=True)
