"""GIF на основе иллюстрации сердца: импульс по проводящей системе + II отведение.
Запуск: python3 heart_gif.py <heart.webp> <out.gif>   (TEST=1 — только контрольные кадры)
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import beat_p  # noqa

SRC, OUT = sys.argv[1], sys.argv[2]
FW, FH = 540, 958                 # итоговый кадр
K = 2                             # рабочее разрешение = 2× итогового
WW, WH = FW * K, FH * K
FD = "/usr/share/fonts/truetype/dejavu/"
F = lambda s, b=False: ImageFont.truetype(FD + ("DejaVuSans-Bold.ttf" if b else "DejaVuSans.ttf"), int(s * K))

BG = (7, 12, 26); WHITE = (255, 255, 255); INK = (31, 36, 48); MUTED = (150, 158, 172)
GOLD = (255, 205, 40); TINT = np.array([255, 62, 30], np.float32)
GREEN = (70, 190, 120); BLUE = (90, 150, 230); RED = (240, 80, 64); ORANGE = (245, 165, 40); VIOLET = (170, 125, 235)

# ---------- фон ----------
src = Image.open(SRC).convert("RGB")
SX = WW / src.width                       # 1080 / 2160 = 0.5
base = src.resize((WW, round(src.height * SX)), Image.LANCZOS).crop((0, 0, WW, WH))
CUT = 722 * K                             # ниже — своя панель вместо статичной ленты
bd = ImageDraw.Draw(base)
bd.rectangle([0, CUT, WW, WH], fill=BG)
BASE_ARR = np.asarray(base).astype(np.float32)

O = lambda x, y: (x * SX, y * SX)         # координаты исходника → рабочие

# ---------- проводящая система (координаты исходника 2160×3832) ----------
SA = (617, 950); AV = (942, 1492); BIF = (1060, 1750)
INTERNODAL = [SA, (700, 1050), (867, 1200), (917, 1300), AV]
INTER2 = [SA, (633, 1100), (733, 1250), (867, 1350), AV]
INTER3 = [SA, (533, 1200), (667, 1367), (900, 1467), AV]
BACHMANN = [SA, (717, 967), (1167, 1017), (1500, 1100), (1600, 1167)]
HIS = [AV, (1017, 1550), (1050, 1650), BIF]
RBB = [BIF, (1042, 1883), (1083, 2050), (1167, 2217), (1200, 2333), (1150, 2450), (1083, 2483)]
PURK_R = [(1083, 2483), (933, 2383), (750, 2267), (583, 2100), (417, 1883)]
LBB = [BIF, (1133, 1800), (1267, 1983), (1383, 2183), (1500, 2350), (1583, 2583)]
PURK_L = [(1583, 2583), (1667, 2417), (1750, 2217), (1800, 1967), (1767, 1750)]


def plen(p): return sum(math.dist(p[i], p[i + 1]) for i in range(len(p) - 1))


def ppos(p, f):
    f = max(0.0, min(1.0, f)); L = plen(p) * f
    for i in range(len(p) - 1):
        d = math.dist(p[i], p[i + 1])
        if L <= d:
            k = L / d if d else 0
            return (p[i][0] + (p[i + 1][0] - p[i][0]) * k, p[i][1] + (p[i + 1][1] - p[i][1]) * k)
        L -= d
    return p[-1]


def sub(p, f):
    f = max(0.0, min(1.0, f))
    if f <= 0: return []
    L = plen(p) * f; out = [p[0]]
    for i in range(len(p) - 1):
        d = math.dist(p[i], p[i + 1])
        if L <= d:
            k = L / d if d else 0
            out.append((p[i][0] + (p[i + 1][0] - p[i][0]) * k, p[i][1] + (p[i + 1][1] - p[i][1]) * k)); return out
        out.append(p[i + 1]); L -= d
    return out


def ramp(t, a, b): return 0.0 if t <= a else 1.0 if t >= b else (t - a) / (b - a)


# ---------- маски отделов по цвету ----------
a = BASE_ARR.astype(int); R, G, B = a[..., 0], a[..., 1], a[..., 2]
ys, xs = np.mgrid[0:WH, 0:WW]
bg = (R + G + B) < 110
vessel = (np.abs(R - B) < 40) & (B >= G - 5) & (G > 90) & ~bg
tissue = (R > 150) & (R - B > 35) & (R - G > 30) & ~vessel
cavity = (R > 45) & (R < 150) & (R - G > 18) & (R - B > 10) & ~vessel & ~bg
cream = (R > 190) & (G > 165) & (B > 130) & (R - B < 70)
heart = tissue | cavity | cream


def close(m, r=7):
    im = Image.fromarray((m * 255).astype(np.uint8))
    im = im.filter(ImageFilter.MaxFilter(r)).filter(ImageFilter.MinFilter(r))
    return np.asarray(im) > 127


heart = close(heart) & ~vessel & (ys < CUT - 20)


def fill_holes(m):
    """Всё, что не сердце и не связано с краем кадра, — дыра внутри сердца."""
    inv = Image.fromarray(((~m) * 255).astype(np.uint8)).copy()
    ImageDraw.floodfill(inv, (0, 0), 128)
    return np.asarray(inv) != 128


heart = fill_holes(heart) & (ys < CUT - 20)
av_line = np.interp(xs, [0, 175, 500, 750, 1080], [850, 833, 780, 770, 770]) * (WW / 1080)
ATRIA = heart & (ys < av_line) & (ys > 420 * WW / 1080) & ~((xs > 520) & (ys < 475))
VENT = heart & (ys > av_line + 15)


def sample(p, t0, t1, n=50): return [(ppos(p, k / n), t0 + (t1 - t0) * k / n) for k in range(n + 1)]


def act_map(mask, sources, v):
    """Время активации: min(t источника + расстояние / v); считаем на ¼ разрешения."""
    q = 4
    m = mask[::q, ::q]; yy, xx = np.nonzero(m)
    best = np.full(xx.shape, 9.0, np.float32)
    for (sx, sy), t0 in sources:
        px, py = O(sx, sy)
        best = np.minimum(best, t0 + np.hypot(xx * q - px, yy * q - py) / v)
    out = np.full(m.shape, np.nan, np.float32); out[yy, xx] = best
    return out, q


A_SRC = [(SA, 0.05)] + sample(INTERNODAL, 0.05, 0.14) + sample(INTER2, 0.05, 0.14) + sample(INTER3, 0.05, 0.14) + sample(BACHMANN, 0.05, 0.09)
V_SRC = sample(LBB, 0.205, 0.222) + sample(RBB, 0.208, 0.224) + sample(PURK_R, 0.224, 0.236) + sample(PURK_L, 0.222, 0.234)
A_ACT, Q = act_map(ATRIA, A_SRC, 3500.0)
V_ACT, _ = act_map(VENT, V_SRC, 5000.0)
_v = V_ACT[~np.isnan(V_ACT)]; V0, V1 = float(_v.min()), float(_v.max())
V_REC = 0.34 + 0.19 * (1 - (V_ACT - V0) / (V1 - V0))
_a = A_ACT[~np.isnan(A_ACT)]; A0, A1 = float(_a.min()), float(_a.max())
A_REC = 0.21 + 0.08 * (A_ACT - A0) / (A1 - A0)
ATRIA_F = ATRIA.astype(np.float32); VENT_F = VENT.astype(np.float32)


def alpha_map(t):
    with np.errstate(invalid="ignore"):
        on_a = (A_ACT <= t).astype(np.float32) * (1 - ramp(t, 0.21, 0.30))
        on_v = ((V_ACT <= t) & (t < V_REC)).astype(np.float32)
    on = np.maximum(on_a, on_v)
    im = Image.fromarray((on * 255).astype(np.uint8)).resize((WW, WH), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3 * K))
    al = np.asarray(im).astype(np.float32) / 255.0
    return al * np.maximum(ATRIA_F, VENT_F) * 0.68


# ---------- фазы и ЭКГ ----------
PHASES = [
    (0.00, 0.05, "Синусовый узел", "импульс рождается — на ЭКГ изолиния", MUTED),
    (0.05, 0.15, "Предсердия", "возбуждение предсердий → зубец P", GREEN),
    (0.15, 0.20, "АВ-узел", "задержка импульса → сегмент PQ", BLUE),
    (0.20, 0.255, "Гис → ножки → Пуркинье", "возбуждение желудочков → QRS", RED),
    (0.255, 0.33, "Желудочки возбуждены", "разности потенциалов нет → ST", ORANGE),
    (0.33, 0.55, "Восстановление", "реполяризация желудочков → зубец T", VIOLET),
    (0.55, 0.80, "Покой (диастола)", "до следующего импульса → изолиния", MUTED),
]
FRAMES = [8, 26, 18, 34, 14, 30, 14]
BAND = {1: (0.05, 0.15, "P"), 2: (0.15, 0.20, "PQ"), 3: (0.20, 0.255, "QRS"), 4: (0.255, 0.33, "ST"), 5: (0.33, 0.55, "T")}
PX0, PX1, PY0, PY1 = 14, 526, 772, 936     # панель ЭКГ (итоговые px)
EBASE = 892
PXS = (PX1 - PX0 - 24) / 0.80               # px на секунду
PXMV = 92
lead2 = lambda t: beat_p(t, P=0.16, Q=-0.08, R=1.05, S=-0.22, T=0.32)
EX = lambda t: (PX0 + 12 + t * PXS) * K
EY = lambda mv: (EBASE - mv * PXMV) * K


def draw_panel(d, img):
    d.rounded_rectangle([PX0 * K, PY0 * K, PX1 * K, PY1 * K], radius=12 * K, fill=(253, 232, 234), outline=(232, 170, 176), width=K)
    step = 9.8
    x = PX0 + 4
    i = 0
    while x < PX1 - 2:
        d.line([(x * K, (PY0 + 3) * K), (x * K, (PY1 - 3) * K)], fill=(236, 160, 168) if i % 5 == 0 else (246, 204, 208), width=K)
        x += step; i += 1
    y = EBASE; j = 0
    while y > PY0 + 2:
        d.line([((PX0 + 3) * K, y * K), ((PX1 - 3) * K, y * K)], fill=(236, 160, 168) if j % 5 == 0 else (246, 204, 208), width=K)
        y -= step; j += 1
    y = EBASE + step; j = 1
    while y < PY1 - 2:
        d.line([((PX0 + 3) * K, y * K), ((PX1 - 3) * K, y * K)], fill=(236, 160, 168) if j % 5 == 0 else (246, 204, 208), width=K)
        y += step; j += 1


def tag(d, xy, s, anchor, bold=True, size=11):
    x, y = xy[0] * K, xy[1] * K
    bb = d.textbbox((x, y), s, font=F(size, bold), anchor=anchor)
    d.rounded_rectangle([bb[0] - 5 * K, bb[1] - 3 * K, bb[2] + 5 * K, bb[3] + 3 * K], radius=6 * K, fill=(255, 255, 255))
    d.text((x, y), s, font=F(size, bold), fill=INK, anchor=anchor)


def frame(t, pi, final=False):
    al = alpha_map(t)[..., None]
    arr = BASE_ARR * (1 - al) + TINT * al
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    ov = Image.new("RGBA", (WW, WH), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    # подсветка путей
    lit = [sub(INTERNODAL, ramp(t, 0.05, 0.14)), sub(INTER2, ramp(t, 0.05, 0.14)), sub(INTER3, ramp(t, 0.05, 0.14)),
           sub(BACHMANN, ramp(t, 0.05, 0.11)), sub(HIS, ramp(t, 0.195, 0.205)),
           sub(RBB, ramp(t, 0.205, 0.222)), sub(LBB, ramp(t, 0.205, 0.222)),
           sub(PURK_R, ramp(t, 0.222, 0.235)), sub(PURK_L, ramp(t, 0.222, 0.235))]
    fade = 1 - ramp(t, 0.30, 0.37)
    if fade > 0:
        for seg in lit:
            if len(seg) >= 2:
                pts = [O(*p) for p in seg]
                od.line(pts, fill=GOLD + (int(70 * fade),), width=26, joint="curve")
                od.line(pts, fill=GOLD + (int(255 * fade),), width=9, joint="curve")
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)

    def dot(p, r=13):
        x, y = O(*p)
        d.ellipse([x - r - 8, y - r - 8, x + r + 8, y + r + 8], fill=(255, 225, 120))
        d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD, outline=INK, width=3)
    if t < 0.05:
        dot(SA, 12 + 8 * abs(math.sin(t / 0.05 * math.pi * 2)))
    elif t < 0.15:
        dot(ppos(INTERNODAL, ramp(t, 0.05, 0.14))); dot(ppos(BACHMANN, ramp(t, 0.05, 0.11)), 9)
    elif t < 0.20:
        dot(AV, 13 + 7 * abs(math.sin((t - 0.15) / 0.05 * math.pi * 3)))
    elif t < 0.205:
        dot(ppos(HIS, ramp(t, 0.195, 0.205)))
    elif t < 0.222:
        dot(ppos(RBB, ramp(t, 0.205, 0.222)), 11); dot(ppos(LBB, ramp(t, 0.205, 0.222)), 11)
    elif t < 0.235:
        dot(ppos(PURK_R, ramp(t, 0.222, 0.235)), 9); dot(ppos(PURK_L, ramp(t, 0.222, 0.235)), 9)

    # подписи структур (итоговые px)
    tag(d, (SA[0] / 4 - 14, SA[1] / 4 - 4), "СА-узел", "rm")
    tag(d, (AV[0] / 4 - 16, AV[1] / 4 + 18), "АВ-узел", "rm")
    tag(d, (BIF[0] / 4 + 18, BIF[1] / 4 - 6), "пучок Гиса", "lm", False, 10)
    tag(d, (300, 640), "ножки и волокна Пуркинье", "mm", False, 10)
    # заголовок
    tb = d.textbbox((WW // 2, 22 * K), "Импульс в сердце и II отведение", font=F(17, True), anchor="mm")
    d.rounded_rectangle([tb[0] - 12 * K, tb[1] - 7 * K, tb[2] + 12 * K, tb[3] + 7 * K], radius=10 * K, fill=(7, 12, 26))
    d.text((WW // 2, 22 * K), "Импульс в сердце и II отведение", font=F(17, True), fill=WHITE, anchor="mm")

    # подпись фазы
    name, desc, col = PHASES[pi][2], PHASES[pi][3], PHASES[pi][4]
    if final:
        name, desc, col = "Один кардиоцикл", "путь импульса: P → PQ → QRS → ST → T", WHITE
    d.text((18 * K, 738 * K), name, font=F(17, True), fill=col, anchor="lm")
    d.text((18 * K, 760 * K), desc, font=F(12.5), fill=(225, 230, 238), anchor="lm")

    # ЭКГ
    draw_panel(d, img)
    if pi in BAND and not final:
        a_, b_, lab = BAND[pi]
        ov = Image.new("RGBA", (WW, WH), (0, 0, 0, 0))
        ImageDraw.Draw(ov).rectangle([EX(a_), (PY0 + 4) * K, EX(b_), (PY1 - 4) * K], fill=PHASES[pi][4] + (70,))
        img.paste(ov, (0, 0), ov); d = ImageDraw.Draw(img)
        d.text(((EX(a_) + EX(b_)) / 2, (PY0 + 14) * K), lab, font=F(13, True), fill=tuple(int(c * 0.75) for c in PHASES[pi][4]), anchor="mm")
    pts = []; tt = 0.0
    while tt <= t + 1e-9:
        pts.append((EX(tt), EY(lead2(tt)))); tt += 0.002
    if len(pts) > 1:
        d.line(pts, fill=(60, 64, 76), width=int(2.4 * K), joint="curve")
    if not final:
        x, y = pts[-1]; d.ellipse([x - 6 * K, y - 6 * K, x + 6 * K, y + 6 * K], fill=(220, 50, 40))
    else:
        for i, (a_, b_, lab) in BAND.items():
            c = tuple(int(v * 0.8) for v in PHASES[i][4])
            y = (PY1 - 26) if i in (1, 3, 5) else (PY1 - 12)
            d.line([(EX(a_) + K, (y - 9) * K), (EX(b_) - K, (y - 9) * K)], fill=c, width=4 * K)
            d.text(((EX(a_) + EX(b_)) / 2, (y + 1) * K), lab, font=F(10.5, True), fill=c, anchor="mm")
    d.text((PX1 * K - 8 * K, (PY0 + 12) * K), "II отведение", font=F(10.5, True), fill=(150, 90, 96), anchor="rm")
    d.text((WW // 2, 953 * K), "анимация замедлена, быстрые фазы растянуты · схема учебная", font=F(9), fill=MUTED, anchor="mb")
    return img.resize((FW, FH), Image.LANCZOS)


if os.environ.get("TEST"):
    for t, i in ((0.10, 1), (0.18, 2), (0.23, 3), (0.42, 5)):
        frame(t, i).save(f"/home/claude/png/hg_{int(t * 1000)}.png")
    frame(0.799, 6, True).save("/home/claude/png/hg_final.png")
    sys.exit()

frames, durs = [], []
for i, ((a_, b_, *_), n) in enumerate(zip(PHASES, FRAMES)):
    for k in range(n):
        frames.append(frame(a_ + (b_ - a_) * k / n, i)); durs.append(70)
frames.append(frame(0.799, 6, True)); durs.append(2600)
picks = [frames[i] for i in range(0, len(frames), max(1, len(frames) // 12))]
mont = Image.new("RGB", (FW, FH * len(picks)))
for k, f in enumerate(picks): mont.paste(f, (0, k * FH))
pal = mont.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
q[0].save(OUT, save_all=True, append_images=q[1:], duration=durs, loop=0, optimize=True, disposal=1)
print(OUT, len(frames), "frames", os.path.getsize(OUT) // 1024, "KB")
