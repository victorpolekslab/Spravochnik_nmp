"""SVG-схемы для части 6 цикла «ЭКГ» (ecg_vt). Запуск: python3 ecg_part6_svg.py <папка>"""
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)


def strip(b, x0, y0, w, rows_mm, px, fn, base_mm, lw=2.0, color=INK):
    h = rows_mm * px
    b.append(grid(x0, y0, w - (w % px), h, px))
    base = y0 + base_mm * px
    b.append(trace(fn, x0, base, w - 2, 25 * px, 10 * px, color, lw, 0.4))
    return base


def vt_beat(lt):
    """Широкий желудочковый комплекс, lt — от начала QRS, с."""
    return (gauss(lt, 1.25, 0.065, 0.03) + gauss(lt, -0.45, 0.13, 0.022)
            + gauss(lt, -0.5, 0.26, 0.05))


def narrow(lt):
    """Узкий проведённый комплекс; R в момент lt=0.03."""
    return (gauss(lt, -0.08, 0.01, 0.007) + gauss(lt, 1.0, 0.03, 0.009)
            + gauss(lt, -0.22, 0.05, 0.009) + gauss(lt, 0.28, 0.24, 0.04))


def p_wave(lt):
    return gauss(lt, 0.15, 0.0, 0.022)


def box(x, y, w, h, title, lines, col, fill="#f8fafc", size=13.3):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{col}" stroke-width="2.5"/>',
         text(x + 14, y + 26, title, 16, col, "start", "bold")]
    for j, ln in enumerate(lines):
        s.append(text(x + 14, y + 48 + j * 19, ln, size, INK))
    return "\n".join(s)


def arrow(x1, y1, x2, y2, label=None, lx=0, ly=0, anchor="start", col=MUTED):
    s = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="2.5" marker-end="url(#ar)"/>']
    if label:
        s.append(text(lx, ly, label, 13, col, anchor, "bold"))
    return "\n".join(s)


MARKER = ('<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
          f'<path d="M0,0 L9,4.5 L0,9 z" fill="{MUTED}"/></marker></defs>')


# ---------- 1. Мономорфная ЖТ ----------
def vt():
    b = [text(W / 2, 38, "Желудочковая тахикардия: широкие QRS и АВ-диссоциация", 22, INK, "middle", "bold")]
    px = 3.4; pxs = 25 * px
    rr = 0.36                      # ≈ 167 в минуту
    starts = [0.25 + rr * k for k in range(29)]
    capture_i, fusion_i = 13, 21
    ps = [0.12 + 0.8 * k for k in range(14)]   # синусовые P 75 в минуту
    # захват: P перед узким комплексом
    starts[capture_i] = starts[capture_i] + 0.02
    ps_cap = starts[capture_i] - 0.16
    ps = [p for p in ps if abs(p - ps_cap) > 0.3] + [ps_cap]

    def f(t):
        v = 0.0
        for i, s0 in enumerate(starts):
            lt = t - s0
            if -0.05 < lt < 0.42:
                if i == capture_i:
                    v += narrow(lt + 0.035)
                elif i == fusion_i:
                    v += 0.5 * vt_beat(lt) + 0.5 * narrow(lt + 0.035)
                else:
                    v += vt_beat(lt)
        for p in ps:
            if abs(t - p) < 0.1:
                v += p_wave(t - p)
        return v
    y0 = 74
    strip(b, 40, y0, 880, 40, px, f, 24)
    b.append(text(40, y0 - 10, "II", 16, INK, "start", "bold"))
    b.append(text(920, y0 - 10, "ЧСС около 165, ритм правильный", 14, INK, "end"))
    for p in ps:
        x = 40 + p * pxs
        if x < 915:
            b.append(f'<path d="M{x-6:.1f},{y0+40*px+14} L{x+6:.1f},{y0+40*px+14} L{x:.1f},{y0+40*px+4} z" fill="{RED}"/>')
    b.append(text(40, y0 + 40 * px + 34, "▲ синусовые P идут своим ритмом, около 75 в мин — без связи с QRS", 13.5, RED, "start", "bold"))
    xc = 40 + (starts[capture_i] + 0.0) * pxs
    xf = 40 + (starts[fusion_i] + 0.06) * pxs
    b.append(text(xc, y0 + 16, "захват", 13.5, GREEN, "middle", "bold"))
    b.append(text(xf, y0 + 16, "сливной", 13.5, VIOLET, "middle", "bold"))
    ty = 290
    b.append(f'<rect x="40" y="{ty}" width="880" height="214" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    items = [("QRS шире 0,12 с, деформирован", "ST и T дискордантны — направлены против основного зубца"),
             ("Ритм чаще правильный, ЧСС 140–220", "приступ начинается и заканчивается внезапно"),
             ("АВ-диссоциация", "P редкие, «плавают» по комплексам; видны не всегда"),
             ("Захваченные и сливные комплексы", "узкий комплекс среди широких — почти доказательство ЖТ")]
    for j, (h, s_) in enumerate(items):
        y = ty + 40 + j * 47
        b.append(f'<circle cx="68" cy="{y-6}" r="8" fill="{RED}"/>')
        b.append(text(88, y, h, 16, INK, "start", "bold"))
        b.append(text(88, y + 20, s_, 13.5, MUTED))
    b.append(text(W / 2, 532, "Пособие, гл. 5.3.2.3; определения — КР569_2", 12.5, MUTED, "middle"))
    return svg("\n".join(b), "Желудочковая тахикардия")


