"""Шаг 2. Скачивает выбранные ОХЛП, извлекает текст (или распознаёт скан) и режет на разделы.

python3 fetch_texts.py pick.json out_dir [--only "Амиодарон,Эпинефрин"] [--sample N] [--workers 4]
Выход: out_dir/pdf/<oid>.pdf, out_dir/md/<slug>.md, out_dir/report.json
"""
import json, os, re, sys, collections, subprocess, random, argparse, concurrent.futures as cf
import pymupdf
sys.path.insert(0, os.path.dirname(__file__))
from getfile import get_file

ap = argparse.ArgumentParser()
ap.add_argument('pick'); ap.add_argument('out')
ap.add_argument('--only', default=''); ap.add_argument('--sample', type=int, default=0)
ap.add_argument('--workers', type=int, default=4); ap.add_argument('--ocr-dpi', type=int, default=300)
a = ap.parse_args()
pick = json.load(open(a.pick, encoding='utf-8'))
if a.only:
    want = [w.strip().lower() for w in a.only.split(',')]
    pick = [p for p in pick if any(p['inn'].lower().startswith(w) for w in want)]
if a.sample:
    random.seed(7); pick = random.sample(pick, min(a.sample, len(pick)))
for d in ('pdf', 'md'):
    os.makedirs(os.path.join(a.out, d), exist_ok=True)

SEC = re.compile(r'^\s*(\d{1,2}(?:\.\d{1,2})?)\.?\s+([А-ЯЁA-Z][^\n]{2,160})$', re.M)
MIN_CHARS_PER_PAGE = 300   # меньше — считаем страницу сканом

def ocr_page(page):
    png = page.get_pixmap(dpi=a.ocr_dpi, colorspace=pymupdf.csGRAY).tobytes('png')
    r = subprocess.run(['tesseract', 'stdin', 'stdout', '-l', 'rus+eng', '--psm', '6'],
                       input=png, capture_output=True, timeout=180)
    return r.stdout.decode('utf-8', 'replace')

def extract(path):
    doc = pymupdf.open(path)
    pages, ocr_pages = [], 0
    for pg in doc:
        t = pg.get_text()
        if len(t.strip()) < MIN_CHARS_PER_PAGE:
            t = ocr_page(pg); ocr_pages += 1
        pages.append(t)
    return '\n'.join(pages), len(doc), ocr_pages

SECLINE = re.compile(r'\d{1,2}(\.\d{1,2})?\.?\s+[А-ЯЁA-Z]')

def reflow(t):
    """Склеивает строки, разорванные выравниванием по ширине, убирает номера страниц."""
    lines = [l.strip() for l in t.split('\n')]
    lines = [l for l in lines if not re.fullmatch(r'\d{1,3}|стр\.? ?\d+( из \d+)?', l, re.I)]
    out = []
    for l in lines:
        prev = out[-1] if out else ''
        join = (prev and l and not re.search(r'[.:;!?»)]$', prev) and not SECLINE.match(l) and (not SECLINE.match(prev) or l[:1].islower())
                and (l[0].islower()
                     or (l[0].isdigit() and not re.match(r'\d+[.)] ', l))
                     or (len(prev) < 40 and not prev.startswith(('•', '-', '–')))))
        if join:
            out[-1] = prev + ' ' + l
        else:
            out.append(l)
    return '\n'.join(out)

def tidy(t):
    t = t.replace('­', '').replace('\xa0', ' ')
    t = re.sub(r'(\w)-\n(\w)', r'\1\2', t)            # переносы слов
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return reflow(t).strip()

