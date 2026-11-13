"""SVG-схемы для части 4 цикла «ЭКГ» (ecg_svt). Запуск: python3 ecg_part4_svg.py <папка>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)


def bracket(x1, x2, y, label, col=BLUE, size=14, up=True):
    d = -1 if up else 1
    s = [f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="{col}" stroke-width="2.2"/>']
    for x in (x1, x2):
        s.append(f'<line x1="{x:.1f}" y1="{y-6}" x2="{x:.1f}" y2="{y+6}" stroke="{col}" stroke-width="2.2"/>')
    if label:
        s.append(text((x1 + x2) / 2, y + d * 9 + (0 if up else 8), label, size, col, "middle", "bold"))
    return "\n".join(s)


def beat_kind(lt, kind):
    if kind == "N":   # синусовый
        return beat_p(lt, P=0.15, Q=-0.07, R=1.05, S=-0.25, T=0.32)
    if kind == "A":   # предсердная ЭС: деформированный P'
        return beat_p(lt, P=0.0, Q=-0.07, R=1.05, S=-0.25, T=0.32) + gauss(lt, 0.07, 0.10, 0.016) + gauss(lt, -0.07, 0.135, 0.016)
    if kind == "J":   # из АВ-соединения: узкий QRS, P− после
        return beat_p(lt, P=0.0, Q=-0.07, R=1.05, S=-0.25, T=0.32) + gauss(lt, -0.12, 0.33, 0.02)
    if kind == "V":   # желудочковая ЭС: широкий, T дискордантный
        return beat_p(lt, P=0.0, Q=-0.04, R=1.25, S=-0.35, T=-0.5, qrs=2.7)
    if kind == "V2":  # другая морфология (политопная)
        return beat_p(lt, P=0.0, Q=0.0, R=0.25, S=-1.15, T=0.55, qrs=2.7)
    if kind == "S":   # НЖТ: узкий, P не виден
        return beat_p(lt, P=0.0, Q=-0.06, R=1.0, S=-0.25, T=0.22)
    return 0.0


def compose(events):
    def f(t):
        v = 0.0
        for r, k in events:
            lt = t - r + 0.225
            if -0.3 < lt < 0.75:
                v += beat_kind(lt, k)
        return v
    return f


def strip(b, x0, y0, w, rows_mm, px, fn, base_mm, lw=2.0):
    h = rows_mm * px
    b.append(grid(x0, y0, w - (w % px), h, px))
    base = y0 + base_mm * px
    b.append(trace(fn, x0, base, w - 2, 25 * px, 10 * px, INK, lw))
    return base


# ---------- 1. Синусовая тахикардия или НЖТ ----------
def sinus_vs_svt():
    b = [text(W / 2, 38, "Синусовая тахикардия или пароксизмальная НЖТ?", 23, INK, "middle", "bold")]
    px = 3.4
    # синусовая: RR 0.52 → на вагусной пробе постепенно 0.6, 0.68, затем снова 0.55
    rr = [0.52] * 5 + [0.56, 0.62, 0.68, 0.70, 0.64, 0.58, 0.54, 0.52, 0.52, 0.52, 0.52, 0.52, 0.52]
    ev, t = [], 0.3
    for d in rr:
        ev.append((t, "N")); t += d
    y0 = 70
    strip(b, 40, y0, 880, 34, px, compose(ev), 23)
    b.append(text(40, y0 - 10, "Синусовая: P+ перед каждым QRS, на вагусной пробе ЧСС снижается постепенно", 15.5, GREEN, "start", "bold"))
    x1 = 40 + (0.3 + 0.52 * 5 - 0.1) * 25 * px
    b.append(f'<rect x="{x1:.1f}" y="{y0+2}" width="{3.2*25*px:.1f}" height="{34*px-4}" fill="{BLUE}" opacity="0.08"/>')
    b.append(text(x1 + 6, y0 + 20, "вагусная проба", 13, BLUE, "start", "bold"))
    # НЖТ: RR 0.32 фиксировано, проба — резкий обрыв, затем синусовый
    ev2, t = [], 0.25
    for _ in range(20):
        ev2.append((t, "S")); t += 0.32
    t += 0.55
    for _ in range(5):
        ev2.append((t, "N")); t += 0.85
    y1 = 300
    strip(b, 40, y1, 880, 34, px, compose(ev2), 23)
    b.append(text(40, y1 - 10, "НЖТ: регулярно 190 в мин, P не видны; проба либо обрывает приступ, либо ничего не меняет", 15.5, RED, "start", "bold"))
    xs = 40 + (0.25 + 0.32 * 19 + 0.3) * 25 * px
    b.append(f'<line x1="{xs:.1f}" y1="{y1+4}" x2="{xs:.1f}" y2="{y1+34*px-4}" stroke="{BLUE}" stroke-width="2.5" stroke-dasharray="6 5"/>')
    b.append(text(xs + 8, y1 + 20, "обрыв приступа", 13, BLUE, "start", "bold"))
    b.append(text(W / 2, 528, "Пособие, гл. 5; КР619_3 · схема учебная, 25 мм/с", 13, MUTED, "middle"))
    return svg("\n".join(b), "Синусовая тахикардия и НЖТ")


# ---------- 2. Три вида экстрасистол ----------
def es_types():
    b = [text(W / 2, 36, "Три вида экстрасистол", 23, INK, "middle", "bold")]
    px = 3.0; pxs = 25 * px
    RR = 0.8
    rows = [("Предсердная", "P′ изменён · QRS обычный · пауза неполная", BLUE, "A", 0.55, 0.88),
            ("Из АВ-соединения", "QRS обычный · P− после или не виден · пауза неполная", ORANGE, "J", 0.55, 0.88),
            ("Желудочковая", "P нет · QRS широкий, T против QRS · пауза полная", RED, "V", 0.55, 2 * RR - 0.55)]
    for i, (name, desc, col, k, ci, pause) in enumerate(rows):
        y0 = 62 + i * 155
        r = [0.3, 0.3 + RR, 0.3 + 2 * RR]
        es = r[-1] + ci
        after = es + pause
        ev = [(x, "N") for x in r] + [(es, k)] + [(after + j * RR, "N") for j in range(6)]
        base = strip(b, 300, y0, 630, 36, px, compose(ev), 24)
        xe = 300 + es * pxs
        b.append(f'<circle cx="{xe:.1f}" cy="{y0+10}" r="0"/>')
        b.append(text(xe, y0 + 16, "ЭС", 13, col, "middle", "bold"))
        yb = y0 + 36 * px - 26
        b.append(bracket(300 + r[-1] * pxs, xe, yb, "", MUTED, 11, False))
        b.append(bracket(xe, 300 + after * pxs, yb, "", col, 11, False))
        b.append(text(300 + r[-1] * pxs - 4, yb + 17, "сцепление", 11, MUTED, "end", "bold"))
        b.append(text(300 + after * pxs + 4, yb + 17, "пауза", 11, col, "start", "bold"))
        b.append(f'<rect x="30" y="{y0+6}" width="7" height="{36*px-12}" rx="3" fill="{col}"/>')
        b.append(text(48, y0 + 34, name, 18, col, "start", "bold"))
        for j, part in enumerate(desc.split(" · ")):
            b.append(text(48, y0 + 58 + j * 19, part, 13, INK))
    b.append(text(W / 2, 530, "Полная пауза: RR до ЭС + RR после ЭС = 2 обычных RR (пособие, гл. 5)", 13.5, MUTED, "middle"))
    return svg("\n".join(b), "Предсердная, АВ и желудочковая экстрасистолы")


# ---------- 3. Угрожающие ЖЭ ----------
def threatening():
    b = [text(W / 2, 36, "Желудочковые экстрасистолы, которые настораживают", 22, INK, "middle", "bold")]
    px = 2.8
    RR = 0.8
    rows = [("Бигеминия", [(0.3, "N"), (0.85, "V"), (1.9, "N"), (2.45, "V"), (3.5, "N"), (4.05, "V"), (5.1, "N"), (5.65, "V"), (6.7, "N"), (7.25, "V")]),
            ("Парные", [(0.3, "N"), (1.1, "N"), (1.65, "V"), (2.1, "V"), (3.3, "N"), (4.1, "N"), (4.9, "N"), (5.7, "N"), (6.5, "N"), (7.3, "N")]),
            ("Политопные", [(0.3, "N"), (0.85, "V"), (1.9, "N"), (2.7, "N"), (3.25, "V2"), (4.3, "N"), (5.1, "N"), (5.65, "V"), (6.7, "N"), (7.5, "N")]),
            ("Ранние («R на T»)", [(0.3, "N"), (1.1, "N"), (1.43, "V"), (2.7, "N"), (3.5, "N"), (4.3, "N"), (5.1, "N"), (5.43, "V"), (6.7, "N"), (7.5, "N")])]
    for i, (name, ev) in enumerate(rows):
        last = ev[-1][0]
        ev = ev + [(last + 0.8 * (j + 1) + (0.25 if ev[-1][1] != "N" else 0), "N") for j in range(4)]
        y0 = 60 + i * 112
        strip(b, 250, y0, 680, 32, px, compose(ev), 21, 1.8)
        b.append(f'<rect x="30" y="{y0+8}" width="7" height="{32*px-16}" rx="3" fill="{RED}"/>')
        b.append(text(48, y0 + 52, name, 18, RED, "start", "bold"))
    b.append(text(W / 2, 522, "По пособию «угрожающие»: частые, политопные, парные (групповые), ранние — предвестники ЖТ и ФЖ", 14, INK, "middle"))
    return svg("\n".join(b), "Угрожающие желудочковые экстрасистолы")


# ---------- 4. Пароксизм НЖТ ----------
def svt_paroxysm():
    b = [text(W / 2, 38, "Пароксизмальная НЖТ: внезапно началась — внезапно закончится", 22, INK, "middle", "bold")]
    px = 3.4; pxs = 25 * px
    ev, t = [], 0.3
    for _ in range(3):
        ev.append((t, "N")); t += 0.85
    t -= 0.45
    ev.append((t, "A")); t += 0.33
    for _ in range(26):
        ev.append((t, "S")); t += 0.31
    y0 = 80
    strip(b, 40, y0, 880, 40, px, compose(ev), 27)
    xs = 40 + (ev[3][0]) * pxs
    b.append(f'<line x1="{xs:.1f}" y1="{y0+4}" x2="{xs:.1f}" y2="{y0+40*px-4}" stroke="{RED}" stroke-width="2.5" stroke-dasharray="6 5"/>')
    b.append(text(xs - 8, y0 + 22, "синусовый ритм", 13, GREEN, "end", "bold"))
    b.append(text(xs + 8, y0 + 22, "внезапный старт: ранний P′ запускает приступ", 13, RED, "start", "bold"))
    r1 = 40 + ev[8][0] * pxs; r2 = 40 + ev[9][0] * pxs
    b.append(bracket(r1, r2, y0 + 40 * px - 20, "RR 0,31 с → ЧСС ≈ 190", BLUE, 13, False))
    # таблица признаков
    ty = 250
    b.append(f'<rect x="40" y="{ty}" width="880" height="250" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    left = [("ЧСС 140–250 в мин", "по пособию; ритм правильный"), ("QRS узкие", "как до приступа (редко — аберрация)"),
            ("P не видны", "или P− сразу после QRS")]
    right = [("Частота постоянна", "не меняется при нагрузке и дыхании"), ("Начало и конец внезапные", "пациент сам их чувствует"),
             ("Вагусная проба", "обрыв приступа или без эффекта")]
    for col_i, items in enumerate((left, right)):
        for j, (h, s_) in enumerate(items):
            x = 70 + col_i * 440; y = ty + 50 + j * 70
            b.append(f'<circle cx="{x}" cy="{y-6}" r="8" fill="{RED if col_i == 0 else BLUE}"/>')
            b.append(text(x + 20, y, h, 17, INK, "start", "bold"))
            b.append(text(x + 20, y + 23, s_, 14, MUTED))
    b.append(text(W / 2, 528, "Пособие, гл. 5.3.2 · схема учебная, 25 мм/с", 13, MUTED, "middle"))
    return svg("\n".join(b), "Пароксизм НЖТ")


# ---------- 5. Алгоритм: узкий QRS ----------
def algorithm():
    b = [text(W / 2, 38, "Регулярная тахикардия с узким QRS: что делать (КР619_3)", 22, INK, "middle", "bold")]
    b.append('<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
             f'<path d="M0,0 L9,4.5 L0,9 z" fill="{MUTED}"/></marker></defs>')

    def box(x, y, w, h, title, lines, col, fill="#f8fafc"):
        s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{col}" stroke-width="2.5"/>',
             text(x + 16, y + 28, title, 17, col, "start", "bold")]
        for j, ln in enumerate(lines):
            s.append(text(x + 16, y + 52 + j * 20, ln, 14, INK))
        return "\n".join(s)

    def arrow(x1, y1, x2, y2, label=None, lx=None, ly=None, anchor="start"):
        s = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="2.5" marker-end="url(#ar)"/>']
        if label:
            s.append(text(lx, ly, label, 13, MUTED, anchor, "bold"))
        return "\n".join(s)
    b.append(box(330, 60, 300, 70, "ЭКГ в 12 отведениях", ["QRS ≤ 120 мс, ритм регулярный"], INK))
    b.append(arrow(400, 130, 210, 170, "нестабилен", 268, 140, "end"))
    b.append(arrow(560, 130, 700, 170, "стабилен", 668, 140, "start"))
    b.append(box(40, 175, 330, 110, "Синхронизированная ЭИТ", ["гипотония, нарушение сознания,", "отёк лёгких, ангинозная боль", "нет ЭИТ на месте — СМП"], RED, "#fdf2f2"))
    b.append(box(560, 175, 360, 86, "1. Вагусные приёмы", ["лёжа, ноги подняты, 15–20 с", "проба Вальсальвы и другие"], BLUE))
    b.append(arrow(740, 261, 740, 282, None))
    b.append(box(560, 284, 360, 86, "2. #Трифосаденин в/в болюсом", ["10 мг за 2 с; через 2 мин — 20 мг", "нельзя: тяжёлая БА, стенокардия"], BLUE))
    b.append(arrow(740, 370, 740, 391, None))
    b.append(box(560, 393, 360, 106, "3. Верапамил или метопролол", ["верапамил 5–10 мг в/в за 2–3 мин", "метопролол 5 мг, повтор через 5 мин,", "всего 10–15 мг"], BLUE))
    b.append(box(40, 330, 470, 150, "Не помогло или стало хуже", ["синхронизированная ЭИТ (КР619_3)", "широкий QRS — верапамил не вводить", "после купирования: ЭКГ, актив или", "госпитализация, если приступ впервые"], ORANGE))
    b.append(arrow(560, 446, 514, 420, None))
    b.append(text(W / 2, 528, "Дозы — КР619_3, приложение А3 · препараты — если есть в укладке", 13, MUTED, "middle"))
    return svg("\n".join(b), "Алгоритм при НЖТ с узким QRS")


files = {"s02_sinus_vs_svt.svg": sinus_vs_svt(), "s05_es_types.svg": es_types(), "s07_threatening.svg": threatening(),
         "s08_svt.svg": svt_paroxysm(), "s09_algorithm.svg": algorithm()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
