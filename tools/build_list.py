"""Шаг 1. Список препаратов из выгрузки реестра ЕАЭС (ОП-26).

Вход:  OP26_*.json из https://opendata.eaeunion.org/registry-archives/OP26_1.0.0_full.zip
Выход: index.json  — все действующие в РФ РУ (для поиска в приложении)
       pick.json   — по одной ОХЛП на пару «МНН + путь введения» (что скачивать)
       stats.txt   — сводка

Исключаем: гомеопатию, РУ без действующей регистрации в РФ.
Выбор ОХЛП: оригинальный препарат > самая свежая ОХЛП по дате документа.
"""
import json, re, sys, collections, glob, os

src_dir, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
recs = []
for f in sorted(glob.glob(os.path.join(src_dir, 'OP26_*.json'))):
    recs += json.load(open(f, encoding='utf-8'))

def d8(x):
    v = (x or {}).get('$date')
    return v[:10] if isinstance(v, str) else ''

def clean_inn(s):
    s = (s or '').replace('[', '').replace(']', '')
    s = re.sub(r'\s*\(.*', '', s).strip(' ;,.')   # химическое название в скобках
    # обрывки химических названий и дозировок — не МНН
    if not s or re.match(r'[\d\W]', s) or re.search(r'\d\s*(мг|мкг|г|мл|%|МЕ|ЕД)\b', s):
        return ''
    return s[:1].upper() + s[1:]

def inns(dd):
    top = [x.get('drugName') for x in dd.get('drugNameDetails', []) if x.get('drugName')]
    top = [t for t in top if t.strip().lower() not in ('отсутствует', '-', 'не применимо')]
    if top:
        parts = []
        for t in top:
            parts += re.split(r'\s*\+\s*', t)
    else:
        parts = [x.get('drugNameDetails', {}).get('drugName') for x in dd.get('activeIngredientDetails', [])]
    out = sorted({clean_inn(p) for p in parts if p and clean_inn(p)}, key=str.lower)
    if not out:   # МНН не разобрать (химическое название) — берём МНН из сведений о субстанциях
        alt = [x.get('drugNameDetails', {}).get('drugName') for x in dd.get('activeIngredientDetails', [])]
        out = sorted({clean_inn(p) for p in alt if p and clean_inn(p)}, key=str.lower)
    return out

FORM_BY_CODE = {}
for _r in recs:
    _f = (_r['drugDetails'].get('dosageFormDetails') or {})
    if _f.get('dosageFormCode') and _f.get('dosageFormName'):
        FORM_BY_CODE.setdefault(_f['dosageFormCode'], _f['dosageFormName'])

def form_of(dd):
    fd = dd.get('dosageFormDetails') or {}
    f = fd.get('dosageFormName') or FORM_BY_CODE.get(fd.get('dosageFormCode'))
    if not f:
        for p in dd.get('packageFormDetails', []):
            for q in p.get('packageDetails', []):
                if q.get('dosageFormName'):
                    return q['dosageFormName']
    return f or ''

ROUTES = [  # порядок важен: первое совпадение
    ('ингаляц', r'ингал|небулайз|аэрозоль для ингал|порошок для ингал'),
    ('парентерально', r'инъекц|инфуз|внутривен|внутримыш|подкож|парентер|лиофилизат|концентрат для приготовления раствора для (инфуз|инъек)|эмульсия для инфуз|внутрисустав|интратекал|эндотрахеал'),
    ('глаза', r'глазн'),
    ('уши', r'ушн'),
    ('нос', r'назальн|в нос'),
    ('ректально', r'ректальн|клизм'),
    ('вагинально', r'вагинальн'),
    ('под язык/за щеку', r'подъязыч|сублингв|защеч|трансбуккал'),
    ('наружно', r'наружн|мазь|крем|гель|пластыр|трансдермал|линимент|паста|присыпк|лак для ногтей|шампунь|местного'),
    ('внутрь', r'таблет|капсул|драже|гранул|сироп|суспенз|для приема внутрь|порошок для приготовления раствора для приема|капли для приема|раствор для приема|эликсир|пастилк|леденц|жеват|шипуч|диспергир|саше|экстракт|настойк|сбор|чай|измельч|порошок|цельн|^сок'),
]
def route(form):
    f = form.lower()
    for name, rx in ROUTES:
        if re.search(rx, f):
            return name
    return 'прочее'

def is_homeo(r):
    dd = r['drugDetails']
    s = form_of(dd) + ' ' + json.dumps(dd.get('drugAdditionalFeatureDetails', []), ensure_ascii=False) + ' ' + (dd.get('registrationDrugKindName') or '')
    if re.search('гомеопат', s, re.I):
        return True
    names = ' '.join(x.get('drugName') or '' for x in dd.get('drugNameDetails', []))
    return len(re.findall(r'\b[DC]\d{1,3}\b|Ø', names)) >= 2   # потенции D6, C12, Ø

def atc(dd):
    c = dd.get('atcCode') or ''
    if not c and dd.get('atcName'):
        m = re.match(r'\s*([A-ZА-Я]\d\d[A-ZА-Я]{0,2}\d{0,2})', dd['atcName'])
        c = m.group(1) if m else ''
    tr = str.maketrans('АВСЕНКМОРТХ', 'ABCEHKMOPTX')   # кириллица в кодах АТХ
    return c.translate(tr).strip()

