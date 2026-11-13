"""SVG-схемы для части 9 цикла «ЭКГ» (ecg_bbb). Запуск: python3 ecg_part9_svg.py <папка>"""
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)

G = gauss


def P(lt):
    return G(lt, 0.13, 0.0, 0.022)


# Комплексы: lt — время от начала QRS (с)
def n_v1(lt):  # норма V1: rS, T+
    return G(lt, 0.25, 0.02, 0.008) + G(lt, -0.9, 0.05, 0.012) + G(lt, 0.15, 0.25, 0.045)


def n_v6(lt):  # норма V6: qRs
    return G(lt, -0.08, 0.005, 0.006) + G(lt, 1.1, 0.03, 0.009) + G(lt, -0.15, 0.055, 0.008) + G(lt, 0.3, 0.25, 0.045)


def rbbb_v1(lt):  # rSR', T−
    return (G(lt, 0.3, 0.015, 0.008) + G(lt, -0.4, 0.045, 0.01) + G(lt, 0.95, 0.09, 0.016)
            + G(lt, -0.25, 0.3, 0.05))


def rbbb_v6(lt):  # qRS с широким S
    return (G(lt, -0.08, 0.005, 0.006) + G(lt, 1.0, 0.03, 0.009) + G(lt, -0.35, 0.085, 0.024)
            + G(lt, 0.25, 0.3, 0.05))


def lbbb_v1(lt):  # широкий QS, ST↑, T+
    return (G(lt, -1.1, 0.06, 0.028) + G(lt, 0.15, 0.06, 0.006) + 0.12 * smooth(0.11, 0.14, lt) * (1 - smooth(0.2, 0.3, lt))
            + G(lt, 0.4, 0.3, 0.05))


def lbbb_v6(lt):  # широкий зазубренный R, ST↓, T−
    return (G(lt, 0.8, 0.04, 0.022) + G(lt, 0.95, 0.095, 0.022) - 0.12 * smooth(0.13, 0.16, lt) * (1 - smooth(0.22, 0.3, lt))
            + G(lt, -0.35, 0.3, 0.05))


def qrs_fn(kind, amp=1.0):
    def f(lt):
        return amp * kind(lt)
    return f


def beats(qrs, rr=1.0, pq=0.16, n=3, t0=0.15):
    def f(t):
        v = 0.0
        for k in range(n):
            p = t0 + k * rr
            if abs(t - p) < 0.1:
                v += P(t - p)
            lt = t - (p + pq)
            if -0.05 < lt < 0.6:
                v += qrs(lt)
        return v
    return f


def panel(b, x0, y0, w, h, px, fn, base_mm, title, col=INK, sub=None):
    b.append(grid(x0, y0, w - (w % px), h, px))
    b.append(trace(fn, x0, y0 + base_mm * px, w - 2, 25 * px, 10 * px, INK, 2.0, 0.4))
    b.append(text(x0 + 8, y0 + 20, title, 15, col, "start", "bold"))
    if sub:
        b.append(text(x0 + w - 8, y0 + 20, sub, 12.5, MUTED, "end"))


def box(x, y, w, h, title, lines, col, fill="#f8fafc", size=13.3):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{col}" stroke-width="2.5"/>',
         text(x + 14, y + 26, title, 16, col, "start", "bold")]
    for j, ln in enumerate(lines):
        s.append(text(x + 14, y + 48 + j * 19, ln, size, INK))
    return "\n".join(s)


