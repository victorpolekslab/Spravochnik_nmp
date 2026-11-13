#!/usr/bin/env python3
"""Схемы «Почему так на ЭКГ»: проводящая система сердца + где поломка + какой вектор видят какие отведения.
Слева — сердце (вид спереди) с проводящей системой и отведениями-«глазами», справа — комплексы в нужных отведениях.
  python3 gen_cond.py <папка_вывода> [тема ...]"""
import math, os, sys

W, H = 960, 540
INK, MUTED, RED, GREEN, BLUE, ORANGE = '#1f2430', '#6b7280', '#d0342c', '#2e8b57', '#2f6db5', '#e08a00'
COND, COND_DARK = '#f2b705', '#b8860b'


def esc(s): return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def text(x, y, s, size=14, fill=INK, anchor='start', weight='normal', italic=False):
    st = ' font-style="italic"' if italic else ''
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}"{st}>{esc(s)}</text>'


def lines(x, y, rows, size=13.5, fill=INK, lh=None, weight='normal', anchor='start'):
    lh = lh or size * 1.35
    return ''.join(text(x, y + i * lh, r, size, fill, anchor, weight) for i, r in enumerate(rows))


def arrow(x1, y1, x2, y2, color, w=5, dash=None, head=14, op=1):
    a = math.atan2(y2 - y1, x2 - x1); hx, hy = x2 - head * math.cos(a), y2 - head * math.sin(a)
    p1 = (hx + head * .55 * math.sin(a), hy - head * .55 * math.cos(a)); p2 = (hx - head * .55 * math.sin(a), hy + head * .55 * math.cos(a))
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return (f'<g opacity="{op}"><line x1="{x1}" y1="{y1}" x2="{hx:.1f}" y2="{hy:.1f}" stroke="{color}" stroke-width="{w}" stroke-linecap="round"{d}/>'
            f'<polygon points="{x2},{y2} {p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" fill="{color}"/></g>')


def num(x, y, n, color):
    return f'<circle cx="{x}" cy="{y}" r="11" fill="{color}"/>' + text(x, y + 5, str(n), 13, '#fff', 'middle', 'bold')


# ---------- сердце ----------
# координаты в системе сердца: ширина ~400, высота ~420; ставится translate(ox, oy) scale(k)
RA = 'M 70,150 C 60,95 105,60 160,62 C 205,64 235,95 240,140 L 240,190 L 85,190 C 74,180 70,165 70,150 Z'
LA = 'M 250,135 C 255,85 300,62 345,68 C 390,75 410,110 405,150 L 400,190 L 250,190 Z'
RV = 'M 85,200 L 240,200 L 262,420 C 215,405 150,360 112,300 C 92,268 82,232 85,200 Z'
LV = 'M 252,200 L 400,200 C 420,250 415,310 385,355 C 352,402 305,428 270,432 Z'
SA, AV = (118, 92), (238, 192)
HIS_END = (246, 228)
RBB = 'M 246,228 C 238,280 232,330 226,375'
LBB_STEM = 'M 246,228 L 258,250'
LAF = 'M 258,250 C 300,250 345,240 382,222'
LPF = 'M 258,250 C 275,310 300,360 320,402'
PURK = ['M 226,375 C 190,360 150,330 125,290', 'M 226,375 C 215,395 240,410 255,415', 'M 226,375 C 180,385 140,350 108,262',
        'M 382,222 C 395,250 398,285 392,320', 'M 320,402 C 345,395 370,372 386,345', 'M 320,402 C 300,415 282,420 268,424',
        'M 300,330 C 330,325 360,300 378,270']
INTERNODAL = ['M 118,92 C 150,110 190,150 238,192', 'M 118,92 C 120,140 170,178 238,192', 'M 118,92 C 175,95 215,140 238,192']
BACHMANN = 'M 118,92 C 200,70 290,78 360,96'


