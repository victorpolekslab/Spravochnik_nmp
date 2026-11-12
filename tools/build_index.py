"""Шаг 3. Оглавление INDEX.md и компактный индекс для приложения drugs_index.json.

python3 build_index.py out/ full/ dest/
"""
import json, os, sys, re, collections, datetime
sys.argv += []
out_dir, full_dir, dest = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(dest, exist_ok=True)
pick = json.load(open(os.path.join(out_dir, 'pick.json'), encoding='utf-8'))
index = json.load(open(os.path.join(out_dir, 'index.json'), encoding='utf-8'))
rep = {}
for l in open(os.path.join(full_dir, 'report.jsonl'), encoding='utf-8'):
    r = json.loads(l)
    if 'error' not in r:
        rep[r['key']] = r
sys.path.insert(0, os.path.dirname(__file__))

# тот же ключ группировки, что в build_list.py
SALT = r'(гидрохлорид|гидробромид|дигидрохлорид|малеат|сульфат|тартрат|битартрат|сукцинат|мезилат|безилат|ацетат|фосфат|цитрат|фумарат|лактат|бромид|хлорид|натрия|калия|кальция|магния|моно|ди|три|гидрат|моногидрат|дигидрат|тригидрат|тетрагидрат|сесквигидрат|гемигидрат|безводный|безводная)'
def inn_key(names):
    out = []
    for n in names:
        w = [x for x in re.split(r'[\s,]+', n.lower().replace('ё', 'е')) if x]
        core = [x for x in w if not re.fullmatch(SALT, x)] or w
        core = [re.sub(r'(а|ы)$', '', x) if len(x) > 6 else x for x in core]
        out.append(' '.join(core))
    return ' + '.join(sorted(set(out)))

doc_by_group = {}
for p in pick:
    r = rep.get(p['key'])
    if r:
        doc_by_group[(p['gkey'], p['route'])] = {'md': r['md'], 'ocr': r['ocr_pages'], 'pages': r['pages'],
                                                 'oid': r.get('fallback') or p['oid'], 'date': p['date']}

# дозагрузка из ГРЛС (grls_fetch.py + grls_texts.py) для групп без ОХЛП
grls = {}
gdir = os.environ.get('GRLS_DIR', 'grls_out')
if os.path.exists(os.path.join(gdir, 'report.jsonl')):
    meta = {}
    for l in open(os.path.join(gdir, 'found.jsonl'), encoding='utf-8'):
        x = json.loads(l)
        if x.get('pdf'): meta[(x['inn'], x['route'])] = x
    for l in open(os.path.join(gdir, 'report.jsonl'), encoding='utf-8'):
        x = json.loads(l)
        if 'error' not in x and (x['inn'], x['route']) in meta:
            grls[(x['inn'], x['route'])] = {**meta[(x['inn'], x['route'])], **x}

items = []
for i in index:
    g = (inn_key(i['inn']), i['route']) if i['inn'] else None
    d = doc_by_group.get(g) if g else None
    gr = grls.get((' + '.join(i['inn']), i['route'])) if not d else None
    items.append({'tn': i['tn'], 'inn': ' + '.join(i['inn']), 'form': i['form'], 'route': i['route'],
                  'atc': i['atc'], 'rx': i['rx'], 'holder': i['holder'], 'oid': i['oid'],
                  'doc': d['md'] if d else (gr['md'] if gr else None),
                  'src': 'ЕАЭС: ОХЛП' if d else (('ГРЛС: ' + gr['kind']) if gr else None)})
json.dump(items, open(os.path.join(dest, 'drugs_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

snap = json.load(open(os.path.join(sys.argv[4] if len(sys.argv) > 4 else '.', 'metadata.json'))) if len(sys.argv) > 4 else {}
rows = sorted(doc_by_group.items(), key=lambda kv: kv[1]['md'])
by_md = {d['md']: (g, d) for g, d in doc_by_group.items()}
lines = ['# Инструкции лекарственных препаратов (ОХЛП, реестр ЕАЭС)', '',
         f'Снимок реестра: {snap.get("snapshot_at", "—")}. Собрано: {datetime.date.today()}.', '',
         f'- Документов: {len(doc_by_group) + len(grls)} (один документ на пару «МНН + путь введения»)',
         f'- Записей в индексе для поиска: {len(items)}, из них со ссылкой на документ: {sum(1 for x in items if x["doc"])}',
         f'- Из них дозагружено из ГРЛС: {len(grls)} (инструкция по медицинскому применению или листок-вкладыш)',
         f'- Распознано через OCR хотя бы частично: {sum(1 for d in doc_by_group.values() if d["ocr"]) + sum(1 for g in grls.values() if g["ocr_pages"])} документов', '',
         '| МНН | Путь | Препарат | АТХ | Источник | Дата | OCR | Файл |', '|---|---|---|---|---|---|---|---|']
pk = {(p['gkey'], p['route']): p for p in pick}
for g, d in sorted(doc_by_group.items(), key=lambda kv: pk[kv[0]]['inn'].lower()):
    p = pk[g]
    ocr = f'{d["ocr"]}/{d["pages"]}' if d['ocr'] else ''
    lines.append(f'| {p["inn"]} | {p["route"]} | {p["tn"]} | {p["atc"]} | ЕАЭС: ОХЛП | {d["date"]} | {ocr} | [md](md/{d["md"]}) |')
for (inn, rt), g in sorted(grls.items(), key=lambda kv: kv[0][0].lower()):
    ocr = f'{g["ocr_pages"]}/{g["pages"]}' if g['ocr_pages'] else ''
    lines.append(f'| {inn} | {rt} | {g["tn"]} | {g["atc"]} | ГРЛС: {g["kind"]} | {g["date"]} | {ocr} | [md](md/{g["md"]}) |')
open(os.path.join(dest, 'INDEX.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print(len(items), 'index items;', sum(1 for x in items if x['doc']), 'with doc;', len(doc_by_group), 'ЕАЭС docs;', len(grls), 'ГРЛС docs')
