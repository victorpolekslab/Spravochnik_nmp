"""Данные для приложений: поиск, карточки документов, индекс взаимодействий.

python3 build_app_data.py <ветка drugs (папка с md/ и drugs_index.json)> <выход app/>
Выход:
  app/search.json   — строки поиска [ТН, МНН, форма, путь, АТХ, отпуск, № документа] и список документов
  app/doc/<id>.json — документ: заголовок, сведения об источнике, разделы [номер, заголовок, текст]
  app/ix.json       — взаимодействия: группы; для каждого документа — его собственные ключи (МНН и группы)
                      и упоминания в разделе 4.5: ключ → номера абзацев
Проверка пары A–B в приложении: абзацы 4.5 препарата A, где упомянут B (по МНН или группе), и наоборот.
"""
import json, os, re, sys, hashlib, collections
sys.path.insert(0, os.path.dirname(__file__))
from drug_classes import CLASSES, GENERIC

src, out = sys.argv[1], sys.argv[2]
RAW = 'https://raw.githubusercontent.com/victorpolekslab/Spravochnik_nmp/drugs/'
os.makedirs(os.path.join(out, 'doc'), exist_ok=True)

ENDINGS = sorted(['ами', 'ями', 'ого', 'его', 'ому', 'ему', 'ыми', 'ими', 'ой', 'ей', 'ом', 'ем', 'ая', 'яя', 'ое', 'ее', 'ые',
                  'ие', 'ых', 'их', 'ую', 'юю', 'ам', 'ям', 'ах', 'ях', 'ов', 'ев', 'а', 'я', 'ы', 'и', 'у', 'ю', 'е', 'о', 'ь', 'й'],
                 key=len, reverse=True)
def stem(w):
    w = w.lower().replace('ё', 'е')
    for e in ENDINGS:
        if w.endswith(e) and len(w) - len(e) >= 5:
            return w[:-len(e)]
    return w

WORD = re.compile(r'[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё-]+')
def inn_keys(inn):
    keys = []
    for comp in re.split(r'\s*\+\s*', inn):
        for w in WORD.findall(comp):
            lw = w.lower().replace('ё', 'е')
            if lw in GENERIC or len(lw) < 5:
                continue
            keys.append(stem(lw)); break
    return keys

def did(md):
    return hashlib.sha1(md.encode('utf-8')).hexdigest()[:10]

# --- документы
def parse_md(text):
    head, _, rest = text.partition('\n## ')
    lines = head.split('\n')
    title = lines[0].lstrip('# ').strip()
    meta = [l[2:].strip() for l in lines[1:] if l.startswith('- ')]
    secs, check = [], []
    for block in ('## ' + rest).split('\n## ')[0:]:
        block = block[3:] if block.startswith('## ') else block
        if not block.strip():
            continue
        h, _, body = block.partition('\n')
        if h.startswith('Проверка распознавания'):
            for m in re.finditer(r'- стр\. (\d+): «(.*?)» — (.*?)  \n  !\[[^\]]*\]\(\.\./ocr/([^)]+)\)', body):
                check.append([int(m.group(1)), m.group(2), m.group(3), RAW + 'ocr/' + m.group(4)])
            continue
        m = re.match(r'(\d+(?:\.\d+)?)\.\s+(.*)', h)
        num, t = (m.group(1), m.group(2)) if m else ('', h)
        secs.append([num, t, body.strip()])
    return title, meta, secs, check