def heart(over='', cond_hide=(), cond_red=(), cond_dim=False, wall=None):
    """over — SVG поверх (в координатах сердца). cond_red — ветви, отмеченные красным (блокада).
    wall — {'ant'|'inf'|'lat'|'sept'|'rv': цвет} — подсвеченная зона миокарда."""
    g = []
    g.append(f'<path d="{RA}" fill="#f7d6cf" stroke="#c98f86" stroke-width="2"/>')
    g.append(f'<path d="{LA}" fill="#f7d6cf" stroke="#c98f86" stroke-width="2"/>')
    g.append('<rect x="80" y="190" width="330" height="10" rx="5" fill="#d9d3c7"/>')   # фиброзное кольцо
    g.append(f'<path d="{RV}" fill="#f0b3a8" stroke="#c0766b" stroke-width="2"/>')
    g.append(f'<path d="{LV}" fill="#eaa093" stroke="#b5655a" stroke-width="2.5"/>')
    if wall: g.append(wall)
    g.append(text(150, 145, 'ПП', 15, '#a3685f', 'middle', 'bold') + text(330, 140, 'ЛП', 15, '#a3685f', 'middle', 'bold'))
    g.append(text(160, 270, 'ПЖ', 16, '#9b5a50', 'middle', 'bold') + text(335, 285, 'ЛЖ', 16, '#8a4a40', 'middle', 'bold'))
    op = .45 if cond_dim else 1
    def br(d, key, w=5):
        if key in cond_hide: return ''
        col = RED if key in cond_red else COND
        return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round" opacity="{op}"/>'
    for d in INTERNODAL: g.append(br(d, 'intern', 3.5))
    g.append(br(BACHMANN, 'bach', 3.5))
    for d in PURK: g.append(br(d, 'purk', 2.2))
    g.append(br(RBB, 'rbb')); g.append(br(LBB_STEM, 'lbb', 6)); g.append(br(LAF, 'laf')); g.append(br(LPF, 'lpf'))
    g.append(br(f'M {AV[0]},{AV[1]} L {HIS_END[0]},{HIS_END[1]}', 'his', 6.5))
    g.append(f'<circle cx="{SA[0]}" cy="{SA[1]}" r="10" fill="{RED if "sa" in cond_red else "#ff9f1c"}" stroke="#fff" stroke-width="2.5" opacity="{op}"/>')
    g.append(f'<ellipse cx="{AV[0]}" cy="{AV[1]}" rx="12" ry="8" fill="{RED if "av" in cond_red else "#ff9f1c"}" stroke="#fff" stroke-width="2.5" opacity="{op}"/>')
    g.append(over)
    return ''.join(g)


def tag(x, y, s, color=INK, anchor='middle', size=12.5):
    w = len(s) * size * .66 + 14
    x0 = x - w / 2 if anchor == 'middle' else (x if anchor == 'start' else x - w)
    return (f'<rect x="{x0:.1f}" y="{y - size - 3:.1f}" width="{w:.1f}" height="{size + 9:.1f}" rx="7" fill="#fff" stroke="{color}" stroke-width="1.3" opacity=".95"/>'
            + text(x0 + w / 2, y + 1, s, size, color, 'middle', 'bold'))


def eye(x, y, label, color=BLUE, side='left'):
    """отведение-«глаз»: значок и подпись"""
    lx = x - 18 if side == 'left' else x + 18
    return (f'<g><ellipse cx="{x}" cy="{y}" rx="15" ry="10" fill="#fff" stroke="{color}" stroke-width="2.2"/><circle cx="{x}" cy="{y}" r="5" fill="{color}"/></g>'
            + text(lx, y + 5, label, 15, color, 'end' if side == 'left' else 'start', 'bold'))


# ---------- мини-ЭКГ ----------
def wave(params, x0, y0, w, h, mm=None, color=INK, sw=2.2):
    """params: список (центр 0..1, ширина 0..1, амплитуда в мм) — сумма гауссиан; ST-сдвиг: ('st', a, от, до)"""
    n = 220; pts = []
    mm = mm or h / 16
    for i in range(n + 1):
        t = i / n; v = 0
        for p in params:
            if p[0] == 'st':
                _, a, t1, t2 = p
                if t1 <= t <= t2: v += a * min(1, (t - t1) / .03, (t2 - t) / .06 if t2 - t < .06 else 1)
                continue
            c, s, a = p; v += a * math.exp(-((t - c) / s) ** 2)
        pts.append(f'{x0 + t * w:.1f},{y0 - v * mm:.1f}')
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round"/>'


