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

from textlib import *
import textlib
textlib.OCR_DPI = a.ocr_dpi

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