# ---------- 2. Алгоритм при широких QRS ----------
def wide_algo():
    b = [text(W / 2, 36, "Тахикардия с широкими QRS на вызове (КР569_2)", 22, INK, "middle", "bold"), MARKER]
    b.append(box(300, 52, 360, 62, "Широкие QRS, ЧСС > 100", ["пульс есть? гемодинамика?"], INK))
    b.append(arrow(330, 114, 200, 150, "нет пульса", 250, 128, "end"))
    b.append(arrow(480, 114, 480, 150, "нестабильна", 494, 138, "start"))
    b.append(arrow(630, 114, 760, 150, "стабильна", 712, 128, "start"))
    b.append(box(20, 152, 290, 112, "Остановка", ["ФЖ или ЖТ без пульса:", "СЛР и дефибрилляция", "немедленно"], RED, "#fdf2f2"))
    b.append(box(330, 152, 290, 112, "Кардиоверсия", ["гипотония, обморок, ишемия,", "отёк лёгких; нет ЭИТ —", "бригада СМП"], RED, "#fdf2f2"))
    b.append(box(640, 152, 300, 112, "ЭКГ в 12 отведениях", ["считать ЖТ, пока не доказана", "НЖТ; верапамил — нельзя"], BLUE))
    b.append(arrow(700, 264, 600, 300))
    b.append(arrow(880, 264, 880, 300))
    b.append(box(380, 302, 290, 124, "НЖТ несомненна", ["вагусные пробы;", "не помогли — #трифосаденин", "по КР619_3"], GREEN))
    b.append(box(690, 302, 250, 124, "ЖТ или неясно", ["#прокаинамид, если нет", "тяжёлой СН, гипотонии,", "острого ИМ;", "иначе — #амиодарон"], ORANGE))
    b.append(box(20, 302, 340, 124, "Нерегулярная и широкая", ["ФП + WPW: не вводить", "#трифосаденин, β-блокаторы,", "верапамил, дигоксин, амиодарон"], VIOLET, "#f6f1fd"))
    b.append(f'<rect x="20" y="442" width="920" height="80" rx="14" fill="#fff8eb" stroke="{ORANGE}" stroke-width="1.5"/>')
    b.append(text(40, 470, "Частая ошибка: «давление нормальное — значит, НЖТ»", 16, ORANGE, "start", "bold"))
    b.append(text(40, 496, "Стабильная гемодинамика не исключает ЖТ. Препараты от ЖТ помогают и при НЖТ, а верапамил при ЖТ", 13.3, INK))
    b.append(text(40, 514, "может уронить давление (КР569_2). Препараты — если есть в укладке.", 13.3, INK))
    return svg("\n".join(b), "Алгоритм при тахикардии с широкими QRS")


