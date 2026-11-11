"""SVG-схемы для части 2 цикла «ЭКГ» (ecg_normal). Запуск: python3 ecg_part2_svg.py <папка>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)


def bracket(x1, x2, y, label, col=BLUE, size=15, up=True):
    d = -1 if up else 1
    s = [f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="{col}" stroke-width="2.2"/>']
    for x in (x1, x2):
        s.append(f'<line x1="{x:.1f}" y1="{y-7}" x2="{x:.1f}" y2="{y+7}" stroke="{col}" stroke-width="2.2"/>')
    s.append(text((x1 + x2) / 2, y + d * 10 + (0 if up else 8), label, size, col, "middle", "bold"))
    return "\n".join(s)


# ---------- 1. Размеченный комплекс ----------
def complex_():
    b = [text(W / 2, 40, "Из чего состоит ЭКГ", 26, INK, "middle", "bold")]
    px = 14.0          # 1 мм = 14 px
    x0, y0, w, h = 60, 60, 840, 30 * px
    b.append(grid(x0, y0, w, h, px))
    base = y0 + 20 * px
    pxs = 50 * px     # 50 мм/с
    fn = lambda t: beat_p(t, P=0.18, Q=-0.12, R=1.6, S=-0.4, T=0.45, U=0.06)
    off = 0.0
    x_start = x0 + 40
    b.append(f'<line x1="{x0}" y1="{base}" x2="{x0+w}" y2="{base}" stroke="{MUTED}" stroke-width="1" stroke-dasharray="6 5"/>')
    b.append(trace(lambda t: fn(t + off) if t + off < 1.05 else 0, x_start, base, 1.05 * pxs - 10, pxs, 10 * px, INK, 3.2))
    X = lambda t: x_start + (t - off) * pxs
    p_on, p_off, q_on, s_off, t_off = 0.05, 0.15, 0.20, 0.252, 0.53
    b.append(bracket(X(p_on), X(p_off), base + 66, "P ≤ 0,10 с", GREEN, 15, False))
    b.append(bracket(X(p_on), X(q_on), base + 104, "PQ 0,12–0,20 с", BLUE, 15, False))
    b.append(bracket(X(q_on), X(s_off), base + 66, "", RED, 15, False))
    b.append(text(X(s_off) + 10, base + 82, "QRS ≤ 0,10 с", 15, RED, "start", "bold"))
    b.append(bracket(X(q_on), X(t_off), y0 + 30, "QT — электрическая систола желудочков", VIOLET, 15, True))
    b.append(bracket(X(s_off), X(0.36), base - 40, "ST", ORANGE, 15, True))
    for lab, t, dy, dx in (("P", 0.10, -40, 0), ("Q", 0.200, 30, -6), ("R", 0.225, -200, -26), ("S", 0.25, 56, 22), ("T", 0.43, -78, 0), ("U", 0.59, -24, 0)):
        b.append(text(X(t) + dx, base + dy, lab, 20, INK, "middle", "bold"))
    b.append(f'<circle cx="{X(s_off):.1f}" cy="{base:.1f}" r="7" fill="none" stroke="{ORANGE}" stroke-width="3"/>')
    b.append(text(X(s_off) + 26, base + 26, "точка J", 14, ORANGE))
    b.append(text(x0 + w - 8, base - 8, "изолиния", 13, MUTED, "end"))
    b.append(text(W / 2, 520, "Скорость 50 мм/с · 1 мм = 0,02 с · схема учебная", 13, MUTED, "middle"))
    return svg("\n".join(b), "Элементы ЭКГ: зубцы, сегменты, интервалы")


# ---------- 2. Нормальная ЭКГ в 12 отведениях ----------
LEADS = {
    "I":   dict(P=0.10, Q=-0.05, R=0.70, S=-0.10, T=0.25),
    "II":  dict(P=0.15, Q=-0.05, R=1.10, S=-0.20, T=0.35),
    "III": dict(P=0.05, Q=-0.02, R=0.50, S=-0.20, T=0.08),
    "aVR": dict(P=-0.12, Q=-0.75, R=0.0, S=-0.10, T=-0.30),
    "aVL": dict(P=0.03, Q=-0.03, R=0.30, S=-0.20, T=0.10),
    "aVF": dict(P=0.11, Q=-0.03, R=0.80, S=-0.20, T=0.22),
    "V1":  dict(P=0.07, Q=0.0, R=0.20, S=-1.00, T=-0.08),
    "V2":  dict(P=0.10, Q=0.0, R=0.45, S=-1.30, T=0.45),
    "V3":  dict(P=0.10, Q=0.0, R=0.85, S=-0.85, T=0.50),
    "V4":  dict(P=0.10, Q=-0.03, R=1.40, S=-0.40, T=0.45),
    "V5":  dict(P=0.10, Q=-0.08, R=1.30, S=-0.15, T=0.35),
    "V6":  dict(P=0.10, Q=-0.08, R=1.00, S=-0.05, T=0.30),
}


def normal12():
    b = [text(W / 2, 38, "Нормальная ЭКГ в 12 отведениях", 24, INK, "middle", "bold")]
    px = 3.2
    order = [["I", "aVR", "V1", "V4"], ["II", "aVL", "V2", "V5"], ["III", "aVF", "V3", "V6"]]
    cw, rh = 222, 140
    x0, y0 = 30, 60
    for r, row in enumerate(order):
        for c, name in enumerate(row):
            gx, gy = x0 + c * (cw + 8), y0 + r * (rh + 8)
            b.append(grid(gx, gy, cw - (cw % px), rh - (rh % px), px))
            base = gy + rh * 0.58
            prm = LEADS[name]
            b.append(trace(lambda t, p=prm: beat_p((t + 0.62) % 0.8, **p), gx, base, cw - 4, 25 * px, 10 * px, INK, 1.9))
            col = RED if name == "aVR" else (VIOLET if name in ("III", "aVL", "V1") else INK)
            b.append(f'<rect x="{gx+4}" y="{gy+4}" width="{14 + 10*len(name)}" height="22" rx="5" fill="#ffffff" opacity="0.9"/>')
            b.append(text(gx + 9, gy + 21, name, 16, col, "start", "bold"))
    b.append(text(30, 512, "aVR: P, QRS и T отрицательные — норма", 15, RED, "start", "bold"))
    b.append(text(30, 533, "III, aVL, V1: T и P бывают сглаженными или отрицательными — вариант нормы", 14, VIOLET))
    b.append(text(930, 512, "R растёт от V1 к V4, S убывает", 15, INK, "end", "bold"))
    b.append(text(930, 533, "схема учебная", 13, MUTED, "end"))
    return svg("\n".join(b), "Нормальная ЭКГ в 12 отведениях")


# ---------- 3. Прогрессия R в грудных отведениях ----------
def progression():
    b = [text(W / 2, 40, "Грудные отведения: R растёт, S убывает", 24, INK, "middle", "bold")]
    px = 6.0
    cw = 140
    x0, gy, h = 40, 90, 300
    for i, name in enumerate(["V1", "V2", "V3", "V4", "V5", "V6"]):
        gx = x0 + i * (cw + 8)
        b.append(grid(gx, gy, cw - (cw % px), h - (h % px), px))
        base = gy + h * 0.55
        prm = LEADS[name]
        b.append(trace(lambda t, p=prm: beat_p(t + 0.02, **p), gx + 4, base, cw - 10, 230, 10 * px, INK, 2.6))
        col = ORANGE if name == "V3" else INK
        b.append(text(gx + cw / 2, gy - 12, name, 19, col, "middle", "bold"))
    # переходная зона
    tx = x0 + 2 * (cw + 8)
    b.append(f'<rect x="{tx-4}" y="{gy-34}" width="{cw+8}" height="{h+44}" rx="10" fill="none" stroke="{ORANGE}" stroke-width="2.5" stroke-dasharray="7 5"/>')
    b.append(text(tx + cw / 2, gy + h + 32, "переходная зона: R = S", 15, ORANGE, "middle", "bold"))
    # стрелки роста
    b.append('<defs><marker id="a2" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">'
             f'<path d="M0,0 L10,5 L0,10 z" fill="{RED}"/></marker>'
             '<marker id="a3" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">'
             f'<path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker></defs>')
    b.append(f'<line x1="60" y1="474" x2="470" y2="474" stroke="{RED}" stroke-width="3" marker-end="url(#a2)"/>')
    b.append(text(482, 480, "R растёт до V4, в V5–V6 чуть меньше", 15, RED))
    b.append(f'<line x1="60" y1="508" x2="470" y2="508" stroke="{BLUE}" stroke-width="3" marker-end="url(#a3)"/>')
    b.append(text(482, 514, "S уменьшается к V5–V6", 15, BLUE))
    return svg("\n".join(b), "Прогрессия зубца R в грудных отведениях")


# ---------- 4. Сегмент ST: как мерить и пороги ----------
def st():
    b = [text(W / 2, 40, "Подъём ST: где кончается норма", 24, INK, "middle", "bold")]
    px = 9.0
    x0, y0, w, h = 40, 70, 46 * px, 44 * px
    b.append(grid(x0, y0, w, h, px))
    base = y0 + 30 * px
    pxs = 50 * px
    fn = lambda t: beat_p(t, P=0.12, Q=-0.05, R=1.3, S=-0.35, T=0.45, st=0.2)
    b.append(trace(lambda t: fn(t + 0.04), x0 + 4, base, w - 8, pxs, 10 * px, INK, 3))
    X = lambda t: x0 + 4 + (t - 0.04) * pxs
    jx = X(0.252)
    jy = base - 0.2 * 10 * px
    b.append(f'<line x1="{x0}" y1="{base}" x2="{x0+w}" y2="{base}" stroke="{MUTED}" stroke-width="1.5" stroke-dasharray="6 5"/>')
    b.append(text(x0 + w - 8, base + 22, "изолиния (TP / PQ)", 13, MUTED, "end"))
    b.append(f'<circle cx="{jx:.1f}" cy="{jy:.1f}" r="7" fill="none" stroke="{ORANGE}" stroke-width="3"/>')
    b.append(text(jx + 12, jy - 12, "точка J", 15, ORANGE, "start", "bold"))
    rx_ = jx + 30
    b.append(f'<line x1="{rx_:.1f}" y1="{base}" x2="{rx_:.1f}" y2="{jy:.1f}" stroke="{RED}" stroke-width="3"/>')
    b.append(f'<line x1="{rx_-8:.1f}" y1="{jy:.1f}" x2="{rx_+8:.1f}" y2="{jy:.1f}" stroke="{RED}" stroke-width="3"/>')
    b.append(f'<line x1="{rx_-8:.1f}" y1="{base}" x2="{rx_+8:.1f}" y2="{base}" stroke="{RED}" stroke-width="3"/>')
    b.append(text(rx_, base + 46, "подъём 2 мм", 16, RED, "middle", "bold"))
    # таблица порогов
    tx, ty = 500, 90
    b.append(f'<rect x="{tx}" y="{ty}" width="430" height="380" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(tx + 18, ty + 34, "Критерий ИМпST по КР", 18, RED, "start", "bold"))
    b.append(text(tx + 18, ty + 58, "подъём в точке J в 2 смежных отведениях", 14, INK))
    rows = [("все отведения, кроме V2–V3", "≥ 1 мм"), ("V2–V3: мужчины ≥ 40 лет", "≥ 2 мм"),
            ("V2–V3: мужчины < 40 лет", "≥ 2,5 мм"), ("V2–V3: женщины", "≥ 1,5 мм")]
    for i, (a, v) in enumerate(rows):
        y = ty + 100 + i * 46
        b.append(f'<line x1="{tx+18}" y1="{y+16}" x2="{tx+412}" y2="{y+16}" stroke="#e2e8f0"/>')
        b.append(text(tx + 18, y + 4, a, 15, INK))
        b.append(text(tx + 412, y + 4, v, 18, RED, "end", "bold"))
    b.append(text(tx + 18, ty + 300, "Норма по пособию:", 15, GREEN, "start", "bold"))
    b.append(text(tx + 18, ty + 324, "конечности ±0,5 мм; V1–V3 подъём до 2 мм", 14, INK))
    b.append(text(tx + 18, ty + 360, "КР157_5 · без ГЛЖ и БЛНПГ", 13, MUTED))
    return svg("\n".join(b), "Подъём ST: измерение и пороги ИМпST")


# ---------- 5. Интервал QT ----------
def qt():
    b = [text(W / 2, 40, "Интервал QT и QTc", 24, INK, "middle", "bold")]
    px = 4.0
    pxs = 50 * px
    rows = [("Норма: QT 0,40 с при RR 1,0 с → QTc 400 мс", 0.40, GREEN),
            ("Удлинён: QT 0,56 с при RR 1,0 с → QTc 560 мс", 0.56, RED)]
    for i, (lab, qtv, col) in enumerate(rows):
        k = (qtv - 0.08) / 0.245
        y0 = 80 + i * 200
        w, h = 880, 34 * px
        b.append(grid(40, y0, w, h, px))
        base = y0 + 22 * px
        fn = lambda t, k=k: beat_p(t % 1.0, P=0.13, Q=-0.07, R=1.1, S=-0.25, T=0.35, qt=k)
        b.append(trace(lambda t: fn(t + 0.85), 40, base, w, pxs, 10 * px, INK, 2.3))
        b.append(text(40, y0 - 12, lab, 17, col, "start", "bold"))
        q_on = 40 + (1.0 - 0.85 + 0.205) * pxs
        b.append(bracket(q_on, q_on + qtv * pxs, y0 + 20, "QT", col, 15, False))
        r1 = 40 + (1.0 - 0.85 + 0.225) * pxs
        b.append(bracket(r1 + pxs, r1 + 2 * pxs, y0 + h - 14, "RR = 1,0 с", MUTED, 13, True))
    b.append(f'<rect x="40" y="470" width="880" height="56" rx="12" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(60, 496, "QTc = QT / √RR (Базетт)   ·   норма: мужчины 340–460 мс, женщины 340–480 мс", 15.5, INK, "start", "bold"))
    b.append(text(60, 516, "более 500 мс — патологически удлинён: риск ЖТ типа «пируэт» (КР569_2) · 50 мм/с", 14.5, RED))
    return svg("\n".join(b), "Интервал QT: норма и удлинение")


files = {"s02_complex.svg": complex_(), "s04_normal12.svg": normal12(), "s07_progression.svg": progression(),
         "s08_st.svg": st(), "s10_qt.svg": qt()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