def grid(x, y, w, h, step=6):
    g = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff6f6" stroke="#eaa3a3" stroke-width="1"/>']
    for i in range(1, int(w / step)):
        g.append(f'<line x1="{x + i * step}" y1="{y}" x2="{x + i * step}" y2="{y + h}" stroke="{"#efb9b9" if i % 5 == 0 else "#f9dede"}" stroke-width="{.9 if i % 5 == 0 else .5}"/>')
    for i in range(1, int(h / step)):
        g.append(f'<line x1="{x}" y1="{y + i * step}" x2="{x + w}" y2="{y + i * step}" stroke="{"#efb9b9" if i % 5 == 0 else "#f9dede"}" stroke-width="{.9 if i % 5 == 0 else .5}"/>')
    return ''.join(g)


def strip(x, y, w, h, label, params, color=INK, lcolor=INK, note=None):
    s = grid(x, y, w, h) + wave(params, x + 4, y + h * .6, w - 8, h, mm=h / 19, color=color)
    s += text(x + 1, y - 7, label, 13, lcolor, 'start', 'bold')
    if note: s += text(x + w - 1, y - 7, note, 13, lcolor, 'end', 'bold')
    return s


# комплексы (центр, ширина, амплитуда мм); один удар на полосе
P = (.16, .035, 1.2)
N_V1 = [P, (.335, .010, 1.2), (.37, .018, -6.5), (.62, .07, 1.5)]                 # rS
N_V6 = [P, (.325, .008, -1), (.35, .012, 9.5), (.38, .012, -1.5), (.62, .07, 2.5)]   # qR(s)
LBBB_V1 = [P, (.39, .055, -7), (.66, .07, 2.4)]                                    # широкий QS, T вверх
LBBB_V6 = [P, (.36, .03, 7.5), (.43, .03, 8.5), (.40, .03, 1.5), (.68, .07, -2.6)]   # широкий зазубренный R без q, T вниз
RBBB_V1 = [P, (.33, .010, 2.5), (.355, .012, -3), (.40, .025, 8), (.64, .07, -2.2)]  # rSR'
RBBB_V6 = [P, (.33, .010, 9.5), (.40, .03, -3.2), (.62, .07, 2.3)]                  # R + широкий S
ST_UP = [P, (.33, .009, -1.5), (.355, .012, 9), (.38, .012, -1), ('st', 3.2, .40, .66), (.58, .07, 2.5)]
ST_DN = [P, (.335, .009, -.6), (.355, .012, 7), (.38, .012, -1), ('st', -1.8, .40, .62), (.62, .07, -1.2)]
NORM_II = [P, (.33, .008, -.8), (.355, .012, 10), (.38, .012, -1.2), (.62, .07, 2.6)]


def slide(title, left, right, foot):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="DejaVu Sans, Arial, sans-serif">'
            f'<title>{esc(title)}</title><rect width="{W}" height="{H}" rx="18" fill="#ffffff"/>'
            + text(W / 2, 36, title, 22, INK, 'middle', 'bold') + left + right
            + text(W / 2, H - 14, foot, 12, MUTED, 'middle') + '</svg>')


def place(inner, ox, oy, k):
    return f'<g transform="translate({ox},{oy}) scale({k})">{inner}</g>'