# ---------- 3. Пируэт ----------
def torsades():
    b = [text(W / 2, 38, "ЖТ типа «пируэт»: длинный QT, затем «веретено»", 22, INK, "middle", "bold")]
    px = 3.0; pxs = 25 * px
    sinus = [0.2, 1.3, 2.4]
    t0 = 3.05                      # ранняя ЖЭ на T — запуск

    def long_qt(lt):
        return beat_p(lt, T=0.32, qt=1.9, U=0.08)

    def tdp(t):
        u = t - t0
        env = 0.25 + 1.1 * abs(math.sin(math.pi * u / 1.9)) ** 0.8
        sign = 1 if math.sin(math.pi * u / 1.9) >= 0 else -1
        ph = 2 * math.pi * 4.1 * u
        return sign * env * (0.8 * math.sin(ph) + 0.2 * math.sin(2 * ph + 0.5))

    def f(t):
        v = 0.0
        for s in sinus:
            lt = t - s
            if -0.05 < lt < 1.1:
                v += long_qt(lt)
        if t >= t0:
            v += tdp(t) * smooth(t0, t0 + 0.15, t) * (1 - smooth(10.3, 10.6, t))
        return v
    y0 = 70
    strip(b, 40, y0, 880, 56, px, f, 30)
    xs = 40 + t0 * pxs
    b.append(f'<line x1="{xs:.1f}" y1="{y0}" x2="{xs:.1f}" y2="{y0+56*px}" stroke="{RED}" stroke-width="2" stroke-dasharray="6 5"/>')
    # QT скобка на втором синусовом комплексе
    qs = 40 + (1.3 + 0.205) * pxs; qe = 40 + (1.3 + 0.225 + 0.205 * 1.9 + 0.08) * pxs
    yb = y0 + 56 * px - 16
    b.append(f'<line x1="{qs:.1f}" y1="{yb}" x2="{qe:.1f}" y2="{yb}" stroke="{BLUE}" stroke-width="2.2"/>')
    for x in (qs, qe):
        b.append(f'<line x1="{x:.1f}" y1="{yb-6}" x2="{x:.1f}" y2="{yb+6}" stroke="{BLUE}" stroke-width="2.2"/>')
    b.append(text((qs + qe) / 2, yb - 10, "QT удлинён", 13.5, BLUE, "middle", "bold"))
    b.append(text(xs + 8, y0 + 20, "ранняя ЖЭ на зубец T — запуск", 13.5, RED, "start", "bold"))
    b.append(text(920, y0 + 56 * px - 10, "QRS меняются, «скручиваются» вокруг изолинии", 13.5, RED, "end", "bold"))
    ty = 262
    b.append(box(40, ty, 430, 214, "Как узнать (КР569_2)", [
        "полиморфная ЖТ при длинном QT",
        "QRS постоянно меняются и",
        "«скручиваются» вокруг изолинии",
        "провоцируют: гипокалиемия,",
        "гипомагниемия, брадикардия,",
        "препараты, удлиняющие QT",
        "приступы повторяются,",
        "могут перейти в ФЖ"], RED, "#fdf2f2", 13.5))
    b.append(box(490, ty, 430, 214, "Что делать (КР569_2)", [
        "без пульса — СЛР, дефибрилляция",
        "#магния сульфат 2 г в/в медленно",
        "под контролем АД; не помогло —",
        "повтор через 5–15 мин",
        "отменить препараты, удлиняющие QT",
        "коррекция калия и магния",
        "избегать ААП III класса (амиодарон)",
        "экстренная госпитализация"], GREEN, "#f1faf4", 13.5))
    return svg("\n".join(b), "Пируэтная желудочковая тахикардия")


# ---------- 4. ТЖ и ФЖ ----------
def vf():
    b = [text(W / 2, 36, "Трепетание и фибрилляция желудочков — это остановка кровообращения", 21, INK, "middle", "bold")]
    px = 2.8

    def flut(t):
        return 0.95 * math.sin(2 * math.pi * 4.4 * t) + 0.12 * math.sin(2 * math.pi * 8.8 * t + 1)

    def fibw(amp, seed):
        rnd = random.Random(seed)
        comps = [(rnd.uniform(3.5, 7.5), rnd.uniform(0, 6.28), rnd.uniform(0.4, 1.0)) for _ in range(8)]
        slow = [(rnd.uniform(0.2, 0.5), rnd.uniform(0, 6.28)) for _ in range(2)]
        norm = sum(c[2] for c in comps)

        def f(t):
            env = 0.65 + 0.35 * sum(math.sin(2 * math.pi * fr * t + ph) for fr, ph in slow) / 2
            return amp * env * sum(a * math.sin(2 * math.pi * fr * t + ph) for fr, ph, a in comps) / norm * 2.4
        return f
    rows = [("Трепетание желудочков", "синусоида 200–300 в мин, элементы QRS и T не различить", flut, RED),
            ("ФЖ крупноволновая", "хаос волн разной формы и амплитуды, 200–500 в мин", fibw(0.75, 4), RED),
            ("ФЖ мелковолновая", "низкие волны — легко принять за асистолию: проверьте усиление и отведения", fibw(0.2, 9), RED)]
    for i, (name, desc, fn, col) in enumerate(rows):
        y0 = 74 + i * 148
        strip(b, 40, y0, 880, 40, px, fn, 20)
        b.append(text(40, y0 - 10, name, 17, col, "start", "bold"))
        b.append(text(920, y0 - 10, desc, 13.3, INK, "end"))
    b.append(text(W / 2, 524, "Пульса нет → СЛР и дефибрилляция немедленно (пособие, гл. 5.3.5; КР569_2)", 14.5, RED, "middle", "bold"))
    return svg("\n".join(b), "Трепетание и фибрилляция желудочков")


