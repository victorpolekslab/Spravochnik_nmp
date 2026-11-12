"""Тексты инструкций из ГРЛС: извлечение (с OCR) и разбивка на разделы.

python3 grls_texts.py grls_out [--workers 6]
Инструкции в ГРЛС бывают двух видов: ОХЛП/ЛВ по правилам ЕАЭС (нумерованные разделы) и
национальная «Инструкция по медицинскому применению» (ненумерованные заголовки). Разделы
национальной инструкции получают номера ОХЛП, чтобы приложение искало их одинаково:
дозы — 4.2, противопоказания — 4.3, взаимодействия — 4.5 и т. д.
Выход: grls_out/md/<slug>__grls.md, grls_out/report.jsonl
"""
import json, os, re, sys, argparse, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(__file__))
from textlib import extract, tidy, sections, slug

ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--workers', type=int, default=6)
a = ap.parse_args()
os.makedirs(os.path.join(a.out, 'md'), exist_ok=True)

# заголовок национальной инструкции → (номер раздела ОХЛП, заголовок для вывода)
NAT = [
    (r'показания(?: к применению| к медицинскому применению)?', '4.1', 'Показания к применению'),
    (r'противопоказания(?: к применению)?', '4.3', 'Противопоказания'),
    (r'с осторожностью', '4.3a', 'С осторожностью'),
    (r'применение (?:при|в период) беременност\w*.*|беременность и (?:период )?(?:грудн\w+ вскармлива\w+|лактац\w+)', '4.6', 'Применение при беременности и в период грудного вскармливания'),
    (r'способ применения и доз\w*|способ применения и режим дозирования|режим дозирования', '4.2', 'Способ применения и дозы'),
    (r'побочн\w+ действи\w*|побочные эффекты|нежелательные реакции', '4.8', 'Побочное действие'),
    (r'передозировка', '4.9', 'Передозировка'),
    (r'взаимодействие(?: с другими лекарственными (?:средствами|препаратами))?.*', '4.5', 'Взаимодействие с другими лекарственными средствами'),
    (r'особые указания(?: и меры предосторожности)?', '4.4', 'Особые указания'),
    (r'влияние на способность (?:к )?управл\w+.*', '4.7', 'Влияние на способность управлять транспортными средствами, механизмами'),
    (r'фармакодинамика', '5.1', 'Фармакодинамика'),
    (r'фармакокинетика', '5.2', 'Фармакокинетика'),
    (r'состав', '2', 'Состав'),
    (r'лекарственная форма', '3', 'Лекарственная форма'),
    (r'форма выпуска', '6.5', 'Форма выпуска'),
    (r'условия хранения', '6.4', 'Условия хранения'),
    (r'срок годности', '6.3', 'Срок годности'),
]
NAT_RX = [(re.compile(r'^[ \t]*(' + rx + r')[ \t]*[:.]?[ \t]*(.*)$', re.I | re.M), num, title) for rx, num, title in NAT]

def nat_sections(t):
    """Первое вхождение каждого заголовка в начале строки (заголовок с заглавной буквы)."""
    found = []
    for rx, num, title in NAT_RX:
        for m in rx.finditer(t):
            if not m.group(1)[:1].isupper():
                continue
            rest = m.group(m.lastindex).strip()
            # «Противопоказания» в начале фразы внутри текста — не заголовок: после заголовка либо конец строки,
            # либо двоеточие, либо текст с заглавной буквы
            line = m.group(0)
            if rest and not re.match(r'[ \t]*' + re.escape(m.group(1)) + r'[ \t]*[:.]', line.strip(), re.I) and rest[:1].islower():
                continue
            found.append((m.start(), num, title, m.start() + len(line) - len(rest), rest))
            break
    found.sort()
    return found

# Листок-вкладыш ЕАЭС: шесть нумерованных разделов, внутри — подзаголовки
LV_TOP = [('1', r'что (?:из себя )?представляет|для чего'), ('2', r'о ч[её]м следует знать|перед (?:при[её]мом|применением|использованием)'),
          ('3', r'(?:при[её]м|применение|использование|как принимать|как применять)'), ('4', r'возможные нежелательные|побочные'),
          ('5', r'хранение'), ('6', r'содержимое упаковки|прочие сведения')]
LV_SUB = {  # подзаголовки → (номер раздела ОХЛП, заголовок)
    '1': [(r'.', '4.1', 'Показания к применению (листок-вкладыш, раздел 1)')],
    '2': [(r'(?:противопоказания|не (?:принимайте|применяйте|используйте))', '4.3', 'Противопоказания'),
          (r'особые указания|предупреждения и меры предосторожности', '4.4', 'Особые указания и меры предосторожности'),
          (r'другие (?:лекарственные )?препараты и|другие лекарственные средства|взаимодействие', '4.5', 'Другие препараты и данный препарат (взаимодействие)'),
          (r'беременность', '4.6', 'Беременность и грудное вскармливание'),
          (r'управление транспортными', '4.7', 'Управление транспортными средствами и работа с механизмами')],
    '3': [(r'.', '4.2', 'Способ применения и дозы (листок-вкладыш, раздел 3)'),
          (r'если вы (?:приняли|применили|ввели|использовали).{0,40}больше', '4.9', 'Передозировка')],
    '4': [(r'.', '4.8', 'Нежелательные реакции')],
    '5': [(r'.', '6.4', 'Хранение')],
    '6': [(r'.', '6.5', 'Содержимое упаковки и прочие сведения')],
}