# Структура ОХЛП по Решению Совета ЕЭК № 88: номер и ключевое слово заголовка
OHLP = [('1', 'наименован'), ('2', 'качествен'), ('3', 'лекарственн'), ('4', 'клиническ'),
        ('4.1', 'показан'), ('4.2', 'режим дозир|дозирован|способ примен'), ('4.3', 'противопоказ'),
        ('4.4', 'особые указан|меры предосторож'), ('4.5', 'взаимодейств'), ('4.6', 'фертильн|беремен'),
        ('4.7', 'управл|транспорт|механизм'), ('4.8', 'нежелательн|побочн'), ('4.9', 'передозир'),
        ('5', 'фармакологическ'), ('5.1', 'фармакодинам'), ('5.2', 'фармакокинет'), ('5.3', 'доклиническ'),
        ('6', 'фармацевтическ'), ('6.1', 'вспомогательн'), ('6.2', 'несовместим'), ('6.3', 'срок годност'),
        ('6.4', 'хранен'), ('6.5', 'упаковк'), ('6.6', 'уничтожен|утилизац|обращен|использован'),
        ('7', 'держател'), ('8', 'номер'), ('9', 'дата первичн|дата регистрац|первичной регистрац'), ('10', 'пересмотр')]

TITLES = {'1': 'Наименование лекарственного препарата', '2': 'Качественный и количественный состав',
          '3': 'Лекарственная форма', '4': 'Клинические данные', '4.1': 'Показания к применению',
          '4.2': 'Режим дозирования и способ применения', '4.3': 'Противопоказания',
          '4.4': 'Особые указания и меры предосторожности при применении',
          '4.5': 'Взаимодействие с другими лекарственными препаратами и другие виды взаимодействия',
          '4.6': 'Фертильность, беременность и лактация',
          '4.7': 'Влияние на способность управлять транспортными средствами и работать с механизмами',
          '4.8': 'Нежелательные реакции', '4.9': 'Передозировка', '5': 'Фармакологические свойства',
          '5.1': 'Фармакодинамические свойства', '5.2': 'Фармакокинетические свойства',
          '5.3': 'Данные доклинической безопасности', '6': 'Фармацевтические свойства',
          '6.1': 'Перечень вспомогательных веществ', '6.2': 'Несовместимость', '6.3': 'Срок годности (срок хранения)',
          '6.4': 'Особые меры предосторожности при хранении', '6.5': 'Характер и содержание первичной упаковки',
          '6.6': 'Особые меры предосторожности при уничтожении использованного лекарственного препарата',
          '7': 'Держатель регистрационного удостоверения', '8': 'Номер регистрационного удостоверения',
          '9': 'Дата первичной регистрации', '10': 'Дата пересмотра текста'}

def _strip_title(line, title):
    """Отрезает от строки заголовок (по словам, без учёта регистра); возвращает остаток — начало текста."""
    lw, tw = line.split(), title.lower().replace('(', '').replace(')', '').split()
    i = 0
    while i < len(lw) and i < len(tw) and lw[i].lower().strip('().,:') == tw[i].strip(',').lower():
        i += 1
    while i < len(lw) and lw[i][:1].islower():   # хвост заголовка, которого нет в эталоне
        i += 1
    return ' '.join(lw[i:])

def sections(t):
    out, pos = [], 0
    for num, kw in OHLP:
        # номер может стоять в начале строки, на отдельной строке или в конце предыдущей строки
        rx = re.compile(r'(?:^|(?<=[\s]))' + re.escape(num) + r'[ \t]?\.?[ \t]*\n?[ \t]*(?=[А-ЯЁA-Z])((?i:' + kw + r')[^\n]*)', re.M)
        m = rx.search(t, pos)
        if not m:   # номер потерян: заголовок без номера в начале строки (первые слова эталона)
            first = ' '.join(TITLES[num].split()[:2])
            m = re.compile(r'^[ \t]*(' + re.escape(first) + r'[^\n]*)', re.M | re.I).search(t, pos)
            if m and not m.group(1)[:1].isupper():
                m = None
        if m:
            rest = _strip_title(m.group(1), TITLES[num])
            out.append((m.start(), num, TITLES[num], m.end(), rest))
            pos = m.end()
    return out

def slug(s):
    s = re.sub(r'[^\w]+', '_', s.lower()).strip('_')
    return s[:90]

