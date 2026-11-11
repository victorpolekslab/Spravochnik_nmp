"""Генератор SVG-схем для части 1 цикла «ЭКГ» (ecg_record)."""
import math, random, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)

W, H = 960, 540
INK = "#1f2430"; MUTED = "#6b7280"; RED = "#d0342c"; BLUE = "#2f6fb5"
GREEN = "#2e8b57"; ORANGE = "#e08a00"; VIOLET = "#7b4bb7"; BROWN = "#8b5a2b"
GRID_S = "#f7d4d4"; GRID_B = "#eaa3a3"
FONT = "DejaVu Sans, Arial, sans-serif"


def svg(body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}" font-family="{FONT}">\n'
            f'<title>{title}</title>\n'
            f'<rect width="{W}" height="{H}" rx="18" fill="#ffffff"/>\n{body}\n</svg>\n')


def text(x, y, s, size=18, fill=INK, anchor="start", weight="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{s}</text>')


def gauss(t, a, mu, sd):
    return a * math.exp(-((t - mu) ** 2) / (2 * sd * sd))


def beat(t, scale=1.0):
    """Один кардиоцикл, t в секундах от начала цикла; результат в мВ."""
    v = (gauss(t, 0.15, 0.10, 0.022) + gauss(t, -0.10, 0.205, 0.007)
         + gauss(t, 1.05, 0.225, 0.009) + gauss(t, -0.28, 0.245, 0.009)
         + gauss(t, 0.32, 0.43, 0.04))
    return v * scale


def ecg(t, rr=0.8, scale=1.0):
    return beat(t % rr, scale)


def grid(x0, y0, w, h, px_mm):
    out = []
    n = int(w / px_mm)
    for i in range(n + 1):
        x = x0 + i * px_mm
        big = i % 5 == 0
        out.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0+h}" '
                   f'stroke="{GRID_B if big else GRID_S}" stroke-width="{1.2 if big else 0.6}"/>')
    m = int(h / px_mm)
    for j in range(m + 1):
        y = y0 + j * px_mm
        big = j % 5 == 0
        out.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+w}" y2="{y:.1f}" '
                   f'stroke="{GRID_B if big else GRID_S}" stroke-width="{1.2 if big else 0.6}"/>')
    return "\n".join(out)


