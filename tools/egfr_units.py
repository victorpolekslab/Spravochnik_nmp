"""Единица СКФ «мл/мин/1,73 м²»: приводит её к одному виду в текстах и снимает пометки OCR, вызванные только ею.

python3 egfr_units.py md_dir flags.json reviews_done.json [...] --out ocr/reviews_auto_egfr.json
1. Во всех md варианты «мл/мин/1,73 м2», «…м?», «…1.73м2», «мл/мин / 1,73 м”» и т. п. → «мл/мин/1,73 м²».
2. Для непроверенных пометок: если неуверенно распознаны только части этой единицы («мл/мин/1,73», «м2)»,
   «73»), а остальные числа строки при повторном чтении совпали, пометка считается снятой.
   Результат — файл решений в формате apply_reviews.py (список ok), с пометкой auto.
"""
import json, os, re, sys, argparse

# «мг/мл/1,73» и «мл/мл/1,73» — частые ошибки OCR той же единицы: с хвостом «/1,73 м²» другой единицы не бывает
RX = re.compile(r'(?:мл|ml|мг)\s*/\s*(?:мин|min|мл)\s*/\s*1\s*[,.\s‚]\s*73\s*(?:м|m|M)\s*(?:2|²|\?|”|"|’|\'|ʼ)?')
CANON = 'мл/мин/1,73 м²'
UNIT_TOK = re.compile(r'^(?:(?:мл|ml|мг)/(?:мин|min|мл)(?:/1(?:[,.‚]?73)?)?|1[,.‚]?73|‚?73|[мmM][2²?”"’]?|мин/1[,.‚]73)$')

ap = argparse.ArgumentParser()
ap.add_argument('md_dir'); ap.add_argument('flags'); ap.add_argument('done', nargs='*'); ap.add_argument('--out', required=True)
a = ap.parse_args()

# 1. тексты
n_files = n_rep = 0
for f in sorted(os.listdir(a.md_dir)):
    p = os.path.join(a.md_dir, f)
    t = open(p, encoding='utf-8').read()
    body, sep, check = t.partition('\n## Проверка распознавания\n')
    changed = sum(1 for m in RX.finditer(body) if m.group(0) != CANON)
    if changed:
        open(p, 'w', encoding='utf-8').write(RX.sub(CANON, body) + sep + check)
        n_files += 1; n_rep += changed
print('единица СКФ приведена к виду «%s»: %d мест в %d документах' % (CANON, n_rep, n_files))

# 2. пометки
done = set()
for d in a.done:
    r = json.load(open(d, encoding='utf-8'))
    done |= {x['id'] for x in r.get('bad', [])} | {x[1] for x in r.get('ok', [])} | {x[1] for x in r.get('skip', [])}
flags = [f for f in json.load(open(a.flags, encoding='utf-8')) if f['id'] not in done]

def nums(s):
    return re.findall(r'\d+(?:[.,]\d+)?', RX.sub(' ', s).replace('.', ','))

auto = []
for f in flags:
    if not re.search(r'1\s*[,.\s]\s*73|мл/мин', f['line']):
        continue
    explained = True
    for why in f['why']:
        if why.startswith('низкая уверенность'):
            toks = re.findall(r'«([^»]*)» \((\d+)\)', why)
            for tok, conf in toks:
                t = tok.strip('()[];:,.')
                if not UNIT_TOK.match(t):
                    explained = False
        elif why.startswith('повторное чтение'):
            second = re.search(r'«(.*)»', why)
            if not second or nums(second.group(1)) != nums(f['line']):
                explained = False
        else:   # искажённая единица и прочее
            if not RX.search(f['line']):
                explained = False
    if explained:
        auto.append([f['md'], f['id']])
json.dump({'source': 'auto: единица СКФ мл/мин/1,73 м² (egfr_units.py)', 'bad': [], 'ok': auto, 'skip': []},
          open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('пометок со строкой СКФ снято автоматически: %d из %d непроверенных' % (len(auto), len(flags)))
