"""SVG-схемы для части 11 цикла «ЭКГ» (ecg_mi). Запуск: python3 ecg_part11_svg.py <папка>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)
G = gauss

MARKER = ('<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
          f'<path d="M0,0 L9,4.5 L0,9 z" fill="{MUTED}"/></marker></defs>')


def mi(lt, q=-0.06, qw=0.007, R=1.0, S=-0.2, st=0.0, T=0.3, tsym=False, tw=0.045):
    """Комплекс с настраиваемым Q; lt от начала цикла, R при 0.225."""
    c = 0.225
    v = G(lt, 0.13, 0.10, 0.022)
    qc = c - 0.012 - qw * 1.6
    v += G(lt, q, qc, qw) + G(lt, R, c, 0.009) + G(lt, S, c + 0.02, 0.009)
    j = c + 0.035
    tc = c + 0.22
    if tsym:
        v += G(lt, T, tc, tw)
    else:
        sd = tw * 1.25 if lt < tc else tw * 0.7
        v += T * math.exp(-((lt - tc) ** 2) / (2 * sd * sd))
    if st:
        w = smooth(j - 0.012, j + 0.006, lt) * (1 - smooth(tc - 0.01, tc + 0.09, lt))
        v += st * w
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


def panel(b, x0, y0, w, h, px, fn, base_mm, title, col=INK, sub=None, sub2=None, lw=2.1):
    b.append(grid(x0, y0, w - (w % px), h, px))
    b.append(trace(fn, x0, y0 + base_mm * px, w - 2, 25 * px, 10 * px, INK, lw, 0.3))
    b.append(text(x0 + 8, y0 + 20, title, 14.5, col, "start", "bold"))
    if sub:
        b.append(text(x0 + w / 2, y0 + h + 19, sub, 13, INK, "middle", "bold"))
    if sub2:
        b.append(text(x0 + w / 2, y0 + h + 37, sub2, 12.5, MUTED, "middle"))


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


# ---------- 1. Патологический Q ----------
def qwave():
    b = [text(W / 2, 36, "Патологический зубец Q — признак некроза", 22, INK, "middle", "bold")]
    px = 7.0; pxs = 25 * px
    items = [("Норма: q маленький", GREEN, dict(q=-0.08, qw=0.006, R=1.2), "q < 0,03 с и < 1/4 R"),
             ("Патологический Q", RED, dict(q=-0.45, qw=0.016, R=0.8), "Q ≥ 0,03 с и > 1/4 R"),
             ("QS", RED, dict(q=-1.1, qw=0.022, R=0.0, S=0.0), "R нет — трансмуральный некроз")]
    for i, (name, col, kw, sub) in enumerate(items):
        x0 = 30 + i * 306
        f = lambda lt, kw=kw: mi(lt - 0.15, **kw)
        b.append(grid(x0, 56, 294 - (294 % px), 260, px))
        b.append(trace(f, x0, 56 + 22 * px, 292, pxs, 10 * px, INK, 2.5, 0.25))
        b.append(text(x0 + 10, 80, name, 16, col, "start", "bold"))
        b.append(text(x0 + 147, 340, sub, 14, col, "middle", "bold"))
    b.append(f'<rect x="30" y="366" width="900" height="156" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
    lines = [("Пособие, гл. 8.1.3:", INK, True),
             ("• патологический Q — продолжительность больше 0,03 с, амплитуда больше 1/4 R: нетрансмуральный некроз", INK, False),
             ("• комплекс QS — трансмуральный некроз", INK, False),
             ("• Q может углубиться и без некроза: острая ишемия, гипертрофия, блокады ножек", MUTED, False),
             ("• КР155_2: Q после перенесённого ИМ — единственный достаточно специфичный признак ИБС на ЭКГ покоя", INK, False)]
    for j, (ln, col, bold) in enumerate(lines):
        b.append(text(50, 394 + j * 27, ln, 14, col, "start", "bold" if bold else "normal"))
    return svg("\n".join(b), "Патологический зубец Q")


# ---------- 2. Стадии ----------
def stages():
    b = [text(W / 2, 34, "Динамика ЭКГ при крупноочаговом инфаркте (пособие, гл. 8.2)", 20, INK, "middle", "bold")]
    px = 3.3
    items = [("1. Первые 20–30 мин", BLUE, dict(st=-0.08, T=0.75, tsym=True), "высокий T, ST ↓", "субэндокардиальная ишемия"),
             ("2. Часы", RED, dict(st=0.35, T=0.55, tsym=True, tw=0.06), "ST ↑ сливается с T", "«монофазная кривая»"),
             ("3. 1–2 сутки", RED, dict(q=-0.4, qw=0.015, R=0.5, st=0.3, T=0.35, tsym=True, tw=0.06), "Q + ST ↑, R меньше", "формируется некроз"),
             ("4. Несколько суток", ORANGE, dict(q=-0.5, qw=0.016, R=0.4, st=0.12, T=-0.3, tsym=True), "ST ближе к изолинии, T−", "острая стадия до 8–10 сут"),
             ("5. Подострая", VIOLET, dict(q=-0.5, qw=0.016, R=0.4, T=-0.55, tsym=True, tw=0.04), "Q + глубокий T−, ST = 0", "до 1,5–2 мес"),
             ("6. Рубцовая", MUTED, dict(q=-0.5, qw=0.016, R=0.45, T=0.12), "Q остаётся, T сглажен", "годами, часто пожизненно")]
    for i, (name, col, kw, s1, s2) in enumerate(items):
        x0 = 30 + (i % 3) * 306; y0 = 52 + (i // 3) * 236
        panel(b, x0, y0, 294, 170, px, beats(lambda lt, kw=kw: mi(lt, **kw), 1.0, 3, 0.05), 28, name, col, s1, s2)
    return svg("\n".join(b), "Стадии инфаркта на ЭКГ")


# ---------- 3. Локализация ----------
def localization():
    b = [text(W / 2, 36, "Где инфаркт: стенка по отведениям (пособие, гл. 8.2.4)", 21, INK, "middle", "bold")]
    regs = [("Переднеперегородочный", "V1–V3", BLUE, ["V1", "V2", "V3"]),
            ("Передневерхушечный", "V3–V4", GREEN, ["V3", "V4"]),
            ("Переднебоковой", "I, aVL, V5, V6", ORANGE, ["I", "aVL", "V5", "V6"]),
            ("Распространённый передний", "I, aVL, V1–V6", VIOLET, ["I", "aVL", "V1", "V2", "V3", "V4", "V5", "V6"]),
            ("Нижний (заднедиафрагмальный)", "II, III, aVF", RED, ["II", "III", "aVF"]),
            ("Заднебазальный", "V7–V9; в V1–V2 высокий R, ST ↓", BROWN, ["V7", "V8", "V9"]),
            ("Правый желудочек", "V3R–V4R: ST ↑ ≥ 1 мм (КР157_5)", "#0e7490", ["V3R", "V4R"])]
    rows = [["I", "aVR", "V1", "V4", "V7", "V3R"], ["II", "aVL", "V2", "V5", "V8", "V4R"], ["III", "aVF", "V3", "V6", "V9", ""]]
    # сетка отведений (подсветка — по нижней и переднеперегородочной для примера)
    cell_w, cell_h = 66, 44
    gx, gy = 40, 66
    b.append(text(gx, gy - 8, "Пример: нижний инфаркт", 13.5, RED, "start", "bold"))
    hl = set(["II", "III", "aVF"])
    recip = set(["I", "aVL"])
    for r, row in enumerate(rows):
        for c, ld in enumerate(row):
            if not ld:
                continue
            x = gx + c * (cell_w + 6); y = gy + r * (cell_h + 6)
            fill = "#fde2e1" if ld in hl else ("#e0ecfa" if ld in recip else "#f8fafc")
            stroke = RED if ld in hl else (BLUE if ld in recip else "#cbd5e1")
            b.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            b.append(text(x + cell_w / 2, y + 28, ld, 15, INK, "middle", "bold"))
    b.append(text(gx, 236, "■ подъём ST, Q — зона инфаркта", 13, RED, "start", "bold"))
    b.append(text(gx, 256, "■ зеркальная депрессия ST", 13, BLUE, "start", "bold"))
    b.append(text(gx, 286, "V7–V9 и V3R–V4R снимают", 12.5, MUTED))
    b.append(text(gx, 304, "дополнительно", 12.5, MUTED))
    # таблица регионов
    tx, ty = 490, 58
    for i, (name, leads, col, _) in enumerate(regs):
        y = ty + i * 64
        b.append(f'<rect x="{tx}" y="{y}" width="440" height="56" rx="10" fill="#ffffff" stroke="{col}" stroke-width="2"/>')
        b.append(f'<rect x="{tx}" y="{y}" width="8" height="56" rx="4" fill="{col}"/>')
        b.append(text(tx + 20, y + 23, name, 14.5, col, "start", "bold"))
        b.append(text(tx + 20, y + 44, leads, 13.5, INK))
    b.append(text(40, 350, "Зеркальные изменения (пособие):", 13.5, INK, "start", "bold"))
    b.append(text(40, 372, "• передний ИМ — депрессия ST, высокий T", 13, INK))
    b.append(text(40, 391, "  в III, aVF", 13, INK))
    b.append(text(40, 412, "• нижний ИМ — депрессия ST в I, aVL", 13, INK))
    b.append(text(40, 433, "• заднебазальный — высокий R, ST ↓,", 13, INK))
    b.append(text(40, 452, "  высокий T в V1–V2", 13, INK))
    return svg("\n".join(b), "Локализация инфаркта")


# ---------- 4. Правый желудочек и задняя стенка ----------
def rv_post():
    b = [text(W / 2, 36, "Инфаркт правого желудочка и задней стенки", 22, INK, "middle", "bold")]
    px = 3.6
    up = lambda lt: mi(lt, R=0.6, S=-0.2, st=0.14, T=0.35, tsym=True)
    v1post = lambda lt: mi(lt, q=0.0, R=0.9, S=-0.35, st=-0.15, T=0.45, tsym=True)
    v8 = lambda lt: mi(lt, q=-0.35, qw=0.015, R=0.35, st=0.1, T=0.2, tsym=True)
    panel(b, 30, 56, 440, 140, px, beats(up, 0.95, 4), 24, "V4R: подъём ST ≥ 1 мм", "#0e7490")
    panel(b, 490, 56, 210, 140, px, beats(v1post, 0.95, 2), 24, "V1–V2", BROWN)
    panel(b, 720, 56, 210, 140, px, beats(v8, 0.95, 2), 24, "V7–V9", BROWN)
    b.append(box(30, 230, 440, 228, "Правый желудочек (КР157_5)", [
        "у ≥ 25 % пациентов с нижним ИМпST",
        "гипотония, набухшие вены шеи,",
        "застоя в лёгких нет",
        "ЭКГ: ST ↑ ≥ 1 мм в V3R, V4R",
        "нитраты не рекомендуются",
        "избегать диуретиков и вазодилататоров",
        "гипотония — натрия хлорид 0,9 % в/в",
        "(увеличить приток к правым отделам)",
        "снимать V3R–V4R при каждом нижнем ИМ"], "#0e7490", "#ecfeff"))
    b.append(box(490, 230, 440, 228, "Задняя стенка (пособие)", [
        "в V1–V2: высокий R, депрессия ST,",
        "высокий T — зеркальные изменения",
        "в V7–V9: патологический Q,",
        "подъём ST",
        "депрессия ST в V1–V3 при боли —",
        "снимите V7–V9 (КР157_5)",
        "",
        "часто сочетается с нижним ИМ:",
        "заднебоковой, распространённый задний"], BROWN, "#fbf4ec"))
    return svg("\n".join(b), "Инфаркт правого желудочка и задней стенки")


# ---------- 5. Помощь на вызове ----------
def prehosp():
    b = [text(W / 2, 34, "ОКС на вызове: алгоритм КР для фельдшера (адаптировано к укладке НМП)", 19, INK, "middle", "bold"), MARKER]
    b.append(box(20, 50, 920, 104, "Всем с подозрением на ОКС (КР157_5, прил. Б4; КР154_4, прил. Б2)", [
        "жалобы, анамнез, АД, ЧСС · ограничить активность · ЭКГ в 12 отведениях ≤ 10 мин, телемедицина ·",
        "мониторинг ЭКГ, венозный доступ, готовность к СЛР · вызвать бригаду СМП · время начала боли в карту"], INK))
    b.append(box(20, 170, 450, 190, "Боль", [
        "нитроглицерин 0,4–0,5 мг под язык",
        "или спрей при отсутствии гипотонии;",
        "повтор через 5 мин, контроль АД",
        "нельзя: гипотония, ИМ правого",
        "желудочка, силденафил ≤ 24 ч, тадалафил ≤ 48 ч",
        "боль сохраняется — нужен наркотический",
        "анальгетик: бригада СМП"], ORANGE, "#fff8eb"))
    b.append(box(490, 170, 450, 190, "Антиагреганты", [
        "АСК 150–300 мг разжевать",
        "(не кишечнорастворимую), если нет",
        "противопоказаний",
        "ОКСпST, стратегия ЧКВ — возможен",
        "клопидогрел 600 мг (не обязателен)",
        "ОКСбпST: клопидогрел и гепарин",
        "не рекомендуются"], RED, "#fdf2f2"))
    b.append(box(20, 376, 450, 150, "Не делать", [
        "кислород — только при SpO2 < 90 %",
        "(в укладке НМП нет — бригада СМП)",
        "гепарин без тромболизиса —",
        "не рекомендуется",
        "в/в β-блокаторы при гипотонии, ИМ ПЖ"], MUTED))
    b.append(box(490, 376, 450, 146, "Маршрут", [
        "экстренно — в стационар системы ОКС,",
        "лучше с ЧКВ; предупредить стационар",
        "ЧКВ ≤ 120 мин от диагноза ОКСпST",
        "или транспортировка ≤ 60 мин"], BLUE, "#f3f7fc"))
    return svg("\n".join(b), "ОКС на вызове")


files = {"s02_qwave.svg": qwave(), "s04_stages.svg": stages(), "s06_localization.svg": localization(),
         "s08_rv_post.svg": rv_post(), "s10_prehosp.svg": prehosp()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