def docs(c, kind):
    out = []
    for x in (c.get('drugDocumentsDetails') or {}).get('drugDocumentList') or []:
        u = x.get('uploadedFile') or {}
        if x.get('drugKindCode') == kind and u.get('path'):
            out.append({'path': u['path'], 'size': u.get('size') or 0,
                        'date': d8(x.get('docCreationDate')) or d8(x.get('createdCustomDate'))})
    return out

SALT = r'(гидрохлорид|гидробромид|дигидрохлорид|малеат|сульфат|тартрат|битартрат|сукцинат|мезилат|безилат|ацетат|фосфат|цитрат|фумарат|лактат|бромид|хлорид|натрия|калия|кальция|магния|моно|ди|три|гидрат|моногидрат|дигидрат|тригидрат|тетрагидрат|сесквигидрат|гемигидрат|безводный|безводная)'
def inn_key(names):
    out = []
    for n in names:
        w = [x for x in re.split(r'[\s,]+', n.lower().replace('ё', 'е')) if x]
        core = [x for x in w if not re.fullmatch(SALT, x)] or w
        core = [re.sub(r'(а|ы)$', '', x) if len(x) > 6 else x for x in core]  # «амиодарона» → «амиодарон»
        out.append(' '.join(core))
    return ' + '.join(sorted(set(out)))

index, groups, st = [], collections.defaultdict(list), collections.Counter()
for r in recs:
    st['всего записей'] += 1
    ru = [c for c in r.get('drugCountryRegistrationDetails', [])
          if c.get('unifiedCountryCode', {}).get('value') == 'RU'
          and (c.get('drugRegistrationCertificateDetails') or {}).get('registrationStatusCode') == '03']
    if not ru:
        continue
    st['действуют в РФ'] += 1
    if is_homeo(r):
        st['исключено: гомеопатия'] += 1
        continue
    dd = r['drugDetails']
    inn, form = inns(dd), form_of(dd)
    c = ru[0]
    ohlp = docs(c, 'GENERAL_CHARACTERISTIC')
    lv = docs(c, 'USAGE_INSTRUCTION')
    if not ohlp:   # ОХЛП могла быть загружена референтным государством
        for c2 in r.get('drugCountryRegistrationDetails', []):
            ohlp += docs(c2, 'GENERAL_CHARACTERISTIC')
    item = {
        'oid': r['_id']['$oid'], 'ru': 'ЛП-№' + (r.get('registrationNumberId') or '') + '-(РГ-RU)',
        'tn': (c.get('drugTradeName') or '').strip(), 'inn': inn, 'form': form, 'route': route(form),
        'atc': atc(dd), 'kind': dd.get('registrationDrugKindCode') or '',
        'rx': dd.get('descriptionText') or '',
        'holder': (r.get('registrationCertificateHolderDetails') or {}).get('businessEntityName') or '',
        'ohlp': sorted(ohlp, key=lambda x: x['date'], reverse=True)[:1],
        'lv': sorted(lv, key=lambda x: x['date'], reverse=True)[:1],
    }
    index.append(item)
    st['в индексе'] += 1
    st['есть ОХЛП'] += bool(item['ohlp'])
    st['без МНН'] += not inn
    if inn and item['ohlp']:
        groups[(inn_key(inn), item['route'])].append(item)

pick = []
for (inn, rt), items in groups.items():
    items = sorted(items, key=lambda x: (x['kind'] == '01', x['ohlp'][0]['date']), reverse=True)
    best = items[0]
    name = collections.Counter(' + '.join(x['inn']) for x in items).most_common(1)[0][0]
    pick.append({'key': name + ' | ' + rt, 'inn': name, 'gkey': inn,
                 'cands': [{'oid': x['oid'], 'path': x['ohlp'][0]['path'], 'tn': x['tn'], 'form': x['form'], 'date': x['ohlp'][0]['date']} for x in items[1:4]], 'route': rt, 'oid': best['oid'], 'tn': best['tn'],
                 'form': best['form'], 'atc': best['atc'], 'original': best['kind'] == '01',
                 'date': best['ohlp'][0]['date'], 'path': best['ohlp'][0]['path'],
                 'size': best['ohlp'][0]['size'], 'alt': len(items) - 1})
pick.sort(key=lambda x: x['key'].lower())

st['МНН (уникальных)'] = len({p['gkey'] for p in pick})
st['ОХЛП к скачиванию (МНН + путь)'] = len(pick)
st['объём ОХЛП, МБ'] = round(sum(p['size'] for p in pick) / 2**20)
rc = collections.Counter(p['route'] for p in pick)
json.dump(index, open(os.path.join(out_dir, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(pick, open(os.path.join(out_dir, 'pick.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
with open(os.path.join(out_dir, 'stats.txt'), 'w', encoding='utf-8') as f:
    for k, v in st.items():
        f.write(f'{k}: {v}\n')
    f.write('по путям введения: ' + ', '.join(f'{k} {v}' for k, v in rc.most_common()) + '\n')
print(open(os.path.join(out_dir, 'stats.txt'), encoding='utf-8').read())
