"""SVG-схемы для части 3 цикла «ЭКГ» (ecg_analysis). Запуск: python3 ecg_part3_svg.py <папка>"""
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)


def bracket(x1, x2, y, label, col=BLUE, size=15, up=True):
    d = -1 if up else 1
    s = [f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="{col}" stroke-width="2.2"/>']
    for x in (x1, x2):
        s.append(f'<line x1="{x:.1f}" y1="{y-7}" x2="{x:.1f}" y2="{y+7}" stroke="{col}" stroke-width="2.2"/>')
    if label:
        s.append(text((x1 + x2) / 2, y + d * 10 + (0 if up else 8), label, size, col, "middle", "bold"))
    return "\n".join(s)


def rhythm(beats, P=0.15, wide=False, p_mode="before", Pfix=None):
    """Функция ЭКГ по списку моментов R (с). p_mode: before/neg_before/none/neg_after/dissoc."""
    def f(t):
        v = 0.0
        for r in beats:
            lt = t - r + 0.225
            if -0.3 < lt < 0.8:
                if wide:
                    v += beat_p(lt, P=0, Q=-0.05, R=1.0, S=-0.5, T=-0.45, qrs=2.6)
                else:
                    pp = {"before": P, "neg_before": -0.12, "none": 0, "neg_after": 0, "dissoc": 0}[p_mode]
                    v += beat_p(lt, P=pp, Q=-0.07, R=1.05, S=-0.25, T=0.32)
                    if p_mode == "neg_after":
                        v += gauss(lt, -0.12, 0.33, 0.02)
        if Pfix:
            for p in Pfix:
                v += gauss(t, 0.14, p, 0.022)
        return v
    return f


# ---------- 1. Алгоритм ----------
def algorithm():
    b = [text(W / 2, 42, "Алгоритм расшифровки ЭКГ: 8 шагов", 26, INK, "middle", "bold")]
    steps = [("1", "Техника", "скорость, калибровка, помехи", MUTED),
             ("2", "Регулярность", "RR одинаковые? ±10 %", BLUE),
             ("3", "ЧСС", "60 / RR или комплексы за 3 с × 20", BLUE),
             ("4", "Источник ритма", "P+ во II перед каждым QRS?", GREEN),
             ("5", "Проводимость", "P, PQ, QRS — длительность", GREEN),
             ("6", "ЭОС", "I и aVF, угол α", ORANGE),
             ("7", "P, QRS, ST, T, QT", "форма, смещение ST, QTc", RED),
             ("8", "Заключение", "ритм · ЧСС · ЭОС · синдромы", VIOLET)]
    def wrap(t_, n=22):
        out, cur = [], ""
        for w_ in t_.split(" "):
            if len((cur + " " + w_).strip()) <= n: cur = (cur + " " + w_).strip()
            else: out.append(cur); cur = w_
        return out + [cur]
    for i, (n, h, sub, col) in enumerate(steps):
        c, r = i % 4, i // 4
        x, y = 40 + c * 225, 100 + r * 200
        b.append(f'<rect x="{x}" y="{y}" width="200" height="160" rx="18" fill="#f8fafc" stroke="{col}" stroke-width="2.5"/>')
        b.append(f'<circle cx="{x+36}" cy="{y+38}" r="22" fill="{col}"/>')
        b.append(text(x + 36, y + 46, n, 22, "#ffffff", "middle", "bold"))
        b.append(text(x + 18, y + 92, h, 17, INK, "start", "bold"))
        for j, ln in enumerate(wrap(sub)):
            b.append(text(x + 18, y + 118 + j * 20, ln, 13.5, MUTED))
        if c < 3:
            b.append(f'<path d="M{x+204},{y+80} l14,0" stroke="{MUTED}" stroke-width="3" marker-end="url(#ar)"/>')
    b.append('<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">'
             f'<path d="M0,0 L8,4 L0,8 z" fill="{MUTED}"/></marker></defs>')
    b.append(f'<path d="M{40+3*225+100},{262} C{900},{285} {140},{275} {140},{298}" fill="none" stroke="{MUTED}" stroke-width="2.5" stroke-dasharray="6 5" marker-end="url(#ar)"/>')
    b.append(text(W / 2, 520, "План по пособию Мурашко и Струтынского: ритм и проводимость → ЭОС → P → QRST → заключение", 14, MUTED, "middle"))
    return svg("\n".join(b), "Алгоритм расшифровки ЭКГ")


# ---------- 2. Регулярность ----------
def regularity():
    b = [text(W / 2, 40, "Регулярность: сравните интервалы RR", 24, INK, "middle", "bold")]
    px = 3.6; pxs = 25 * px
    rows = [("Правильный ритм: RR одинаковые", [0.3, 1.1, 1.9, 2.7, 3.5, 4.3, 5.1, 5.9, 6.7, 7.5, 8.3, 9.1], GREEN, "RR = 0,80 с"),
            ("Неправильный ритм: разброс RR больше ±10 %", [0.3, 0.95, 1.95, 2.45, 3.4, 4.0, 5.15, 5.75, 6.5, 7.6, 8.15, 9.0], RED, None)]
    for i, (lab, beats, col, rr) in enumerate(rows):
        y0 = 80 + i * 215
        w, h = 880, 40 * px
        b.append(grid(40, y0, w, h, px))
        base = y0 + 28 * px
        b.append(trace(rhythm(beats, p_mode="before" if i == 0 else "none"), 40, base, w, pxs, 10 * px, INK, 2))
        b.append(text(40, y0 - 12, lab, 18, col, "start", "bold"))
        for k in range(4):
            x1, x2 = 40 + beats[k] * pxs, 40 + beats[k + 1] * pxs
            lbl = (f"{beats[k+1]-beats[k]:.2f}".replace('.', ','))
            b.append(bracket(x1, x2, y0 + 14, lbl, col, 13, False))
    b.append(text(W / 2, 525, "Ритм правильный, если RR отличаются не больше чем на ±10 % от среднего (пособие, гл. 4)", 15, INK, "middle"))
    return svg("\n".join(b), "Регулярность ритма")


# ---------- 3. ЧСС ----------
def hr():
    b = [text(W / 2, 40, "Как посчитать ЧСС", 24, INK, "middle", "bold")]
    px = 4.0; pxs = 25 * px
    # правильный ритм — правило больших клеток
    y0 = 78; w, h = 880, 36 * px
    b.append(grid(40, y0, w, h, px))
    base = y0 + 25 * px
    beats = [0.4 + 0.8 * k for k in range(12)]
    b.append(trace(rhythm(beats), 40, base, w, pxs, 10 * px, INK, 2))
    x1, x2 = 40 + beats[1] * pxs, 40 + beats[2] * pxs
    b.append(bracket(x1, x2, y0 + 14, "RR = 20 мм = 4 большие клетки", BLUE, 14, False))
    b.append(text(40, y0 - 12, "Правильный ритм (25 мм/с)", 18, GREEN, "start", "bold"))
    b.append(text(920, y0 - 12, "60 / 0,8 с = 75   ·   300 / 4 клетки = 75", 17, INK, "end", "bold"))
    # неправильный — 3 секунды
    y1 = 300
    b.append(grid(40, y1, w, h, px))
    base = y1 + 25 * px
    ib = [0.3, 0.75, 1.3, 1.75, 2.35, 2.95, 3.55, 4.0, 4.7, 5.2, 5.95, 6.4, 7.1, 7.6, 8.3]
    b.append(trace(rhythm(ib, p_mode="none"), 40, base, w, pxs, 10 * px, INK, 2))
    b.append(f'<rect x="{40 + 0.1*pxs}" y="{y1+2}" width="{3*pxs}" height="{h-4}" fill="{ORANGE}" opacity="0.12" stroke="{ORANGE}" stroke-width="2"/>')
    b.append(text(44, y1 + h + 22, "3 секунды = 7,5 см при 25 мм/с (15 см при 50 мм/с)", 14, ORANGE, "start", "bold"))
    for k, r in enumerate([x for x in ib if 0.1 <= x <= 3.08]):
        b.append(text(40 + r * pxs, y1 + 22, str(k + 1), 15, ORANGE, "middle", "bold"))
    b.append(text(40, y1 - 12, "Неправильный ритм", 18, RED, "start", "bold"))
    b.append(text(920, y1 - 12, "6 комплексов за 3 с × 20 = 120", 17, INK, "end", "bold"))
    b.append(text(W / 2, 530, "Норма в покое: 60–90 (пособие) · тахикардия — более 100 по КР619_3, норма 60–100 (КР160_2)", 13.5, MUTED, "middle"))
    return svg("\n".join(b), "Подсчёт ЧСС")


# ---------- 4. Источник ритма ----------
def pacemakers():
    b = [text(W / 2, 38, "Где водитель ритма: смотрим на P во II отведении", 23, INK, "middle", "bold")]
    px = 3.0; pxs = 25 * px
    rows = [("Синусовый", "P+ перед каждым QRS · форма P одинакова", GREEN,
             rhythm([0.35 + 0.85 * k for k in range(9)])),
            ("Нижнепредсердный", "P− перед QRS, QRS узкий", BLUE,
             rhythm([0.35 + 0.9 * k for k in range(9)], p_mode="neg_before")),
            ("Из АВ-соединения", "P нет или P− после QRS · 40–60 в мин", ORANGE,
             rhythm([0.35 + 1.15 * k for k in range(7)], p_mode="neg_after")),
            ("Идиовентрикулярный", "QRS широкий, < 40 в мин · P сами по себе", RED,
             rhythm([0.5 + 1.75 * k for k in range(5)], wide=True, p_mode="dissoc", Pfix=[0.15 + 0.8 * k for k in range(11)]))]
    for i, (name, desc, col, fn) in enumerate(rows):
        y0 = 62 + i * 118
        gx, w, h = 300, 630, 32 * px
        b.append(grid(gx, y0, w, h, px))
        base = y0 + 21 * px
        b.append(trace(fn, gx, base, w, pxs, 10 * px, INK, 2))
        b.append(f'<rect x="30" y="{y0+4}" width="8" height="{h-8}" rx="4" fill="{col}"/>')
        b.append(text(50, y0 + 38, name, 18, col, "start", "bold"))
        words = desc.split(" · ")
        b.append(text(50, y0 + 62, words[0], 13, INK))
        if len(words) > 1: b.append(text(50, y0 + 81, words[1], 13, INK))
    b.append(text(W / 2, 534, "Пособие, гл. 4 · схема учебная", 13, MUTED, "middle"))
    return svg("\n".join(b), "Источник ритма")


# ---------- 5. ЭОС ----------
def axis():
    b = [text(W / 2, 40, "Электрическая ось сердца (угол α)", 24, INK, "middle", "bold")]
    cx, cy, r = 265, 278, 180

    def pt(ang, rr):
        a = math.radians(ang); return cx + rr * math.cos(a), cy + rr * math.sin(a)

    def sector(a1, a2, col, op=0.85):
        x1, y1 = pt(a1, r); x2, y2 = pt(a2, r)
        large = 1 if abs(a2 - a1) > 180 else 0
        sweep = 1 if a2 > a1 else 0
        return f'<path d="M{cx},{cy} L{x1:.1f},{y1:.1f} A{r},{r} 0 {large} {sweep} {x2:.1f},{y2:.1f} Z" fill="{col}" opacity="{op}"/>'
    b.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#f3f4f6"/>')
    b.append(sector(30, 69, "#86d0a2"))
    b.append(sector(70, 90, "#b8e3c7"))
    b.append(sector(0, 29, "#cfe9d8"))
    b.append(sector(91, 180, "#f6c2bd"))
    b.append(sector(-90, 0, "#c9d8f0"))
    for name, ang in (("I", 0), ("II", 60), ("III", 120), ("aVF", 90), ("aVL", -30), ("aVR", -150)):
        x, y = pt(ang, r + 4); b.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{INK}" stroke-width="1.6"/>')
        lx, ly = pt(ang, r + 30)
        b.append(text(lx, ly + 6, name, 16, INK, "middle", "bold"))
    for lab, ang, rr in (("норма", 50, 120), ("верт.", 80, 118), ("гориз.", 15, 150), ("вправо", 135, 130), ("влево", -45, 130)):
        x, y = pt(ang, rr); b.append(text(x, y + 5, lab, 14, INK, "middle", "bold"))
    for ang in (0, 30, 70, 90, 180, -90):
        x, y = pt(ang, r - 14)
        b.append(text(x, y + 5, (f"+{ang}°" if ang > 0 else f"{ang}°".replace('-', '−')), 12, MUTED, "middle"))
    # таблица быстрого определения
    tx, ty = 520, 90
    b.append(f'<rect x="{tx}" y="{ty}" width="410" height="380" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(tx + 18, ty + 32, "Быстро: QRS в I и aVF", 18, INK, "start", "bold"))
    rows = [("+", "+", "0…+90°: норма, гориз., верт.", GREEN), ("+", "−", "меньше 0°: влево", BLUE),
            ("−", "+", "больше +90°: вправо", RED), ("−", "−", "резко отклонена: проверить электроды", VIOLET)]
    b.append(text(tx + 40, ty + 70, "I", 16, MUTED, "middle", "bold")); b.append(text(tx + 90, ty + 70, "aVF", 16, MUTED, "middle", "bold"))
    for i, (a1, a2, s_, col) in enumerate(rows):
        y = ty + 112 + i * 62
        for xx, sg in ((tx + 40, a1), (tx + 90, a2)):
            b.append(f'<circle cx="{xx}" cy="{y-6}" r="16" fill="{GREEN if sg == "+" else RED}" opacity="0.18"/>')
            b.append(text(xx, y + 1, sg, 22, GREEN if sg == "+" else RED, "middle", "bold"))
        words = s_.split(": ")
        b.append(text(tx + 130, y - 8, words[0], 15, col, "start", "bold"))
        b.append(text(tx + 130, y + 14, words[1] if len(words) > 1 else "", 14, INK))
    b.append(text(tx + 18, ty + 362, "«+» — R больше S, «−» — S больше R", 13, MUTED))
    b.append(text(W / 2, 532, "Нормальная +30…+69° · вертикальная +70…+90° · горизонтальная 0…+29° (пособие, гл. 4)", 13.5, MUTED, "middle"))
    return svg("\n".join(b), "Электрическая ось сердца")


files = {"s02_algorithm.svg": algorithm(), "s03_regularity.svg": regularity(), "s04_hr.svg": hr(),
         "s06_pacemakers.svg": pacemakers(), "s08_axis.svg": axis()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
