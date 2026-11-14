#!/usr/bin/env python3
"""Помощник выписки рецептов — перенос из «Справочника терапевта».

    python3 tools/rx/import_rx.py [путь к клону Spravochnik_terapevt]

Без аргумента скачивает файлы из ветки main репозитория victorpolekslab/Spravochnik_terapevt.
Собирает www/content_rx.js = window.RX (data/rx/rules.json + lat из data/rx/latin.json) + web/rx.js и обновляет
блок стилей .rx*/.rb* в www/app.css между метками /* rx:begin */ … /* rx:end */.
Нормы правятся только в rules.json терапевта, затем этот скрипт запускается снова.
"""
import json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WWW = os.path.join(ROOT, 'android/app/src/main/assets/www')
RAW = 'https://raw.githubusercontent.com/victorpolekslab/Spravochnik_terapevt/main/'


def get(rel):
    if len(sys.argv) > 1:
        return open(os.path.join(sys.argv[1], rel), encoding='utf-8').read()
    return urllib.request.urlopen(RAW + rel, timeout=60).read().decode('utf-8')


rules = json.loads(get('data/rx/rules.json'))
rules['lat'] = json.loads(get('data/rx/latin.json'))   # МНН на латыни в родительном падеже для строки Rp.
rx = get('web/rx.js')
css = get('web/app.css')
start = css.index('/* помощник выписки рецептов */')
block = css[start:].rstrip() + '\n'

js = ('/* Помощник выписки рецептов — перенесён из «Справочника терапевта» (tools/rx/import_rx.py, не править вручную).\n'
      '   Нормы сверены ' + rules.get('checked', '') + '. */\n'
      'window.RX = ' + json.dumps(rules, ensure_ascii=False, separators=(',', ':')) + ';\n' + rx)
open(os.path.join(WWW, 'content_rx.js'), 'w', encoding='utf-8').write(js)

p = os.path.join(WWW, 'app.css')
a = open(p, encoding='utf-8').read()
a = re.sub(r'\n?/\* rx:begin.*?/\* rx:end \*/\n?', '\n', a, flags=re.S).rstrip() + '\n'
a += '/* rx:begin — из «Справочника терапевта», обновляется tools/rx/import_rx.py */\n' + block + '/* rx:end */\n'
open(p, 'w', encoding='utf-8').write(a)
print('content_rx.js', len(js) // 1024, 'KB; стили', block.count('\n'), 'строк; нормы от', rules.get('checked'))