def bracket(x1, x2, y, label, col=BLUE, size=12.5, up=True):
    d = -1 if up else 1
    s = [f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="{col}" stroke-width="2"/>']
    for x in (x1, x2):
        s.append(f'<line x1="{x:.1f}" y1="{y-5}" x2="{x:.1f}" y2="{y+5}" stroke="{col}" stroke-width="2"/>')
    if label:
        s.append(text((x1 + x2) / 2, y + d * 9 + (0 if up else 7), label, size, col, "middle", "bold"))
    return "\n".join(s)


def four(title, rows, notes, fname_title):
    b = [text(W / 2, 36, title, 22, INK, "middle", "bold")]
    px = 3.6
    for i, (lab, col, f1, f2) in enumerate(rows):
        y0 = 56 + i * 166
        panel(b, 40, y0, 430, 150, px, beats(f1, 1.0, 0.16, 5, 0.12), 22, f"{lab} · V1", col)
        panel(b, 490, y0, 430, 150, px, beats(f2, 1.0, 0.16, 5, 0.12), 26, f"{lab} · V6", col)
    for j, ln in enumerate(notes):
        b.append(text(W / 2, 410 + j * 26, ln[0], 14.5 if j == 0 else 13.8, ln[1], "middle", "bold" if ln[1] == RED else "normal"))
    return svg("\n".join(b), fname_title)


# ---------- 1. БПНПГ ----------
def rbbb():
    return four("Блокада правой ножки пучка Гиса",
                [("Норма", GREEN, n_v1, n_v6), ("Полная БПНПГ", RED, rbbb_v1, rbbb_v6)],
                [("V1: rSR' — «буква М», R' > r;  V6, I: широкий зазубренный S", RED),
                 ("QRS ≥ 0,12 с — полная блокада; 0,09–0,11 с — неполная (rSr' в V1)", INK),
                 ("В V1 ST и T направлены против R' (T отрицательный)", INK),
                 ("Пособие, гл. 6.7.1.1", MUTED),
                 ("", INK)], "Блокада правой ножки")


# ---------- 2. БЛНПГ ----------
def lbbb():
    return four("Блокада левой ножки пучка Гиса",
                [("Норма", GREEN, n_v1, n_v6), ("Полная БЛНПГ", RED, lbbb_v1, lbbb_v6)],
                [("V5, V6, I, aVL: широкий R с расщеплённой вершиной, q нет;  V1, V2: широкий QS или rS", RED),
                 ("QRS ≥ 0,12 с; ST и T дискордантны: в V6 ST ниже изолинии, T отрицательный", INK),
                 ("Пособие, гл. 6.7.2.1", MUTED),
                 ("Остро возникшая БЛНПГ с симптомами ишемии = ОКС с подъёмом ST (КР157_5)", RED),
                 ("", INK)], "Блокада левой ножки")


# ---------- 3. Блокады ветвей левой ножки ----------
def fascicular():
    b = [text(W / 2, 36, "Блокады ветвей левой ножки: смотрим на ось", 22, INK, "middle", "bold")]
    px = 2.8

    def mk(r, s, q=0.0):
        return lambda lt: G(lt, -q, 0.005, 0.006) + G(lt, r, 0.03, 0.009) + G(lt, -s, 0.055, 0.009) + G(lt, 0.2, 0.25, 0.045)
    rows = [("Передняя ветвь (ЛПВ)", ORANGE, [("I", mk(0.9, 0.05, 0.12)), ("II", mk(0.35, 0.6)), ("III", mk(0.25, 1.0))], "ось < −30°: в I, aVL — qR; во II, III, aVF — rS", -50),
            ("Задняя ветвь (ЛЗВ)", VIOLET, [("I", mk(0.25, 0.9)), ("II", mk(0.8, 0.15, 0.1)), ("III", mk(1.0, 0.05, 0.12))], "ось > +120°: в I, aVL — rS; в III, aVF — qR", 125)]
    for i, (name, col, leads, desc, ang) in enumerate(rows):
        y0 = 74 + i * 196
        b.append(text(40, y0 - 6, name, 17, col, "start", "bold"))
        for j, (ln, f) in enumerate(leads):
            x0 = 40 + j * 200
            panel(b, x0, y0 + 4, 190, 126, px, beats(f, 0.9, 0.16, 3, 0.1), 26, ln, col)
        b.append(text(40, y0 + 154, desc, 14, INK))
        cx, cy, R = 800, y0 + 70, 62
        b.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5"/>')
        b.append(f'<line x1="{cx-R}" y1="{cy}" x2="{cx+R}" y2="{cy}" stroke="#cbd5e1"/>')
        b.append(f'<line x1="{cx}" y1="{cy-R}" x2="{cx}" y2="{cy+R}" stroke="#cbd5e1"/>')
        a = math.radians(ang)
        ex, ey = cx + (R - 6) * math.cos(a), cy + (R - 6) * math.sin(a)
        b.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{col}" stroke-width="4" stroke-linecap="round"/>')
        b.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{col}"/>')
        b.append(text(cx + R + 8, cy + 5, "0°", 12, MUTED))
        b.append(text(cx, cy + R + 16, "+90°", 12, MUTED, "middle"))
        b.append(text(cx, cy - R - 6, "−90°", 12, MUTED, "middle"))
    b.append(text(W / 2, 498, "QRS при изолированной блокаде ветви узкий: 0,08–0,11 с (пособие, гл. 6.7.1.2–6.7.1.3)", 14, INK, "middle"))
    b.append(text(W / 2, 522, "Сочетание БПНПГ с блокадой ветви левой ножки — двухпучковая блокада", 14, RED, "middle", "bold"))
    return svg("\n".join(b), "Блокады ветвей левой ножки")


# ---------- 4. WPW и CLC ----------
def delta_qrs(lt):
    return (G(lt, 0.32, 0.03, 0.022) + G(lt, 0.9, 0.075, 0.012) + G(lt, -0.2, 0.105, 0.012)
            + G(lt, -0.15, 0.32, 0.05))


def norm_qrs(lt):
    return G(lt, -0.08, 0.005, 0.006) + G(lt, 1.0, 0.03, 0.009) + G(lt, -0.2, 0.055, 0.009) + G(lt, 0.3, 0.25, 0.045)


def preexc():
    b = [text(W / 2, 36, "Синдромы предвозбуждения: WPW и CLC", 22, INK, "middle", "bold")]
    px = 5.2; pxs = 25 * px
    rows = [("Норма", GREEN, norm_qrs, 0.16, "PQ 0,16; QRS 0,08"),
            ("WPW", RED, delta_qrs, 0.09, "PQ < 0,12; дельта-волна; QRS > 0,12"),
            ("CLC", ORANGE, norm_qrs, 0.09, "PQ < 0,12; QRS узкий")]
    for i, (name, col, q, pq, sub) in enumerate(rows):
        x0 = 30 + i * 308
        fn = beats(q, 1.6, pq, 1, 0.12)
        b.append(grid(x0, 56, 296 - (296 % px), 220, px))
        b.append(trace(fn, x0, 56 + 30 * px, 294, pxs, 10 * px, INK, 2.4, 0.3))
        b.append(text(x0 + 10, 80, name, 19, col, "start", "bold"))
        b.append(text(x0 + 148, 300, sub, 13.3, INK, "middle", "bold"))
        p0 = x0 + (0.12 - 0.04) * pxs; r0 = x0 + (0.12 + pq) * pxs
        b.append(bracket(p0, r0, 56 + 30 * px + 30, "PQ", BLUE, 12.5, False))
        if name == "WPW":
            dx = x0 + (0.12 + pq + 0.03) * pxs
            b.append(f'<line x1="{dx+40:.1f}" y1="{56+30*px-90:.1f}" x2="{dx+4:.1f}" y2="{56+30*px-22:.1f}" stroke="{RED}" stroke-width="2" marker-end="url(#ar)"/>')
            b.append(text(dx + 44, 56 + 30 * px - 94, "дельта-волна", 13.5, RED, "start", "bold"))
    b.append('<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
             f'<path d="M0,0 L9,4.5 L0,9 z" fill="{RED}"/></marker></defs>')
    b.append(box(30, 326, 440, 196, "WPW (пучок Кента)", ["импульс идёт в обход АВ-узла,", "желудочек начинает возбуждаться раньше", "ST и T часто дискордантны QRS", "ЭКГ без приступов — феномен WPW,", "с пароксизмами НЖТ — синдром WPW", "(пособие, КР619_3)"], RED, "#fdf2f2"))
    b.append(box(490, 326, 440, 196, "CLC (пучок Джеймса)", ["пучок шунтирует АВ-узел, дальше —", "обычный путь, поэтому QRS узкий,", "дельта-волны нет", "нередки пароксизмы НЖТ и ФП", "(пособие, гл. 6.8.2)"], ORANGE, "#fff8eb"))
    return svg("\n".join(b), "WPW и CLC")


# ---------- 5. Тахикардии при WPW ----------
def wpw_tachy():
    b = [text(W / 2, 34, "Тахикардии при WPW: три варианта (КР619_3, КР382_2)", 21, INK, "middle", "bold")]
    px = 2.6; pxs = 25 * px

    def narrow(lt):
        return G(lt, 1.0, 0.03, 0.009) + G(lt, -0.2, 0.055, 0.009) + G(lt, 0.25, 0.17, 0.035) - G(lt, 0.08, 0.13, 0.015)

    def wide(lt):
        return G(lt, 0.4, 0.03, 0.025) + G(lt, 1.0, 0.08, 0.02) + G(lt, -0.3, 0.13, 0.02) + G(lt, -0.4, 0.2, 0.035)

    def reg(q, rr):
        def f(t):
            v = 0.0
            k0 = int(t / rr)
            for k in (k0 - 1, k0):
                lt = t - k * rr
                if 0 <= lt < rr + 0.1:
                    v += q(lt)
            return v
        return f
    rnd = random.Random(5)
    rs = []; t = 0.05
    while t < 9:
        rs.append((t, rnd.random())); t += rnd.uniform(0.2, 0.42)

    def afw(t):
        v = 0.0
        for r, m in rs:
            lt = t - r
            if -0.05 < lt < 0.45:
                v += (m * wide(lt) + (1 - m) * narrow(lt)) * (0.85 + 0.3 * m)
        return v
    rows = [("Ортодромная АВРТ", "QRS узкие, ритм правильный", reg(narrow, 0.3), GREEN,
             ["вагусные приёмы", "#трифосаденин 10–20 мг в/в болюсом", "затем верапамил или метопролол"]),
            ("Антидромная АВРТ", "QRS широкие, ритм правильный", reg(wide, 0.3), ORANGE,
             ["вагусные приёмы", "пропафенон в/в или синхр. ЭИТ;", "амиодарон — если другое неэффективно"]),
            ("ФП + WPW", "широкие, разные, нерегулярные", afw, RED,
             ["нестабилен — ЭИТ; стабилен — прокаинамид", "нельзя: верапамил, дигоксин, β-блокаторы,", "амиодарон в/в, #трифосаденин (КР569_2)"])]
    for i, (name, sub, fn, col, act) in enumerate(rows):
        y0 = 54 + i * 160
        b.append(grid(30, y0, 520 - (520 % px), 130, px))
        b.append(trace(fn, 30, y0 + 28 * px, 518, pxs, 10 * px, INK, 1.8, 0.4))
        b.append(text(38, y0 + 18, name, 15, col, "start", "bold"))
        b.append(text(545, y0 + 18, sub, 12.5, MUTED, "end"))
        b.append(f'<rect x="566" y="{y0}" width="364" height="130" rx="12" fill="#f8fafc" stroke="{col}" stroke-width="2"/>')
        for j, a in enumerate(act):
            b.append(text(580, y0 + 32 + j * 24, a, 13.3, INK))
    b.append(text(W / 2, 530, "ФП с высокой ЧСС при WPW может перейти в ФЖ — ЭИТ должна быть доступна (КР619_3)", 13.5, RED, "middle", "bold"))
    return svg("\n".join(b), "Тахикардии при WPW")


files = {"s02_rbbb.svg": rbbb(), "s04_lbbb.svg": lbbb(), "s06_fascicular.svg": fascicular(),
         "s08_wpw.svg": preexc(), "s10_wpw_tachy.svg": wpw_tachy()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
