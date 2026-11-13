"""SVG-схемы для части 5 цикла «ЭКГ» (ecg_af). Запуск: python3 ecg_part5_svg.py <папка>"""
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)


def bracket(x1, x2, y, label, col=BLUE, size=13, up=True):
    d = -1 if up else 1
    s = [f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="{col}" stroke-width="2.2"/>']
    for x in (x1, x2):
        s.append(f'<line x1="{x:.1f}" y1="{y-6}" x2="{x:.1f}" y2="{y+6}" stroke="{col}" stroke-width="2.2"/>')
    if label:
        s.append(text((x1 + x2) / 2, y + d * 9 + (0 if up else 8), label, size, col, "middle", "bold"))
    return "\n".join(s)


def qrs(lt, wide=False):
    if wide:
        return beat_p(lt, P=0.0, Q=-0.03, R=1.2, S=-0.3, T=-0.35, qrs=2.4)
    return beat_p(lt, P=0.0, Q=-0.06, R=1.0, S=-0.22, T=0.28)


def vent(rs, wide=False):
    def f(t):
        v = 0.0
        for r in rs:
            lt = t - r + 0.225
            if -0.3 < lt < 0.75:
                v += qrs(lt, wide)
        return v
    return f


def fib_waves(amp, seed):
    rnd = random.Random(seed)
    comps = [(rnd.uniform(5.5, 9.5), rnd.uniform(0, 6.28), rnd.uniform(0.5, 1.0)) for _ in range(7)]
    norm = sum(c[2] for c in comps)
    return lambda t: amp * sum(a * math.sin(2 * math.pi * fr * t + ph) for fr, ph, a in comps) / norm * 2.2


def saw(t, rate=5.0, amp=0.28):
    ph = (t * rate) % 1.0
    if ph < 0.78:
        v = 0.12 - 0.36 * ph / 0.78        # пологое нисходящее колено
    else:
        v = -0.24 + 0.36 * (ph - 0.78) / 0.22   # крутое восходящее
    return v * amp / 0.28


def irregular(t0, t1, lo, hi, seed):
    rnd = random.Random(seed); out = []; t = t0
    while t < t1:
        out.append(t); t += rnd.uniform(lo, hi)
    return out


def strip(b, x0, y0, w, rows_mm, px, fn, base_mm, lw=2.0):
    h = rows_mm * px
    b.append(grid(x0, y0, w - (w % px), h, px))
    base = y0 + base_mm * px
    b.append(trace(fn, x0, base, w - 2, 25 * px, 10 * px, INK, lw, 0.4))
    return base


# ---------- 1. ФП ----------
def af():
    b = [text(W / 2, 38, "Фибрилляция предсердий: нет P, хаотичные волны f, RR все разные", 21, INK, "middle", "bold")]
    px = 3.4; pxs = 25 * px
    rows = [("Крупноволновая", "волны f > 0,5 мм, 350–450 в мин", fib_waves(0.10, 3), irregular(0.25, 10.4, 0.42, 0.95, 11)),
            ("Мелковолновая", "волны f < 0,5 мм, 600–700 в мин, иногда почти не видны", fib_waves(0.03, 5), irregular(0.3, 10.4, 0.45, 1.0, 21))]
    for i, (name, desc, fw, rs) in enumerate(rows):
        y0 = 80 + i * 210
        vf = vent(rs)
        strip(b, 40, y0, 880, 36, px, lambda t, fw=fw, vf=vf: vf(t) + fw(t), 24)
        b.append(text(40, y0 - 12, name, 18, RED, "start", "bold"))
        b.append(text(920, y0 - 12, desc, 14.5, INK, "end"))
        for k in range(3, 6):
            b.append(bracket(40 + rs[k] * pxs, 40 + rs[k + 1] * pxs, y0 + 36 * px - 18,
                             f"{rs[k+1]-rs[k]:.2f}".replace('.', ','), BLUE, 12, False))
    b.append(text(W / 2, 520, "Волны f лучше видны в V1, V2, II, III, aVF · QRS обычно узкие (пособие, гл. 5.3.4)", 14, MUTED, "middle"))
    return svg("\n".join(b), "Фибрилляция предсердий")


# ---------- 2. ТП ----------
def flutter():
    b = [text(W / 2, 36, "Трепетание предсердий: «пила» волн F 250–400 в мин", 22, INK, "middle", "bold")]
    px = 3.0; pxs = 25 * px
    rate = 5.0  # 300 в минуту
    rows = [("2:1 — ЧСС 150", [0.32 + 0.4 * k for k in range(26)], "две волны F на один QRS,|одна прячется в QRS или T"),
            ("4:1 — ЧСС 75", [0.32 + 0.8 * k for k in range(13)], "«пила» видна отчётливо"),
            ("Неправильная форма", None, "проведение меняется:|2:1, 3:1, 4:1 —|ритм неправильный")]
    for i, (name, rs, desc) in enumerate(rows):
        if rs is None:
            rs, t = [], 0.32
            for k in [2, 3, 4, 2, 3, 2, 4, 3, 2, 3, 4, 2]:
                rs.append(t); t += k * 0.2
        y0 = 62 + i * 152
        vf = vent(rs)
        strip(b, 300, y0, 630, 36, px, lambda t, vf=vf: vf(t) + saw(t + 0.03, rate, 0.26), 24, 1.8)
        b.append(f'<rect x="30" y="{y0+6}" width="7" height="{36*px-12}" rx="3" fill="{ORANGE}"/>')
        b.append(text(48, y0 + 34, name, 18, ORANGE, "start", "bold"))
        for j, ln in enumerate(desc.split("|")):
            b.append(text(48, y0 + 58 + j * 19, ln, 13, INK))
    b.append(text(W / 2, 530, "Волны F лучше видны во II, III, aVF и V1 · QRS обычные (пособие, гл. 5.3.3)", 13.5, MUTED, "middle"))
    return svg("\n".join(b), "Трепетание предсердий")


# ---------- 3. Ловушка 150 ----------
def trap150():
    b = [text(W / 2, 38, "Регулярно 150 в минуту? Подумайте о трепетании 2:1", 22, INK, "middle", "bold")]
    px = 3.6; pxs = 25 * px
    rs = [0.3 + 0.4 * k for k in range(9)]
    t = rs[-1] + 0.8
    rs += [t + 0.8 * k for k in range(6)]
    vf = vent(rs)
    y0 = 80
    strip(b, 40, y0, 880, 40, px, lambda t: vf(t) + saw(t + 0.01, 5.0, 0.26), 26)
    xs = 40 + (rs[8] + 0.25) * pxs
    b.append(f'<rect x="{xs:.1f}" y="{y0+2}" width="{(920-xs):.1f}" height="{40*px-4}" fill="{BLUE}" opacity="0.07"/>')
    b.append(f'<line x1="{xs:.1f}" y1="{y0+2}" x2="{xs:.1f}" y2="{y0+40*px-2}" stroke="{BLUE}" stroke-width="2.5" stroke-dasharray="6 5"/>')
    b.append(text(xs - 8, y0 + 20, "до пробы: 2:1, ЧСС 150", 13.5, ORANGE, "end", "bold"))
    b.append(text(xs + 8, y0 + 20, "вагусная проба или #трифосаденин: 4:1 — «пила» видна", 13.5, BLUE, "start", "bold"))
    ty = 270
    b.append(f'<rect x="40" y="{ty}" width="880" height="225" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    items = [("ЧСС ровно около 150 и не меняется", "типично для ТП 2:1: 300 волн F, проводится каждая вторая"),
             ("Ищите вторую волну F", "во II, III, aVF и V1: она прячется в T или конце QRS"),
             ("Проба или #трифосаденин", "блок усиливается, ЧСС временно падает — «пила» открывается (КР619_3)"),
             ("Это меняет тактику", "ТП лечат как ФП: контроль ЧСС, 48 часов, антикоагуляция")]
    for j, (h, s_) in enumerate(items):
        y = ty + 42 + j * 50
        b.append(f'<circle cx="68" cy="{y-6}" r="8" fill="{ORANGE}"/>')
        b.append(text(88, y, h, 16, INK, "start", "bold"))
        b.append(text(88, y + 21, s_, 13.5, MUTED))
    return svg("\n".join(b), "Трепетание предсердий 2:1")


# ---------- 4. Алгоритм ----------
def algorithm():
    b = [text(W / 2, 36, "ФП или ТП на вызове (КР382_2)", 22, INK, "middle", "bold")]
    b.append('<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
             f'<path d="M0,0 L9,4.5 L0,9 z" fill="{MUTED}"/></marker></defs>')

    def box(x, y, w, h, title, lines, col, fill="#f8fafc"):
        s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{col}" stroke-width="2.5"/>',
             text(x + 14, y + 26, title, 16, col, "start", "bold")]
        for j, ln in enumerate(lines):
            s.append(text(x + 14, y + 48 + j * 19, ln, 13.3, INK))
        return "\n".join(s)

    def arrow(x1, y1, x2, y2, label=None, lx=0, ly=0, anchor="start"):
        s = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="2.5" marker-end="url(#ar)"/>']
        if label:
            s.append(text(lx, ly, label, 13, MUTED, anchor, "bold"))
        return "\n".join(s)
    b.append(box(330, 54, 300, 62, "ЭКГ в 12 отведениях", ["ФП / ТП, оценить ЧСС и гемодинамику"], INK))
    b.append(arrow(400, 116, 200, 156, "нестабильна", 262, 130, "end"))
    b.append(arrow(560, 116, 720, 156, "стабильна", 690, 130, "start"))
    b.append(box(30, 160, 360, 120, "Экстренная кардиоверсия", ["гипотония, обморок или предобморок,", "ишемия миокарда, отёк лёгких", "нет ЭИТ на месте — бригада СМП,", "экстренная госпитализация"], RED, "#fdf2f2"))
    b.append(box(540, 160, 390, 120, "1. Контроль ЧСС — всем", ["метопролол 5 мг в/в за 5 мин, повтор", "через 5 мин, максимум 20 мг", "или верапамил 5–10 мг в/в за 5 мин", "СН — дигоксин 0,25 мг в/в"], BLUE))
    b.append(arrow(735, 280, 735, 300))
    b.append(box(540, 302, 390, 82, "2. Сколько длится эпизод?", ["пароксизм часто проходит сам", "через несколько часов"], BLUE))
    b.append(arrow(640, 384, 600, 404))
    b.append(arrow(830, 384, 850, 404))
    b.append(box(440, 406, 244, 116, "< 48 часов", ["ритм можно восстановить:", "#гепарин 80 МЕ/кг, ≤ 5000 МЕ;", "прокаинамид или амиодарон"], GREEN))
    b.append(box(692, 406, 238, 116, "≥ 48 ч или неизвестно", ["ритм не восстанавливать,", "только контроль ЧСС;", "антикоагуляция — план"], ORANGE))
    b.append(box(30, 300, 380, 150, "ФП + WPW (широкий, нерегулярный)", ["не вводить: верапамил, дигоксин,", "β-блокаторы, амиодарон в/в", "нестабилен — кардиоверсия", "стабилен — прокаинамид"], VIOLET, "#f6f1fd"))
    b.append(text(220, 490, "Дозы — КР382_2, табл. П3, П11, П12", 13, MUTED, "middle"))
    b.append(text(220, 510, "препараты — если есть в укладке", 13, MUTED, "middle"))
    return svg("\n".join(b), "Алгоритм при ФП и ТП")


files = {"s02_af.svg": af(), "s04_flutter.svg": flutter(), "s06_trap150.svg": trap150(), "s09_algorithm.svg": algorithm()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
