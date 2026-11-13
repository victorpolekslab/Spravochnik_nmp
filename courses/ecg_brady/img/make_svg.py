"""SVG-схемы для части 7 цикла «ЭКГ» (ecg_brady). Запуск: python3 ecg_part7_svg.py <папка>"""
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)

MARKER = ('<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
          f'<path d="M0,0 L9,4.5 L0,9 z" fill="{MUTED}"/></marker></defs>')


def strip(b, x0, y0, w, rows_mm, px, fn, base_mm, lw=2.0):
    h = rows_mm * px
    b.append(grid(x0, y0, w - (w % px), h, px))
    base = y0 + base_mm * px
    b.append(trace(fn, x0, base, w - 2, 25 * px, 10 * px, INK, lw, 0.4))
    return base


def cyc(kind, lt):
    """Комплекс; lt — время от начала цикла. R узкого комплекса — при lt = 0.225."""
    if kind == "s":        # синусовый
        return beat_p(lt)
    if kind == "a":        # нижнепредсердный: P отрицательный
        return beat_p(lt, P=-0.13, pr=-0.02)
    if kind == "j":        # из АВ-соединения: P не виден
        return beat_p(lt, P=0.0)
    if kind == "jr":       # из АВ-соединения: P− после QRS
        return beat_p(lt, P=0.0) + gauss(lt, -0.1, 0.33, 0.02)
    if kind == "v":        # идиовентрикулярный: широкий
        return (gauss(lt, 1.1, 0.225, 0.032) + gauss(lt, -0.35, 0.29, 0.024)
                + gauss(lt, -0.42, 0.47, 0.06))
    if kind == "p":        # только P (заблокированный — не используется)
        return gauss(lt, 0.15, 0.10, 0.022)
    return 0.0


def rhythm(beats, extra=None):
    """beats — список (время начала цикла, вид)."""
    def f(t):
        v = 0.0
        for t0, k in beats:
            lt = t - t0
            if -0.05 < lt < 0.9:
                v += cyc(k, lt)
        if extra:
            v += extra(t)
        return v
    return f


