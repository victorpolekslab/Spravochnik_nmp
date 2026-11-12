"""Сводит документы из ГРЛС: найденные по номеру РУ (found.jsonl) и замены листков-вкладышей (upgrade*.jsonl).

python3 grls_combine.py grls_out/found.jsonl grls_out/upgrade2.jsonl dest/found.jsonl
"""
import json, sys
found_p, up_p, dest = sys.argv[1:4]
ST = {'Д': 'действующее', 'ПП': 'действующее', 'ЕАЭС': 'национальное РУ, переоформленное по правилам ЕАЭС',
      'ИЗМ': 'прежняя редакция', 'ИСКЛ': 'исключено из реестра', 'ИСТ': 'срок действия истёк'}
F = {}
for l in open(found_p, encoding='utf-8'):
    x = json.loads(l); F[(x['inn'], x['route'])] = x
U = {}
for l in open(up_p, encoding='utf-8'):
    x = json.loads(l)
    if x.get('pdf'):
        U[(x['inn'], x['route'])] = x
keys = ('guid', 'ru', 'tn', 'form', 'date', 'url', 'pdf')
out = []
for k in sorted(set(F) | set(U)):
    x, u = F.get(k, {'inn': k[0], 'route': k[1], 'atc': ''}), U.get(k)
    if u:
        r = {'atc': '', **x, **{kk: u[kk] for kk in keys}}
        st = u.get('status', '')
        if st not in ('Д', 'ПП'):
            r['note'] = (f'Инструкция к другому РУ того же препарата: {u["ru"]} ({ST.get(st, st)}, '
                         f'решение от {u.get("decision") or "—"}). Текст может быть старше действующего')
        elif u.get('by_tn'):
            r['note'] = f'Инструкция найдена по торговому наименованию: {u["tn"]}, РУ {u["ru"]}'
        out.append(r)
    elif x.get('pdf'):
        out.append(x)
open(dest, 'w', encoding='utf-8').writelines(json.dumps(x, ensure_ascii=False) + '\n' for x in out)
print(len(out), 'документов; заменено', len(U))