_names = collections.Counter(slug(p['inn'] + '__' + p['route']) for p in json.load(open(a.pick, encoding='utf-8')))

def md_name(p):
    n = slug(p['inn'] + '__' + p['route'])
    return (n + '__' + p['oid'][-8:] if _names[n] > 1 else n) + '.md'

def work(p):
    pdf = os.path.join(a.out, 'pdf', p['oid'] + '.pdf')
    res = {'key': p['key'], 'oid': p['oid']}
    try:
        if not os.path.exists(pdf) or os.path.getsize(pdf) < 1000:
            last = None
            for c in [p] + p.get('cands', []):   # если файл не отдаётся — берём следующего кандидата
                try:
                    open(pdf, 'wb').write(get_file(c['oid'], c['path']))
                    if c is not p:
                        p = {**p, 'oid': c['oid'], 'tn': c['tn'], 'form': c['form'], 'date': c['date']}
                        res['fallback'] = c['oid']
                    break
                except Exception as e:
                    last = e
            else:
                raise last
        text, npages, nocr = extract(pdf)
        text = tidy(text)
        secs = sections(text)
        nums = [s[1] for s in secs]
        res.update(pages=npages, ocr_pages=nocr, chars=len(text), n_sections=len(secs),
                   has_4_2='4.2' in nums, has_4_3='4.3' in nums, has_4_5='4.5' in nums)
        head = [f'# {p["inn"]} — {p["route"]}', '',
                f'- Препарат: {p["tn"]} ({p["form"]})', f'- АТХ: {p["atc"]}',
                f'- Источник: ОХЛП, Единый реестр ЛС ЕАЭС, запись {p["oid"]}, документ от {p["date"]}',
                f'- Распознано автоматически (OCR): {nocr} из {npages} стр.' if nocr else '- Текстовый слой PDF',
                '']
        body = []
        for i, (pos, num, title, _e, rest) in enumerate(secs):
            end = secs[i + 1][0] if i + 1 < len(secs) else len(text)
            body += [f'## {num}. {title}', '', (rest + '\n' + text[secs[i][3]:end]).strip(), '']
        if not secs:
            body = ['## Текст', '', text]
        name = md_name(p)
        open(os.path.join(a.out, 'md', name), 'w', encoding='utf-8').write('\n'.join(head + body))
        res['md'] = name
    except Exception as e:
        res['error'] = repr(e)[:300]
    return res

# повторный запуск продолжает с места остановки: готовые записи берём из report.jsonl
jl = os.path.join(a.out, 'report.jsonl')
done = {}
if os.path.exists(jl):
    for line in open(jl, encoding='utf-8'):
        r = json.loads(line)
        if 'error' not in r:
            done[r['key']] = r
todo = [p for p in pick if p['key'] not in done]
print(f'уже готово {len(done)}, осталось {len(todo)}', flush=True)
rep = list(done.values())
with cf.ThreadPoolExecutor(a.workers) as ex, open(jl, 'a', encoding='utf-8') as jf:
    for r in ex.map(work, todo):
        rep.append(r)
        jf.write(json.dumps(r, ensure_ascii=False) + '\n'); jf.flush()
        print(('ERR ' if 'error' in r else 'ok  ') + r['key'][:60], r.get('pages'), 'ocr', r.get('ocr_pages'),
              'sec', r.get('n_sections'), '4.5' if r.get('has_4_5') else '-', flush=True)
json.dump(rep, open(os.path.join(a.out, 'report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
ok = [r for r in rep if 'error' not in r]
print(f'\nготово {len(ok)}/{len(rep)}; со сканами {sum(1 for r in ok if r["ocr_pages"])}; '
      f'страниц {sum(r["pages"] for r in ok)}, из них OCR {sum(r["ocr_pages"] for r in ok)}; '
      f'найден 4.2: {sum(r["has_4_2"] for r in ok)}, 4.3: {sum(r["has_4_3"] for r in ok)}, 4.5: {sum(r["has_4_5"] for r in ok)}')
