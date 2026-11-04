"""Строит content_addr.js — адреса г. Тюмени с административным округом (по данным OpenStreetMap).
   python3 tools/build_addr.py tmn_addr.json   (tmn_addr.json — выгрузка из ветки addr-data)"""
import json, re, sys, collections, os
SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(__file__), '../android/app/src/main/assets/www/content_addr.js')
C = {'Центральный административный округ': 'cen', 'Калининский административный округ': 'kal',
     'Восточный административный округ': 'vos', 'Ленинский административный округ': 'len'}
TYPES = {'улица': 'ул.', 'проезд': 'пр-д', 'переулок': 'пер.', 'проспект': 'пр-т', 'тупик': 'туп.', 'бульвар': 'б-р', 'шоссе': 'ш.',
         'тракт': 'тракт', 'набережная': 'наб.', 'площадь': 'пл.', 'микрорайон': 'мкр', 'квартал': 'кв-л', 'аллея': 'ал.', 'взвоз': 'взвоз'}
SKIP = re.compile(r'^(снт|днт|днп|ст|сосн|сот|сот|с/о|cт|тсн|гск|район)\b|["«]|\bкм\b|километр', re.I)
GLUED = re.compile(r'[а-яё](улица|проезд|переулок|проспект)', re.I)
def key(n):
    w = re.sub(r'[^0-9a-zа-яё]+', ' ', n.lower().replace('ё', 'е')).split()
    return ' '.join(sorted(x for x in w if x not in TYPES))
def disp(n):
    w = n.split(); t = [x for x in w if x.lower() in TYPES]
    if not t: return n
    rest = ' '.join(x for x in w if x.lower() not in TYPES)
    return rest + ' ' + TYPES[t[0].lower()]
def hn(h):
    h = h.upper().replace('КОРПУС', 'К').replace('СТРОЕНИЕ', 'С').replace(' ', '')
    return h
o = json.load(open(SRC, encoding='utf-8'))
st = collections.defaultdict(lambda: collections.defaultdict(collections.Counter)); names = collections.defaultdict(collections.Counter)
for ok, rows in o['addr'].items():
    for s, h, city, sub, lat, lon in rows:
        if not s or not h or city.lower() not in ('', 'тюмень') or SKIP.search(s) or GLUED.search(s): continue
        k = key(s)
        if not k: continue
        names[k][s] += 1
        for one in re.split(r'[;,]', h):
            one = hn(one.strip())
            if one: st[k][one][C[ok]] += 1
out = []
for k, houses in st.items():
    okc = collections.Counter()
    hmap = {}
    for h, c in houses.items():
        o1 = c.most_common(1)[0][0]; hmap[h] = o1; okc[o1] += 1
    if len(okc) == 1:
        spec = next(iter(okc))
    else:
        by = collections.defaultdict(list)
        for h, o1 in hmap.items(): by[o1].append(h)
        nk = lambda x: (int(re.match(r'\d*', x).group() or 0), x)
        spec = '|'.join(f'{o1}:' + ','.join(sorted(v, key=nk)) for o1, v in sorted(by.items(), key=lambda kv: -len(kv[1])))
    out.append([disp(names[k].most_common(1)[0][0]), spec])
out.sort(key=lambda x: x[0].lower())
js = ('/* Адреса г. Тюмени → административный округ. Данные © участники OpenStreetMap (ODbL), выгрузка ' +
      (sys.argv[2] if len(sys.argv) > 2 else '') + '.\n   [улица, "округ"] или [улица, "округ:дома|округ:дома"] для улиц на границе округов. */\n'
      'window.TMN_ADDR = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\n')
open(OUT, 'w', encoding='utf-8').write(js)
print('streets', len(out), 'multi', sum('|' in x[1] for x in out), 'size KB', len(js.encode()) // 1024)
