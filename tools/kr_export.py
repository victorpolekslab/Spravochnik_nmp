#!/usr/bin/env python3
"""Выгрузка действующих КР в Markdown для чата-редакции курсов (ветка `kr` репозитория).

  python3 tools/kr_export.py <папка_json_cache> <папка_вывода>

Источник — кэш JSON рубрикатора cr.minzdrav.gov.ru (<id>.json.gz), список действующих — таблица cr в cr.db.
Результат: <вывод>/kr/<id>.md (одна КР), <вывод>/INDEX.md и index.json (оглавление: id, название, возраст, год, МКБ).
Пропускаются: исходный документ целиком (дубль), титульный лист, состав рабочей группы, список литературы.
"""
import gzip, json, os, re, sqlite3, sys
from bs4 import BeautifulSoup, NavigableString, Comment

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB = os.environ.get('KR_DB') or ('/home/claude/cr/build/cr.db' if os.path.exists('/home/claude/cr/build/cr.db') else os.path.join(ROOT, 'android/app/src/main/assets/cr.db'))
SKIP = {'doc_whole', 'doc_title', 'doc_a1', 'doc_bible'}
AGE = {1: 'взрослые', 2: 'дети', 3: 'взрослые и дети'}


def txt(el):
    """Строчный текст элемента с **жирным**, без переносов."""
    out = []
    for c in el.children:
        if isinstance(c, Comment): continue
        if isinstance(c, NavigableString): out.append(str(c)); continue
        n = c.name.lower()
        if n in ('script', 'style'): continue
        if n == 'br': out.append(' '); continue
        if n == 'img': out.append('[рисунок]'); continue
        s = txt(c)
        if n in ('b', 'strong') and s.strip(): s = f'**{s.strip()}** '
        if n == 'sup': s = '^' + s
        out.append(s)
    return re.sub(r'\s+', ' ', ''.join(out).replace('\xa0', ' '))


def table(t):
    rows, spans = [], {}
    for tr in t.find_all('tr'):
        if tr.find_parent('table') is not t: continue
        row, col = [], 0
        cells = [c for c in tr.find_all(['td', 'th']) if c.find_parent('tr') is tr]
        for c in cells:
            while spans.get(col):
                row.append(spans[col][1]); spans[col] = (spans[col][0] - 1, spans[col][1]) if spans[col][0] > 1 else None; col += 1
            s = txt(c).strip().replace('|', '/')
            cs = int(c.get('colspan', 1)) if str(c.get('colspan', 1)).isdigit() else 1
            rs = int(c.get('rowspan', 1)) if str(c.get('rowspan', 1)).isdigit() else 1
            for k in range(cs):
                row.append(s if k == 0 else '')
                if rs > 1: spans[col] = (rs - 1, '〃')
                col += 1
        while spans.get(col):
            row.append(spans[col][1]); spans[col] = (spans[col][0] - 1, spans[col][1]) if spans[col][0] > 1 else None; col += 1
        if any(x.strip() for x in row): rows.append(row)
    if not rows: return ''
    w = max(len(r) for r in rows)
    rows = [r + [''] * (w - len(r)) for r in rows]
    if w == 1: return '\n'.join(r[0] for r in rows)
    return '\n'.join(['| ' + ' | '.join(rows[0]) + ' |', '|' + '---|' * w] + ['| ' + ' | '.join(r) + ' |' for r in rows[1:]])


def block(el, out):
    for c in el.children:
        if isinstance(c, Comment): continue
        if isinstance(c, NavigableString):
            s = re.sub(r'\s+', ' ', str(c)).strip()
            if s: out.append(s)
            continue
        n = c.name.lower()
        if n in ('script', 'style', 'head'): continue
        if n == 'table': out.append(table(c)); continue
        if n in ('ul', 'ol'):
            for i, li in enumerate([x for x in c.find_all('li') if x.find_parent(['ul', 'ol']) is c], 1):
                s = txt(li).strip()
                if s: out.append(('- ' if n == 'ul' else f'{i}. ') + s)
            continue
        if c.find(['table', 'ul', 'ol', 'p', 'div']) is not None:
            block(c, out); continue
        s = txt(c).strip()
        if s: out.append(s)


