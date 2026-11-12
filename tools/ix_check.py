"""Проверка пары по данным app/ (как в приложении): python3 ix_check.py app 'варфарин|внутрь' 'амиодарон|внутрь'"""
import json, sys
app = sys.argv[1]
ix = json.load(open(app + '/ix.json', encoding='utf-8')); s = json.load(open(app + '/search.json', encoding='utf-8'))
cls = dict(ix['classes'])
def find(q):
    name, route = q.split('|')
    for r in s['rows']:
        if r[1].lower().startswith(name) and r[3] == route and r[6] >= 0:
            return s['docs'][r[6]][0], r[1]
def paras(d):
    doc = json.load(open(f'{app}/doc/{d}.json', encoding='utf-8'))
    for n, t, b in doc['s']:
        if n == '4.5': return [p.strip() for p in b.split('\n') if len(p.strip()) > 2]
    return []
def label(k): return k[2:] if k.startswith('i:') else cls[k[2:]]
(a, na), (b, nb) = find(sys.argv[2]), find(sys.argv[3])
for x, nx, y, ny in ((a, na, b, nb), (b, nb, a, na)):
    hits = {k: v for k, v in ix['men'].get(x, {}).items() if k in ix['own'][y]}
    ps = paras(x)
    print(f'== В инструкции «{nx}» о «{ny}»: {", ".join(label(k) for k in hits) or "нет упоминаний"}')
    for i in sorted({i for v in hits.values() for i in v})[:4]:
        print('   ¶', ps[i][:230])
