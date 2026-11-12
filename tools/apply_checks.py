"""Добавляет в md раздел «Проверка распознавания» по результатам check_ocr.py и копирует вырезки.

python3 apply_checks.py map.json md_dir dest_ocr_dir chk1 [chk2 ...]
map.json: {"<имя md>": "<путь к PDF>"}; chkN — папки с check.jsonl, crops/ и jobs (id → pdf) в jobs.json.
Ссылки на вырезки в md: ../ocr/<файл>.png (md лежат в md/, вырезки — в ocr/).
"""
import json, os, sys, shutil
mp, md_dir, dest, chks = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
os.makedirs(dest, exist_ok=True)
by_pdf = {}
for c in chks:
    jobs = {j['id']: j['pdf'] for j in json.load(open(os.path.join(c, 'jobs.json'), encoding='utf-8'))}
    for l in open(os.path.join(c, 'check.jsonl'), encoding='utf-8'):
        x = json.loads(l)
        if x.get('flags'):
            by_pdf[os.path.normpath(jobs[x['id']])] = (c, x['flags'])
n_docs = n_flags = 0
for md_name, pdf in json.load(open(mp, encoding='utf-8')).items():
    hit = by_pdf.get(os.path.normpath(pdf))
    md = os.path.join(md_dir, md_name)
    if not hit or not os.path.exists(md):
        continue
    c, flags = hit
    text = open(md, encoding='utf-8').read().split('\n## Проверка распознавания\n')[0].rstrip()
    lines = ['', '## Проверка распознавания', '',
             f'Страницы-сканы распознаны автоматически. В {len(flags)} строках с дозировками цифры могли '
             'распознаться с ошибкой — сверьте с вырезкой из оригинала:', '']
    for f in flags:
        lines.append(f'- стр. {f["page"]}: «{f["line"]}» — {"; ".join(f["why"])}  ')
        lines.append(f'  ![стр. {f["page"]}](../ocr/{f["crop"]})')
        shutil.copy(os.path.join(c, 'crops', f['crop']), os.path.join(dest, f['crop']))
    head, sep, rest = text.partition('\n\n## ')
    head += f'\n- Сомнительных строк после OCR: {len(flags)} (см. раздел «Проверка распознавания»)'
    open(md, 'w', encoding='utf-8').write(head + sep + rest + '\n'.join(lines) + '\n')
    n_docs += 1; n_flags += len(flags)
print('документов с отметками', n_docs, 'строк', n_flags)
