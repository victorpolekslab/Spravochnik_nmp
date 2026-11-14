"""Правила исправления типовых ошибок OCR и автоматическое снятие пометок, которые ими объясняются.

python3 ocr_rules.py md_dir flags.json --done reviews_*.json --out ocr/reviews_auto_rules.json [--flags-out flags.json]
Правила (применяются только к документам, где были страницы-сканы; единица СКФ — ко всем):
  • «мл/мин/1,73 м2 | м? | …» → «мл/мин/1,73 м²» (единица СКФ);
  • «|» или «]» перед единицей или счётным словом → «1»: «| г» → «1 г», «по | таблетке», «5 мг | раз в сутки»;
  • «1]» перед словом → «1».
Пометка снимается, если после правил все её сомнения объяснены: неуверенно был распознан только символ,
который правило заменило на «1», или числа повторного чтения совпали с числами строки.
"""
import json, os, re, sys, argparse

EGFR = re.compile(r'(?:мл|ml|мг)\s*/\s*(?:мин|min|мл)\s*/\s*1\s*[,.\s‚]\s*73\s*(?:м|m|M)\s*(?:2|²|\?|”|"|’|\'|ʼ)?')
WORD = (r'(?:раз|г\b|мг|мкг|мл|таблет|капсул|ампул|флакон|доз|суппозитор|пакет|саше|капл|ингаляц|впрыск|день|дня|дней|сут|'
        r'недел|месяц|год|лет|час|ч\b|мин|кг|шт|пастил|драже|свеч|пластыр|аппликатор|мерн|ложк|стакан)')
PIPE = re.compile(r'(?:(?<=\s)|(?<=^)|(?<=\())[|\]](?=\s?' + WORD + ')', re.M)
BRACKET = re.compile(r'(?<=\b1)\](?=\s+[а-яё])')

def rules(t, ocr=True):
    t = EGFR.sub('мл/мин/1,73 м²', t)
    if ocr:
        t = PIPE.sub('1', t)
        t = BRACKET.sub('', t)
    return t

def nums(s):
    return re.findall(r'\d+(?:[.,]\d+)?', EGFR.sub(' ', s).replace('.', ','))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('md_dir'); ap.add_argument('flags'); ap.add_argument('--done', nargs='*', default=[])
    ap.add_argument('--out', required=True); ap.add_argument('--flags-out')
    a = ap.parse_args()

    n_docs = n_rep = 0
    for f in sorted(os.listdir(a.md_dir)):
        p = os.path.join(a.md_dir, f)
        t = open(p, encoding='utf-8').read()
        ocr = 'Распознано автоматически (OCR)' in t
        new = rules(t, ocr)
        if new != t:
            n_rep += len(PIPE.findall(t)) + len(BRACKET.findall(t)) if ocr else 0
            open(p, 'w', encoding='utf-8').write(new); n_docs += 1
    print('правила применены: «|»/«]» → «1» в %d местах; изменено документов: %d' % (n_rep, n_docs))

    done = set()
    for d in a.done:
        r = json.load(open(d, encoding='utf-8'))
        done |= {x['id'] for x in r.get('bad', [])} | {x[1] for x in r.get('ok', [])} | {x[1] for x in r.get('skip', [])}
    flags = json.load(open(a.flags, encoding='utf-8'))
    auto, changed = [], 0
    for f in flags:
        new_line = rules(f['line'])
        if f['id'] in done:
            f['line'] = new_line; continue
        if new_line != f['line']:
            changed += 1
            ok = True
            for why in f['why']:
                if why.startswith('низкая уверенность'):
                    for tok, conf in re.findall(r'«([^»]*)» \((\d+)\)', why):
                        t = tok.strip('()[];:,.')
                        if t in ('|', ']', '1]') or EGFR.fullmatch(t) or re.fullmatch(r'(?:мл/мин(?:/1[,.]?73)?|1[,.]?73|[мm][2²?”"’]?)', t):
                            continue
                        ok = False
                elif why.startswith('повторное чтение'):
                    m = re.search(r'«(.*)»', why)
                    if not m or nums(rules(m.group(1))) != nums(new_line):
                        ok = False
                elif 'единица' in why and not PIPE.search(f['line']) and not EGFR.search(f['line']):
                    ok = False
            if ok:
                auto.append([f['md'], f['id']])
        f['line'] = new_line
    json.dump({'source': 'auto: правила OCR (ocr_rules.py): «|» → «1», единица СКФ', 'bad': [], 'ok': auto, 'skip': []},
              open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.flags_out:
        json.dump(flags, open(a.flags_out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('строк в пометках исправлено правилами: %d; пометок снято автоматически: %d' % (changed, len(auto)))
