"""Общая основа анимаций на иллюстрации сердца: фон, маски отделов, проводящая система."""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC = os.environ.get("HEART_SRC", os.path.join(os.path.dirname(os.path.abspath(__file__)), "heart_base.webp"))
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