def trace(fn, x0, y_base, w, px_per_s, px_per_mv, color=INK, width=2.2, step=0.5):
    pts = []
    x = 0.0
    while x <= w:
        t = x / px_per_s
        pts.append(f"{x0 + x:.1f},{y_base - fn(t) * px_per_mv:.1f}")
        x += step
    return (f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')


def calib(x, y_base, px_mm, color=INK):
    h = 10 * px_mm
    return (f'<polyline points="{x},{y_base} {x+px_mm},{y_base} {x+px_mm},{y_base-h} '
            f'{x+6*px_mm},{y_base-h} {x+6*px_mm},{y_base} {x+7*px_mm},{y_base}" '
            f'fill="none" stroke="{color}" stroke-width="2"/>')


# ---------- 1. Отведения: фронтальная и горизонтальная плоскости ----------
def leads():
    b = []
    b.append(text(W / 2, 44, "Как отведения «смотрят» на сердце", 26, INK, "middle", "bold"))
    # левая панель — шестиосевая система
    cx, cy, r = 250, 290, 165
    b.append(text(cx, 84, "Фронтальная плоскость: отведения от конечностей", 16, MUTED, "middle"))
    b.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fafafa" stroke="#d6d9de"/>')
    axes = [("I", 0, BLUE), ("II", 60, RED), ("III", 120, RED), ("aVF", 90, RED),
            ("aVL", -30, BLUE), ("aVR", -150, MUTED)]
    lab_off = {"I": (34, 0), "aVF": (0, 26), "II": (30, 18), "III": (30, 18), "aVL": (30, 0), "aVR": (30, 0)}
    for name, ang, col in axes:
        a = math.radians(ang)
        x1, y1 = cx + r * math.cos(a), cy + r * math.sin(a)
        x2, y2 = cx - r * math.cos(a), cy - r * math.sin(a)
        b.append(f'<line x1="{x2:.1f}" y1="{y2:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
                 f'stroke="{col}" stroke-width="1.4" stroke-dasharray="5 4" opacity="0.55"/>')
        b.append(f'<line x1="{cx}" y1="{cy}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{col}" stroke-width="3"/>')
        b.append(f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="5" fill="{col}"/>')
        rr = r + lab_off[name][0] + (lab_off[name][1] if name == "aVF" else 0)
        lx, ly = cx + rr * math.cos(a), cy + rr * math.sin(a) + 6
        sign = "+" if ang > 0 else ("−" if ang < 0 else "")
        b.append(text(lx, ly, name, 19, col, "middle", "bold"))
        b.append(text(lx, ly + 18, f"{sign}{abs(ang)}°", 13, MUTED, "middle"))
    # сердце в центре
    b.append(f'<ellipse cx="{cx}" cy="{cy}" rx="34" ry="26" fill="#f3c1bd" stroke="{RED}" '
             f'stroke-width="1.5" transform="rotate(35 {cx} {cy})"/>')
    # правая панель — горизонтальная плоскость
    hx, hy = 690, 300
    b.append(text(hx + 10, 84, "Горизонтальная плоскость: грудные отведения", 16, MUTED, "middle"))
    b.append(f'<ellipse cx="{hx}" cy="{hy}" rx="190" ry="125" fill="#fafafa" stroke="#d6d9de" stroke-width="2"/>')
    b.append(text(hx, hy - 100, "спереди", 13, MUTED, "middle"))
    b.append(text(hx, hy + 112, "сзади", 13, MUTED, "middle"))
    b.append(text(hx - 178, hy + 5, "справа", 13, MUTED, "start"))
    b.append(text(hx + 165, hy + 60, "слева", 13, MUTED, "end"))
    hcx, hcy = hx + 15, hy - 5
    b.append(f'<ellipse cx="{hcx}" cy="{hcy}" rx="62" ry="46" fill="#f3c1bd" stroke="{RED}" '
             f'stroke-width="1.5" transform="rotate(-25 {hcx} {hcy})"/>')
    # позиции V1–V6 на «грудной стенке» эллипса
    pos = [("V1", -100, VIOLET), ("V2", -80, VIOLET), ("V3", -58, GREEN), ("V4", -38, GREEN),
           ("V5", -14, BLUE), ("V6", 8, BLUE)]
    for name, ang, col in pos:
        a = math.radians(ang)
        ex, ey = hx + 190 * math.cos(a), hy + 125 * math.sin(a)
        b.append(f'<line x1="{hcx}" y1="{hcy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{col}" stroke-width="2.4"/>')
        b.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="7" fill="{col}"/>')
        tx, ty = hx + 218 * math.cos(a), hy + 150 * math.sin(a) + 6
        b.append(text(tx, ty, name, 17, col, "middle", "bold"))
    # легенда
    ly = 512
    leg = [(RED, "нижняя: II, III, aVF"), (BLUE, "боковая: I, aVL, V5–V6"),
           (VIOLET, "перегородка: V1–V2"), (GREEN, "передняя: V3–V4")]
    x = 40
    for col, s in leg:
        b.append(f'<rect x="{x}" y="{ly-13}" width="16" height="16" rx="3" fill="{col}"/>')
        b.append(text(x + 24, ly, s, 15, INK))
        x += 24 + len(s) * 8.8 + 30
    return svg("\n".join(b), "Отведения ЭКГ: фронтальная и горизонтальная плоскости")


# ---------- 2. Наложение электродов ----------
def electrodes():
    b = []
    b.append(text(W / 2, 44, "Куда ставить электроды", 26, INK, "middle", "bold"))
    # силуэт (вид спереди: правая сторона пациента — слева на рисунке)
    cx = 250
    b.append(f'<circle cx="{cx}" cy="105" r="34" fill="#eef0f3" stroke="#c4c9d1" stroke-width="2"/>')
    b.append(f'<rect x="{cx-75}" y="145" width="150" height="190" rx="40" fill="#eef0f3" stroke="#c4c9d1" stroke-width="2"/>')
    # руки
    b.append(f'<path d="M{cx-72},165 L{cx-120},300 L{cx-128},380" fill="none" stroke="#c4c9d1" stroke-width="26" stroke-linecap="round"/>')
    b.append(f'<path d="M{cx+72},165 L{cx+120},300 L{cx+128},380" fill="none" stroke="#c4c9d1" stroke-width="26" stroke-linecap="round"/>')
    # ноги
    b.append(f'<path d="M{cx-38},330 L{cx-48},480" fill="none" stroke="#c4c9d1" stroke-width="30" stroke-linecap="round"/>')
    b.append(f'<path d="M{cx+38},330 L{cx+48},480" fill="none" stroke="#c4c9d1" stroke-width="30" stroke-linecap="round"/>')
    lim = [(cx - 126, 362, RED, "R", "правая рука"), (cx + 126, 362, "#e6c200", "L", "левая рука"),
           (cx + 47, 462, GREEN, "F", "левая нога"), (cx - 47, 462, "#222222", "N", "правая нога")]
    for x, y, col, lab, name in lim:
        b.append(f'<circle cx="{x}" cy="{y}" r="15" fill="{col}" stroke="#ffffff" stroke-width="2.5"/>')
        b.append(text(x, y + 6, lab, 15, "#ffffff" if col != "#e6c200" else INK, "middle", "bold"))
    b.append(text(cx - 160, 366, "красный", 15, RED, "end", "bold"))
    b.append(text(cx + 160, 366, "жёлтый", 15, "#b39500", "start", "bold"))
    b.append(text(cx + 78, 492, "зелёный", 15, GREEN, "start", "bold"))
    b.append(text(cx - 78, 492, "чёрный", 15, INK, "end", "bold"))
    # порядок по часовой стрелке
    order = [(cx - 126, 330, "1"), (cx + 126, 330, "2"), (cx + 47, 430, "3"), (cx - 47, 430, "4")]
    for x, y, n in order:
        b.append(f'<circle cx="{x}" cy="{y}" r="10" fill="#ffffff" stroke="{MUTED}" stroke-width="1.5"/>')
        b.append(text(x, y + 5, n, 13, MUTED, "middle", "bold"))
    b.append(text(cx, 522, "«Каждая Женщина Злее Чёрта»: 1 → 4 по часовой", 14, MUTED, "middle"))
    # грудная клетка крупно
    gx, gy = 560, 80
    b.append(text(gx + 190, 84, "Грудные электроды", 18, INK, "middle", "bold"))
    b.append(f'<rect x="{gx}" y="{gy+20}" width="380" height="320" rx="26" fill="#fafafa" stroke="#d6d9de"/>')
    stx = gx + 120
    ribs = [gy + 95, gy + 130, gy + 165, gy + 200, gy + 235, gy + 270]  # 2–7 рёбра
    for y in ribs:
        b.append(f'<line x1="{gx+50}" y1="{y}" x2="{gx+365}" y2="{y+8}" stroke="#d9dce1" stroke-width="7" stroke-linecap="round"/>')
    b.append(f'<rect x="{stx-15}" y="{gy+45}" width="30" height="240" rx="9" fill="#e5e7eb" stroke="#cfd3d9"/>')
    b.append(text(stx, gy + 302, "грудина", 12, MUTED, "middle"))
    ics = {2: (ribs[0] + ribs[1]) / 2, 3: (ribs[1] + ribs[2]) / 2, 4: (ribs[2] + ribs[3]) / 2, 5: (ribs[3] + ribs[4]) / 2}
    for n, y in ics.items():
        b.append(text(gx + 14, y + 5, f"{n} м/р", 12.5, MUTED, "start"))
    lines = [(gx + 225, "СКЛ"), (gx + 290, "ППЛ"), (gx + 345, "СПЛ")]
    for x, lab in lines:
        b.append(f'<line x1="{x}" y1="{gy+45}" x2="{x}" y2="{gy+315}" stroke="#aab0b8" stroke-dasharray="4 4"/>')
        b.append(text(x, gy + 332, lab, 12, MUTED, "middle"))
    y4 = ics[4]; y5 = ics[5] + 3
    v4x = gx + 225
    vs = [("V1", stx - 28, y4, RED), ("V2", stx + 28, y4, "#e6c200"), ("V3", (stx + 28 + v4x) / 2, (y4 + y5) / 2, GREEN),
          ("V4", v4x, y5, BROWN), ("V5", gx + 290, y5, INK), ("V6", gx + 345, y5, VIOLET)]
    for name, x, y, col in vs:
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="{col}" stroke="#ffffff" stroke-width="2"/>')
        b.append(text(x, y - 17, name, 14, INK, "middle", "bold"))
    notes = ["V1, V2 — 4-е межреберье у краёв грудины", "V3 — посередине между V2 и V4",
             "V4 — 5-е межреберье по СКЛ", "V5, V6 — уровень V4: ППЛ и СПЛ"]
    for i, t in enumerate(notes):
        b.append(text(gx + 4, 448 + i * 21, t, 14, INK))
    return svg("\n".join(b), "Наложение электродов ЭКГ")


# ---------- 3. Скорость бумаги ----------
def speed():
    b = []
    b.append(text(W / 2, 40, "Одна и та же ЭКГ (ЧСС 75) на разной скорости", 24, INK, "middle", "bold"))
    px = 4.6  # px на мм
    x0, w = 60, 840
    for i, (spd, y0, lab, formula) in enumerate([(25, 80, "25 мм/с", "RR = 20 мм → 1500 / 20 = 75"),
                                                  (50, 310, "50 мм/с", "RR = 40 мм → 3000 / 40 = 75")]):
        h = 30 * px
        b.append(grid(x0, y0, w, h, px))
        base = y0 + 22 * px
        b.append(calib(x0 + 2 * px, base, px))
        px_s = spd * px
        b.append(trace(lambda t: ecg(t + 0.55, 0.8), x0 + 10 * px, base, w - 10 * px, px_s, 10 * px))
        b.append(text(x0, y0 - 10, lab, 20, RED, "start", "bold"))
        b.append(text(x0 + w, y0 - 10, formula, 17, INK, "end"))
        # скобка RR: пики R при t + 0.55 ≡ 0.225 (mod 0.8) → t = 0.475, 1.275 ...
        r1 = x0 + 10 * px + 0.475 * px_s
        r2 = r1 + 0.8 * px_s
        yb = y0 + 4 * px
        b.append(f'<line x1="{r1:.1f}" y1="{yb}" x2="{r2:.1f}" y2="{yb}" stroke="{BLUE}" stroke-width="2.5"/>')
        for rx in (r1, r2):
            b.append(f'<line x1="{rx:.1f}" y1="{yb-8}" x2="{rx:.1f}" y2="{yb+8}" stroke="{BLUE}" stroke-width="2.5"/>')
        b.append(text((r1 + r2) / 2, yb - 10, "RR", 16, BLUE, "middle", "bold"))
    # подсказка про клетки
    b.append(text(60, 520, "1 мм: 0,04 с на 25 мм/с · 0,02 с на 50 мм/с   |   большая клетка 5 мм: 0,2 с · 0,1 с   |   калибровка 1 мВ = 10 мм",
                  14.5, MUTED))
    return svg("\n".join(b), "ЭКГ на скорости 25 и 50 мм/с")


# ---------- 4. Помехи ----------
def artifacts():
    random.seed(7)
    b = []
    b.append(text(W / 2, 40, "Три главные помехи", 24, INK, "middle", "bold"))
    px = 3.6
    x0, w = 330, 600
    noise = [random.gauss(0, 1) for _ in range(4000)]
    # сгладим шум до «тремора» 6–12 Гц
    sm = []
    for i in range(len(noise)):
        sm.append(sum(noise[max(0, i - 3):i + 4]) / 7)

    def tremor(t):
        i = int(t * 1000) % len(sm)
        return sm[i] * 0.22

    rows = [
        ("Сетевая наводка", "частые правильные колебания", "заземление, убрать зарядки",
         lambda t: ecg(t, 0.8) + 0.07 * math.sin(2 * math.pi * 50 * t)),
        ("Дрейф изолинии", "линия «плывёт»", "контакт: спирт, гель",
         lambda t: ecg(t, 0.8) + 0.45 * math.sin(2 * math.pi * 0.35 * t + 1)),
        ("Мышечный тремор", "неправильные колебания", "согреть, руки вдоль тела",
         lambda t: ecg(t, 0.8) + tremor(t)),
    ]
    for i, (name, look, fix, fn) in enumerate(rows):
        y0 = 70 + i * 152
        h = 34 * px
        b.append(grid(x0, y0, w, h, px))
        base = y0 + 24 * px
        b.append(trace(fn, x0, base, w, 25 * px, 10 * px, INK, 1.8, 0.4))
        b.append(text(28, y0 + 40, name, 19, RED, "start", "bold"))
        b.append(text(28, y0 + 66, look, 14.5, INK))
        b.append(text(28, y0 + 92, "→ " + fix, 14.5, GREEN))
    b.append(text(W / 2, 528, "Тремор может имитировать ФП и трепетание: сверьте ленту с пульсом", 15, MUTED, "middle"))
    return svg("\n".join(b), "Помехи на ЭКГ")


# ---------- 5. Перепутанные электроды рук ----------
def reversal():
    b = []
    b.append(text(W / 2, 40, "Перепутаны электроды рук: красный ↔ жёлтый", 24, INK, "middle", "bold"))
    px = 3.4
    leads_ok = [("I", 0.6), ("aVR", -0.55), ("aVL", 0.35), ("V5", 1.3)]
    leads_bad = [("I", -0.6), ("aVR", 0.35), ("aVL", -0.55), ("V5", 1.3)]
    cols = [(150, "Правильно", GREEN), (560, "Перепутаны руки", RED)]
    for (x0, title, col), lst in zip(cols, (leads_ok, leads_bad)):
        b.append(text(x0 + 160, 85, title, 20, col, "middle", "bold"))
        for j, (name, sc) in enumerate(lst):
            y0 = 100 + j * 100
            w, h = 330, 26 * px
            b.append(grid(x0, y0, w, h, px))
            base = y0 + 15 * px
            b.append(trace(lambda t, s=sc: ecg(t + 0.5, 0.8, s), x0, base, w, 25 * px, 10 * px, INK, 2))
            changed = (lst is leads_bad) and name != "V5"
            b.append(text(x0 - 14, y0 + 52, name, 18, RED if changed else INK, "end", "bold"))
    b.append(text(W / 2, 512, "I — всё отрицательное, aVR и aVL поменялись местами, грудные (V5) — без изменений.", 15, INK, "middle"))
    b.append(text(W / 2, 532, "При декстрокардии изменились бы и грудные: R уменьшается от V1 к V6.", 14, MUTED, "middle"))
    return svg("\n".join(b), "Перепутанные электроды рук")


# ---------- 6. Дополнительные отведения ----------
def extra():
    b = []
    b.append(text(W / 2, 40, "Дополнительные отведения: правые и задние", 24, INK, "middle", "bold"))
    cx, cy, rx, ry = 350, 290, 260, 165
    b.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#fafafa" stroke="#c4c9d1" stroke-width="2"/>')
    b.append(text(cx, cy - ry + 26, "спереди", 13, MUTED, "middle"))
    b.append(f'<rect x="{cx-14}" y="{cy+ry-44}" width="28" height="32" rx="6" fill="#e5e7eb"/>')
    b.append(text(cx, cy + ry - 52, "позвоночник", 12, MUTED, "middle"))
    b.append(text(cx - rx + 14, cy + 50, "справа", 13, MUTED, "start"))
    b.append(text(cx + rx - 14, cy + 30, "слева", 13, MUTED, "end"))
    b.append(f'<ellipse cx="{cx+35}" cy="{cy-20}" rx="90" ry="66" fill="#f3c1bd" stroke="{RED}" stroke-width="1.5" transform="rotate(-20 {cx+35} {cy-20})"/>')
    b.append(f'<ellipse cx="{cx-8}" cy="{cy-44}" rx="46" ry="28" fill="#c9d8f0" stroke="{BLUE}" stroke-width="1.5" transform="rotate(-15 {cx-8} {cy-44})"/>')
    b.append(text(cx - 8, cy - 39, "ПЖ", 15, BLUE, "middle", "bold"))
    b.append(text(cx + 65, cy + 5, "ЛЖ", 15, RED, "middle", "bold"))

    def on(ang, k=1.0):
        a = math.radians(ang)
        return cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)

    std = [("V1", -100), ("V2", -80), ("V3", -62), ("V4", -45), ("V5", -22), ("V6", 0)]
    right = [("V3R", -118), ("V4R", -135)]
    back = [("V7", 28), ("V8", 52), ("V9", 74)]
    for group, col in ((std, "#9aa0a8"), (right, BLUE), (back, ORANGE)):
        for name, ang in group:
            x, y = on(ang)
            b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{col}" stroke="#ffffff" stroke-width="2"/>')
            a = math.radians(ang)
            tx, ty = cx + (rx + 30) * math.cos(a), cy + (ry + 22) * math.sin(a) + 6
            b.append(text(tx, ty, name, 15, col if col != "#9aa0a8" else MUTED, "middle", "bold"))
    x = 672
    b.append(f'<rect x="{x-14}" y="100" width="290" height="360" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(x, 132, "V3R–V4R", 20, BLUE, "start", "bold"))
    for i, t in enumerate(["справа, зеркально V3–V4", "→ правый желудочек", "нижний ИМпST — снять", "ST ↑ ≥ 1 мм = ИМ ПЖ"]):
        b.append(text(x, 160 + i * 23, t, 15, INK))
    b.append(text(x, 280, "V7–V9", 20, ORANGE, "start", "bold"))
    for i, t in enumerate(["на уровне V4–V6:", "V7 — задняя подмышечная", "V8 — лопаточная", "V9 — паравертебральная", "→ задняя стенка ЛЖ"]):
        b.append(text(x, 308 + i * 23, t, 15, INK))
    b.append(text(x, 444, "КР157_5", 13, MUTED))
    return svg("\n".join(b), "Дополнительные отведения V3R–V4R и V7–V9")


def smooth(e0, e1, x):
    if x <= e0: return 0.0
    if x >= e1: return 1.0
    u = (x - e0) / (e1 - e0)
    return u * u * (3 - 2 * u)


def beat_st(t, scale=1.0, st=0.0):
    """Кардиоцикл со смещением ST (мВ): от точки J с плавным переходом в T."""
    v = beat(t, scale)
    if st:
        env = smooth(0.238, 0.262, t) * (1 - smooth(0.40, 0.53, t))
        v += st * env
    return v


def inferior():
    b = []
    b.append(text(W / 2, 40, "Случай 2: подъём ST в II, III, aVF", 24, INK, "middle", "bold"))
    px = 4.4
    rows = [("II", 0.85, 0.42, RED, 0), ("III", 0.75, 0.48, RED, 1), ("aVF", 0.8, 0.45, RED, 2),
            ("I", 0.6, -0.2, BLUE, 3), ("aVL", 0.45, -0.25, BLUE, 4)]
    w, h = 400, 22 * px
    for name, sc, st, col, k in rows:
        colx = 90 if k < 3 else 545
        y0 = 70 + (k if k < 3 else k - 3) * 150
        b.append(grid(colx, y0, w, h, px))
        base = y0 + 13 * px
        b.append(trace(lambda t, s_=sc, st_=st: beat_st((t + 0.6) % 0.8, s_, st_), colx, base, w, 25 * px, 10 * px, INK, 2.3))
        b.append(text(colx - 12, y0 + 55, name, 20, col, "end", "bold"))
    b.append(text(290, 62, "подъём ST — нижняя стенка", 15, RED, "middle", "bold"))
    b.append(text(745, 62, "реципрокная депрессия ST", 15, BLUE, "middle", "bold"))
    x = 545
    b.append(f'<rect x="{x}" y="372" width="{w}" height="120" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(x + 16, 402, "«Зеркало» в I и aVL подтверждает ИМпST", 15, INK))
    b.append(text(x + 16, 432, "Дальше снять: V3R–V4R (ПЖ),", 15, INK, "start", "bold"))
    b.append(text(x + 16, 456, "V7–V9 (задняя стенка)", 15, INK, "start", "bold"))
    b.append(text(x + 16, 480, "схема учебная, амплитуды условные", 12.5, MUTED))
    return svg("\n".join(b), "Нижний ИМпST: подъём ST в II, III, aVF")


files = {"s03_leads.svg": leads(), "s04_electrodes.svg": electrodes(), "s06_speed.svg": speed(),
         "s07_artifacts.svg": artifacts(), "s09_reversal.svg": reversal(), "s11_inferior.svg": inferior(), "s12_extra_leads.svg": extra()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
