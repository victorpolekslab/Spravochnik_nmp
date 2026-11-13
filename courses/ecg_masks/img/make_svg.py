"""SVG-схемы для части 13 цикла «ЭКГ» (ecg_masks). Запуск: python3 ecg_part13_svg.py <папка>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)
G = gauss

MARKER = ('<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
          f'<path d="M0,0 L9,4.5 L0,9 z" fill="{MUTED}"/></marker></defs>')


def cx(lt, P=0.13, pr_dep=0.0, Q=-0.05, qw=0.007, R=1.0, S=-0.2, sw=0.009, st=0.0, shape="flat",
       T=0.3, tsym=False, tw=0.045, notch=0.0, coved=0.0, rp=0.0):
    """Универсальный комплекс. shape: convex (выпуклый ST), concave (вогнутый), flat.
    pr_dep — смещение сегмента PR (мВ), notch — зазубрина J, coved — сводчатый ST (Бругада)."""
    c = 0.225
    v = G(lt, P, 0.10, 0.022)
    if pr_dep:
        v += pr_dep * smooth(0.12, 0.14, lt) * (1 - smooth(c - 0.04, c - 0.025, lt))
    v += G(lt, Q, c - 0.012 - qw * 1.6, qw) + G(lt, R, c, 0.009) + G(lt, S, c + 0.02, sw)
    if rp:
        v += G(lt, rp, c + 0.045, 0.01)
    j = c + 0.035
    tc = c + 0.22
    if tsym:
        v += G(lt, T, tc, tw)
    else:
        sd = tw * 1.25 if lt < tc else tw * 0.7
        v += T * math.exp(-((lt - tc) ** 2) / (2 * sd * sd))
    if st:
        u = max(0.0, min(1.0, (lt - j) / (tc - j)))
        if shape == "convex":
            prof = 1.0 + 0.35 * math.sin(math.pi * u)
        elif shape == "concave":
            prof = 0.55 + 0.45 * u
        else:
            prof = 1.0
        w = smooth(j - 0.012, j + 0.006, lt) * (1 - smooth(tc - 0.01, tc + 0.09, lt))
        v += st * prof * w
    if notch:
        v += G(lt, notch, j - 0.004, 0.006)
    if coved:
        # сводчатый подъём от J, спускающийся в отрицательный T
        u = lt - j
        v += coved * smooth(-0.01, 0.0, u) * math.exp(-max(0, u) / 0.07) * (1 if u > -0.01 else 0)
    return v


def beats(f, rr=0.95, n=3, t0=0.05):
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


def panel(b, x0, y0, w, h, px, fn, base_mm, title, col=INK, sub=None, lw=2.1, sub2=None):
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


def arrow(x1, y1, x2, y2, label=None, lx=0, ly=0, anchor="start"):
    s = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="2.5" marker-end="url(#ar)"/>']
    if label:
        s.append(text(lx, ly, label, 13, MUTED, anchor, "bold"))
    return "\n".join(s)


# ---------- 1. Обзор масок ----------
def mimics():
    b = [text(W / 2, 34, "Подъём ST: инфаркт и его маски", 22, INK, "middle", "bold")]
    px = 3.2
    items = [("Инфаркт", RED, lambda lt: cx(lt, R=0.8, st=0.3, shape="convex", T=0.45, tsym=True, tw=0.06), "выпуклый ST, зона артерии", "зеркальная депрессия"),
             ("Перикардит", ORANGE, lambda lt: cx(lt, pr_dep=-0.1, st=0.18, shape="concave", T=0.35), "вогнутый ST во многих отв.", "депрессия PR"),
             ("Ранняя реполяризация", GREEN, lambda lt: cx(lt, R=1.1, S=-0.05, st=0.15, shape="concave", T=0.55, notch=0.18), "J-зазубрина, V4–V6", "высокий T"),
             ("Бругада, V1", VIOLET, lambda lt: cx(lt, R=0.3, S=-0.5, T=-0.35, tsym=True, coved=0.6, rp=0.25), "сводчатый ST ≥ 2 мм", "T отрицательный"),
             ("Аневризма", BROWN, lambda lt: cx(lt, Q=-0.9, qw=0.02, R=0.0, S=0.0, st=0.18, T=0.15), "QS + подъём ST", "ЭКГ не меняется"),
             ("ТЭЛА, III", BLUE, lambda lt: cx(lt, Q=-0.35, qw=0.012, R=0.6, S=-0.05, st=0.05, T=-0.25, tsym=True), "Q в III, T− в III", "S в I, ЧСС ↑")]
    for i, (name, col, f, s1, s2) in enumerate(items):
        x0 = 30 + (i % 3) * 306; y0 = 52 + (i // 3) * 236
        panel(b, x0, y0, 294, 160, px, beats(f, 0.95, 3), 28, name, col, s1, 2.1, s2)
    b.append(text(W / 2, 528, "Список состояний, затрудняющих диагностику ИМпST, — КР157_5; признаки — пособие, КР746_2, КР569_2", 13, MUTED, "middle"))
    return svg("\n".join(b), "Инфаркт и его маски")


# ---------- 2. Перикардит ----------
def pericarditis():
    b = [text(W / 2, 34, "Острый перикардит: диффузный вогнутый подъём ST", 21, INK, "middle", "bold")]
    px = 3.0
    up = lambda lt: cx(lt, pr_dep=-0.07, st=0.2, shape="concave", T=0.35)
    avr = lambda lt: -cx(lt, pr_dep=-0.07, st=0.2, shape="concave", T=0.35)
    leads = [("I", up), ("II", up), ("aVR", avr), ("V2", lambda lt: cx(lt, pr_dep=-0.07, R=0.4, S=-0.8, st=0.2, shape="concave", T=0.4)), ("V5", up), ("V6", up)]
    for i, (name, f) in enumerate(leads):
        x0 = 30 + (i % 3) * 306; y0 = 50 + (i // 3) * 132
        panel(b, x0, y0, 294, 118, px, beats(f, 0.9, 3), 22, name, ORANGE if name != "aVR" else BLUE)
    b.append(f'<rect x="30" y="322" width="900" height="200" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(48, 348, "Миоперикардит или ИМ (КР746_2, табл. А3-5)", 16, INK, "start", "bold"))
    rows = [("", "Инфаркт", "Перикардит"),
            ("ST", "выпуклый, может > 5 мм", "вогнутый, обычно < 5 мм"),
            ("Отведения", "зона одной артерии", "диффузно, почти во всех"),
            ("Зеркальные изменения", "характерны", "нет, кроме aVR и V1"),
            ("Q", "появляются", "нет"),
            ("PR", "не изменён", "↑ в aVR, ↓ в остальных")]
    for r, (a, bb, c) in enumerate(rows):
        y = 374 + r * 25
        wgt = "bold" if r == 0 else "normal"
        b.append(text(48, y, a, 13.5, INK, "start", "bold"))
        b.append(text(300, y, bb, 13.5, RED if r == 0 else INK, "start", wgt))
        b.append(text(600, y, c, 13.5, ORANGE if r == 0 else INK, "start", wgt))
    return svg("\n".join(b), "Острый перикардит")


# ---------- 3. ТЭЛА ----------
def pe():
    b = [text(W / 2, 34, "Острое лёгочное сердце (ТЭЛА): признак SI–QIII", 21, INK, "middle", "bold")]
    px = 3.2
    leads = [("I: глубокий S", lambda lt: cx(lt, Q=0.0, R=0.5, S=-0.6, T=0.2)),
             ("III: Q и T−", lambda lt: cx(lt, Q=-0.35, qw=0.012, R=0.7, S=-0.05, st=0.06, T=-0.3, tsym=True)),
             ("V1: rSR', T−", lambda lt: cx(lt, Q=0.0, R=0.25, S=-0.35, rp=0.6, T=-0.3, tsym=True))]
    for i, (name, f) in enumerate(leads):
        x0 = 30 + i * 306
        panel(b, x0, 50, 294, 150, px, beats(f, 0.55, 5), 24, name, BLUE)
    b.append(text(W / 2, 222, "Синусовая тахикардия — частый сопутствующий признак", 13.5, MUTED, "middle"))
    b.append(box(30, 244, 440, 226, "Признаки (пособие, гл. 9.2)", [
        "SI–QIII: глубокий S в I, Q в III",
        "(узкий, не шире 0,03–0,04 с)",
        "подъём ST в III, aVF, V1–V2,",
        "депрессия ST в I, aVL, V5–V6",
        "отрицательные T в III, aVF, V1–V3",
        "полная или неполная БПНПГ",
        "P-pulmonale в II, III, aVF",
        "быстрая обратная динамика"], BLUE, "#f3f7fc"))
    b.append(box(490, 244, 440, 226, "На вызове", [
        "ЭКГ при ТЭЛА может быть нормальной:",
        "признаки неспецифичны",
        "внезапная одышка, тахикардия,",
        "гипотония, SpO2 ↓, факторы риска",
        "тромбоза — думать о ТЭЛА",
        "Q в III и T− в III, V1–V3",
        "легко принять за нижний ИМ",
        "экстренная госпитализация,",
        "бригада СМП"], RED, "#fdf2f2"))
    return svg("\n".join(b), "ТЭЛА на ЭКГ")


# ---------- 4. СРР и Бругада ----------
def er_brugada():
    b = [text(W / 2, 34, "Ранняя реполяризация и синдром Бругада", 22, INK, "middle", "bold")]
    px = 4.4
    er = lambda lt: cx(lt, R=1.2, S=-0.05, st=0.15, shape="concave", T=0.6, notch=0.2)
    br = lambda lt: cx(lt, R=0.3, S=-0.5, T=-0.35, tsym=True, coved=0.6, rp=0.25)
    panel(b, 30, 50, 440, 190, px, beats(er, 0.95, 4), 30, "СРР · V4", GREEN, "J-зазубрина, вогнутый ST, высокий T")
    panel(b, 490, 50, 440, 190, px, beats(br, 0.95, 4), 22, "Бругада 1 типа · V1", VIOLET, "сводчатый подъём ST ≥ 2 мм, T−")
    b.append(box(30, 282, 440, 206, "Ранняя реполяризация (пособие, гл. 9.8)", [
        "чаще в V4–V6",
        "подъём ST выпуклостью книзу",
        "точка J высоко, зазубрина на",
        "нисходящем колене R",
        "S в левых грудных уменьшается",
        "бывает у здоровых; при нагрузке",
        "подъём ST уменьшается",
        "сравнить со старой ЭКГ"], GREEN, "#f1faf4"))
    b.append(box(490, 282, 440, 206, "Синдром Бругада (КР569_2)", [
        "сводчатый подъём ST ≥ 2 мм в V1–V2",
        "каналопатия, риск ФЖ и ВСС",
        "чаще у мужчин, ФЖ во сне и покое",
        "триггеры: лихорадка, алкоголь, кокаин,",
        "психотропные, некоторые ААП",
        "лихорадка — сразу снижать температуру",
        "обморок + Бругада 1 типа — к ИКД",
        "исключить ОКС, ТЭЛА, перикардит"], VIOLET, "#f6f1fd"))
    return svg("\n".join(b), "Ранняя реполяризация и Бругада")


# ---------- 5. Алгоритм ----------
def algorithm():
    b = [text(W / 2, 34, "Подъём ST: инфаркт или маска? Вопросы на вызове", 21, INK, "middle", "bold")]
    qs = [("1. Есть ли типичная боль или эквиваленты?", "есть — сначала думаем об ОКС"),
          ("2. Подъём в зоне одной артерии?", "диффузный — перикардит"),
          ("3. Есть зеркальная депрессия?", "есть — за ИМ (при перикардите — только aVR, V1)"),
          ("4. Форма ST?", "выпуклый — ИМ; вогнутый — перикардит, СРР"),
          ("5. Есть Q? Депрессия PR?", "Q — ИМ или аневризма; PR ↓ — перикардит"),
          ("6. Что на старой ЭКГ?", "то же — СРР, аневризма, ГЛЖ; новое — острое"),
          ("7. Клиника не сердечная?", "внезапная одышка — ТЭЛА; лихорадка + V1 — Бругада")]
    for i, (q, a) in enumerate(qs):
        y = 56 + i * 54
        b.append(f'<rect x="30" y="{y}" width="900" height="46" rx="10" fill="#f8fafc" stroke="#e2e8f0"/>')
        b.append(text(48, y + 29, q, 15, INK, "start", "bold"))
        b.append(text(512, y + 29, a, 13.8, BLUE))
    b.append(f'<rect x="30" y="440" width="900" height="82" rx="14" fill="#fdf2f2" stroke="{RED}" stroke-width="2"/>')
    b.append(text(48, 470, "Сомневаетесь — тактика ОКС и телемедицина.", 17, RED, "start", "bold"))
    b.append(text(48, 498, "Пропущенный инфаркт опаснее лишней доставки в стационар.", 14.5, INK))
    return svg("\n".join(b), "Инфаркт или маска")


files = {"s02_mimics.svg": mimics(), "s04_pericarditis.svg": pericarditis(), "s06_pe.svg": pe(),
         "s08_er_brugada.svg": er_brugada(), "s10_algorithm.svg": algorithm()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