def md(html):
    if not html or not html.strip(): return ''
    soup = BeautifulSoup(html, 'lxml')
    out = []; block(soup.body or soup, out); prev_lst = None
    s = ''
    for x in (x for x in out if x):   # пункты списка — без пустых строк между ними
        lst = re.match(r'(- |\d+\. )', x)
        s += ('\n' if lst and prev_lst else '\n\n') + x if s else x
        prev_lst = lst
    s = re.sub(r'\*\*\s*\*\*', '', s)
    return re.sub(r'\n{3,}', '\n\n', s).strip()


def main():
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.join(dst, 'kr'), exist_ok=True)
    db = sqlite3.connect(DB)
    built = db.execute("SELECT v FROM meta WHERE k='built'").fetchone()[0]
    items, total = [], 0
    for cid, code, ver, name, age, ass, pub, mkb in db.execute('SELECT id, code, version, name, age, ass, pub, mkb FROM cr ORDER BY code, version'):
        p = os.path.join(src, cid + '.json.gz')
        if not os.path.exists(p): print('нет текста', cid); continue
        d = json.load(gzip.open(p))
        head = [f'# {name.strip()}', '',
                f'КР{cid} · ID {cid} на cr.minzdrav.gov.ru · {AGE.get(age, "")} · опубликованы {pub or "?"} · МКБ-10: {mkb}',
                f'Разработчики: {(ass or "").strip()}', f'Источник: https://cr.minzdrav.gov.ru/preview-cr/{cid}', '']
        body = []
        for s in d['obj']['sections']:
            if s.get('id') in SKIP: continue
            t = md(s.get('content'))
            if not t: continue
            title = (s.get('title') or '').strip()
            body.append(('### ' if re.match(r'^\d+\.\d+', title) else '## ') + title + '\n\n' + t)
        text = '\n'.join(head) + '\n' + '\n\n'.join(body) + '\n'
        # GitHub API отдаёт содержимое файла целиком только до 1 МБ — длинные КР режем по разделам
        parts, cur = [], '\n'.join(head) + '\n'
        for b in body:
            if len((cur + b).encode()) > 850_000 and len(cur.encode()) > 2000: parts.append(cur); cur = f'# {name.strip()} (продолжение)\n\n'
            cur += '\n\n' + b
        parts.append(cur + '\n')
        for k, t in enumerate(parts, 1):
            nxt = f'\n\n(Продолжение: kr/{cid}_part{k + 1}.md)\n' if k < len(parts) else ''
            open(os.path.join(dst, 'kr', cid + ('.md' if k == 1 else f'_part{k}.md')), 'w', encoding='utf-8').write(t + nxt)
        total += len(text.encode())
        items.append({'id': cid, 'name': name.strip(), 'age': AGE.get(age, ''), 'pub': (pub or '')[:10], 'mkb': mkb, 'kb': round(len(text.encode()) / 1024)})
    json.dump(items, open(os.path.join(dst, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    lines = ['# Действующие клинические рекомендации Минздрава России', '',
             f'{len(items)} КР, тексты в папке `kr/<ID>.md` (самые длинные продолжаются в `kr/<ID>_part2.md`). Выгружено из рубрикатора cr.minzdrav.gov.ru для «Справочника НМП», база от {built}.', '',
             '| ID | Название | Возраст | Опубликованы | МКБ-10 | КБ |', '|---|---|---|---|---|---|']
    lines += [f'| {x["id"]} | {x["name"].replace("|", "/")} | {x["age"]} | {x["pub"]} | {x["mkb"]} | {x["kb"]} |' for x in sorted(items, key=lambda x: x['name'])]
    open(os.path.join(dst, 'INDEX.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(len(items), 'КР;', round(total / 1e6, 1), 'МБ')


if __name__ == '__main__':
    main()
