"""SVG-схемы для части 8 цикла «ЭКГ» (ecg_avb). Запуск: python3 ecg_part8_svg.py <папка>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)


def strip(b, x0, y0, w, rows_mm, px, fn, base_mm, lw=2.0):
    h = rows_mm * px
    b.append(grid(x0, y0, w - (w % px), h, px))
    base = y0 + base_mm * px
    b.append(trace(fn, x0, base, w - 2, 25 * px, 10 * px, INK, lw, 0.4))
    return base


def P(lt):
    return gauss(lt, 0.15, 0.0, 0.022)


def QRS(lt, wide=False):
    """lt — от пика R."""
    if wide:
        return (gauss(lt, 1.1, 0.0, 0.03) + gauss(lt, -0.35, 0.065, 0.024)
                + gauss(lt, -0.42, 0.25, 0.06))
    return (gauss(lt, -0.08, -0.02, 0.007) + gauss(lt, 1.0, 0.0, 0.009)
            + gauss(lt, -0.22, 0.02, 0.009) + gauss(lt, 0.3, 0.22, 0.04))


def ecgfn(ps, rs, wide=False):
    """ps — моменты пика P; rs — моменты пика R."""
    def f(t):
        v = 0.0
        for p in ps:
            if abs(t - p) < 0.1:
                v += P(t - p)
        for r in rs:
            lt = t - r
            if -0.1 < lt < 0.5:
                v += QRS(lt, wide)
        return v
    return f


def bracket(x1, x2, y, label, col=BLUE, size=12.5, up=True):
    d = -1 if up else 1
    s = [f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="{col}" stroke-width="2"/>']
    for x in (x1, x2):
        s.append(f'<line x1="{x:.1f}" y1="{y-5}" x2="{x:.1f}" y2="{y+5}" stroke="{col}" stroke-width="2"/>')
    if label:
        s.append(text((x1 + x2) / 2, y + d * 9 + (0 if up else 7), label, size, col, "middle", "bold"))
    return "\n".join(s)


def pmarks(b, ps, x0, y, pxs, col=RED, xmax=915, blocked=()):
    for p in ps:
        x = x0 + p * pxs
        if x < xmax:
            c = RED if p in blocked else col
            b.append(f'<path d="M{x-6:.1f},{y+10} L{x+6:.1f},{y+10} L{x:.1f},{y} z" fill="{c}"/>')


def box(x, y, w, h, title, lines, col, fill="#f8fafc", size=13.5):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{col}" stroke-width="2.5"/>',
         text(x + 14, y + 26, title, 16, col, "start", "bold")]
    for j, ln in enumerate(lines):
        s.append(text(x + 14, y + 48 + j * 19, ln, size, INK))
    return "\n".join(s)


# ---------- 1. АВ-блокада I степени ----------
def avb1():
    b = [text(W / 2, 38, "АВ-блокада I степени: PQ постоянно больше 0,20 с", 22, INK, "middle", "bold")]
    px = 3.6; pxs = 25 * px
    pp = 0.9
    rows = [("Норма", 0.16, GREEN), ("АВ-блокада I степени", 0.32, RED)]
    for i, (name, pq, col) in enumerate(rows):
        ps = [0.25 + pp * k for k in range(10)]
        rs = [p + pq for p in ps]
        y0 = 78 + i * 180
        strip(b, 40, y0, 880, 34, px, ecgfn(ps, rs), 22)
        b.append(text(40, y0 - 12, name, 18, col, "start", "bold"))
        for k in (1, 4, 7):
            x1 = 40 + (ps[k] - 0.04) * pxs; x2 = 40 + (rs[k] - 0.02) * pxs
            b.append(bracket(x1, x2, y0 + 34 * px - 14, f"PQ {pq+0.02:.2f}".replace(".", ","), col, 12.5, False))
        b.append(text(920, y0 - 12, "каждый P проводится" if i == 0 else "каждый P проводится, но с задержкой", 14.5, INK, "end"))
    b.append(f'<rect x="40" y="420" width="880" height="104" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(60, 448, "Выпадений QRS нет — ЧСС не меняется, жалоб обычно нет", 15, INK, "start", "bold"))
    b.append(text(60, 472, "QRS узкие — задержка в АВ-узле; QRS широкие и деформированы — возможна дистальная блокада (пособие)", 13.5, INK))
    b.append(text(60, 494, "Встречается у здоровых: транзиторно у 12 % подростков, у 4–6 % молодых взрослых (КР160_2)", 13.5, INK))
    b.append(text(60, 514, "Причины: ваготония, β-блокаторы, верапамил, гликозиды, ИБС, миокардит", 13.5, MUTED))
    return svg("\n".join(b), "АВ-блокада I степени")


# ---------- 2. Мобитц I и II ----------
def mobitz():
    b = [text(W / 2, 36, "АВ-блокада II степени: Мобитц I и Мобитц II", 22, INK, "middle", "bold")]
    px = 3.4; pxs = 25 * px
    pp = 0.8
    ps = [0.2 + pp * k for k in range(13)]
    pqs = [0.18, 0.28, 0.34, None] * 4
    rs = [p + q for p, q in zip(ps, pqs) if q is not None]
    y0 = 76
    strip(b, 40, y0, 880, 36, px, ecgfn(ps, rs), 24)
    b.append(text(40, y0 - 12, "Мобитц I (Самойлова — Венкебаха)", 18, ORANGE, "start", "bold"))
    b.append(text(920, y0 - 12, "PQ удлиняется → выпадение QRS → цикл снова", 14, INK, "end"))
    for k, q in enumerate(pqs[:4]):
        if q:
            x1 = 40 + (ps[k] - 0.04) * pxs; x2 = 40 + (ps[k] + q - 0.02) * pxs
            b.append(bracket(x1, x2, y0 + 36 * px - 14, f"{q+0.02:.2f}".replace(".", ","), ORANGE, 12, False))
    xd = 40 + ps[3] * pxs
    b.append(text(xd, y0 + 18, "P без QRS", 13, RED, "middle", "bold"))
    # Мобитц II
    pq2 = 0.18
    drop = {3, 7, 10}
    ps2 = [0.2 + pp * k for k in range(13)]
    rs2 = [p + pq2 for k, p in enumerate(ps2) if k not in drop]
    y1 = 286
    strip(b, 40, y1, 880, 36, px, ecgfn(ps2, rs2, wide=True), 24)
    b.append(text(40, y1 - 12, "Мобитц II", 18, RED, "start", "bold"))
    b.append(text(920, y1 - 12, "PQ постоянный → внезапное выпадение; QRS часто широкие", 14, INK, "end"))
    for k in drop:
        x = 40 + ps2[k] * pxs
        b.append(text(x, y1 + 18, "P без QRS", 13, RED, "middle", "bold"))
    for k in (1, 5, 8):
        x1 = 40 + (ps2[k] - 0.04) * pxs; x2 = 40 + (ps2[k] + pq2 - 0.02) * pxs
        b.append(bracket(x1, x2, y1 + 36 * px - 14, "0,20", RED, 12, False))
    b.append(text(W / 2, 482, "Мобитц I — чаще в АВ-узле, QRS обычно узкие (пособие)", 14, ORANGE, "middle", "bold"))
    b.append(text(W / 2, 506, "Мобитц II — чаще на уровне ветвей пучка Гиса; может перейти в полную блокаду", 14, RED, "middle", "bold"))
    b.append(text(W / 2, 528, "Число P всегда больше числа QRS (пособие, гл. 6.3.2; КР160_2)", 13, MUTED, "middle"))
    return svg("\n".join(b), "Мобитц I и Мобитц II")


# ---------- 3. 2:1 и далеко зашедшая ----------
def advanced():
    b = [text(W / 2, 36, "Блокада 2:1 и далеко зашедшая АВ-блокада II степени", 22, INK, "middle", "bold")]
    px = 3.4; pxs = 25 * px
    pp = 0.75
    ps = [0.2 + pp * k for k in range(14)]
    rs = [p + 0.2 for k, p in enumerate(ps) if k % 2 == 0]
    y0 = 76
    strip(b, 40, y0, 880, 34, px, ecgfn(ps, rs), 22)
    b.append(text(40, y0 - 12, "2:1 — ЧСС 40 при частоте P 80", 18, ORANGE, "start", "bold"))
    b.append(text(920, y0 - 12, "проводится каждый второй P", 14, INK, "end"))
    pmarks(b, ps, 40, y0 + 34 * px + 4, pxs, ORANGE, blocked=set(p for k, p in enumerate(ps) if k % 2))
    rs3 = [p + 0.2 for k, p in enumerate(ps) if k % 3 == 0]
    y1 = 280
    strip(b, 40, y1, 880, 34, px, ecgfn(ps, rs3, wide=True), 22)
    b.append(text(40, y1 - 12, "3:1 — ЧСС около 27", 18, RED, "start", "bold"))
    b.append(text(920, y1 - 12, "выпадают 2 и больше QRS подряд", 14, INK, "end"))
    pmarks(b, ps, 40, y1 + 34 * px + 4, pxs, ORANGE, blocked=set(p for k, p in enumerate(ps) if k % 3))
    b.append(text(40, 446, "▲ проведённый P", 13.5, ORANGE, "start", "bold"))
    b.append(text(200, 446, "▲ заблокированный P", 13.5, RED, "start", "bold"))
    b.append(text(W / 2, 478, "2:1 нельзя отнести к Мобитц I или II по одной записи: два подряд проведённых P для сравнения PQ нет", 13.5, INK, "middle"))
    b.append(text(W / 2, 500, "Далеко зашедшая блокада: резкая брадикардия, головокружение, обмороки, замещающие ритмы (пособие)", 13.5, INK, "middle"))
    b.append(text(W / 2, 524, "Мобитц II, далеко зашедшая и полная блокада без обратимой причины — показание к ЭКС (КР160_2)", 13.5, RED, "middle", "bold"))
    return svg("\n".join(b), "АВ-блокада 2:1 и далеко зашедшая")


# ---------- 4. Полная АВ-блокада ----------
def avb3():
    b = [text(W / 2, 36, "АВ-блокада III степени: предсердия и желудочки — каждый в своём ритме", 20, INK, "middle", "bold")]
    px = 3.4; pxs = 25 * px
    ps = [0.15 + 0.8 * k for k in range(14)]          # 75 в минуту
    rows = [("Проксимальная: QRS узкие, ЧСС 40–60", [0.55 + 1.3 * k for k in range(8)], False, ORANGE),
            ("Дистальная: QRS широкие, ЧСС ≤ 40–45", [0.7 + 1.6 * k for k in range(7)], True, RED)]
    for i, (name, rs, wide, col) in enumerate(rows):
        y0 = 76 + i * 196
        strip(b, 40, y0, 880, 36, px, ecgfn(ps, rs, wide), 24)
        b.append(text(40, y0 - 12, name, 17, col, "start", "bold"))
        b.append(text(920, y0 - 12, "P 75 в мин, RR > PP, связи P и QRS нет", 13.5, INK, "end"))
        pmarks(b, ps, 40, y0 + 36 * px + 4, pxs, BLUE)
    b.append(text(40, 470, "▲ зубцы P: идут ровно, «наезжают» на QRS и T в любом месте", 13.5, BLUE, "start", "bold"))
    b.append(text(40, 496, "PQ всё время разный — главный признак: P и QRS не связаны (пособие, гл. 6.3.3)", 14, INK))
    b.append(text(40, 520, "Чем ниже водитель ритма желудочков, тем реже ритм, шире QRS и выше риск асистолии", 14, RED, "start", "bold"))
    return svg("\n".join(b), "Полная АВ-блокада")


# ---------- 5. Приступ МАС ----------
def mas():
    b = [text(W / 2, 36, "Приступ Морганьи — Адамса — Стокса: асистолия желудочков", 21, INK, "middle", "bold")]
    px = 3.0; pxs = 25 * px
    ps = [0.15 + 0.8 * k for k in range(15)]
    rs = [0.37, 1.17, 1.97] + [10.4, 11.6]
    y0 = 74
    strip(b, 40, y0, 880, 36, px, ecgfn(ps, rs, wide=False), 24)
    xs = 40 + 2.5 * pxs; xe = 40 + 10.3 * pxs
    b.append(f'<rect x="{xs:.1f}" y="{y0+2}" width="{xe-xs:.1f}" height="{36*px-4}" fill="{RED}" opacity="0.07"/>')
    b.append(text((xs + xe) / 2, y0 + 20, "P есть, QRS нет — асистолия желудочков", 14, RED, "middle", "bold"))
    b.append(bracket(xs, xe, y0 + 36 * px - 14, "> 10–20 с — потеря сознания, судороги", RED, 13.5, False))
    b.append(text(920, y0 - 10, "затем — замещающий ритм", 13.5, BLUE, "end", "bold"))
    ty = 222
    b.append(box(40, ty, 430, 236, "Что происходит (пособие)", [
        "переход АВ-блокады II степени в",
        "полную, пока не включился",
        "замещающий водитель ритма",
        "или угнетение замещающего ритма",
        "или ТЖ, ФЖ при полной блокаде",
        "внезапная потеря сознания,",
        "затем судороги",
        "каждый приступ может стать",
        "последним — прогноз плохой"], RED, "#fdf2f2"))
    b.append(box(490, ty, 430, 236, "Что делать", [
        "пульса нет — СЛР, ритм на мониторе:",
        "асистолия — #эпинефрин 1 мг сразу,",
        "ФЖ — дефибрилляция (КР569_2)",
        "пульс есть, брадикардия с симптомами —",
        "атропин 0,5–1 мг, до 3 мг;",
        "затем #допамин (КР160_2)",
        "вызов бригады СМП — временная ЭКС",
        "экстренная госпитализация",
        "препараты — если есть в укладке"], BLUE, "#f3f7fc"))
    return svg("\n".join(b), "Приступ Морганьи-Адамса-Стокса")


files = {"s02_avb1.svg": avb1(), "s04_mobitz.svg": mobitz(), "s06_advanced.svg": advanced(),
         "s08_avb3.svg": avb3(), "s10_mas.svg": mas()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