# ---------- темы ----------
def t_lbbb():
    over = (f'<g stroke="{RED}" stroke-width="5" stroke-linecap="round"><line x1="244" y1="232" x2="262" y2="250"/><line x1="262" y1="232" x2="244" y2="250"/></g>'
            + arrow(212, 262, 262, 270, BLUE, 5) + num(198, 258, 1, BLUE)
            + arrow(205, 330, 140, 300, ORANGE, 4) + num(214, 340, 2, ORANGE)
            + arrow(265, 330, 385, 300, RED, 7, dash='10 7') + num(272, 350, 3, RED)
            + tag(345, 325, 'медленно', RED, size=11.5))
    h = heart(over, cond_red=('lbb', 'laf', 'lpf'), cond_dim=False)
    left = place(h, 80, 22, 0.98) + eye(66, 300, 'V1', BLUE, 'left') + eye(500, 286, 'V6', BLUE, 'right')
    left += text(40, 500, 'Красный крест — блок левой ножки; ветви ЛЖ молчат', 12.5, RED)
    x, w, hh = 560, 370, 84
    right = strip(x, 76, w / 2 - 6, hh, 'V1 норма', N_V1, lcolor=GREEN) + strip(x + w / 2 + 6, 76, w / 2 - 6, hh, 'V6 норма', N_V6, lcolor=GREEN)
    right += strip(x, 184, w / 2 - 6, hh, 'V1 БЛНПГ', LBBB_V1, lcolor=RED) + strip(x + w / 2 + 6, 184, w / 2 - 6, hh, 'V6 БЛНПГ', LBBB_V6, lcolor=RED)
    right += num(x + 10, 285, 1, BLUE) + lines(x + 28, 290, ['Перегородка — справа налево (в норме', 'наоборот) → нет q в V6, нет r в V1'], 13.5)
    right += num(x + 10, 340, 2, ORANGE) + lines(x + 28, 345, ['ПЖ возбуждается вовремя по правой', 'ножке — его вклад тонет в вольтаже ЛЖ'], 13.5)
    right += num(x + 10, 395, 3, RED) + lines(x + 28, 400, ['ЛЖ — последним и по мышце, медленно:', 'QRS ≥ 0,12 с; большой вектор от V1 к V6 →', 'QS в V1, широкий зазубренный R в V6'], 13.5)
    right += lines(x + 28, 466, ['Реполяризация идёт тем же путём →', 'ST и T направлены против QRS'], 13.5, MUTED)
    return slide('Почему так при блокаде левой ножки', left, right, 'Схема учебная, вид спереди; V1 и V6 смотрят на сердце в горизонтальной плоскости · пособие, гл. 6.7.1.2')


def t_inferior():
    zone = '<path d="M 112,300 C 150,360 215,405 262,420 L 270,432 C 305,428 352,402 385,355 L 360,335 C 330,375 300,392 268,398 C 225,388 170,350 140,300 Z" fill="#c0392b" opacity=".55"/>'
    over = (arrow(300, 290, 300, 420, RED, 7) + tag(300, 452, 'вектор повреждения', RED, size=11.5)
            + f'<circle cx="238" cy="192" r="19" fill="none" stroke="{RED}" stroke-width="3" stroke-dasharray="5 4"/>'
            + tag(150, 225, 'АВ-узел: часто блокада', RED, size=11.5))
    h = heart(over, wall=zone)
    left = place(h, 70, 18, 0.98)
    left += eye(262, 500, 'II, III, aVF', RED, 'right') + eye(498, 118, 'I, aVL', BLUE, 'right')
    x, w, hh = 590, 340, 88
    right = strip(x, 76, w, hh, 'II, III, aVF — смотрят снизу', ST_UP, lcolor=RED, note='ST ↑')
    right += strip(x, 190, w, hh, 'I, aVL — сверху слева', ST_DN, lcolor=BLUE, note='ST ↓')
    right += lines(x, 296, ['Ток повреждения идёт к зоне инфаркта —', 'к нижней стенке.'], 14, INK, weight='bold')
    right += lines(x, 344, ['Отведения снизу видят вектор «на себя» —', 'подъём ST. Отведения сверху видят его', '«от себя» — зеркальная депрессия.'], 13.5)
    right += lines(x, 420, ['Нижнюю стенку и АВ-узел обычно питает', 'одна артерия (чаще правая коронарная) →', 'при нижнем ИМ ищите АВ-блокаду', 'и снимите V3R–V4R.'], 13.5, MUTED)
    return slide('Почему нижний инфаркт виден в II, III, aVF', left, right, 'Схема учебная, вид спереди · КР157_5; пособие, гл. 8.2.4')


TOPICS = {'lbbb': t_lbbb, 'inferior': t_inferior}

if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    for k in (sys.argv[2:] or TOPICS):
        open(os.path.join(out, f'cond_{k}.svg'), 'w', encoding='utf-8').write(TOPICS[k]())
        print('ok', k)
