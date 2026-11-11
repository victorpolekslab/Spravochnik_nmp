#!/usr/bin/env python3
"""Импорт учебного курса из course.json (формат — docs/COURSE_FORMAT.md) в приложение.

  python3 tools/course/import_course.py fetch <id>            взять courses/<id>/course.json из ветки origin/courses
  python3 tools/course/import_course.py check <id|путь>       только проверка
  python3 tools/course/import_course.py preview <id> [папка]  проверка + слайды без озвучки + обзорный лист contact.jpg
  python3 tools/course/import_course.py build <id>            слайды + озвучка в media/<id>/, content_courses.js, лента learn.json
  python3 tools/course/import_course.py gen                   только пересобрать content_courses.js из courses/*/course.json
После build: проверить, затем tools/release_content.sh "Курс: …" (и закоммитить media/, courses/, learn/).

Озвучка: Vosk TTS ru 0.9 multi, голос 3 (как у лекции по ГБН). Путь к модели — переменная VOSK_MODEL.
Файлы озвучки версионируются (lecture_v<N>.mp3), картинки слайдов грузятся с ?v=<N>, поэтому повторный
импорт не смешивается с кэшем WebView/CDN.
"""
import html, json, os, re, shutil, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WWW = os.path.join(ROOT, 'android/app/src/main/assets/www')
COURSES = os.path.join(ROOT, 'courses')
MEDIA = os.path.join(ROOT, 'media')
LEARN = os.path.join(ROOT, 'learn/learn.json')
GEN = os.path.join(WWW, 'content_courses.js')
VOSK = os.environ.get('VOSK_MODEL', '/home/claude/cr/tts/vosk/vosk-model-tts-ru-0.9-multi')
SPEAKER = 3
RESERVED = {'gbn'}   # курсы, написанные вручную в content_course.js

BLOCKS = {'targets': ['h', 'items'], 'exam': ['h', 'items'], 'flags': ['h', 'items'], 'warn': ['h', 'items'],
          'steps': ['h', 'items'], 'scheme': ['h', 'items'], 'table': ['h', 'cols', 'rows'], 'rx': ['h', 'rows'],
          'note': ['text'], 'fold': ['h', 'items'], 'img': ['img']}
LAYOUTS = {'title': ['h'], 'points': ['h', 'items'], 'big': ['value', 'text'], 'compare': ['h', 'left', 'right'],
           'table': ['h', 'cols', 'rows'], 'flags': ['h', 'items'], 'case': ['kicker', 'h', 'facts'],
           'answer': ['kicker', 'h', 'items', 'verdict'], 'meme': ['left', 'right'], 'end': ['h', 'items'], 'image': ['h', 'img']}
IMG_EXT = ('.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif')
imgs_of = lambda v: [v] if isinstance(v, str) else list(v or [])
LIMITS = {'points': ('items', 6), 'big': ('items', 3), 'table': ('rows', 7), 'flags': ('items', 14), 'case': ('facts', 6),
          'answer': ('items', 5), 'end': ('items', 5)}


# ------------------------------------------------------------------ загрузка и проверка
def path_of(arg):
    if arg.endswith('.json') or os.sep in arg:
        return arg
    return os.path.join(COURSES, arg, 'course.json')


def load(arg):
    IMG_BASE[0] = os.path.dirname(os.path.abspath(path_of(arg)))
    with open(path_of(arg), encoding='utf-8') as f:
        return json.load(f)


def words(t):
    return len(re.findall(r'\w+', t or ''))


