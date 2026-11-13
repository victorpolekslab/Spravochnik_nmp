"""SVG-схемы для части 10 цикла «ЭКГ» (ecg_ischemia). Запуск: python3 ecg_part10_svg.py <папка>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)
G = gauss

MARKER = ('<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
          f'<path d="M0,0 L9,4.5 L0,9 z" fill="{MUTED}"/></marker></defs>')


def cx(lt, R=1.0, S=-0.2, Q=-0.06, st=0.0, T=0.3, tsym=False, tw=0.045, slope=0.0, rnoise=0.0):
    """Комплекс; lt — время от начала цикла, R при 0.225. st — смещение ST (мВ); slope — наклон ST."""
    c = 0.225
    v = G(lt, 0.13, 0.10, 0.022)
    v += G(lt, Q, c - 0.02, 0.007) + G(lt, R, c, 0.009) + G(lt, S, c + 0.02, 0.009)
    j = c + 0.04
    tc = c + 0.22
    if tsym:
        v += G(lt, T, tc, tw)
    else:  # асимметричный: пологое восхождение, крутое снижение
        sd = tw * 1.25 if lt < tc else tw * 0.7
        v += T * math.exp(-((lt - tc) ** 2) / (2 * sd * sd))
    if st or slope:
        w = smooth(j - 0.012, j + 0.004, lt) * (1 - smooth(tc - 0.02, tc + 0.09, lt))
        v += (st + slope * max(0.0, lt - j)) * w
    return v


def beats(f, rr=0.95, n=4, t0=0.05):
    def g(t):
        v = 0.0
        k = int((t - t0) / rr)
        for kk in (k - 1, k, k + 1):
            if 0 <= kk < n:
                lt = t - t0 - kk * rr
                if -0.05 < lt < rr + 0.2:
                    v += f(lt)
        return v
    return g


def panel(b, x0, y0, w, h, px, fn, base_mm, title, col=INK, sub=None, lw=2.1):
    b.append(grid(x0, y0, w - (w % px), h, px))
    b.append(trace(fn, x0, y0 + base_mm * px, w - 2, 25 * px, 10 * px, INK, lw, 0.3))
    b.append(text(x0 + 8, y0 + 20, title, 15, col, "start", "bold"))
    if sub:
        b.append(text(x0 + w / 2, y0 + h + 20, sub, 13, INK, "middle"))


def box(x, y, w, h, title, lines, col, fill="#f8fafc", size=13.3):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{col}" stroke-width="2.5"/>',
         text(x + 14, y + 26, title, 16, col, "start", "bold")]
    for j, ln in enumerate(lines):
        s.append(text(x + 14, y + 48 + j * 19, ln, size, INK))
    return "\n".join(s)


def arrow(x1, y1, x2, y2, label=None, lx=0, ly=0, anchor="start"):
    s = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="2.5" marker-end="url(#ar)"/>']
    if label:
        s.append(text(lx, ly, label, 13, MUTED, anchor, "bold"))
    return "\n".join(s)


# ---------- 1. Зубец T ----------
def twaves():
    b = [text(W / 2, 36, "Зубец T при ишемии", 22, INK, "middle", "bold")]
    px = 4.0
    items = [("Норма", GREEN, lambda lt: cx(lt, T=0.3), "асимметричный, пологое начало"),
             ("Высокий коронарный T", RED, lambda lt: cx(lt, T=0.75, tsym=True, tw=0.04), "высокий, симметричный, острый"),
             ("Отрицательный коронарный T", BLUE, lambda lt: cx(lt, T=-0.45, tsym=True, tw=0.04), "симметричный, заострённый"),
             ("Двухфазный T", ORANGE, lambda lt: cx(lt, T=0.0) + G(lt, 0.22, 0.40, 0.03) + G(lt, -0.25, 0.49, 0.03), "граница зоны ишемии")]
    for i, (name, col, f, sub) in enumerate(items):
        x0 = 30 + (i % 2) * 460; y0 = 56 + (i // 2) * 200
        panel(b, x0, y0, 440, 150, px, beats(f, 0.9, 3, 0.05), 24, name, col, sub)
    b.append(f'<rect x="30" y="460" width="900" height="66" rx="12" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(48, 486, "Высокий T в грудных — субэндокардиальная ишемия передней стенки или ишемия задней (зеркально)", 13.5, INK))
    b.append(text(48, 508, "Отрицательный коронарный T — ишемия передней стенки. Высокий T бывает и в норме у молодых (пособие, гл. 8.1.1)", 13.5, INK))
    return svg("\n".join(b), "Зубец T при ишемии")


# ---------- 2. Как мерить ST ----------
def measure():
    b = [text(W / 2, 36, "Как измерить смещение ST", 22, INK, "middle", "bold")]
    px = 9.0; pxs = 25 * px
    f = lambda lt: cx(lt, R=1.2, S=-0.1, st=0.2, T=0.45)
    x0, y0, w, h = 30, 56, 520, 360
    b.append(grid(x0, y0, w - (w % px), h, px))
    base = y0 + 28 * px
    sh = 0.75
    b.append(trace(lambda t: f(t - sh), x0, base, w - 2, pxs, 10 * px, INK, 2.6, 0.25))
    xj = x0 + (sh + 0.265) * pxs
    b.append(f'<line x1="{x0}" y1="{base}" x2="{x0+w-10}" y2="{base}" stroke="{BLUE}" stroke-width="1.8" stroke-dasharray="7 5"/>')
    b.append(text(x0 + 10, base + 24, "изолиния — по сегменту PQ (TP)", 13.5, BLUE, "start", "bold"))
    yj = base - 0.2 * 10 * px
    b.append(f'<circle cx="{xj:.1f}" cy="{yj:.1f}" r="6" fill="{RED}"/>')
    b.append(text(xj - 14, yj - 70, "точка J — конец QRS", 13.5, RED, "end", "bold"))
    b.append(f'<line x1="{xj-16:.1f}" y1="{yj-64:.1f}" x2="{xj-4:.1f}" y2="{yj-8:.1f}" stroke="{RED}" stroke-width="1.6"/>')
    xb = xj + 150
    b.append(f'<line x1="{xj+8:.1f}" y1="{yj:.1f}" x2="{xb+6:.1f}" y2="{yj:.1f}" stroke="{RED}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    b.append(f'<line x1="{xb:.1f}" y1="{base}" x2="{xb:.1f}" y2="{yj:.1f}" stroke="{RED}" stroke-width="2.5"/>')
    for yy in (base, yj):
        b.append(f'<line x1="{xb-6:.1f}" y1="{yy:.1f}" x2="{xb+6:.1f}" y2="{yy:.1f}" stroke="{RED}" stroke-width="2.5"/>')
    b.append(text(xb, yj - 12, "2 мм = 0,2 мВ", 14, RED, "middle", "bold"))
    b.append(box(570, 56, 360, 250, "Подъём ST (КР157_5)", [
        "в точке J, минимум в 2 смежных",
        "отведениях:",
        "• все отведения — ≥ 1 мм",
        "• V2–V3: мужчины ≥ 40 лет — ≥ 2 мм",
        "• V2–V3: мужчины < 40 лет — ≥ 2,5 мм",
        "• V2–V3: женщины — ≥ 1,5 мм",
        "критерии — без ГЛЖ и БЛНПГ",
        "стойкий > 20 мин — ОКСпST"], RED, "#fdf2f2"))
    b.append(box(570, 318, 360, 150, "Депрессия ST, инверсия T", [
        "ОКСбпST (КР154_4): ST ↓ ≥ 0,5 мм",
        "горизонтальная или косонисходящая;",
        "T отрицательный > 1 мм",
        "в 2 смежных отведениях"], BLUE, "#f3f7fc"))
    b.append(text(290, 450, "1 мм = 0,1 мВ при стандартном усилении 10 мм/мВ", 13.5, INK, "middle"))
    b.append(text(290, 474, "Смежные: II, III, aVF · I, aVL · V1–V6 по соседству", 13.5, INK, "middle"))
    return svg("\n".join(b), "Как измерить смещение ST")


# ---------- 3. Виды депрессии ST ----------
def depression():
    b = [text(W / 2, 36, "Депрессия ST: какая говорит об ишемии", 22, INK, "middle", "bold")]
    px = 4.2
    items = [("Горизонтальная", RED, lambda lt: cx(lt, st=-0.15, T=0.2), "ишемическая"),
             ("Косонисходящая", RED, lambda lt: cx(lt, st=-0.07, slope=-0.7, T=-0.1), "ишемическая"),
             ("Косовосходящая", ORANGE, lambda lt: cx(lt, st=-0.18, slope=1.4, T=0.3), "менее специфична")]
    for i, (name, col, f, sub) in enumerate(items):
        x0 = 30 + i * 306
        panel(b, x0, 56, 294, 180, px, beats(f, 0.9, 2, 0.05), 25, name, col, sub)
    b.append(box(30, 290, 440, 230, "ОКС без подъёма ST (КР154_4)", [
        "депрессия ST ≥ 0,5 мм в 2 смежных",
        "отведениях — особенно горизонтальная",
        "или косонисходящая",
        "инверсия T > 1 мм в 2 смежных",
        "глубокие (≥ 2 мм) симметричные T в",
        "грудных — высокая вероятность ишемии",
        "ST < 0,5 мм, T < 1 мм — неспецифично"], BLUE, "#f3f7fc"))
    b.append(box(490, 290, 440, 230, "Приступ стенокардии (КР155_2)", [
        "специфично: горизонтальная или",
        "косонисходящая депрессия ST ≥ 1 мм",
        "длительностью ≥ 0,06–0,08 с от точки J",
        "ЭКГ во время боли важнее ЭКГ покоя",
        "транзиторный подъём ST при приступе —",
        "вазоспазм (стенокардия Принцметала)"], ORANGE, "#fff8eb"))
    return svg("\n".join(b), "Виды депрессии ST")


# ---------- 4. Реципрокные изменения ----------
def reciprocal():
    b = [text(W / 2, 36, "Подъём ST и зеркальная депрессия: нижняя стенка", 22, INK, "middle", "bold")]
    px = 3.4
    up = lambda lt: cx(lt, R=0.8, S=-0.15, st=0.22, T=0.55, tsym=True)
    dn = lambda lt: cx(lt, R=0.9, S=-0.2, st=-0.15, T=-0.2)
    nl = lambda lt: cx(lt, R=0.9, T=0.3)
    leads = [("I", dn, BLUE), ("II", up, RED), ("III", up, RED), ("aVR", lambda lt: -nl(lt), INK), ("aVL", dn, BLUE), ("aVF", up, RED)]
    for i, (name, f, col) in enumerate(leads):
        x0 = 30 + (i % 3) * 306; y0 = 56 + (i // 3) * 170
        panel(b, x0, y0, 294, 150, px, beats(f, 0.9, 3, 0.05), 24, name, col)
    b.append(text(40, 418, "■ подъём ST в II, III, aVF — зона повреждения", 14.5, RED, "start", "bold"))
    b.append(text(40, 444, "■ депрессия ST в I, aVL — реципрокные (зеркальные) изменения", 14.5, BLUE, "start", "bold"))
    b.append(text(40, 476, "Зеркальная депрессия подтверждает ишемическую природу подъёма ST.", 14, INK))
    b.append(text(40, 500, "При нижнем подъёме ST снимите V3R–V4R (правый желудочек) и V7–V9 (задняя стенка) — КР157_5.", 14, INK))
    b.append(text(40, 524, "Депрессия ST в V1–V3 может быть зеркалом задней стенки (пособие, гл. 8.1.2).", 14, INK))
    return svg("\n".join(b), "Реципрокные изменения")


# ---------- 5. Алгоритм ----------
def algorithm():
    b = [text(W / 2, 36, "Боль в груди: ЭКГ на вызове (КР157_5, КР154_4)", 22, INK, "middle", "bold"), MARKER]
    b.append(box(280, 52, 400, 78, "ЭКГ в 12 отведениях ≤ 10 мин", ["от первого контакта; трудно трактовать —", "телемедицина"], INK))
    b.append(arrow(330, 130, 160, 170))
    b.append(arrow(480, 130, 480, 170))
    b.append(arrow(630, 130, 800, 170))
    b.append(box(20, 172, 290, 160, "ОКС с подъёмом ST", ["стойкий подъём ST > 20 мин", "в 2 смежных по критериям", "или новая БЛНПГ", "", "маршрут ОКСпST"], RED, "#fdf2f2"))
    b.append(box(335, 172, 290, 160, "ОКС без подъёма ST", ["депрессия ST ≥ 0,5 мм", "инверсия T > 1 мм", "преходящий подъём ST", "", "маршрут ОКСбпST"], ORANGE, "#fff8eb"))
    b.append(box(650, 172, 290, 160, "ЭКГ без изменений", ["ОКС не исключён!", "V7–V9, V3R–V4R", "повтор ЭКГ каждые 15–30 мин", "при сохранении боли", "сравнить со старой ЭКГ"], BLUE, "#f3f7fc"))
    b.append(f'<rect x="20" y="352" width="920" height="170" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(40, 380, "Что важно", 16, INK, "start", "bold"))
    lines = ["• ЭКГ во время боли информативнее, чем после неё (КР155_2)",
             "• смотрите аритмии и блокады: они меняют лечение (КР154_4, прил. А3)",
             "• подъём ST бывает не только при ИМ: ранняя реполяризация, перикардит, ГЛЖ, БЛНПГ — часть 13",
             "• лечение и маршрутизация при ОКС — часть 11"]
    for j, ln in enumerate(lines):
        b.append(text(40, 408 + j * 26, ln, 14, INK))
    return svg("\n".join(b), "Алгоритм ЭКГ при боли в груди")


files = {"s02_twaves.svg": twaves(), "s04_measure.svg": measure(), "s06_depression.svg": depression(),
         "s08_reciprocal.svg": reciprocal(), "s10_algorithm.svg": algorithm()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
