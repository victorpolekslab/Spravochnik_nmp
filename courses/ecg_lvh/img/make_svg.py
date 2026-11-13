"""SVG-схемы для части 12 цикла «ЭКГ» (ecg_lvh). Запуск: python3 ecg_part12_svg.py <папка>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "img"
os.makedirs(OUT, exist_ok=True)
G = gauss


def cyc(lt, P=None, Q=-0.05, R=1.0, S=-0.2, qrsw=1.0, st=0.0, T=0.3, tsym=False, tw=0.045, pr=0.0):
    """P — функция зубца P(lt) или None (обычный)."""
    c = 0.225 + pr
    v = P(lt) if P else G(lt, 0.13, 0.10, 0.022)
    v += G(lt, Q, c - 0.02 * qrsw, 0.007 * qrsw) + G(lt, R, c, 0.01 * qrsw) + G(lt, S, c + 0.022 * qrsw, 0.01 * qrsw)
    j = c + 0.04 * qrsw
    tc = c + 0.23
    if tsym:
        v += G(lt, T, tc, tw)
    else:
        sd = tw * 1.25 if lt < tc else tw * 0.7
        v += T * math.exp(-((lt - tc) ** 2) / (2 * sd * sd))
    if st:
        # выпуклая книзу дуга ST, переходящая в T (strain)
        w = smooth(j - 0.01, j + 0.01, lt) * (1 - smooth(tc - 0.02, tc + 0.08, lt))
        v += st * w * (0.4 + 0.6 * smooth(j, tc - 0.02, lt))
    return v


def p_mitrale(lt):
    return G(lt, 0.14, 0.075, 0.018) + G(lt, 0.16, 0.125, 0.018)


def p_mitrale_v1(lt):
    return G(lt, 0.08, 0.075, 0.016) + G(lt, -0.16, 0.125, 0.022)


def p_pulm(lt):
    return G(lt, 0.3, 0.10, 0.016)


def p_pulm_v1(lt):
    return G(lt, 0.22, 0.09, 0.014) + G(lt, -0.03, 0.13, 0.015)


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


def panel(b, x0, y0, w, h, px, fn, base_mm, title, col=INK, sub=None, lw=2.1, pxm=None):
    b.append(grid(x0, y0, w - (w % px), h, px))
    b.append(trace(fn, x0, y0 + base_mm * px, w - 2, 25 * px, (pxm or 10 * px), INK, lw, 0.3))
    b.append(text(x0 + 8, y0 + 20, title, 14.5, col, "start", "bold"))
    if sub:
        b.append(text(x0 + w / 2, y0 + h + 19, sub, 13, INK, "middle"))


def box(x, y, w, h, title, lines, col, fill="#f8fafc", size=13.3):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{col}" stroke-width="2.5"/>',
         text(x + 14, y + 26, title, 16, col, "start", "bold")]
    for j, ln in enumerate(lines):
        s.append(text(x + 14, y + 48 + j * 19, ln, size, INK))
    return "\n".join(s)


def vbracket(x, y1, y2, label, col, side="right"):
    s = [f'<line x1="{x}" y1="{y1:.1f}" x2="{x}" y2="{y2:.1f}" stroke="{col}" stroke-width="2.2"/>']
    for y in (y1, y2):
        s.append(f'<line x1="{x-5}" y1="{y:.1f}" x2="{x+5}" y2="{y:.1f}" stroke="{col}" stroke-width="2.2"/>')
    anchor = "start" if side == "right" else "end"
    dx = 9 if side == "right" else -9
    s.append(text(x + dx, (y1 + y2) / 2 + 5, label, 13.5, col, anchor, "bold"))
    return "\n".join(s)


# ---------- 1. Предсердия ----------
def atria():
    b = [text(W / 2, 36, "Гипертрофия предсердий: P-mitrale и P-pulmonale", 22, INK, "middle", "bold")]
    px = 5.0
    items = [("Левое предсердие · I", RED, lambda lt: cyc(lt, P=p_mitrale, pr=0.03), "P широкий > 0,10 с, двугорбый"),
             ("Левое предсердие · V1", RED, lambda lt: cyc(lt, P=p_mitrale_v1, R=0.3, S=-0.9, pr=0.03), "глубокая отрицательная вторая фаза"),
             ("Правое предсердие · II", BLUE, lambda lt: cyc(lt, P=p_pulm), "P высокий, острый, ≤ 0,10 с"),
             ("Правое предсердие · V1", BLUE, lambda lt: cyc(lt, P=p_pulm_v1, R=0.3, S=-0.9), "первая фаза высокая, острая")]
    for i, (name, col, f, sub) in enumerate(items):
        x0 = 30 + (i % 2) * 460; y0 = 56 + (i // 2) * 196
        panel(b, x0, y0, 440, 150, px, beats(f, 1.0, 2, 0.08), 18, name, col, sub)
    b.append(f'<rect x="30" y="456" width="900" height="70" rx="12" fill="#f8fafc" stroke="#e2e8f0"/>')
    b.append(text(48, 482, "Левое: митральные пороки, АГ, ХСН. Правое: хроническое лёгочное сердце, лёгочная гипертензия (пособие, гл. 7.1–7.2)", 13.3, INK))
    b.append(text(48, 504, "Остро возникший P-pulmonale при астме, ТЭЛА, отёке лёгких — перегрузка; проходит после улучшения (гл. 7.3)", 13.3, INK))
    return svg("\n".join(b), "Гипертрофия предсердий")


# ---------- 2. ГЛЖ: вольтаж ----------
def lvh():
    b = [text(W / 2, 36, "Гипертрофия левого желудочка: индекс Соколова — Лайона", 21, INK, "middle", "bold")]
    px = 4.0; pxm = 4.0  # 1 мм = 1 мм сетки: 10 мм/мВ → 40 px/мВ
    v1 = lambda lt: cyc(lt, Q=0.0, R=0.25, S=-2.0, qrsw=1.2, T=0.35)
    v5 = lambda lt: cyc(lt, Q=-0.1, R=2.2, S=-0.1, qrsw=1.2, st=-0.12, T=-0.25)
    panel(b, 30, 56, 300, 300, px, beats(v1, 1.1, 2, 0.06), 32, "V1", RED, None, 2.2, 10 * pxm)
    panel(b, 350, 56, 300, 300, px, beats(v5, 1.1, 2, 0.06), 64, "V5", RED, None, 2.2, 10 * pxm)
    base1 = 56 + 32 * px; base5 = 56 + 64 * px
    x1 = 30 + (0.06 + 0.225 + 0.026) * 25 * px + 26
    b.append(vbracket(x1, base1, base1 + 2.0 * 10 * pxm * 0.97, "SV1 = 19 мм", BLUE))
    x5 = 350 + (0.06 + 0.225) * 25 * px + 24
    b.append(vbracket(x5, base5, base5 - 2.2 * 10 * pxm, "RV5 = 22 мм", BLUE))
    b.append(text(340, 386, "SV1 + RV5 = 41 мм  >  35 мм — ГЛЖ", 17, RED, "middle", "bold"))
    b.append(text(340, 412, "В V5 — депрессия ST и асимметричный отрицательный T («систолическая перегрузка»)", 13, INK, "middle"))
    b.append(box(670, 56, 270, 420, "Критерии ГЛЖ", [
        "КР62_3 (АГ):",
        "• SV1 + RV5–6 > 35 мм",
        "  (Соколов — Лайон)",
        "• RaVL ≥ 11 мм",
        "• RaVL + SV3 > 28 мм",
        "  у мужчин, > 20 мм у женщин",
        "  (корнельский индекс)",
        "• корнельское произведение",
        "  > 2440 мм·мс",
        "",
        "Пособие, гл. 7.4:",
        "• RV5–6 > 25 мм",
        "• RI + SIII ≥ 25 мм; RI > 15 мм",
        "• ось влево, ST ↓ и T− в V5–6",
        "• внутреннее отклонение",
        "  в V5–6 > 0,05 с"], RED, "#fdf2f2", 13))
    b.append(text(340, 446, "1 мм = 0,1 мВ при стандартном усилении", 13, MUTED, "middle"))
    b.append(text(340, 470, "ГЛЖ при АГ — поражение сердца как органа-мишени (КР62_3)", 13.5, INK, "middle", "bold"))
    return svg("\n".join(b), "Гипертрофия левого желудочка")


# ---------- 3. Strain против ишемии ----------
def strain():
    b = [text(W / 2, 36, "ГЛЖ с «перегрузкой» или ишемия?", 22, INK, "middle", "bold")]
    px = 4.2
    s1 = lambda lt: cyc(lt, Q=-0.1, R=2.0, S=-0.1, qrsw=1.15, st=-0.14, T=-0.3)
    s2 = lambda lt: cyc(lt, R=1.0, st=-0.0, T=-0.5, tsym=True, tw=0.038)
    panel(b, 30, 56, 440, 200, px, beats(s1, 1.0, 3), 30, "ГЛЖ, V5: «перегрузка»", ORANGE, "высокий R, ST ↓ дугой, T асимметричный", 2.1, 4.2 * 10 * 0.8)
    panel(b, 490, 56, 440, 200, px, beats(s2, 1.0, 3), 24, "Ишемия, V5: коронарный T", BLUE, "R обычный, T симметричный, заострённый")
    b.append(box(30, 300, 440, 180, "В пользу ГЛЖ", [
        "высокие R в V5–V6, глубокие S в V1–V2",
        "изменения ST–T там же, где высокий R",
        "T отрицательный асимметричный",
        "или двухфазный (−+)",
        "та же картина на старых ЭКГ",
        "АГ, аортальные пороки в анамнезе"], ORANGE, "#fff8eb"))
    b.append(box(490, 300, 440, 180, "Помнить", [
        "критерии подъёма ST при ГЛЖ",
        "не применяют (КР157_5)",
        "«перегрузку» ставят, только исключив",
        "ишемию и блокады (пособие, гл. 7.7)",
        "при боли — тактика ОКС, сравнение",
        "со старой ЭКГ, телемедицина"], BLUE, "#f3f7fc"))
    return svg("\n".join(b), "ГЛЖ или ишемия")


# ---------- 4. ГПЖ ----------
def rvh():
    b = [text(W / 2, 36, "Гипертрофия правого желудочка", 22, INK, "middle", "bold")]
    px = 3.6
    leads = [("V1", lambda lt: cyc(lt, Q=0.0, R=1.0, S=-0.25, st=-0.06, T=-0.25), "R ≥ 7 мм, R > S"),
             ("V5", lambda lt: cyc(lt, Q=0.0, R=0.5, S=-0.9), "глубокий S (RS)"),
             ("I", lambda lt: cyc(lt, Q=0.0, R=0.25, S=-0.7), "rS"),
             ("III", lambda lt: cyc(lt, Q=-0.12, R=1.0, S=-0.05, T=-0.15), "qR, ось вправо > +100°")]
    for i, (name, f, sub) in enumerate(leads):
        x0 = 30 + i * 230
        panel(b, x0, 56, 216, 170, px, beats(f, 1.0, 2), 24, name, BLUE, sub)
    b.append(box(30, 276, 900, 136, "Признаки (пособие, гл. 7.5)", [
        "ось вправо: угол α больше +100°   ·   RV1 ≥ 7 мм или RV1 + SV5–6 ≥ 10,5 мм",
        "в V1 комплекс rSR' или qR   ·   поворот по часовой стрелке: переходная зона в V5–V6, в V5–V6 — RS",
        "депрессия ST и отрицательный T в III, aVF, V1–V2",
        "часто вместе с P-pulmonale"], BLUE, "#f3f7fc", 14))
    b.append(text(40, 470, "Причины: хроническое лёгочное сердце (ХОБЛ), лёгочная гипертензия, митральный стеноз, врождённые пороки.", 14, INK))
    b.append(text(40, 496, "Отклонение оси вправо — не всегда ГПЖ: исключите блокаду задней ветви левой ножки (часть 9).", 14, INK))
    return svg("\n".join(b), "Гипертрофия правого желудочка")


# ---------- 5. Острая перегрузка ----------
def overload():
    b = [text(W / 2, 36, "Перегрузка: признаки появились остро и быстро уходят", 21, INK, "middle", "bold")]
    px = 4.0
    items = [("II · до приступа", GREEN, lambda lt: cyc(lt), "P обычный"),
             ("II · астматический статус", RED, lambda lt: cyc(lt, P=p_pulm), "P высокий, острый"),
             ("II · через 3 дня", GREEN, lambda lt: cyc(lt, P=lambda x: G(x, 0.17, 0.10, 0.02)), "P почти норма")]
    for i, (name, col, f, sub) in enumerate(items):
        x0 = 30 + i * 306
        panel(b, x0, 56, 294, 150, px, beats(f, 0.75, 3, 0.05), 20, name, col, sub)
    b.append(text(W / 2, 246, "Пособие, гл. 7.3, рис. 7.5: динамика P при астматическом статусе", 13, MUTED, "middle"))
    b.append(box(30, 266, 440, 200, "Перегрузка предсердий", [
        "признаки, похожие на гипертрофию",
        "правого или левого предсердия",
        "возникают остро: приступ астмы,",
        "отёк лёгких, ТЭЛА, крупозная",
        "пневмония",
        "быстро уменьшаются при улучшении",
        "(пособие, гл. 7.3)"], RED, "#fdf2f2"))
    b.append(box(490, 266, 440, 200, "Перегрузка желудочков", [
        "ST ↓ и T− в V5–6 (левый)",
        "или V1–2 (правый)",
        "быстрая обратная динамика",
        "термин не общепринятый: ставят,",
        "исключив ишемию, блокады, WPW",
        "(пособие, гл. 7.7)",
        "острая перегрузка правых отделов",
        "при ТЭЛА — часть 13"], BLUE, "#f3f7fc"))
    return svg("\n".join(b), "Перегрузка предсердий и желудочков")


files = {"s02_atria.svg": atria(), "s04_lvh.svg": lvh(), "s06_strain.svg": strain(),
         "s08_rvh.svg": rvh(), "s10_overload.svg": overload()}
for name, content in files.items():
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
print("\n".join(files))