def check(c, base=None):
    E, W = [], []
    base = base or os.path.join(COURSES, c.get('id', ''))

    def img_ok(rel, where):
        rel = str(rel or '')
        if not re.fullmatch(r'img/[\w.-]+', rel) or not rel.lower().endswith(IMG_EXT): E.append(f'{where}: картинка «{rel}» — нужен путь img/<файл>.svg|png|jpg|webp'); return
        f = os.path.join(base, rel)
        if not os.path.exists(f): E.append(f'{where}: нет файла {rel} в папке курса'); return
        lim = 3_000_000 if rel.lower().endswith('.gif') else 1_500_000
        if os.path.getsize(f) > lim: E.append(f'{where}: {rel} больше {lim / 1e6:g} МБ')
        if rel.lower().endswith('.svg'):
            t = open(f, encoding='utf-8', errors='replace').read()
            if re.search(r'<script|<foreignObject|\bon\w+\s*=|(xlink:)?href\s*=\s*["\'](https?:|//|data:text)', t, re.I): E.append(f'{where}: в {rel} скрипты или внешние ссылки — недопустимо')
    req = lambda o, keys, where: [E.append(f'{where}: нет поля «{k}»') for k in keys if not o.get(k) and o.get(k) != 0]
    if c.get('format') != 1: E.append('format должен быть 1')
    cid = c.get('id', '')
    if not re.fullmatch(r'[a-z0-9_]{2,24}', cid): E.append('id: только латиница, цифры, _; 2–24 символа')
    if cid in RESERVED: E.append(f'id «{cid}» занят курсом, написанным вручную')
    if c.get('status') not in ('draft', 'ready'): E.append('status: draft или ready')
    req(c, ['title', 'sub', 'srcName', 'feed'], 'курс')
    if c.get('src') and not re.fullmatch(r'КР\d+_\d+', c['src']): W.append(f'src «{c["src"]}» не похож на КР<ID>, например КР162_3')
    if not c.get('course') and not c.get('lecture'): E.append('нужна хотя бы одна часть: course или lecture')
    feed = c.get('feed') or {}

    def quiz(qs, where, lo, hi):
        if not isinstance(qs, list) or not (lo <= len(qs) <= hi): E.append(f'{where}: нужно {lo}–{hi} вопросов'); return
        pos = []
        for i, q in enumerate(qs, 1):
            req(q, ['q', 'o', 'e'], f'{where}, вопрос {i}')
            o = q.get('o') or []
            if not (3 <= len(o) <= 4): E.append(f'{where}, вопрос {i}: нужно 3–4 варианта')
            if not isinstance(q.get('a'), int) or not (0 <= q['a'] < len(o)): E.append(f'{where}, вопрос {i}: a — номер верного варианта с нуля')
            else: pos.append(q['a'])
        if len(pos) >= 4 and len(set(pos)) == 1: W.append(f'{where}: верный ответ везде на одном месте')

    def src_ok(o, where):
        if o.get('src') and not re.fullmatch(r'КР\d+_\d+', str(o['src'])): W.append(f'{where}: src «{o["src"]}» не в виде КР<ID>')

    if c.get('course'):
        co = c['course']
        if not feed.get('course'): E.append('feed.course: нет текста для ленты')
        cards = co.get('cards') or []
        if not (5 <= len(cards) <= 24): E.append('course.cards: нужно 8–20 карточек')
        for i, cd in enumerate(cards, 1):
            req(cd, ['h', 'blocks'], f'карточка {i}')
            for j, b in enumerate(cd.get('blocks') or [], 1):
                w = f'карточка {i}, блок {j}'
                t = b.get('t')
                if t not in BLOCKS: E.append(f'{w}: неизвестный тип «{t}»'); continue
                req(b, BLOCKS[t], f'{w} ({t})')
                src_ok(b, w)
                if t == 'img': img_ok(b.get('img'), w)
                if t == 'steps' and any(not isinstance(x, dict) or 's' not in x for x in b.get('items') or []): E.append(f'{w}: в steps элементы {{s, note?}}')
                if t == 'scheme' and any(not isinstance(x, dict) or 's' not in x or 'text' not in x for x in b.get('items') or []): E.append(f'{w}: в scheme элементы {{s, text}}')
                if t == 'table':
                    n = len(b.get('cols') or [])
                    if any(len(r) != n for r in b.get('rows') or []): E.append(f'{w}: в каждой строке таблицы {n} ячеек')
                if t == 'rx':
                    for r in b.get('rows') or []:
                        for x in (r.get('opts') or []) if r.get('one') else [r]:
                            if not x.get('n') or not x.get('d'): E.append(f'{w}: у препарата нужны n и d')
                            src_ok(x, w)
        quiz(co.get('quiz'), 'course.quiz', 3, 10)

    if c.get('lecture'):
        le = c['lecture']
        if not feed.get('lecture'): E.append('feed.lecture: нет текста для ленты')
        sl = le.get('slides') or []
        if not (3 <= len(sl) <= 20): E.append('lecture.slides: нужно 8–16 слайдов')
        total = 0
        for i, s in enumerate(sl, 1):
            w = f'слайд {i}'
            lay = s.get('layout')
            if lay not in LAYOUTS: E.append(f'{w}: неизвестный макет «{lay}»'); continue
            req(s, LAYOUTS[lay] + ['say'], f'{w} ({lay})')
            if not s.get('h'): W.append(f'{w}: нет h — в списке слайдов будет пусто')
            if s.get('img'):
                if len(imgs_of(s['img'])) > 2: E.append(f'{w}: не больше двух картинок на слайде')
                for im in imgs_of(s['img']): img_ok(im, w)
                if lay in ('title', 'meme'): E.append(f'{w}: на макете {lay} картинка не ставится')
                if s.get('imgMode', 'side') not in ('side', 'full'): E.append(f'{w}: imgMode — side или full')
            if lay in LIMITS:
                k, n = LIMITS[lay]
                if len(s.get(k) or []) > n: E.append(f'{w}: в «{k}» не больше {n}')
            say = s.get('say') or ''
            n = words(say); total += n
            if n < 15 or n > 170: W.append(f'{w}: в озвучке {n} слов (норма 40–130)')
            bad = sorted(set(re.findall(r'[0-9%≥≤<>±×/+=]|[A-Za-z]+', say)))
            if bad: W.append(f'{w}: в озвучке есть «{" ".join(bad[:8])}» — синтез прочитает плохо; числа и знаки пишите словами')
            ab = sorted(a for a in set(re.findall(r'\b[А-ЯЁ]{2,}\b', say)) - set(SAY_FIX) if not vosk_knows(a))
            if ab: W.append(f'{w}: сокращения «{" ".join(ab[:6])}» — проверьте на слух или напишите полностью')
        if sl and not (450 <= total <= 1400): W.append(f'лекция: {total} слов ≈ {total / 125:.1f} мин (норма 5–10 мин)')
        quiz(le.get('quiz'), 'lecture.quiz', 3, 8)
    return E, W


