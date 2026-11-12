"""Вносит решения ручной проверки (страница «Проверка распознанных доз») в md.

python3 apply_reviews.py md_dir reviews_1.json [reviews_2.json ...]
- «верно»: строка убирается из раздела «Проверка распознавания»;
- «ошибка»: распознанная строка в тексте заменяется исправленной, строка убирается из раздела;
- в шапке пересчитывается «Сомнительных строк после OCR», раздел удаляется, если строк не осталось,
  и добавляется «Проверено вручную: N строк».
Запускать после apply_checks.py: решения хранятся в ocr/reviews_*.json и переносятся при пересборке.
"""
import json, os, re, sys, collections
md_dir, files = sys.argv[1], sys.argv[2:]
by_md = collections.defaultdict(lambda: {'ok': set(), 'bad': []})
for f in files:
    r = json.load(open(f, encoding='utf-8'))
    for md, cid in r.get('ok', []):
        by_md[md]['ok'].add(cid)
    for b in r.get('bad', []):
        by_md[b['md']]['bad'].append(b)

stat = collections.Counter()
for md, rv in by_md.items():
    p = os.path.join(md_dir, md)
    if not os.path.exists(p):
        stat['нет файла'] += 1; continue
    text = open(p, encoding='utf-8').read()
    body, sep, check = text.partition('\n## Проверка распознавания\n')
    done = set(rv['ok'])
    for b in rv['bad']:
        if b['line'] in body:
            body = body.replace(b['line'], b['fix'], 1); stat['исправлено'] += 1
        else:
            stat['исправление не найдено в тексте'] += 1
            print('не найдено:', md, '|', b['line'][:60])
        done.add(b['id'])
    stat['подтверждено'] += len(rv['ok'])
    if sep:
        # пункт раздела = строка «- стр. …» + строка с картинкой ../ocr/<id>.png
        items = re.split(r'\n(?=- стр\. )', check)
        intro, rest = items[0], items[1:]
        keep = [it for it in rest if not any(f'../ocr/{cid}.png' in it for cid in done)]
        n = len(keep)
        if n:
            intro = re.sub(r'В \d+ строках', f'В {n} строках', intro)
            check = intro + '\n' + '\n'.join(keep)
        else:
            sep, check = '', ''
        body = re.sub(r'- Сомнительных строк после OCR: \d+[^\n]*',
                      f'- Сомнительных строк после OCR: {n} (см. раздел «Проверка распознавания»)' if n else
                      '- Сомнительных строк после OCR не осталось', body, count=1)
    m = re.search(r'- Проверено вручную строк: (\d+)', body)
    total = len(done) + (int(m.group(1)) if m else 0)
    if m:
        body = body.replace(m.group(0), f'- Проверено вручную строк: {total}', 1)
    else:
        body = re.sub(r'(- (?:Сомнительных строк после OCR[^\n]*))', r'\1' + f'\n- Проверено вручную строк: {total}', body, count=1)
    open(p, 'w', encoding='utf-8').write(body + (sep + check if sep else '\n'))
print(dict(stat))