idx = json.load(open(os.path.join(src, 'drugs_index.json'), encoding='utf-8'))
docs, doc_no, doc_atc = [], {}, collections.defaultdict(set)
sec45 = {}
for i in idx:
    if i['doc'] and i['doc'] not in doc_no:
        md = i['doc']
        text = open(os.path.join(src, 'md', md), encoding='utf-8').read()
        title, meta, secs, check = parse_md(text)
        d = did(md)
        json.dump({'t': title, 'm': meta, 's': secs, 'c': check, 'md': md},
                  open(os.path.join(out, 'doc', d + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        kind = 'lv' if 'листок' in (i.get('src') or '') else ('grls' if (i.get('src') or '').startswith('ГРЛС') else 'ohlp')
        doc_no[md] = len(docs)
        docs.append([d, kind, 1 if check else 0, title])
        for num, t, body in secs:
            if num == '4.5':
                sec45[d] = [p.strip() for p in body.split('\n') if len(p.strip()) > 2]
                break
    if i['doc'] and i['atc']:
        doc_atc[doc_no[i['doc']]].add(i['atc'])

rows = [[i['tn'], i['inn'], i['form'], i['route'], i['atc'], i['rx'], doc_no.get(i['doc'], -1)] for i in idx]
json.dump({'v': 1, 'docs': docs, 'rows': rows}, open(os.path.join(out, 'search.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, separators=(',', ':'))

# --- ключи МНН: известные препараты + МНН из списков групп
inn_of_doc = {}
for i in idx:
    if i['doc'] and i['inn']:
        inn_of_doc.setdefault(doc_no[i['doc']], i['inn'])
ALLKEYS = set()
for inn in inn_of_doc.values():
    ALLKEYS.update(inn_keys(inn))
# АТХ монопрепаратов по ключу МНН — чтобы комбинации получили группы своих компонентов
mono_atc = collections.defaultdict(set)
for i in idx:
    ks = inn_keys(i['inn']) if i['inn'] else []
    if len(ks) == 1 and ' + ' not in i['inn'] and i['atc']:
        mono_atc[ks[0]].add(i['atc'])

CLS = [(code, name, [re.compile(p, re.I) for p in pats], atcs, [stem(m) for m in members]) for code, name, pats, atcs, members in CLASSES]

def own_keys(n):
    inn = inn_of_doc.get(n, '')
    ks = inn_keys(inn)
    atcs = set(doc_atc.get(n, set()))
    for k in ks:
        atcs |= mono_atc.get(k, set())
    keys = ['i:' + k for k in ks]
    for code, name, pats, cls_atc, members in CLS:
        if any(a.startswith(p) for a in atcs for p in cls_atc) or any(k.startswith(m) or m.startswith(k) for k in ks for m in members):
            keys.append('c:' + code)
    return keys

def mentions(paras, own):
    found = collections.defaultdict(list)
    for pi, p in enumerate(paras):
        hit = set()
        for w in WORD.findall(p):
            lw = w.lower().replace('ё', 'е')
            if len(lw) < 5:
                continue
            s = stem(lw)
            if s in ALLKEYS:
                hit.add('i:' + s); continue
            for cut in range(1, 4):   # «амиодароном» → «амиодарон»
                if len(lw) - cut >= 5 and lw[:-cut] in ALLKEYS:
                    hit.add('i:' + lw[:-cut]); break
        for code, name, pats, cls_atc, members in CLS:
            if any(rx.search(p) for rx in pats):
                hit.add('c:' + code)
        for k in hit - set(own):
            found[k].append(pi)
    return found

own = {}
men = {}
for n, (d, kind, chk, title) in enumerate(docs):
    own[d] = own_keys(n)
    if d in sec45:
        m = mentions(sec45[d], [k for k in own[d] if k.startswith('i:')])
        if m:
            men[d] = m
BROAD = {'antihyp', 'abx', 'cns_dep', 'raas', 'bleed', 'diur', 'anticoag', 'antidep', 'glucose_low', 'cyto', 'immsup'}
json.dump({'v': 1, 'classes': [[c[0], c[1], c[2], 1 if c[0] in BROAD else 0] for c in CLASSES], 'own': own, 'men': men},
          open(os.path.join(out, 'ix.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
ver = hashlib.sha1(open(os.path.join(out, 'search.json'), 'rb').read() + open(os.path.join(out, 'ix.json'), 'rb').read()).hexdigest()[:12]
json.dump({'v': ver}, open(os.path.join(out, 'version.json'), 'w'))
print('версия', ver, 'документов', len(docs), 'строк поиска', len(rows), 'с разделом 4.5', len(sec45), 'с упоминаниями', len(men),
      'ключей МНН', len(ALLKEYS))