def report(c, E, W):
    print(f'Курс «{c.get("title")}» ({c.get("id")}, {c.get("status")})')
    if c.get('course'): print(f'  карточек: {len(c["course"].get("cards") or [])}, вопросов: {len(c["course"].get("quiz") or [])}')
    if c.get('lecture'):
        sl = c['lecture'].get('slides') or []
        n = sum(words(s.get('say')) for s in sl)
        print(f'  слайдов: {len(sl)}, слов озвучки: {n} (≈ {n / 125:.1f} мин), вопросов: {len(c["lecture"].get("quiz") or [])}')
    for e in E: print('  ОШИБКА:', e)
    for w in W: print('  внимание:', w)
    if not E: print('  формат в порядке')


# ------------------------------------------------------------------ слайды
def md(t):
    t = html.escape(str(t or ''), quote=False)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    return re.sub(r'==(.+?)==', r'<span class="r">\1</span>', t)


ul = lambda items, cls='': f'<ul class="{cls}">' + ''.join(f'<li>{md(i)}</li>' for i in items or []) + '</ul>'
WARN_SVG = '<svg viewBox="0 0 24 24"><path d="M12 3l10 18H2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M12 10v5M12 18v.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'

CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{background:#000}
section{width:1600px;height:900px;position:relative;overflow:hidden;background:#f6f3ee;color:#1f2430;font-family:'PT Sans',sans-serif}
.in{position:absolute;left:107px;right:107px;top:88px;bottom:96px;display:flex;flex-direction:column;font-size:var(--f,40px)}
h1,h2,h3,.big,.kick,.q,.verdict,.punch,.quote{font-family:Rubik,sans-serif}
h1{font-size:2.6em;font-weight:800;line-height:1.05}
h2{font-size:2.15em;font-weight:800;line-height:1.1;margin-bottom:.9em}
h3{font-size:1.15em;font-weight:700;margin-bottom:.7em}
.kick{font-size:.8em;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:1.1em;color:#1f2430}
.r{color:#b83a35}
ul{list-style:none}
ul li{position:relative;padding-left:1.1em;margin:0 0 .55em;line-height:1.3}
ul li:before{content:'';position:absolute;left:0;top:.5em;width:.36em;height:.36em;background:#e8a33d;border-radius:2px}
.src{position:absolute;left:107px;right:107px;bottom:42px;font-size:20px;color:#7a7f8a}
.note{margin-top:auto;padding:.7em 1em;background:#fff;border-left:6px solid #e8a33d;border-radius:8px;font-size:.85em;line-height:1.35}
/* title */
.title{background:#1f2430;color:#fff}.title .kick{color:#e8a33d}.title .sub{font-size:1.3em;color:#c9ccd3;margin-top:.8em;line-height:1.3}
.title .in{justify-content:center}.title .bar{width:120px;height:10px;background:#e8a33d;border-radius:5px;margin-bottom:1.4em}
/* big */
.bigs .in{justify-content:center}.big{font-size:5em;font-weight:800;line-height:1;color:#b83a35;margin-bottom:.25em}
.bigs .text{font-size:1.55em;font-weight:700;line-height:1.25;max-width:24em;margin-bottom:.9em}
/* compare, meme */
.two{display:flex;gap:34px;flex:1;min-height:0}
.card{flex:1;border-radius:22px;padding:1.4em 1.5em;display:flex;flex-direction:column;background:#fff}
.card.dark{background:#1f2430;color:#fff}.card.dark h3{color:#e8a33d}.card.lite h3{color:#b83a35}
.meme{background:#e8a33d}.meme .quote{font-size:2.1em;font-weight:800;line-height:1.12;margin:auto 0}
.meme .foot{font-size:.85em;color:#c9ccd3}.punch{font-size:1.3em;font-weight:800;line-height:1.2;margin-top:auto}
.meme .card.lite ul{margin:auto 0}
/* table */
table{border-collapse:collapse;width:100%;font-size:.8em;line-height:1.3}
th{background:#1f2430;color:#fff;text-align:left;padding:.55em .7em;font-weight:700}
td{padding:.55em .7em;border-bottom:1px solid rgba(30,36,48,.15);vertical-align:top;background:#fdfcfa}
tr:nth-child(even) td{background:#f6f3ee}td:first-child{font-weight:700;width:28%}tr.red td:first-child{color:#b83a35}
/* flags */
.flagh{display:flex;align-items:center;gap:.4em;color:#b83a35}.flagh svg{width:1.1em;height:1.1em;flex:none}
.cols{columns:2;column-gap:56px}.cols li{break-inside:avoid}.flg li:before{background:#b83a35;border-radius:50%}
/* case, answer */
.case{background:#1f2430;color:#fff}.case .kick{color:#e8a33d}.case ul li:before{background:#e8a33d}
.q{margin-top:auto;font-size:1.25em;font-weight:700;color:#e8a33d;line-height:1.25}
.verdict{margin-top:auto;background:#1f2430;color:#fff;border-radius:16px;padding:.8em 1em;font-size:1.15em;font-weight:700;line-height:1.3}
.ans .kick{color:#b83a35}
/* картинка */
.pic{display:flex;align-items:center;justify-content:center;min-width:0;min-height:0;overflow:hidden}
.pic img{max-width:100%;max-height:100%;border-radius:18px;box-shadow:0 6px 24px rgba(31,36,48,.18);background:#fff}
.side .in{flex-direction:row;gap:44px;align-items:stretch}.side .txt{flex:0 0 38%;display:flex;flex-direction:column;min-width:0;min-height:0}
.side .pic{flex:1}.side h2{font-size:1.75em}
.pics{flex:1;display:flex;gap:24px;min-height:0}.pics.col{flex-direction:column}.pics .pic{flex:1}
.side2 .lcol{flex:1;display:flex;flex-direction:column;gap:22px;min-width:0;min-height:0}.side2 .lcol .txt{flex:0 0 auto}
.side2 .lcol .pic{flex:1 1 0;min-height:46%}.side .big{font-size:3.6em;white-space:nowrap}.side2 .pic.port{flex:0 0 auto;height:100%}
.full .in{top:44px;bottom:58px;left:80px;right:80px}.full .pic{flex:1;margin:.35em 0 .35em}
.fh{font-family:Rubik,sans-serif;font-size:42px;font-weight:800;line-height:1.1;display:flex;align-items:baseline;gap:.6em;flex-wrap:wrap}
.fh .kick{font-size:20px;margin:0;color:#b83a35}.case .fh .kick,.title .fh .kick{color:#e8a33d}.full .cap{font-size:24px}.full .src{bottom:16px;left:80px;font-size:18px}
.cap{font-size:.8em;line-height:1.3;color:#5d6270}.case .cap,.title .cap{color:#c9ccd3}
/* end */
ol.nums{list-style:none;counter-reset:n}
ol.nums li{counter-increment:n;position:relative;padding-left:2.3em;margin-bottom:.8em;line-height:1.3;font-size:1.1em;min-height:1.6em}
ol.nums li:before{content:counter(n);position:absolute;left:0;top:-.1em;width:1.6em;height:1.6em;border-radius:50%;background:#e8a33d;color:#1f2430;font-family:Rubik;font-weight:800;display:flex;align-items:center;justify-content:center}
"""
FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rubik:wght@600;700;800&family=PT+Sans:wght@400;700&display=block">'


def slide_html(s):
    L = s['layout']
    k = f'<div class="kick">{md(s["kicker"])}</div>' if s.get('kicker') else ''
    note = f'<div class="note">{md(s["note"])}</div>' if s.get('note') else ''
    cls, body = L, ''
    if L == 'title':
        body = f'<div class="bar"></div>{k}<h1>{md(s["h"])}</h1>' + (f'<div class="sub">{md(s["sub"])}</div>' if s.get('sub') else '')
    elif L == 'points':
        body = f'{k}<h2>{md(s["h"])}</h2>{ul(s["items"])}{note}'
    elif L == 'big':
        cls = 'bigs'; body = f'{k}<div class="big">{md(s["value"])}</div><div class="text">{md(s["text"])}</div>{ul(s.get("items"))}'
    elif L == 'compare':
        a, b = s['left'], s['right']
        body = f'{k}<h2>{md(s["h"])}</h2><div class="two"><div class="card dark"><h3>{md(a.get("h"))}</h3>{ul(a.get("items"))}</div><div class="card lite"><h3>{md(b.get("h"))}</h3>{ul(b.get("items"))}</div></div>{note}'
    elif L == 'table':
        rows = ''.join(f'<tr class="{"red" if str(r[0]).startswith("!") else ""}">' + ''.join(f'<td>{md(str(x).lstrip("!") if j == 0 else x)}</td>' for j, x in enumerate(r)) + '</tr>' for r in s['rows'])
        body = f'{k}<h2>{md(s["h"])}</h2><table><tr>' + ''.join(f'<th>{md(x)}</th>' for x in s['cols']) + f'</tr>{rows}</table>{note}'
    elif L == 'flags':
        body = f'{k}<h2 class="flagh">{WARN_SVG}{md(s["h"])}</h2>{ul(s["items"], "cols flg" if len(s["items"]) > 5 else "flg")}{note}'
    elif L == 'case':
        body = f'{k}<h2>{md(s["h"])}</h2>{ul(s["facts"])}' + (f'<div class="q">{md(s["question"])}</div>' if s.get('question') else '')
    elif L == 'answer':
        cls = 'ans'; body = f'{k}<h2>{md(s["h"])}</h2>{ul(s["items"])}<div class="verdict">{md(s["verdict"])}</div>'
    elif L == 'meme':
        a, b = s['left'], s['right']
        k = f'<div class="kick">{md(s.get("kicker") or "Мем, чтобы запомнить")}</div>'
        body = (f'{k}<div class="two"><div class="card dark"><h3>{md(a.get("h"))}</h3><div class="quote">{md(a.get("quote"))}</div>'
                + (f'<div class="foot">{md(a["foot"])}</div>' if a.get('foot') else '')
                + f'</div><div class="card lite"><h3>{md(b.get("h"))}</h3>{ul(b.get("items"))}<div class="punch">{md(b.get("punch"))}</div></div></div>')
    elif L == 'end':
        body = f'{k}<h2>{md(s["h"])}</h2><ol class="nums">' + ''.join(f'<li>{md(i)}</li>' for i in s['items']) + f'</ol>{note}'
    src = f'<div class="src">{md(s["src"])}</div>' if s.get('src') else ''
    if L == 'image':
        cls, body = 'image full', f'{k}<h2>{md(s["h"])}</h2>'
    ims = imgs_of(s.get('img'))
    if ims:
        tag = lambda rel, extra='': f'<img src="{img_uri(rel)}"' + (f' data-anim="{rel}"' if rel.lower().endswith('.gif') else '') + f'{extra}>'
        mode = 'full' if L in ('image', 'compare') else s.get('imgMode', 'side')
        if mode == 'full':
            cap = s.get('caption') or s.get('verdict') or s.get('question') or s.get('note') or ''
            head = '<div class="fh">' + (f'<span class="kick">{md(s["kicker"])}</span>' if s.get('kicker') else '') + f'<b>{md(s.get("h", ""))}</b></div>'
            body = f'{head}<div class="pics">' + ''.join(f'<div class="pic">{tag(r)}</div>' for r in ims) + '</div>' + (f'<div class="cap">{md(cap)}</div>' if cap else '')
            cls = cls.replace(' full', '') + ' full'
        elif len(ims) == 2 and img_ratio(ims[1]) < 1 <= img_ratio(ims[0]):
            # текст и горизонтальная схема — слева столбиком, вертикальная (анимация) — справа во всю высоту
            body = f'<div class="lcol"><div class="txt">{body}</div><div class="pic">{tag(ims[0])}</div></div><div class="pic port">{tag(ims[1])}</div>'
            cls += ' side side2'
        else:
            body = f'<div class="txt">{body}</div><div class="pics col">' + ''.join(f'<div class="pic">{tag(r)}</div>' for r in ims) + '</div>'
            cls += ' side'
    return f'<section class="{cls}"><div class="in">{body}</div>{src}</section>'


IMG_BASE = [None]   # папка курса, откуда брать img/…


def img_ratio(rel):
    f = os.path.join(IMG_BASE[0], rel)
    if f.lower().endswith('.svg'):
        t = open(f, encoding='utf-8', errors='replace').read(3000)
        m = re.search(r'viewBox="[\d.\s-]+?\s([\d.]+)\s+([\d.]+)"', t) or re.search(r'width="([\d.]+)[^"]*"\s+height="([\d.]+)', t)
        return float(m.group(1)) / float(m.group(2)) if m else 16 / 9
    from PIL import Image
    w, h = Image.open(f).size
    return w / h


def img_uri(rel):
    import base64, mimetypes, io
    f = os.path.join(IMG_BASE[0], rel)
    if f.lower().endswith('.gif'):   # на слайд — статичный кадр (три четверти цикла), анимацию плеер накладывает сверху
        from PIL import Image
        im = Image.open(f); im.seek(int(getattr(im, 'n_frames', 1) * 0.75)); b = io.BytesIO(); im.convert('RGB').save(b, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
    mt = 'image/svg+xml' if f.lower().endswith('.svg') else (mimetypes.guess_type(f)[0] or 'image/png')
    return f'data:{mt};base64,' + base64.b64encode(open(f, 'rb').read()).decode()


FIT = """() => { const s = document.querySelector('section'), i = s.querySelector('.in');
  i.querySelectorAll('.pic.port').forEach(p => { const im = p.querySelector('img'); p.style.width = (p.clientHeight * im.naturalWidth / im.naturalHeight) + 'px'; });
  let f = 40; i.style.setProperty('--f', f + 'px'); const over = () => i.scrollHeight > i.clientHeight + 2 || [...i.querySelectorAll('.card,.two,.txt,.lcol')].some(e => e.scrollHeight > e.clientHeight + 2);
  while (over() && f > 20) { f -= 1; i.style.setProperty('--f', f + 'px'); }
  i.querySelectorAll('.pic').forEach(p => { const im = p.querySelector('img'), b = p.getBoundingClientRect(), r = (im.naturalWidth || 16) / (im.naturalHeight || 9);
    const w = Math.min(b.width, b.height * r); im.style.width = w + 'px'; im.style.height = (w / r) + 'px'; im.style.maxWidth = 'none'; im.style.maxHeight = 'none'; });
  const S = s.getBoundingClientRect();
  const anim = [...s.querySelectorAll('img[data-anim]')].map(im => { const b = im.getBoundingClientRect();
    return { img: im.dataset.anim, box: [(b.left - S.left) / S.width, (b.top - S.top) / S.height, b.width / S.width, b.height / S.height].map(x => Math.round(x * 10000) / 10000) }; });
  return [f, anim]; }"""


def render(slides, out, prefix='s'):
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    small, anims = [], {}
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1600, 'height': 900})
        for i, s in enumerate(slides, 1):
            pg.set_content(f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{CSS}</style></head><body>{slide_html(s)}</body></html>', wait_until='networkidle')
            pg.evaluate('document.fonts.ready'); pg.wait_for_function('[...document.images].every(i => i.complete)'); f, an = pg.evaluate(FIT)
            if an: anims[str(i)] = an
            if f <= 20: small.append(i)
            png = f'{out}/{prefix}{i:02d}.png'
            pg.locator('section').screenshot(path=png)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', png, '-q:v', '3', f'{out}/{prefix}{i:02d}.jpg'], check=True)
            os.remove(png)
        b.close()
    if small: print('  внимание: на слайдах', small, 'текст пришлось сильно уменьшить — сократите')
    json.dump(anims, open(os.path.join(out, 'anim.json'), 'w'))
    return [f'{out}/{prefix}{i:02d}.jpg' for i in range(1, len(slides) + 1)]


def contact(jpgs, out):
    n = len(jpgs); cols = 4
    args = ['ffmpeg', '-y', '-loglevel', 'error']
    for j in jpgs: args += ['-i', j]
    filt = ''.join(f'[{i}:v]scale=400:225[v{i}];' for i in range(n))
    lay = '|'.join(f'{(i % cols) * 404}_{(i // cols) * 229}' for i in range(n))
    filt += ''.join(f'[v{i}]' for i in range(n)) + f'xstack=inputs={n}:layout={lay}:fill=white[o]' if n > 1 else '[v0]null[o]'
    subprocess.run(args + ['-filter_complex', filt, '-map', '[o]', '-q:v', '3', out], check=True)


# ------------------------------------------------------------------ озвучка
# сокращения, которые словарь Vosk читает неверно (ЭКГ, ЧСС, ИБС, ВИЧ он знает — «экагэ», «чэсэсэ»…)
SAY_FIX = {'ОКС': 'о-ка-эс', 'АД': 'давление'}
_DIC = [None]


def vosk_knows(word):
    if _DIC[0] is None:
        p = os.path.join(VOSK, 'dictionary'); _DIC[0] = set()
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f: _DIC[0] = {l.split(' ', 1)[0] for l in f}
    return word.lower() in _DIC[0]


def clean(t):
    for a, b in SAY_FIX.items(): t = re.sub(rf'\b{a}\b', b, t)
    t = re.sub(r'[«»“”„"()\[\]]', '', t).replace('…', '...').replace('—', ',').replace('–', ',')
    return re.sub(r'\s*,\s*,', ',', re.sub(r'\s+', ' ', t)).strip()


def voice(slides, mp3):
    import wave, numpy as np
    from vosk_tts import Model, Synth
    if not os.path.isdir(VOSK): sys.exit(f'Нет модели озвучки {VOSK}: pip install vosk-tts и скачайте vosk-model-tts-ru-0.9-multi (alphacephei.com/vosk/models)')
    synth = Synth(Model(model_path=VOSK)); SR = 22050
    tmp = mp3 + '.wav'
    def rd(p):
        with wave.open(p) as w: return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    t = np.arange(int(SR * 0.18)) / SR
    chime = (0.18 * np.sin(2 * np.pi * 880 * t) * np.exp(-t * 18)).astype(np.float32)
    gap = lambda s: np.zeros(int(SR * s), dtype=np.float32)
    full, starts, pos = [gap(0.4)], [], 0.4
    for i, s in enumerate(slides):
        synth.synth(clean(s['say']), tmp, speaker_id=SPEAKER); a = rd(tmp); os.remove(tmp)
        if i:
            full += [gap(0.7), chime, gap(0.8)]; starts.append(round(pos + 0.7, 2)); pos += 0.7 + len(chime) / SR + 0.8
        else:
            starts.append(0)
        full.append(a); pos += len(a) / SR
        print(f'  озвучен слайд {i + 1}/{len(slides)}: {len(a) / SR:.1f} с', flush=True)
    full.append(gap(0.8)); audio = np.concatenate(full)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', '-b:a', '96k', mp3],
                   input=(np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes(), check=True)
    return starts, round(len(audio) / SR, 1)


# ------------------------------------------------------------------ встраивание
def lecture_title(t):
    return 'Лекция: ' + (t if re.match(r'^[А-ЯЁA-Z]{2}', t) else t[:1].lower() + t[1:])


def gen():
    out = ['// Сгенерировано tools/course/import_course.py из courses/<id>/course.json — не править вручную.',
           'window.COURSES = window.COURSES || {};', 'window.LECTURES = window.LECTURES || {};']
    for cid in sorted(os.listdir(COURSES)) if os.path.isdir(COURSES) else []:
        p = os.path.join(COURSES, cid, 'course.json')
        if not os.path.exists(p) or cid in RESERVED: continue
        c = json.load(open(p, encoding='utf-8'))
        if c.get('status') != 'ready': continue
        if c.get('course'):
            co = {k: c[k] for k in ('title', 'sub', 'src', 'srcName') if c.get(k)}
            import hashlib
            cards = json.loads(json.dumps(c['course']['cards']))
            for cd in cards:
                for b in cd.get('blocks', []):
                    if b.get('t') == 'img':
                        f = os.path.join(COURSES, cid, b['img'])
                        h = hashlib.sha256(open(f, 'rb').read()).hexdigest()[:10] if os.path.exists(f) else '0'
                        b['img'] = f'media/{cid}/img/{os.path.basename(b["img"])}?v={h}'
            co.update(min=c['course'].get('min', 7), cards=cards, quiz=c['course']['quiz'])
            out.append(f'COURSES[{json.dumps(cid)}] = {json.dumps(co, ensure_ascii=False, indent=1)};')
        import hashlib
        meta_p = os.path.join(MEDIA, cid, 'meta.json')
        if c.get('lecture') and os.path.exists(meta_p):
            le, m = c['lecture'], json.load(open(meta_p, encoding='utf-8'))
            lo = {'title': lecture_title(c['title']), 'sub': le.get('sub') or c['sub'], 'dir': f'media/{cid}/', 'audio': m['audio'],
                  'dur': m['dur'], 'srcName': le.get('srcName') or c['srcName'],
                  'slides': [{'t': t, 'h': s.get('h') or s.get('kicker') or ''} for t, s in zip(m['t'], le['slides'])], 'quiz': le['quiz']}
            if m.get('v', 1) > 1: lo['ver'] = m['v']
            for si, an in (m.get('anim') or {}).items():   # GIF поверх статичного слайда: адрес и рамка в долях слайда
                lo['slides'][int(si) - 1]['anim'] = [{'src': f'media/{cid}/img/{os.path.basename(a["img"])}?v=' + hashlib.sha256(open(os.path.join(COURSES, cid, a['img']), 'rb').read()).hexdigest()[:10], 'box': a['box']} for a in an]
            out.append(f'LECTURES[{json.dumps(cid)}] = {json.dumps(lo, ensure_ascii=False, indent=1)};')
    open(GEN, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    if shutil.which('node'): subprocess.run(['node', '--check', GEN], check=True)
    idx = os.path.join(WWW, 'index.html'); h = open(idx, encoding='utf-8').read()
    if 'content_courses.js' not in h:
        h = h.replace('<script src="content_course.js"></script>', '<script src="content_course.js"></script>\n<script src="content_courses.js"></script>')
        open(idx, 'w', encoding='utf-8').write(h)
    print('  content_courses.js обновлён')


def feed(c):
    d = json.load(open(LEARN, encoding='utf-8'))
    items = d['items']; cid = c['id']; new = []
    if c.get('lecture'):
        new.append({'id': f'lecture-{cid}', 'type': 'lecture', 'lecture': cid, 'title': lecture_title(c['title']), 'text': c['feed']['lecture'], 'new': True})
    if c.get('course'):
        new.append({'id': f'course-{cid}', 'type': 'course', 'course': cid, 'title': 'Курс: ' + c['title'][:1].lower() + c['title'][1:] if not re.match(r'^[А-ЯЁA-Z]{2}', c['title']) else 'Курс: ' + c['title'], 'text': c['feed']['course'], 'new': True})
    ids = {x['id'] for x in new}
    d['items'] = new + [x for x in items if x['id'] not in ids]
    open(LEARN, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1) + '\n')
    print('  лента learn.json:', ', '.join(ids))


def build(arg):
    c = load(arg); E, W = check(c, IMG_BASE[0]); report(c, E, W)
    if E: sys.exit('Исправьте ошибки в course.json')
    if c['status'] != 'ready': sys.exit('status = draft: курс не выпускается')
    cid = c['id']; dst = os.path.join(COURSES, cid, 'course.json')
    if os.path.abspath(path_of(arg)) != os.path.abspath(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(path_of(arg), dst)
        if os.path.isdir(os.path.join(IMG_BASE[0], 'img')):
            shutil.rmtree(os.path.join(COURSES, cid, 'img'), ignore_errors=True)
            shutil.copytree(os.path.join(IMG_BASE[0], 'img'), os.path.join(COURSES, cid, 'img'))
    # картинки карточек — на сайт (media/<id>/img/), имена с версией содержимого против кэша
    used = {b['img'] for cd in (c.get('course') or {}).get('cards', []) for b in cd.get('blocks', []) if b.get('t') == 'img'}
    used |= {r for sl in (c.get('lecture') or {}).get('slides', []) for r in imgs_of(sl.get('img')) if r.lower().endswith('.gif')}   # анимации для плеера
    used = sorted(used)
    mimg = os.path.join(MEDIA, cid, 'img')
    shutil.rmtree(mimg, ignore_errors=True)
    if used:
        os.makedirs(mimg)
        for rel in used: shutil.copy(os.path.join(COURSES, cid, rel), os.path.join(mimg, os.path.basename(rel)))
        print('  картинок в карточках:', len(used))
    if c.get('lecture'):
        md_dir = os.path.join(MEDIA, cid); os.makedirs(md_dir, exist_ok=True)
        meta_p = os.path.join(md_dir, 'meta.json')
        v = json.load(open(meta_p))['v'] + 1 if os.path.exists(meta_p) else 1
        for f in os.listdir(md_dir):
            if re.fullmatch(r's\d\d\.jpg', f): os.remove(os.path.join(md_dir, f))
        render(c['lecture']['slides'], md_dir)
        ap = os.path.join(md_dir, 'anim.json'); anim = json.load(open(ap)); os.remove(ap)
        audio = f'lecture_v{v}.mp3'
        t, dur = voice(c['lecture']['slides'], os.path.join(md_dir, audio))
        for f in os.listdir(md_dir):   # старые озвучки удаляем: ссылки на них уже нет
            if f.endswith('.mp3') and f != audio: os.remove(os.path.join(md_dir, f))
        json.dump({'v': v, 'voice': f'vosk-ru-0.9 speaker {SPEAKER}', 'dur': dur, 't': t, 'audio': audio, 'anim': anim}, open(meta_p, 'w'), ensure_ascii=False)
        print(f'  лекция: {len(t)} слайдов, {dur} с, {audio}')
    gen(); feed(c)
    print('Готово. Проверьте в приложении (тест: python3 tests/... с мок-сервером), затем tools/release_content.sh')


def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    cmd = a[0]
    if cmd == 'fetch':
        cid = a[1]
        subprocess.run(['git', '-C', ROOT, 'fetch', '-q', 'origin', 'courses'], check=True)
        data = subprocess.run(['git', '-C', ROOT, 'show', f'origin/courses:courses/{cid}/course.json'], check=True, capture_output=True).stdout
        dst = os.path.join(COURSES, cid); os.makedirs(dst, exist_ok=True)
        open(os.path.join(dst, 'course.json'), 'wb').write(data)
        names = subprocess.run(['git', '-C', ROOT, 'ls-tree', '--name-only', f'origin/courses:courses/{cid}/img/'], capture_output=True, text=True).stdout.split()
        if names:
            shutil.rmtree(os.path.join(dst, 'img'), ignore_errors=True); os.makedirs(os.path.join(dst, 'img'))
            for n in names:
                if n.lower().endswith(IMG_EXT):
                    b = subprocess.run(['git', '-C', ROOT, 'show', f'origin/courses:courses/{cid}/img/{n}'], check=True, capture_output=True).stdout
                    if len(b) > 3_000_000 and f'img/{n}' not in data.decode('utf-8'): print(f'  пропущен {n}: {len(b) // 1_000_000} МБ, в курсе не используется'); continue
                    open(os.path.join(dst, 'img', n), 'wb').write(b)
            print('  картинок:', len([n for n in names if n.lower().endswith(IMG_EXT)]))
        c = load(cid); report(c, *check(c, IMG_BASE[0]))
    elif cmd == 'check':
        c = load(a[1]); E, W = check(c, IMG_BASE[0]); report(c, E, W); sys.exit(1 if E else 0)
    elif cmd == 'preview':
        c = load(a[1]); E, W = check(c, IMG_BASE[0]); report(c, E, W)
        if E or not c.get('lecture'): sys.exit(1 if E else 0)
        out = a[2] if len(a) > 2 else os.path.join(ROOT, 'build', 'preview', c['id'])
        shutil.rmtree(out, ignore_errors=True)
        j = render(c['lecture']['slides'], out); contact(j, os.path.join(out, 'contact.jpg'))
        print('  слайды:', out)
    elif cmd == 'build':
        build(a[1])
    elif cmd == 'gen':
        gen()
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