def bracket(x1, x2, y, label, col=BLUE, size=13, up=True):
    d = -1 if up else 1
    s = [f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="{col}" stroke-width="2.2"/>']
    for x in (x1, x2):
        s.append(f'<line x1="{x:.1f}" y1="{y-6}" x2="{x:.1f}" y2="{y+6}" stroke="{col}" stroke-width="2.2"/>')
    if label:
        s.append(text((x1 + x2) / 2, y + d * 9 + (0 if up else 8), label, size, col, "middle", "bold"))
    return "\n".join(s)


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


# ---------- 1. Синусовая брадикардия и синусовая аритмия ----------
def sinus():
    b = [text(W / 2, 38, "Синусовая брадикардия и синусовая аритмия", 22, INK, "middle", "bold")]
    px = 3.4; pxs = 25 * px
    rr = 1.33                       # 45 в минуту
    br = [(0.15 + rr * k, "s") for k in range(8)]
    y0 = 80
    strip(b, 40, y0, 880, 34, px, rhythm(br), 22)
    b.append(text(40, y0 - 12, "Синусовая брадикардия — ЧСС 45", 18, BLUE, "start", "bold"))
    b.append(text(920, y0 - 12, "P+ перед каждым QRS, RR одинаковые", 14.5, INK, "end"))
    b.append(bracket(40 + (br[2][0] + 0.225) * pxs, 40 + (br[3][0] + 0.225) * pxs, y0 + 34 * px - 16, "RR 1,33 с", BLUE, 13, False))
    # дыхательная аритмия
    t = 0.15; ar = []
    for k in range(14):
        ar.append((t, "s"))
        t += 0.78 + 0.28 * math.sin(2 * math.pi * k / 6.5)
    y1 = 268
    strip(b, 40, y1, 880, 34, px, rhythm(ar), 22)
    b.append(text(40, y1 - 12, "Синусовая дыхательная аритмия", 18, GREEN, "start", "bold"))
    b.append(text(920, y1 - 12, "RR плавно меняются > 0,15 с с фазами дыхания", 14.5, INK, "end"))
    b.append(text(250, y1 + 34 * px + 22, "вдох — чаще", 13.5, GREEN, "middle", "bold"))
    b.append(text(560, y1 + 34 * px + 22, "выдох — реже", 13.5, GREEN, "middle", "bold"))
    b.append(f'<rect x="40" y="436" width="880" height="90" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(60, 464, "Пособие: синусовая брадикардия — ЧСС 59–40 при правильном синусовом ритме", 14.5, INK, "start", "bold"))
    b.append(text(60, 488, "КР160_2: нижняя граница нормы днём в покое — 40, ночью — 35; паузы до 2 с допустимы", 14, INK))
    b.append(text(60, 510, "У спортсменов и лиц тяжёлого физического труда ЧСС может быть и ниже", 14, MUTED))
    return svg("\n".join(b), "Синусовая брадикардия и аритмия")


# ---------- 2. СА-блокада и отказ синусового узла ----------
def sa_block():
    b = [text(W / 2, 38, "Паузы: синоатриальная блокада и отказ синусового узла", 22, INK, "middle", "bold")]
    px = 3.4; pxs = 25 * px
    pp = 0.85
    sa = [(0.15 + pp * k, "s") for k in range(4)] + [(0.15 + pp * k, "s") for k in range(5, 11)]
    y0 = 82
    strip(b, 40, y0, 880, 34, px, rhythm(sa), 22)
    b.append(text(40, y0 - 12, "СА-блокада II степени", 18, RED, "start", "bold"))
    b.append(text(920, y0 - 12, "выпал целый цикл P–QRS–T", 14.5, INK, "end"))
    x1 = 40 + (sa[3][0] + 0.10) * pxs; x2 = 40 + (sa[4][0] + 0.10) * pxs
    b.append(bracket(x1, x2, y0 + 34 * px - 16, "пауза = 2 × PP", RED, 13.5, False))
    xa = 40 + (sa[2][0] + 0.10) * pxs; xb = 40 + (sa[3][0] + 0.10) * pxs
    b.append(bracket(xa, xb, y0 + 18, "PP", BLUE, 13, True))
    # отказ СУ с выскальзывающим комплексом
    t = 0.15; arr = []
    for k in range(3):
        arr.append((t, "s")); t += pp
    t += 1.95                       # пауза, не кратная PP
    arr.append((t, "j")); t += 1.15  # выскальзывающий из АВ-соединения
    for k in range(4):
        arr.append((t, "s")); t += pp
    y1 = 286
    strip(b, 40, y1, 880, 34, px, rhythm(arr), 22)
    b.append(text(40, y1 - 12, "Отказ (арест) синусового узла", 18, ORANGE, "start", "bold"))
    b.append(text(920, y1 - 12, "пауза не кратна PP; её прерывает выскальзывающий комплекс", 14.5, INK, "end"))
    x1 = 40 + (arr[2][0] + 0.10) * pxs; x2 = 40 + (arr[3][0] + 0.225) * pxs
    b.append(bracket(x1, x2, y1 + 34 * px - 16, "длинная пауза", ORANGE, 13.5, False))
    b.append(text(x2, y1 + 18, "выскальзывающий", 13, VIOLET, "middle", "bold"))
    b.append(text(x2, y1 + 34, "из АВ-соединения", 13, VIOLET, "middle", "bold"))
    b.append(text(W / 2, 470, "СА-блокада: паузы ровно в 2 (реже в 3–4) раза длиннее обычного PP (пособие, гл. 6.1)", 14, INK, "middle"))
    b.append(text(W / 2, 494, "Обе — проявления дисфункции синусового узла (КР160_2)", 14, INK, "middle"))
    b.append(text(W / 2, 520, "Асистолия > 3 с с симптомами — показание к ЭКС у пациентов старше 40 лет (КР160_2)", 13.5, RED, "middle", "bold"))
    return svg("\n".join(b), "Синоатриальная блокада и отказ синусового узла")


# ---------- 3. Выскальзывающие ритмы ----------
def escape():
    b = [text(W / 2, 36, "Замещающие (выскальзывающие) ритмы: кто ведёт сердце", 22, INK, "middle", "bold")]
    px = 3.0; pxs = 25 * px
    rows = [("Нижнепредсердный", "P− во II, III, aVF|перед QRS, QRS узкие", [(0.15 + 1.1 * k, "a") for k in range(8)], BLUE),
            ("Из АВ-соединения", "ЧСС 40–60|P не виден или P− после QRS|QRS узкие", [(0.15 + 1.3 * k, "j" if k % 2 == 0 else "jr") for k in range(7)], GREEN),
            ("Идиовентрикулярный", "ЧСС меньше 40|QRS широкие|P нет или идут сами по себе", [(0.15 + 1.75 * k, "v") for k in range(6)], RED)]
    for i, (name, desc, beats, col) in enumerate(rows):
        y0 = 62 + i * 146
        strip(b, 330, y0, 600, 36, px, rhythm(beats), 24, 1.9)
        b.append(f'<rect x="30" y="{y0+6}" width="7" height="{36*px-12}" rx="3" fill="{col}"/>')
        b.append(text(48, y0 + 32, name, 17, col, "start", "bold"))
        for j, ln in enumerate(desc.split("|")):
            b.append(text(48, y0 + 56 + j * 19, ln, 13.5, INK))
    b.append(text(W / 2, 508, "Чем ниже водитель ритма, тем реже ритм и шире QRS. Замещающий ритм — защита от асистолии:", 13.5, INK, "middle"))
    b.append(text(W / 2, 528, "его не подавляют, а ищут и лечат причину (пособие, гл. 4.1.3, 5.2.1)", 13.5, INK, "middle"))
    return svg("\n".join(b), "Замещающие ритмы")


# ---------- 4. Синдром тахи-бради ----------
def tachybrady():
    b = [text(W / 2, 38, "Синдром тахикардии–брадикардии", 22, INK, "middle", "bold")]
    px = 3.0; pxs = 25 * px
    rnd = random.Random(7)
    af_end = 4.1
    rs = []; t = 0.25
    while t < af_end:
        rs.append((t - 0.225, "j")); t += rnd.uniform(0.38, 0.62)
    t_last = rs[-1][0]
    pause_end = t_last + 4.6
    beats = rs + [(pause_end, "j"), (pause_end + 1.5, "s"), (pause_end + 2.9, "s")]
    comps = [(rnd.uniform(5.5, 9.5), rnd.uniform(0, 6.28), rnd.uniform(0.5, 1.0)) for _ in range(7)]
    norm = sum(c[2] for c in comps)

    def fw(t):
        if t > t_last + 0.45:
            return 0.0
        return 0.09 * sum(a * math.sin(2 * math.pi * fr * t + ph) for fr, ph, a in comps) / norm * 2.2
    y0 = 78
    strip(b, 40, y0, 880, 40, px, rhythm(beats, fw), 26)
    xs = 40 + (t_last + 0.45) * pxs; xe = 40 + (pause_end + 0.225) * pxs
    b.append(text(40 + 2.0 * pxs, y0 + 18, "пароксизм ФП", 14, ORANGE, "middle", "bold"))
    b.append(f'<rect x="{xs:.1f}" y="{y0+2}" width="{xe-xs:.1f}" height="{40*px-4}" fill="{RED}" opacity="0.07"/>')
    b.append(bracket(xs, xe, y0 + 40 * px - 16, "пауза 4 с — головокружение, обморок", RED, 13.5, False))
    b.append(text(xe + 4, y0 + 18, "медленный ритм", 14, BLUE, "start", "bold"))
    ty = 262
    b.append(box(40, ty, 430, 200, "Что это (КР160_2, пособие)", [
        "чередование пароксизмов ФП или ТП",
        "с редким синусовым или",
        "замещающим ритмом, паузами,",
        "асистолией",
        "типично для СССУ"], RED, "#fdf2f2", 13.5))
    b.append(box(490, ty, 430, 200, "На вызове", [
        "обморок после сердцебиения —",
        "думать о паузе после пароксизма",
        "осторожно с урежающими ЧСС:",
        "они усилят брадикардию",
        "запись ЭКГ, наблюдение, мониторинг",
        "обморок, связанный с брадикардией, —",
        "госпитализация (КР160_2)"], BLUE, "#f3f7fc", 13.5))
    return svg("\n".join(b), "Синдром тахикардии-брадикардии")


# ---------- 5. Алгоритм ----------
def algorithm():
    b = [text(W / 2, 36, "Брадикардия на вызове (КР160_2)", 22, INK, "middle", "bold"), MARKER]
    b.append(box(300, 52, 360, 62, "Брадикардия: ЭКГ в 12 отведениях", ["есть симптомы? гемодинамика?"], INK))
    b.append(arrow(360, 114, 220, 150, "нет симптомов", 278, 128, "end"))
    b.append(arrow(600, 114, 740, 150, "симптомы, гипотония", 682, 128, "start"))
    b.append(box(20, 152, 400, 140, "Наблюдение, искать причину", ["лекарства: β-блокаторы, верапамил,", "дилтиазем, гликозиды, антиаритмики", "калий, гипотиреоз, гипотермия, ИМ", "спортсмен без жалоб — норма", "впервые и с симптомами — к врачу"], BLUE))
    b.append(box(540, 152, 400, 140, "1. Атропин", ["0,5–1 мг в/в", "повтор каждые 3–5 мин", "до максимальной дозы 3 мг", "лучше всего — при блокаде в АВ-узле", "и избытке тонуса вагуса"], GREEN))
    b.append(arrow(740, 292, 740, 316, "нет эффекта", 750, 309, "start"))
    b.append(box(540, 318, 400, 100, "2. #Допамин", ["5–20 мкг/кг/мин в/в, начать с 5,", "+5 мкг/кг/мин каждые 2 мин", "при низкой вероятности ИБС"], ORANGE))
    b.append(arrow(740, 418, 740, 440))
    b.append(box(540, 442, 400, 80, "3. Временная ЭКС — бригада СМП", ["экстренная госпитализация с", "реанимацией и мониторингом"], RED, "#fdf2f2"))
    b.append(box(20, 318, 400, 204, "Симптомная брадикардия (КР160_2)", ["обморок или предобморок", "головокружение, слабость", "признаки сердечной недостаточности", "спутанность сознания", "гипотония", "", "препараты — если есть в укладке"], VIOLET, "#f6f1fd"))
    return svg("\n".join(b), "Алгоритм при брадикардии")


files = {"s02_sinus_brady.svg": sinus(), "s04_sa_block.svg": sa_block(), "s06_escape.svg": escape(),
         "s08_tachybrady.svg": tachybrady(), "s10_algorithm.svg": algorithm()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
