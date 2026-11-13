#!/usr/bin/env python3
"""Все схемы «Почему так на ЭКГ» для цикла ЭКГ (части 1–14). Общий шаблон — gen_cond.py.
  python3 topics.py <папка> [тема ...]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_cond import *          # noqa
import gen_cond as G

# ---------- многоударные полосы ----------
def sh(tpl, t0, k=1.0, amp=1.0):
    out = []
    for p in tpl:
        if p[0] == 'st': out.append(('st', p[1] * amp, p[2] * k + t0, p[3] * k + t0))
        else: out.append((p[0] * k + t0, p[1] * k, p[2] * amp))
    return out


def seq(*parts):
    r = []
    for p in parts: r += p
    return r


def wave_fine(params, x0, y0, w, h, mm, color=INK, sw=2.0):
    n = 900; pts = []
    for i in range(n + 1):
        t = i / n; v = 0
        for p in params:
            if p[0] == 'st':
                _, a, t1, t2 = p
                if t1 <= t <= t2: v += a * min(1, (t - t1) / .015 if t - t1 < .015 else 1, (t2 - t) / .03 if t2 - t < .03 else 1)
                continue
            c, s, a = p
            if abs(t - c) < 4 * s: v += a * math.exp(-((t - c) / s) ** 2)
        pts.append(f'{x0 + t * w:.1f},{y0 - v * mm:.1f}')
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round"/>'


def strip2(x, y, w, h, label, params, lcolor=INK, note=None, base=.6):
    s = grid(x, y, w, h) + wave_fine(params, x + 3, y + h * base, w - 6, h, h / 19)
    s += text(x + 1, y - 7, label, 13, lcolor, 'start', 'bold')
    if note: s += text(x + w - 1, y - 7, note, 13, lcolor, 'end', 'bold')
    return s


# шаблоны одного удара в долях «длины удара» (P в .16, QRS около .35, T около .62)
B_NORM = [(.16, .035, 1.2), (.33, .008, -.8), (.355, .012, 10), (.38, .012, -1.2), (.62, .07, 2.6)]
B_NOP = [(.33, .008, -.8), (.355, .012, 10), (.38, .012, -1.2), (.62, .07, 2.6)]
B_QRS = B_NOP
B_PNEG = [(.20, .03, -1.2), (.33, .008, -.6), (.355, .012, 9), (.38, .012, -1.2), (.62, .07, 2.4)]
B_WIDE = [(.36, .04, 9), (.46, .04, -4), (.66, .07, -3)]
B_WIDE2 = [(.34, .05, -8), (.44, .04, 3), (.66, .08, 3.2)]


def P_(t, a=1.2): return [(t, .035 / 3, a)]


# ---------- горизонтальный срез (для грудных отведений) ----------
CH = dict(cx=200, cy=165, rx=185, ry=125)
V_POS = {'V1': (150, 50), 'V2': (205, 42), 'V3': (262, 52), 'V4': (318, 82), 'V5': (362, 128), 'V6': (382, 185)}


def horiz(over='', lv=(240, 175, 66, 40), zone='', rv=True, labels=True):
    cx, cy, R, r = lv
    g = [f'<ellipse cx="{CH["cx"]}" cy="{CH["cy"]}" rx="{CH["rx"]}" ry="{CH["ry"]}" fill="#f3efe7" stroke="#cfc6b4" stroke-width="2"/>',
         text(CH['cx'], CH['cy'] + CH['ry'] - 14, 'спина', 12, MUTED, 'middle'),
         f'<rect x="{CH["cx"] - 18}" y="{CH["cy"] - CH["ry"] + 2}" width="36" height="16" rx="5" fill="#ddd5c6"/>',
         text(CH['cx'], CH['cy'] - CH['ry'] + 32, 'грудина', 11, MUTED, 'middle')]
    if rv:
        g.append(f'<path d="M {cx - R + 6},{cy - 20} C {cx - R - 40},{cy - 40} {cx - 80},{cy - R - 30} {cx - 10},{cy - R - 6} '
                 f'C {cx - 40},{cy - R + 18} {cx - R + 10},{cy - 40} {cx - R + 6},{cy - 20} Z" fill="#f0b3a8" stroke="#c0766b" stroke-width="2"/>')
    g.append(f'<circle cx="{cx}" cy="{cy}" r="{(R + r) / 2}" fill="none" stroke="#eaa093" stroke-width="{R - r}"/>')
    g.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="#b5655a" stroke-width="2"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="#fbe9e4" stroke="#b5655a" stroke-width="1.5"/>')
    g.append(zone)
    if labels:
        g.append(text(cx, cy + 5, 'ЛЖ', 14, '#8a4a40', 'middle', 'bold'))
        if rv: g.append(text(cx - R - 8, cy - R + 4, 'ПЖ', 13, '#9b5a50', 'middle', 'bold'))
    g.append(over)
    return ''.join(g)


def heye(name, color=BLUE, k=1.0, ox=0, oy=0):
    x, y = V_POS[name]
    return (f'<ellipse cx="{x}" cy="{y}" rx="11" ry="7.5" fill="#fff" stroke="{color}" stroke-width="2"/><circle cx="{x}" cy="{y}" r="3.6" fill="{color}"/>'
            + text(x, y - 12, name, 12.5, color, 'middle', 'bold'))


def star(x, y, r=13, color=RED):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5; rr = r if i % 2 == 0 else r * .45
        pts.append(f'{x + rr * math.cos(a):.1f},{y + rr * math.sin(a):.1f}')
    return f'<polygon points="{" ".join(pts)}" fill="{color}" stroke="#fff" stroke-width="1.5"/>'


def xmark(x, y, s=10, color=RED, w=5):
    return f'<g stroke="{color}" stroke-width="{w}" stroke-linecap="round"><line x1="{x - s}" y1="{y - s}" x2="{x + s}" y2="{y + s}"/><line x1="{x + s}" y1="{y - s}" x2="{x - s}" y2="{y + s}"/></g>'


def loop(cx, cy, rx, ry, color, w=4, start=20, end=330, cw=True):
    a1, a2 = math.radians(start), math.radians(end)
    x1, y1 = cx + rx * math.cos(a1), cy + ry * math.sin(a1); x2, y2 = cx + rx * math.cos(a2), cy + ry * math.sin(a2)
    large = 1 if (end - start) % 360 > 180 else 0
    d = f'M {x1:.1f},{y1:.1f} A {rx},{ry} 0 {large} 1 {x2:.1f},{y2:.1f}'
    ta = a2 + math.pi / 2; hx, hy = x2 + 10 * math.cos(ta), y2 + 10 * math.sin(ta)
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>'
            + arrow(x2 - 2 * math.cos(ta), y2 - 2 * math.sin(ta), hx, hy, color, w, head=12))


def wavy(x1, y1, x2, y2, color, w=3.5, amp=6, n=6):
    L = math.hypot(x2 - x1, y2 - y1); a = math.atan2(y2 - y1, x2 - x1); pts = []
    for i in range(n * 8 + 1):
        t = i / (n * 8); d = amp * math.sin(t * n * 2 * math.pi)
        pts.append(f'{x1 + t * L * math.cos(a) - d * math.sin(a):.1f},{y1 + t * L * math.sin(a) + d * math.cos(a):.1f}')
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>' + arrow(x2 - 8 * math.cos(a), y2 - 8 * math.sin(a), x2 + 6 * math.cos(a), y2 + 6 * math.sin(a), color, w, head=12)


def bul(x, y, items, w=0):
    """items: (номер|None, цвет, [строки], 'b'|'m'|'') → SVG; шаг считается по строкам"""
    s = ''; yy = y
    for n, col, rows, st in items:
        if n is not None: s += num(x + 10, yy - 5, n, col)
        tx = x + (28 if n is not None else 0)
        s += lines(tx, yy, rows, 13.5, MUTED if st == 'm' else INK, weight='bold' if st == 'b' else 'normal')
        yy += len(rows) * 18.2 + 12
    return s


def H(over='', **kw):
    """сердце, поставленное в левую половину слайда"""
    return place(heart(over, **kw), 80, 22, .98)


def to_slide(x, y):   # координаты сердца → слайда (для глаз и подписей снаружи)
    return 80 + x * .98, 22 + y * .98


# ======================= ТЕМЫ =======================
def t_leads():   # ч.1 — куда смотрят отведения
    cx, cy = to_slide(255, 300)
    eyes = ''
    for name, ang, col in [('I', 0, BLUE), ('aVL', -30, BLUE), ('II', 60, RED), ('aVF', 90, RED), ('III', 120, RED), ('aVR', -150, MUTED)]:
        a = math.radians(ang); R = 255
        x, y = cx + R * math.cos(a) * 1.0, cy + R * math.sin(a) * .86
        x = min(max(x, 40), 520); y = min(max(y, 90), 488)
        side = 'right' if math.cos(a) >= -0.1 else 'left'
        eyes += eye(round(x), round(y), name, col, side)
    left = H() + eyes
    left += text(30, 64, 'От конечностей — во фронтальной плоскости:', 12.5, MUTED)
    hx = place(horiz(''.join(heye(v) for v in V_POS)), 560, 52, .93)
    right = text(560, 64, 'Грудные отведения — срез сверху вниз', 13, INK, 'start', 'bold') + hx
    right += bul(560, 346, [(None, INK, ['Возбуждение идёт к электроду →', 'зубец вверх; от электрода — вниз.'], 'b'),
                            (None, INK, ['II, III, aVF смотрят снизу — нижняя', 'стенка; I, aVL, V5–V6 — боковая;', 'V1–V4 — перегородка и передняя.'], ''),
                            (None, INK, ['Перепутали электроды — «глаз»', 'смотрит не туда, ЭКГ лжёт.'], 'm')])
    return slide('Куда смотрит каждое отведение', left, right, 'Схема учебная · пособие, гл. 2')


def t_normal():  # ч.2 — почему R растёт
    over = (arrow(282, 262, 222, 270, BLUE, 5) + num(296, 258, 1, BLUE) + arrow(265, 300, 395, 345, RED, 8) + num(258, 318, 2, RED))
    left = H(over) + eye(66, 300, 'V1', BLUE, 'left') + eye(500, 330, 'V6', BLUE, 'right')
    left += text(40, 506, 'Жёлтое — проводящая система: импульс расходится за 0,08–0,10 с', 12.5, MUTED)
    x = 560
    right = (strip2(x, 76, 116, 84, 'V1', sh(B_NORM, 0) and [(.16, .035, 1.2), (.335, .010, 1.6), (.37, .018, -7), (.62, .07, 1.5)], GREEN)
             + strip2(x + 127, 76, 116, 84, 'V3', [(.16, .035, 1.2), (.34, .012, 5), (.38, .016, -5), (.62, .07, 2.2)], GREEN)
             + strip2(x + 254, 76, 116, 84, 'V6', [(.16, .035, 1.2), (.325, .008, -1.2), (.35, .012, 9.5), (.38, .012, -1.2), (.62, .07, 2.5)], GREEN))
    right += bul(x, 196, [(1, BLUE, ['Первой возбуждается перегородка —', 'слева направо, к V1: маленький r', 'в V1 и маленький q в V6.'], ''),
                          (2, RED, ['Затем — мощный левый желудочек:', 'большой вектор от V1 к V6 →', 'глубокий S в V1, высокий R в V6.'], ''),
                          (None, INK, ['V3–V4 — середина пути: R ≈ S,', 'переходная зона. R растёт от V1', 'к V5, S убывает.'], 'm')])
    return slide('Почему R растёт от V1 к V6', left, right, 'Схема учебная; V1 и V6 смотрят в горизонтальной плоскости · пособие, гл. 3')


def t_source():  # ч.3 — источник ритма и P
    over = (arrow(128, 104, 215, 175, GREEN, 5) + tag(150, 62, 'синусовый: волна вниз', GREEN, size=11.5)
            + star(205, 205, 12, BLUE) + arrow(200, 196, 130, 120, BLUE, 5, dash='8 6') + tag(110, 222, 'нижний очаг: волна вверх', BLUE, size=11.5))
    left = H(over) + eye(470, 470, 'II', RED, 'right')
    left += text(40, 506, 'II смотрит снизу слева: волна к нему → P вверх', 12.5, MUTED)
    x = 560
    one = lambda tpl: seq(sh(tpl, 0, .5), sh(tpl, .5, .5))
    right = strip2(x, 76, 370, 74, 'II — синусовый ритм', one(B_NORM), GREEN, 'P +')
    right += strip2(x, 176, 370, 74, 'II — нижнепредсердный', one(B_PNEG), BLUE, 'P −')
    right += strip2(x, 276, 370, 74, 'II — из АВ-соединения', one([(.33, .008, -.6), (.355, .012, 9), (.38, .012, -1.2), (.46, .02, -1.8), (.66, .07, 2.4)]), ORANGE, 'P − после QRS')
    right += bul(x, 380, [(None, INK, ['Очаг внизу предсердий — волна идёт', 'вверх, от II: P отрицательный.'], ''),
                          (None, INK, ['Ниже узла предсердия возбуждаются', 'позже желудочков — P после QRS.'], ''),
                          (None, INK, ['QRS узкий: желудочки — обычным путём.'], 'm')])
    return slide('Почему P «переворачивается» при нижнем водителе', left, right, 'Схема учебная · пособие, гл. 4')


def t_ectopy():  # ч.4 — НЖЭ, ЖЭ, ре-энтри в АВ-узле
    over = (star(330, 120, 11, BLUE) + tag(345, 100, 'НЖЭ', BLUE, size=11.5)
            + star(150, 330, 13, RED) + wavy(160, 330, 330, 360, RED, 3.5) + tag(130, 360, 'ЖЭ', RED, size=11.5)
            + loop(238, 186, 26, 16, ORANGE, 3.5, 200, 520) + tag(150, 230, 'круг в АВ-узле', ORANGE, size=11.5))
    left = H(over) + eye(66, 300, 'V1', BLUE, 'left')
    left += text(40, 506, 'Звёздочка — внеочередной очаг', 12.5, MUTED)
    x = 560
    nje = seq(sh(B_NORM, 0, .34), sh([(.16, .035, -.9 + 2.0), (.33, .008, -.8), (.355, .012, 10), (.38, .012, -1.2), (.62, .07, 2.6)], .26, .34), sh(B_NORM, .66, .34))
    je = seq(sh(B_NORM, 0, .34), sh(B_WIDE, .25, .34), sh(B_NORM, .69, .31))
    svt = seq(*[sh(B_NOP, i * .2, .2) for i in range(5)])
    right = strip2(x, 76, 370, 70, 'НЖЭ: P\' раньше срока, QRS узкий', nje, BLUE)
    right += strip2(x, 172, 370, 70, 'ЖЭ: без P, QRS широкий, T против', je, RED)
    right += strip2(x, 268, 370, 70, 'АВ-узловая НЖТ: узко, ровно, P не видно', svt, ORANGE)
    right += bul(x, 372, [(None, INK, ['Очаг выше узла → дальше обычный', 'путь по ножкам: QRS узкий.'], ''),
                          (None, INK, ['Очаг в желудочке → волна идёт', 'по мышце, медленно: QRS широкий.'], ''),
                          (None, INK, ['Импульс кружит в АВ-узле — каждый', 'круг даёт QRS: 140–250 в минуту.'], '')])
    return slide('Почему экстрасистолы узкие и широкие', left, right, 'Схема учебная · пособие, гл. 5; КР619_3')


def t_af():      # ч.5 — ФП и трепетание
    chaos = ''.join(loop(x, y, 10, 8, '#7a3db8', 2.4, a, a + 260) for x, y, a in [(305, 110, 0), (345, 140, 90), (300, 160, 200), (365, 105, 300), (330, 175, 40)])
    over = (chaos + tag(340, 72, 'ФП: сотни мелких волн', '#7a3db8', size=11.5)
            + loop(160, 140, 58, 40, ORANGE, 4.5, 30, 340) + tag(120, 210, 'трепетание: круг 200–400 в мин', ORANGE, size=11.5)
            + f'<ellipse cx="238" cy="192" rx="18" ry="12" fill="none" stroke="{INK}" stroke-width="2.5" stroke-dasharray="4 3"/>')
    left = H(over) + eye(262, 500, 'II, III, aVF', RED, 'right')
    left += text(40, 470, 'АВ-узел — фильтр: пропускает', 12.5, INK, 'start', 'bold') + text(40, 488, 'лишь часть волн', 12.5, INK, 'start', 'bold')
    x = 560
    import random; rnd = random.Random(3)
    f = [(i / 120, .004, rnd.uniform(-.6, .6)) for i in range(120)]
    qrs = [.07, .27, .38, .63, .82]
    af = f + seq(*[[(c, .006, -.6), (c + .012, .007, 9), (c + .025, .007, -1), (c + .11, .03, 1.6)] for c in qrs])
    fl = seq(*[[(c, .012, -2.2), (c + .03, .02, .9)] for c in [i * .1 for i in range(10)]]) + seq(*[[(c + .012, .007, 8), (c + .025, .007, -1)] for c in [.05, .25, .45, .65, .85]])
    right = strip2(x, 76, 370, 80, 'ФП: волн f много, RR разные', af, '#7a3db8')
    right += strip2(x, 184, 370, 80, 'Трепетание 2:1: «пила» F, ЧСС ~150', fl, ORANGE)
    right += bul(x, 296, [(None, INK, ['ФП: в предсердиях десятки мелких', 'волн — вместо P мелкая дрожь,', 'узел пропускает их случайно.'], ''),
                          (None, INK, ['Трепетание: одна большая волна', 'кружит вокруг трёхстворчатого', 'клапана — «пила» лучше всего', 'видна во II, III, aVF.'], ''),
                          (None, INK, ['Ровно 150 в минуту — ищите «пилу».'], 'm')])
    return slide('Что происходит в предсердиях при ФП и трепетании', left, right, 'Схема учебная · КР382_2; пособие, гл. 5')


def t_vt():      # ч.6 — ЖТ
    scar = '<path d="M 330,330 C 350,320 372,330 368,352 C 362,372 338,378 326,362 C 318,350 318,338 330,330 Z" fill="#8c8c8c" opacity=".75"/>'
    over = (scar + loop(347, 350, 36, 28, RED, 4, 200, 500) + tag(350, 410, 'круг вокруг рубца', RED, size=11.5)
            + wavy(320, 330, 150, 300, RED, 3.2, 5, 7) + wavy(330, 320, 300, 230, RED, 3.2, 5, 4)
            + arrow(128, 104, 215, 175, GREEN, 4) + tag(140, 62, 'синусовый узел — свой ритм', GREEN, size=11.5)
            )
    left = H(over) + eye(66, 300, 'V1', BLUE, 'left') + eye(470, 470, 'II', BLUE, 'right')
    left += text(40, 506, 'Серое — рубец после инфаркта', 12.5, MUTED)
    x = 560
    vt = seq(*[sh(B_WIDE, i * .19, .19) for i in range(5)]) + [(t, .014, 1.6) for t in [.03, .30, .57, .84]]
    right = strip2(x, 76, 370, 90, 'ЖТ: широкие QRS, P сами по себе', vt, RED)
    right += bul(x, 196, [(None, INK, ['Импульс кружит вокруг рубца', 'в желудочке — каждый круг', 'даёт комплекс.'], ''),
                          (None, INK, ['Волна идёт по мышце, а не по', 'ножкам → QRS ≥ 0,12 с.'], ''),
                          (None, INK, ['Предсердия живут в своём ритме:', 'P отдельно от QRS — АВ-', 'диссоциация, признак ЖТ.'], ''),
                          (None, INK, ['Широкий комплекс — считаем ЖТ.'], 'b')])
    return slide('Почему при ЖТ комплексы широкие', left, right, 'Схема учебная · КР569_2; пособие, гл. 5')


def t_brady():   # ч.7 — отказ СА-узла и запасные водители
    over = (xmark(118, 92, 12) + tag(130, 50, 'СА-узел молчит (60–90)', RED, size=11.5)
            + star(244, 214, 11, ORANGE) + tag(330, 214, 'АВ-соединение: 40–60', ORANGE, size=11.5)
            + star(300, 360, 12, BLUE) + tag(330, 395, 'желудочки: < 40', BLUE, size=11.5))
    left = H(over, cond_red=('sa',))
    left += text(40, 500, 'Ниже водитель — реже ритм и шире QRS', 12.5, INK, 'start', 'bold')
    x = 560
    pause = seq(sh(B_NORM, 0, .25), sh(B_NORM, .25, .25), sh(B_NOP, .75, .25))
    idio = seq(sh(B_WIDE2, 0, .5), sh(B_WIDE2, .5, .5))
    right = strip2(x, 76, 370, 80, 'Пауза, затем выскальзывающий из АВ', pause, ORANGE)
    right += strip2(x, 184, 370, 80, 'Идиовентрикулярный ритм', idio, BLUE)
    right += bul(x, 296, [(None, INK, ['Каждый отдел умеет сам рождать', 'импульс, но всё медленнее сверху', 'вниз — это «запасные» водители.'], ''),
                          (None, INK, ['Узел молчит — пауза, потом', 'выскальзывающий комплекс без P.'], ''),
                          (None, INK, ['Из АВ-соединения QRS узкий, из', 'желудочка — широкий и редкий.'], '')])
    return slide('Кто ведёт ритм, когда синусовый узел молчит', left, right, 'Схема учебная · КР160_2; пособие, гл. 4')


def t_avb():     # ч.8 — уровень АВ-блокады
    over = (xmark(238, 192, 10) + tag(120, 205, '1: блок в узле', RED, size=11.5) + star(247, 236, 9, ORANGE) + tag(340, 238, 'выскальзывает пучок: 40–60', ORANGE, size=11.5)
            + xmark(234, 300, 8, '#7a3db8', 4) + xmark(300, 252, 8, '#7a3db8', 4) + tag(120, 300, '2: блок ниже — в ножках', '#7a3db8', size=11.5)
            + star(330, 370, 11, BLUE) + tag(360, 405, 'желудочки: 20–40', BLUE, size=11.5))
    left = H(over, cond_red=('av',))
    left += text(40, 500, 'Атропин действует на узел, но не на ножки', 12.5, INK, 'start', 'bold')
    x = 560
    Ps = [(t, .014, 1.8) for t in [.04, .2, .36, .52, .68, .84]]
    narrow = Ps + seq(sh(B_NOP, .05, .45), sh(B_NOP, .52, .45))
    wide = Ps + seq(sh(B_WIDE2, .02, .48), sh(B_WIDE2, .52, .48))
    right = strip2(x, 76, 370, 80, '1: III степень, QRS узкие, 40–60', narrow, RED)
    right += strip2(x, 184, 370, 80, '2: III степень, QRS широкие, ≤ 40', wide, '#7a3db8')
    right += bul(x, 296, [(None, INK, ['P идут ровно, QRS — сами по себе:', 'предсердия и желудочки', 'разъединены.'], ''),
                          (None, INK, ['Блок в узле → выручает пучок Гиса:', 'QRS узкий, ритм устойчивее.'], ''),
                          (None, INK, ['Блок ниже → выручает мышца', 'желудочков: QRS широкий, редкий,', 'выше риск асистолии.'], 'b')])
    return slide('Где застрял импульс и почему QRS узкий или широкий', left, right, 'Схема учебная · КР160_2; пособие, гл. 6')


def t_rbbb():    # ч.9 — БПНПГ
    over = (xmark(232, 320, 9) + arrow(282, 262, 222, 270, BLUE, 5) + num(296, 258, 1, BLUE)
            + arrow(270, 320, 385, 300, ORANGE, 5) + num(262, 340, 2, ORANGE)
            + arrow(215, 330, 130, 295, RED, 7, dash='10 7') + num(224, 350, 3, RED) + tag(150, 345, 'медленно', RED, size=11.5))
    left = H(over, cond_red=('rbb',)) + eye(66, 300, 'V1', BLUE, 'left') + eye(500, 286, 'V6', BLUE, 'right')
    left += text(40, 500, 'Красный крест — блок правой ножки', 12.5, RED)
    x, w, hh = 560, 370, 84
    from gen_cond import N_V1, N_V6, RBBB_V1, RBBB_V6
    right = strip(x, 76, w / 2 - 6, hh, 'V1 норма', N_V1, lcolor=GREEN) + strip(x + w / 2 + 6, 76, w / 2 - 6, hh, 'V6 норма', N_V6, lcolor=GREEN)
    right += strip(x, 184, w / 2 - 6, hh, 'V1 БПНПГ', RBBB_V1, lcolor=RED) + strip(x + w / 2 + 6, 184, w / 2 - 6, hh, 'V6 БПНПГ', RBBB_V6, lcolor=RED)
    right += bul(x, 300, [(1, BLUE, ['Перегородка — как обычно,', 'к V1: r в V1, q в V6.'], ''),
                          (2, ORANGE, ['ЛЖ — вовремя: S в V1, R в V6.'], ''),
                          (3, RED, ['ПЖ — последним и по мышце,', 'вектор к V1 → R\' в V1 («буква М»),', 'широкий S в V6 и I; QRS ≥ 0,12 с.'], '')])
    return slide('Почему так при блокаде правой ножки', left, right, 'Схема учебная; V1 и V6 смотрят в горизонтальной плоскости · пособие, гл. 6.7.1.1')


def t_wpw():     # ч.9 — WPW
    kent = '<path d="M 392,160 C 404,185 404,205 395,232" fill="none" stroke="#7a3db8" stroke-width="7" stroke-linecap="round"/>'
    over = (kent + tag(395, 128, 'пучок Кента', '#7a3db8', size=12)
            + wavy(390, 238, 330, 300, '#7a3db8', 3.2, 4, 4) + tag(345, 330, 'рано, по мышце', '#7a3db8', size=11.5)
            + f'<ellipse cx="238" cy="192" rx="18" ry="12" fill="none" stroke="{INK}" stroke-width="2.5" stroke-dasharray="4 3"/>' + tag(150, 225, 'узел задерживает', INK, size=11.5)
            + '<path d="M 246,232 C 262,300 330,320 372,290 C 392,272 398,250 396,236" fill="none" stroke="#e08a00" stroke-width="3" stroke-dasharray="7 5"/>'
            + '<path d="M 392,158 C 360,140 290,150 250,182" fill="none" stroke="#e08a00" stroke-width="3" stroke-dasharray="7 5"/>' + arrow(262, 172, 248, 184, ORANGE, 3, head=11) + arrow(394, 250, 396, 234, ORANGE, 3, head=11))
    left = H(over) + eye(470, 470, 'II', BLUE, 'right')
    left += text(40, 500, 'Оранжевое — круг тахикардии: вниз через узел, вверх по Кенту', 12, ORANGE)
    x = 560
    norm = seq(sh(B_NORM, 0, .5), sh(B_NORM, .5, .5))
    dl = [(.16, .035, 1.2), (.27, .035, 3), (.31, .012, 7), (.34, .012, -1), (.6, .07, -1.2)]
    wpw = seq(sh(dl, 0, .5), sh(dl, .5, .5))
    right = strip2(x, 76, 370, 80, 'II — норма: PQ 0,12–0,20 с', norm, GREEN)
    right += strip2(x, 184, 370, 80, 'II — WPW: PQ короткий, дельта-волна', wpw, '#7a3db8')
    right += bul(x, 296, [(None, INK, ['Кент проводит без задержки →', 'PQ < 0,12 с.'], ''),
                          (None, INK, ['Часть желудочка возбуждается', 'раньше и по мышце → пологое начало', 'QRS (дельта), комплекс шире.'], ''),
                          (None, INK, ['При ФП Кент пропускает всё подряд —', 'поэтому блокаторы узла нельзя.'], 'b')])
    return slide('Почему при WPW короткий PQ и дельта-волна', left, right, 'Схема учебная · КР619_3; пособие, гл. 6.8')


def t_injury():  # ч.10 — субэндокардиальное и трансмуральное повреждение
    cav = 'M 272,215 L 392,215 C 402,258 398,305 375,342 C 350,380 312,402 282,408 Z'
    sub = f'<path d="{cav}" fill="none" stroke="#c0392b" stroke-width="14" opacity=".6" clip-path="url(#lvclip)"/>'
    trans = '<path d="M 392,215 L 400,200 C 420,250 415,310 385,355 L 375,342 C 398,305 402,258 392,215 Z" fill="#c0392b" opacity=".6"/>'
    clip = f'<defs><clipPath id="lvclip"><path d="{G.LV}"/></clipPath></defs>'
    lh = place(clip + heart(f'<path d="{cav}" fill="#fbe9e4" stroke="#b5655a" stroke-width="1.2"/>' + sub + arrow(395, 290, 330, 300, RED, 6), cond_dim=True), 10, 70, .62)
    rh = place(heart(f'<path d="{cav}" fill="#fbe9e4" stroke="#b5655a" stroke-width="1.2"/>' + trans + arrow(375, 290, 440, 280, RED, 6), cond_dim=True), 275, 70, .62)
    left = lh + rh + eye(268, 252, 'V5', BLUE, 'right') + eye(535, 252, '', BLUE, 'left') + text(520, 230, 'V5', 15, BLUE, 'end', 'bold')
    left += text(150, 368, 'Внутренний слой', 14, INK, 'middle', 'bold') + text(150, 386, 'вектор — в полость, от электрода', 12.5, MUTED, 'middle')
    left += text(415, 368, 'Вся толща стенки', 14, INK, 'middle', 'bold') + text(415, 386, 'вектор — наружу, к электроду', 12.5, MUTED, 'middle')
    left += lines(30, 440, ['Повреждённые клетки «текут» током — вектор', 'повреждения смотрит в сторону зоны повреждения.'], 13.5, INK, weight='bold')
    x = 560
    from gen_cond import ST_UP, ST_DN
    right = strip2(x, 76, 370, 84, 'Субэндокардиальное → депрессия ST', seq(sh(ST_DN, 0, .5), sh(ST_DN, .5, .5)), BLUE, 'ST ↓')
    right += strip2(x, 190, 370, 84, 'Трансмуральное → подъём ST', seq(sh(ST_UP, 0, .5), sh(ST_UP, .5, .5)), RED, 'ST ↑')
    right += bul(x, 310, [(None, INK, ['Ишемия внутреннего слоя — вектор', 'уходит от электрода: ST ниже', 'изолинии (стенокардия, ОКСбпST).'], ''),
                          (None, INK, ['Повреждение всей стенки — вектор', 'к электроду: подъём ST (ОКСпST).'], ''),
                          (None, INK, ['Электрод с другой стороны видит', 'то же «от себя» — зеркальная', 'депрессия.'], 'm')])
    return slide('Почему ST то опускается, то поднимается', left, right, 'Схема учебная · КР157_5, КР154_4; пособие, гл. 8.1')


def t_inferior():  # ч.11 — берём одобренный образец
    return G.t_inferior()


def t_anterior():  # ч.11 — передний ИМ, горизонтальный срез
    cx, cy, R, r = 240, 175, 66, 40
    zone = (f'<path d="M {cx - 46},{cy - 47} A {R},{R} 0 0 1 {cx + 60},{cy - 28} L {cx + 36},{cy - 17} A {r},{r} 0 0 0 {cx - 28},{cy - 29} Z" fill="#c0392b" opacity=".65"/>')
    over = arrow(cx + 5, cy - 20, cx + 30, cy - 120, RED, 6) + ''.join(heye(v, RED if v in ('V1', 'V2', 'V3', 'V4') else BLUE) for v in V_POS)
    left = place(horiz(over, zone=zone), 40, 70, 1.22)
    left += text(280, 470, 'Срез грудной клетки сверху вниз', 12.5, MUTED, 'middle')
    x = 560
    from gen_cond import ST_UP, ST_DN
    right = strip2(x, 76, 370, 84, 'V1–V4 — смотрят спереди', seq(sh(ST_UP, 0, .5), sh(ST_UP, .5, .5)), RED, 'ST ↑')
    right += strip2(x, 190, 370, 84, 'II, III, aVF — снизу', seq(sh(ST_DN, 0, .5), sh(ST_DN, .5, .5)), BLUE, 'ST ↓')
    right += bul(x, 310, [(None, INK, ['Передняя стенка и перегородка —', 'бассейн передней нисходящей', 'артерии; вектор повреждения —', 'вперёд, к V1–V4.'], ''),
                          (None, INK, ['Нижние отведения видят его', '«от себя» — зеркальная депрессия.'], ''),
                          (None, INK, ['В V5–V6, I, aVL тоже ST ↑ —', 'распространённый передний.'], 'm')])
    return slide('Почему передний инфаркт виден в V1–V4', left, right, 'Схема учебная · КР157_5; пособие, гл. 8.2.4')


def t_lvh():     # ч.12 — ГЛЖ
    cx, cy = 240, 178
    over = arrow(cx, cy, cx + 140, cy + 25, RED, 8) + ''.join(heye(v, RED if v in ('V5', 'V6') else (BLUE if v == 'V1' else MUTED)) for v in V_POS)
    left = place(horiz(over, lv=(cx, cy, 82, 38)), 40, 70, 1.22)
    left += text(280, 470, 'Срез сверху вниз; стенка ЛЖ утолщена', 12.5, MUTED, 'middle')
    x = 560
    v1 = [(.16, .035, 1.0), (.335, .010, 1.0), (.37, .02, -13), (.62, .07, 1.5)]
    v5 = [(.16, .035, 1.0), (.325, .008, -1), (.35, .012, 15), (.38, .012, -1), ('st', -1.4, .40, .55), (.62, .07, -2.2)]
    right = strip2(x, 76, 180, 100, 'V1 — глубокий S', v1, BLUE, base=.35) + strip2(x + 190, 76, 180, 100, 'V5 — высокий R', v5, RED, base=.82)
    right += bul(x, 212, [(None, INK, ['Мышцы ЛЖ больше → его вектор', 'длиннее и сильнее тянет влево-', 'назад, к V5–V6.'], ''),
                          (None, INK, ['V5–V6 видят его «на себя» —', 'высокий R; V1 — «от себя»,', 'глубокий S. Отсюда индекс', 'S V1 + R V5/V6.'], ''),
                          (None, INK, ['Толстая стенка реполяризуется', 'иначе → ST ↓ и T − в V5–V6', '(«перегрузка»).'], 'm')])
    return slide('Почему при гипертрофии ЛЖ растут зубцы', left, right, 'Схема учебная · КР62_3; пособие, гл. 7')


def t_pericard():  # ч.13 — перикардит
    halo = ('<path d="M 85,200 L 400,200 C 420,250 415,310 385,355 C 352,402 305,428 270,432 L 262,420 C 215,405 150,360 112,300 C 92,268 82,232 85,200 Z" '
            'fill="none" stroke="#c0392b" stroke-width="13" opacity=".45"/>')
    vec = ''.join(arrow(a, b, c, d, RED, 4, head=11) for a, b, c, d in [(300, 300, 420, 290), (250, 360, 270, 450), (180, 320, 95, 360), (340, 360, 410, 410), (300, 250, 410, 225)])
    over = halo + vec
    left = H(over, cond_dim=True) + eye(488, 360, 'I, V6', RED, 'right') + eye(400, 500, 'II, aVF', RED, 'right') + eye(50, 80, 'aVR', BLUE, 'right')
    left += text(40, 470, 'Воспалён весь наружный слой — вектор', 12.5, INK, 'start', 'bold') + text(40, 488, 'смотрит наружу во все стороны', 12.5, INK, 'start', 'bold')
    x = 560
    per = [(.16, .035, 1.2), ('st', -1.0, .2, .3), (.355, .012, 8), (.38, .012, -.6), ('st', 3.0, .40, .60), (.60, .07, 2.4)]
    avr = [(.16, .035, -1.0), ('st', 1.0, .2, .3), (.355, .012, -8), ('st', -2.4, .40, .60), (.62, .07, -2.2)]
    right = strip2(x, 76, 370, 80, 'Почти все отведения: ST ↑ дугой, PQ ↓', seq(sh(per, 0, .5), sh(per, .5, .5)), RED)
    right += strip2(x, 184, 370, 80, 'aVR: ST ↓, PQ ↑', seq(sh(avr, 0, .5), sh(avr, .5, .5)), BLUE)
    right += bul(x, 296, [(None, INK, ['Ток повреждения идёт наружу по всей', 'поверхности — почти каждое', 'отведение видит его «на себя».'], ''),
                          (None, INK, ['Зеркала нет: только aVR смотрит', 'изнутри и видит «от себя».'], ''),
                          (None, INK, ['Инфаркт — одна зона, свои', 'отведения и зеркальная депрессия', 'напротив.'], 'b')])
    return slide('Почему при перикардите подъём ST везде', left, right, 'Схема учебная · КР157_5; пособие, гл. 9.2')


def t_hyperk():  # ч.14 — гиперкалиемия
    over = (tag(150, 60, 'предсердия: P уплощается', ORANGE, size=11.5) + tag(310, 230, 'узел: PQ длиннее', ORANGE, size=11.5)
            + tag(160, 410, 'ножки и мышца: QRS шире', RED, size=11.5) + tag(340, 385, 'реполяризация быстрее: T острый', BLUE, size=11.5))
    left = H(over, cond_red=('intern', 'bach', 'his', 'rbb', 'lbb', 'laf', 'lpf'))
    left += text(40, 500, 'Калий тормозит проведение по всей системе', 12.5, RED, 'start', 'bold')
    x = 560
    k1 = [(.16, .035, 1.1), (.33, .008, -.6), (.355, .012, 8), (.38, .012, -1), (.6, .035, 7)]
    k2 = [(.16, .05, .4), (.38, .03, 6), (.44, .03, -3), (.66, .05, 5)]
    k3 = [(.3, .1, 6), (.55, .1, -6), (.8, .1, 6)]
    right = strip2(x, 76, 370, 70, 'Калий 6–7: высокий острый T', seq(sh(k1, 0, .5), sh(k1, .5, .5)), BLUE)
    right += strip2(x, 172, 370, 70, 'Калий 7–8: P плоский, QRS шире', seq(sh(k2, 0, .5), sh(k2, .5, .5)), ORANGE)
    right += strip2(x, 268, 370, 70, 'Калий 8–9: синусоида, дальше — остановка', k3, RED)
    right += bul(x, 372, [(None, INK, ['Калий снижает заряд клеток →', 'проведение замедляется везде:', 'P, PQ, QRS растягиваются.'], ''),
                          (None, INK, ['Первым меняется T в V2–V4 —', 'ранний сигнал, не ишемия.'], 'b')])
    return slide('Почему гиперкалиемия меняет всю ЭКГ', left, right, 'Схема учебная · пороги калия — ммоль/л по КР469_3; пособие, гл. 9.6')


TOPICS = {'leads': t_leads, 'normal': t_normal, 'source': t_source, 'ectopy': t_ectopy, 'af': t_af, 'vt': t_vt, 'brady': t_brady,
          'avb': t_avb, 'rbbb': t_rbbb, 'lbbb': G.t_lbbb, 'wpw': t_wpw, 'injury': t_injury, 'inferior': t_inferior, 'anterior': t_anterior,
          'lvh': t_lvh, 'pericard': t_pericard, 'hyperk': t_hyperk}

if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    for k in (sys.argv[2:] or TOPICS):
        open(os.path.join(out, f'why_{k}.svg'), 'w', encoding='utf-8').write(TOPICS[k]())
        print('ok', k)
