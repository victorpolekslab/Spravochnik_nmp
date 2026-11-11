#!/usr/bin/env python3
"""Забрать КР, которые телефон организатора передал через Google-скрипт (экран «Новое в КР» → «Скачать и передать»).

  python3 tools/kr_pull.py [--key READ_KEY]      ключ — из learn_private/org.json (readKey), если не указан

Файлы: тексты → /home/claude/cr/json/<id>.json.gz (кэш для build_db.py и kr_export.py),
исходный список рубрикатора → /home/claude/cr/raw/list_phone.json.gz (+ разбор в raw/list_phone.json).
Дальше: сверить список, обновить raw/list.json, пересобрать базу (build_db.py), выпустить APK и обновить ветку kr.
"""
import base64, gzip, json, os, re, sys, urllib.request

BASE = '/home/claude/cr'
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
learn = json.load(open(os.path.join(ROOT, 'learn/learn.json'), encoding='utf-8'))
URL = learn['report']
key = sys.argv[sys.argv.index('--key') + 1] if '--key' in sys.argv else json.load(open(os.path.join(BASE, 'learn_private/org.json')))['readKey']


def get(**q):
    u = URL + '?' + '&'.join(f'{k}={urllib.parse.quote(str(v))}' for k, v in dict(key=key, **q).items())
    with urllib.request.urlopen(u, timeout=300) as r:
        d = json.loads(r.read().decode('utf-8'))
    if not d.get('ok'): sys.exit(f'скрипт ответил: {d}')
    return d


import urllib.parse
r = get(op='kr_list')
if 'files' not in r: sys.exit('Скрипт ещё старый: замените код (tools/google_results.gs) и разверните новую версию')
files = r['files']
print('в папке на Диске:', len(files))
for f in sorted(files, key=lambda x: x['name']):
    data = gzip.decompress(base64.b64decode(get(op='kr_get', name=f['name'])['data']))
    if f['name'] == 'list.json.gz':
        open(os.path.join(BASE, 'raw/list_phone.json.gz'), 'wb').write(gzip.compress(data))
        d = json.loads(data.decode('utf-8'))
        print(f'  список ({f.get("src")}): {len(data) // 1024} КБ, тип {type(d).__name__}', f'{len(d)} элементов' if isinstance(d, list) else list(d)[:5])
        json.dump(d, open(os.path.join(BASE, 'raw/list_phone.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        continue
    cid = f['name'].split('.')[0]
    d = json.loads(data.decode('utf-8'))
    secs = (d.get('obj') or {}).get('sections') or []
    if not secs: print('  ', cid, 'НЕТ РАЗДЕЛОВ — пропущен'); continue
    open(os.path.join(BASE, 'json', cid + '.json.gz'), 'wb').write(gzip.compress(data))
    print(f'  {cid}: {d.get("name", "")[:70]} — {len(secs)} разделов, {len(data) // 1024} КБ ({f["at"][:10]})')