def _lv_tops(t, pos):
    tops = []
    for num, kw in LV_TOP:
        m = re.compile(r'^[ \t]*' + num + r'[ \t]*\.?[ \t]*(?=[А-ЯЁA-Z])(?i:[^\n]{0,40}?(?:' + kw + r'))[^\n]*', re.M).search(t, pos)
        if m:
            tops.append((m.start(), m.end(), num)); pos = m.end()
    return tops

def lv_sections(t):
    tops = _lv_tops(t, 0)
    if len(tops) >= 3 and tops[-1][0] - tops[0][0] < 1200:   # это было оглавление листка — ищем дальше
        tops = _lv_tops(t, tops[-1][1])
    out = []
    for i, (st, en, num) in enumerate(tops):
        stop = tops[i + 1][0] if i + 1 < len(tops) else len(t)
        for rx, onum, title in LV_SUB[num]:
            if rx == '.':
                out.append((st, onum, title, en, ''))
                continue
            m = re.compile(r'^[ \t]*(?=[А-ЯЁA-Z«"])(?i:(?:' + rx + r'))[^\n]*', re.M).search(t, en, stop)
            if m:
                out.append((m.start(), onum, title, m.end(), m.group(0).strip()))
    out.sort()
    return out

def doc_kind(path):
    import pymupdf
    d = pymupdf.open(path)
    head = ' '.join(d[i].get_text() for i in range(min(2, len(d)))).lower()[:3000]
    if 'листок-вкладыш' in head or 'листок - вкладыш' in head:
        return 'листок-вкладыш (ЕАЭС)'
    if 'общая характеристика' in head:
        return 'ОХЛП (ЕАЭС)'
    return 'инструкция по медицинскому применению'

def work(r):
    pdf = os.path.join(a.out, 'pdf', r['pdf'])
    res = {'inn': r['inn'], 'route': r['route']}
    try:
        text, npages, nocr = extract(pdf)
        text = tidy(text)
        kind = doc_kind(pdf)
        if kind.startswith('листок'):
            secs = lv_sections(text)
        elif kind.startswith('ОХЛП'):
            secs = sections(text)
        else:
            secs = nat_sections(text)
            alt = lv_sections(text)   # тип не определился по первой странице — берём лучший разбор
            if sum(x[1] in ('4.2', '4.3', '4.5') for x in alt) > sum(x[1] in ('4.2', '4.3', '4.5') for x in secs):
                secs, kind = alt, 'листок-вкладыш (ЕАЭС)'
        nums = [s[1] for s in secs]
        res.update(pages=npages, ocr_pages=nocr, n_sections=len(secs), kind=kind, lv=kind.startswith('листок'),
                   has_4_2='4.2' in nums, has_4_3='4.3' in nums, has_4_5='4.5' in nums)
        head = [f'# {r["inn"]} — {r["route"]}', '',
                f'- Препарат: {r["tn"]} ({r["form"]})', f'- АТХ: {r["atc"]}',
                f'- Источник: ГРЛС, {kind}, РУ {r["ru"]}, файл от {r["date"]} '
                f'(https://grls.rosminzdrav.ru/Grls_View_v2.aspx?routingGuid={r["guid"]})',
                f'- Распознано автоматически (OCR): {nocr} из {npages} стр.' if nocr else '- Текстовый слой PDF']
        if r.get('note'):
            head.append('- ' + r['note'])
        if kind.startswith('листок'):
            head.append('- Листок-вкладыш написан для пациента: полной инструкции по медицинскому применению '
                        'и ОХЛП для этого препарата в открытом доступе нет')
        head.append('')
        body = []
        for i, (pos, num, title, bstart, rest) in enumerate(secs):
            end = secs[i + 1][0] if i + 1 < len(secs) else len(text)
            n = num.replace('a', '')
            body += [f'## {n}. {title}', '', (rest + '\n' + text[bstart:end]).strip(), '']
        if not secs:
            body = ['## Текст', '', text]
        name = slug(r['inn'] + '__' + r['route'])[:80] + '__grls_' + r['guid'][:8] + '.md'
        open(os.path.join(a.out, 'md', name), 'w', encoding='utf-8').write('\n'.join(head + body))
        res['md'] = name
    except Exception as e:
        res['error'] = repr(e)[:300]
    return res

found = [json.loads(l) for l in open(os.path.join(a.out, 'found.jsonl'), encoding='utf-8')]
found = [r for r in found if r.get('pdf')]
jl = os.path.join(a.out, 'report.jsonl')
done = set()
if os.path.exists(jl):
    for l in open(jl, encoding='utf-8'):
        x = json.loads(l)
        if 'error' not in x: done.add((x['inn'], x['route']))
todo = [r for r in found if (r['inn'], r['route']) not in done]
print('осталось', len(todo), flush=True)
with cf.ThreadPoolExecutor(a.workers) as ex, open(jl, 'a', encoding='utf-8') as jf:
    for x in ex.map(work, todo):
        jf.write(json.dumps(x, ensure_ascii=False) + '\n'); jf.flush()
rep = {}
for l in open(jl, encoding='utf-8'):
    x = json.loads(l); rep[(x['inn'], x['route'])] = x
ok = [x for x in rep.values() if 'error' not in x]
print(f'готово {len(ok)}/{len(rep)}; нац. формат {sum(x["kind"].startswith("инстр") for x in ok)}; '
      f'со сканами {sum(1 for x in ok if x["ocr_pages"])}; страниц {sum(x["pages"] for x in ok)}, OCR {sum(x["ocr_pages"] for x in ok)}; '
      f'4.2: {sum(x["has_4_2"] for x in ok)}, 4.3: {sum(x["has_4_3"] for x in ok)}, 4.5: {sum(x["has_4_5"] for x in ok)}')
