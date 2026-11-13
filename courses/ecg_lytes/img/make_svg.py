"""SVG-схемы для части 14 цикла «ЭКГ» (ecg_lytes). Запуск: python3 ecg_part14_svg.py <папка>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)
G = gauss


def cx(lt, P=0.12, pw=0.022, pr=0.0, R=1.0, S=-0.2, qw=1.0, st=0.0, trough=0.0, T=0.3, tsym=False, tw=0.045,
       qt=1.0, U=0.0):
    """Комплекс. qt — множитель длительности ST–T; trough — корытообразная депрессия ST."""
    c = 0.225 + pr
    v = G(lt, P, 0.10, pw) if P else 0.0
    v += G(lt, -0.05, c - 0.02 * qw, 0.007 * qw) + G(lt, R, c, 0.009 * qw) + G(lt, S, c + 0.022 * qw, 0.009 * qw)
    j = c + 0.04 * qw
    tc = j + 0.18 * qt
    if tsym:
        v += G(lt, T, tc, tw)
    else:
        sd = tw * 1.25 if lt < tc else tw * 0.7
        v += T * math.exp(-((lt - tc) ** 2) / (2 * sd * sd))
    if st:
        w = smooth(j - 0.01, j + 0.01, lt) * (1 - smooth(tc - 0.03, tc + 0.05, lt))
        v += st * w
    if trough:
        v += -trough * smooth(j - 0.006, j + 0.012, lt) * math.exp(-((lt - (j + 0.09)) ** 2) / (2 * 0.055 ** 2)) * (1 if lt < j + 0.09 else 1) 
    if U:
        v += G(lt, U, tc + 0.16, 0.035)
    return v


def beats(f, rr=0.95, n=3, t0=0.05):
    def g(t):
        v = 0.0
        k = int((t - t0) / rr)
        for kk in (k - 1, k, k + 1):
            if 0 <= kk < n:
                lt = t - t0 - kk * rr
                if -0.05 < lt < rr + 0.25:
                    v += f(lt)
        return v
    return g


def panel(b, x0, y0, w, h, px, fn, base_mm, title, col=INK, sub=None, sub2=None, lw=2.1):
    b.append(grid(x0, y0, w - (w % px), h, px))
    b.append(trace(fn, x0, y0 + base_mm * px, w - 2, 25 * px, 10 * px, INK, lw, 0.3))
    b.append(text(x0 + 8, y0 + 19, title, 14, col, "start", "bold"))
    if sub:
        b.append(text(x0 + w / 2, y0 + h + 18, sub, 12.8, INK, "middle", "bold"))
    if sub2:
        b.append(text(x0 + w / 2, y0 + h + 35, sub2, 12.3, MUTED, "middle"))


def box(x, y, w, h, title, lines, col, fill="#f8fafc", size=13.3):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{col}" stroke-width="2.5"/>',
         text(x + 14, y + 26, title, 16, col, "start", "bold")]
    for j, ln in enumerate(lines):
        s.append(text(x + 14, y + 48 + j * 19, ln, size, INK))
    return "\n".join(s)


def sine_wave(t):
    return 0.9 * math.sin(2 * math.pi * 2.2 * t)


# ---------- 1. Гиперкалиемия ----------
def hyperk():
    b = [text(W / 2, 34, "Гиперкалиемия: ЭКГ меняется по мере роста калия (КР469_3)", 20, INK, "middle", "bold")]
    px = 2.9
    items = [("Норма", GREEN, lambda lt: cx(lt), "", ""),
             ("K 6–7 ммоль/л", ORANGE, lambda lt: cx(lt, T=0.9, tsym=True, tw=0.03, qt=0.85), "высокий узкий острый T", "QT короче"),
             ("K 7–8 ммоль/л", RED, lambda lt: cx(lt, P=0.04, pw=0.035, R=0.7, S=-0.3, qw=2.0, T=0.8, tsym=True, tw=0.04), "P плоский, QRS широкий", ""),
             ("K 8–9 ммоль/л", RED, lambda lt: cx(lt, P=0.0, R=0.6, S=-0.5, qw=3.2, T=0.7, tsym=True, tw=0.07, qt=0.9), "QRS сливается с T", "«синусоида»"),
             ("K > 9 ммоль/л", RED, None, "ФЖ, АВ-блокада, асистолия", "")]
    for i, (name, col, f, s1, s2) in enumerate(items):
        x0 = 30 + (i % 3) * 306; y0 = 50 + (i // 3) * 226
        fn = beats(f, 0.95, 3) if f else (lambda t: 0.5 * math.sin(2 * math.pi * 4.5 * t) + 0.3 * math.sin(2 * math.pi * 6.7 * t + 1))
        panel(b, x0, y0, 294, 150, px, fn, 26, name, col, s1 or None, s2 or None)
    b.append(box(642, 276, 288, 246, "Когда лечить сразу", [
        "K > 6,0 ммоль/л,",
        "K > 5,5 с изменениями ЭКГ",
        "или желудочковыми",
        "аритмиями (КР469_3)",
        "",
        "кто в группе риска:",
        "ХБП, диализ, СД, ХСН,",
        "иАПФ, БРА, спиронолактон,",
        "НПВП, препараты калия"], RED, "#fdf2f2", 13))
    return svg("\n".join(b), "Гиперкалиемия")


# ---------- 2. Электролиты: сводка ----------
def lytes():
    b = [text(W / 2, 34, "Калий и кальций на ЭКГ (пособие, гл. 9.6, рис. 9.12)", 21, INK, "middle", "bold")]
    px = 3.0
    items = [("Норма", GREEN, lambda lt: cx(lt), "", ""),
             ("Гипокалиемия", BLUE, lambda lt: cx(lt, st=-0.08, T=0.08, U=0.22, qt=1.15), "ST ↓, T ниже, U выше", "QT (QU) длиннее"),
             ("Гиперкалиемия", RED, lambda lt: cx(lt, T=0.85, tsym=True, tw=0.03, qt=0.85), "высокий острый T", "QT короче"),
             ("Гипокальциемия", VIOLET, lambda lt: cx(lt, qt=1.6, T=0.25), "длинный ST — QT длиннее", ""),
             ("Гиперкальциемия", ORANGE, lambda lt: cx(lt, qt=0.6, T=0.2), "короткий ST — QT короче", "T снижен")]
    for i, (name, col, f, s1, s2) in enumerate(items):
        x0 = 30 + (i % 3) * 306; y0 = 50 + (i // 3) * 226
        panel(b, x0, y0, 294, 150, px, beats(f, 1.0, 3), 24, name, col, s1 or None, s2 or None)
    b.append(box(642, 276, 288, 246, "Как запомнить", [
        "QT длиннее:",
        "гипокалиемия (+ ST ↓, U)",
        "гипокальциемия (длинный ST)",
        "",
        "QT короче:",
        "гиперкалиемия (T высокий)",
        "гиперкальциемия (T снижен)",
        "",
        "калий меняет T, кальций — ST"], INK, "#f8fafc", 13))
    return svg("\n".join(b), "Калий и кальций на ЭКГ")


# ---------- 3. Дигоксин ----------
def digoxin():
    b = [text(W / 2, 34, "Сердечные гликозиды на ЭКГ", 22, INK, "middle", "bold")]
    px = 3.4
    trough = lambda lt: cx(lt, trough=0.5, T=0.2, qt=0.95)
    vpb = lambda lt: (G(lt, 1.1, 0.225, 0.03) + G(lt, -0.4, 0.29, 0.025) + G(lt, -0.4, 0.47, 0.06))

    def bigem(t):
        v = 0.0
        t0 = 0.05; k = 0; tt = t0
        while tt < t + 0.2:
            lt = t - tt
            if -0.05 < lt < 0.9:
                v += trough(lt) if k % 2 == 0 else vpb(lt + 0.12)
            tt += 0.62 if k % 2 == 0 else 1.05
            k += 1
        return v
    panel(b, 30, 50, 440, 170, px, beats(trough, 0.95, 4), 22, "«Корытообразная» депрессия ST · V5", ORANGE,
          "ST ↓ корытом, T сглажен или (−+), QT короче")
    panel(b, 490, 50, 440, 170, px, bigem, 22, "Желудочковая бигеминия", RED, "чаще всего при передозировке")
    b.append(box(30, 266, 440, 210, "Действие и интоксикация", [
        "корытообразное смещение ST вниз,",
        "двухфазный (−+) или отрицательный T,",
        "QT короче — пособие, гл. 9.7",
        "сами по себе — эффект препарата,",
        "не обязательно отравление",
        "отравление (КР1025_1): ЖЭ, бигеминия,",
        "ЖТ, АВ-блокады, СА-блокада,",
        "брадикардия, ФП с редким ритмом"], ORANGE, "#fff8eb"))
    b.append(box(490, 266, 440, 210, "Клиника отравления (КР1025_1)", [
        "тошнота, рвота — часто раньше",
        "нарушений ритма",
        "слабость, спутанность; зрение:",
        "жёлто-зелёные пятна, двоение",
        "риск выше: пожилые, ХСН,",
        "гипокалиемия, гипомагниемия,",
        "диуретики",
        "все отравления СГ — тяжёлые"], RED, "#fdf2f2"))
    return svg("\n".join(b), "Сердечные гликозиды на ЭКГ")


# ---------- 4. QT ----------
def qt():
    b = [text(W / 2, 34, "Интервал QT: как измерить и когда опасно", 22, INK, "middle", "bold")]
    px = 7.0; pxs = 25 * px
    f = lambda lt: cx(lt - 0.6, qt=1.35, T=0.4)
    x0, y0, w, h = 30, 50, 560, 280
    b.append(grid(x0, y0, w - (w % px), h, px))
    base = y0 + 24 * px
    b.append(trace(f, x0, base, w - 2, pxs, 10 * px, INK, 2.6, 0.25))
    xq = x0 + (0.6 + 0.225 - 0.03) * pxs
    xt = x0 + (0.6 + 0.225 + 0.04 + 0.18 * 1.35 + 0.095) * pxs
    yb = base + 60
    b.append(f'<line x1="{xq:.1f}" y1="{yb}" x2="{xt:.1f}" y2="{yb}" stroke="{RED}" stroke-width="2.4"/>')
    for x in (xq, xt):
        b.append(f'<line x1="{x:.1f}" y1="{yb-8}" x2="{x:.1f}" y2="{yb+8}" stroke="{RED}" stroke-width="2.4"/>')
        b.append(f'<line x1="{x:.1f}" y1="{y0+10}" x2="{x:.1f}" y2="{yb}" stroke="{RED}" stroke-width="1.2" stroke-dasharray="5 4"/>')
    b.append(text((xq + xt) / 2, yb + 26, "QT: от начала QRS до конца T", 14, RED, "middle", "bold"))
    b.append(box(610, 50, 320, 280, "Нормы (КР569_2)", [
        "QTc — QT с поправкой на ЧСС",
        "(формулы Базетта, Фредерика)",
        "",
        "женщины: 340–480 мс",
        "мужчины: 340–460 мс",
        "",
        "QTc ≥ 480 мс — критерий",
        "синдрома удлинённого QT",
        "у женщин QT длиннее"], BLUE, "#f3f7fc", 13.5))
    b.append(box(30, 352, 440, 170, "Базетт: QTc = QT / √RR", [
        "QT и RR — в секундах",
        "пример: QT 0,44 с, ЧСС 75 (RR 0,8 с)",
        "√0,8 ≈ 0,89 → QTc ≈ 0,49 с = 490 мс",
        "обморок или остановка + QTc ≥ 460 мс —",
        "тоже синдром удлинённого QT (КР569_2)"], INK, "#f8fafc", 13))
    b.append(box(490, 352, 440, 170, "Что удлиняет QT (КР569_2)", [
        "антиаритмики, многие некардиологические",
        "препараты (crediblemeds.org)",
        "гипокалиемия, гипомагниемия,",
        "гипокальциемия; диуретики",
        "риск — ЖТ «пируэт» (часть 6)"], RED, "#fdf2f2", 13))
    return svg("\n".join(b), "Интервал QT")


# ---------- 5. Лекарства и ЭКГ ----------
def drugs():
    b = [text(W / 2, 34, "Лекарства и ЭКГ на вызове", 22, INK, "middle", "bold")]
    rows = [("Препарат", ["ЭКГ"], ["Что делать / что нельзя"], INK),
            ("β-блокаторы, верапамил,|дилтиазем", ["брадикардия, АВ-блокада"], ["атропин; затем #допамин (КР160_2)"], BLUE),
            ("Сердечные гликозиды", ["корыто ST, ЖЭ, бигеминия,", "АВ-блокада"], ["атропин, лидокаин; нельзя: соли Ca,", "эпинефрин, прокаинамид (КР1025_1)"], ORANGE),
            ("Трициклические|антидепрессанты", ["QRS > 0,10 с, тахикардия, ЖА"], ["#натрия гидрокарбонат;", "нельзя: IA, IC, III классы (КР880_1)"], RED),
            ("Удлиняющие QT", ["длинный QT, «пируэт»"], ["#магния сульфат; отменить (КР569_2)"], VIOLET),
            ("Диуретики", ["гипокалиемия: ST ↓, U,", "длинный QT"], ["коррекция калия и магния (КР569_2)"], GREEN),
            ("иАПФ, БРА, спиронолактон,|препараты калия", ["гиперкалиемия: острый T,", "широкий QRS"], ["#кальция глюконат при изменениях", "ЭКГ (КР469_3)"], RED)]
    y = 52
    for i, (a, bb, c, col) in enumerate(rows):
        h = 36 if i == 0 else 60
        fill = "#eef2f7" if i == 0 else "#ffffff"
        b.append(f'<rect x="20" y="{y}" width="920" height="{h}" rx="8" fill="{fill}" stroke="#e2e8f0"/>')
        if i:
            b.append(f'<rect x="20" y="{y}" width="7" height="{h}" rx="3" fill="{col}"/>')
        def lines(x, arr, size, color, weight):
            n = len(arr)
            y0 = y + h / 2 - (n - 1) * 9 + 5
            for k, ln in enumerate(arr):
                b.append(text(x, y0 + k * 18, ln, size, color, "start", weight))
        lines(36, a.split("|"), 13.5, col if i else INK, "bold")
        lines(300, bb, 13, INK, "bold" if i == 0 else "normal")
        lines(580, c, 13, INK, "bold" if i == 0 else "normal")
        y += h + 6
    b.append(text(W / 2, 524, "Первый вопрос при любой «странной» ЭКГ — какие лекарства и в какой дозе принимает пациент", 14, RED, "middle", "bold"))
    return svg("\n".join(b), "Лекарства и ЭКГ")


files = {"s02_hyperk.svg": hyperk(), "s04_lytes.svg": lytes(), "s06_digoxin.svg": digoxin(),
         "s08_qt.svg": qt(), "s10_drugs.svg": drugs()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