# ---------- 5. Ход СЛР при ФЖ ----------
def arrest():
    b = [text(W / 2, 36, "ФЖ или ЖТ без пульса: когда что вводить (КР569_2)", 22, INK, "middle", "bold")]
    x0, x1 = 70, 900
    yl = 210
    n = 6
    step = (x1 - x0) / n
    b.append(f'<line x1="{x0}" y1="{yl}" x2="{x1+20}" y2="{yl}" stroke="{INK}" stroke-width="3"/>')
    for k in range(n):
        xa = x0 + k * step
        # шок
        b.append(f'<path d="M{xa+6},{yl-58} L{xa-6},{yl-30} L{xa+2},{yl-30} L{xa-8},{yl-4} L{xa+12},{yl-36} L{xa+3},{yl-36} L{xa+12},{yl-58} z" fill="{ORANGE}"/>')
        b.append(text(xa + 2, yl - 66, f"разряд {k+1}" if k < 5 else "…", 13.5, ORANGE, "middle", "bold"))
        # СЛР 2 мин
        b.append(f'<rect x="{xa+18}" y="{yl-14}" width="{step-30:.1f}" height="28" rx="8" fill="#dbe7f5"/>')
        b.append(text(xa + 18 + (step - 30) / 2, yl + 5, "СЛР", 13, BLUE, "middle", "bold"))
    # препараты
    xa3 = x0 + 2 * step + 60
    xa5 = x0 + 4 * step + 60
    b.append(f'<line x1="{xa3}" y1="{yl+16}" x2="{xa3}" y2="{yl+56}" stroke="{RED}" stroke-width="2.5"/>')
    b.append(text(xa3, yl + 76, "амиодарон 300 мг", 15, RED, "middle", "bold"))
    b.append(text(xa3, yl + 96, "+ #эпинефрин 1 мг", 15, VIOLET, "middle", "bold"))
    b.append(f'<line x1="{xa5}" y1="{yl+16}" x2="{xa5}" y2="{yl+56}" stroke="{RED}" stroke-width="2.5"/>')
    b.append(text(xa5, yl + 76, "амиодарон 150 мг", 15, RED, "middle", "bold"))
    b.append(text(x0 + 4 * step + 60, yl + 96, "#эпинефрин — каждые 3–5 мин", 15, VIOLET, "middle", "bold"))
    ty = 340
    b.append(box(40, ty, 430, 150, "Главное", [
        "дефибрилляция — ключевой элемент СЛР",
        "лекарства не прерывают СЛР",
        "и не задерживают разряд",
        "нет амиодарона — лидокаин 1 мг/кг",
        "дефибриллятора нет — СЛР и вызов СМП"], RED, "#fdf2f2", 13.5))
    b.append(box(490, ty, 430, 150, "Асистолия и ЭМД", [
        "ритм не для разряда",
        "#эпинефрин 1 мг — сразу",
        "после установки доступа,",
        "далее каждые 3–5 мин",
        "препараты — если есть в укладке"], BLUE, "#f3f7fc", 13.5))
    return svg("\n".join(b), "Схема СЛР при ФЖ")


files = {"s02_vt.svg": vt(), "s04_wide_algo.svg": wide_algo(), "s06_torsades.svg": torsades(),
         "s08_vf.svg": vf(), "s10_arrest.svg": arrest()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
