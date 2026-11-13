"""GIF «Источник ритма»: синусовый, из АВ-соединения, идиовентрикулярный — на иллюстрации сердца.
Запуск: HEART_SRC=heart_base.webp python3 rhythm_gif.py <out.gif>   (TEST=1 — контрольные кадры)
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_lib import beat_p, gauss  # noqa
from heart_core import *  # noqa

OUT = sys.argv[1] if len(sys.argv) > 1 else "rhythm.gif"
FOCUS = (1720, 2380)          # эктопический очаг в стенке ЛЖ (координаты исходника)
rev = lambda p: list(reversed(p))


def norm01(a):
    v = a[~np.isnan(a)]; lo, hi = float(v.min()), float(v.max())
    return (a - lo) / (hi - lo)


# ---------- карты активации для трёх сценариев ----------
A_SINUS = [(SA, 0.05)] + sample(INTERNODAL, 0.05, 0.14) + sample(INTER2, 0.05, 0.14) + sample(INTER3, 0.05, 0.14) + sample(BACHMANN, 0.05, 0.09)
A_RETRO = [(AV, 0.10)] + sample(rev(INTERNODAL), 0.10, 0.17) + sample(rev(INTER2), 0.10, 0.17) + sample(rev(INTER3), 0.10, 0.17) + sample(BACHMANN, 0.17, 0.20)


def v_src(shift):
    return (sample(LBB, 0.205 + shift, 0.222 + shift) + sample(RBB, 0.208 + shift, 0.224 + shift)
            + sample(PURK_R, 0.224 + shift, 0.236 + shift) + sample(PURK_L, 0.222 + shift, 0.234 + shift))


A_S, _ = act_map(ATRIA, A_SINUS, 3500.0)
A_R, _ = act_map(ATRIA, A_RETRO, 3500.0)
V_N, _ = act_map(VENT, v_src(0.0), 5000.0)
V_J, _ = act_map(VENT, v_src(-0.15), 5000.0)
V_E, _ = act_map(VENT, [(FOCUS, 0.30)], 4400.0)
REC_N = 0.34 + 0.19 * (1 - norm01(V_N))
REC_J = 0.19 + 0.19 * (1 - norm01(V_J))
REC_E = 0.52 + 0.22 * norm01(V_E)          # при эктопии восстановление в том же порядке → T против QRS
AF, VF = ATRIA.astype(np.float32), VENT.astype(np.float32)


def to_alpha(on_q):
    im = Image.fromarray((np.nan_to_num(on_q) * 255).astype(np.uint8)).resize((WW, WH), Image.BILINEAR)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(3 * K))).astype(np.float32) / 255.0


def alpha(scn, t):
    with np.errstate(invalid="ignore"):
        if scn == 0:
            a = (A_S <= t) * (1 - ramp(t, 0.21, 0.30)); v = (V_N <= t) & (t < REC_N)
        elif scn == 1:
            a = (A_R <= t) * (1 - ramp(t, 0.27, 0.35)); v = (V_J <= t) & (t < REC_J)
        else:
            a1 = (A_S <= t) * (1 - ramp(t, 0.21, 0.30)); a2 = (A_S + 0.80 <= t).astype(np.float32)
            a = np.maximum(a1, a2); v = (V_E <= t) & (t < REC_E)
    al_a = to_alpha(a.astype(np.float32)) * AF
    al_v = to_alpha(v.astype(np.float32)) * VF
    return np.maximum(al_a, al_v) * 0.68


# ---------- ЭКГ ----------
def ecg(scn, t):
    if scn == 0:
        return beat_p(t, P=0.16, Q=-0.08, R=1.05, S=-0.22, T=0.32)
    if scn == 1:
        return beat_p(t, P=0.0, Q=-0.08, R=1.05, S=-0.22, T=0.32, pr=-0.15) + gauss(t, -0.13, 0.155, 0.02)
    return (beat_p(t, P=0.0, Q=-0.05, R=1.0, S=-0.5, T=-0.45, qrs=2.6, pr=0.155)
            + gauss(t, 0.15, 0.10, 0.022) + gauss(t, 0.15, 0.90, 0.022))


SCN = [
    dict(title="1 · Синусовый ритм", end=0.80,
         summary=("Синусовый ритм", "P+ перед каждым QRS, QRS узкий"),
         phases=[(0.00, 0.05, "Синусовый узел", "импульс рождается в СА-узле", MUTED, None),
                 (0.05, 0.15, "Предсердия", "сверху вниз → P положительный", GREEN, "P"),
                 (0.15, 0.20, "АВ-узел", "задержка → сегмент PQ", BLUE, "PQ"),
                 (0.20, 0.255, "Гис → ножки → Пуркинье", "быстро → узкий QRS", RED, "QRS"),
                 (0.255, 0.55, "Восстановление", "→ зубец T", VIOLET, "T"),
                 (0.55, 0.80, "Покой", "ЧСС 60–90 по пособию", MUTED, None)],
         frames=[5, 14, 9, 18, 16, 6]),
    dict(title="2 · Ритм из АВ-соединения", end=0.80,
         summary=("Ритм из АВ-соединения", "QRS узкий, P нет или P− после QRS"),
         phases=[(0.00, 0.045, "АВ-соединение", "СА-узел молчит, импульс рождается ниже", BLUE, None),
                 (0.045, 0.10, "Гис → ножки → Пуркинье", "обычный путь → узкий QRS", RED, "QRS"),
                 (0.10, 0.20, "Предсердия — снизу вверх", "ретроградно → P− после QRS", GREEN, "P−"),
                 (0.20, 0.42, "Восстановление", "→ зубец T", VIOLET, "T"),
                 (0.42, 0.80, "Покой", "ЧСС 40–60 — реже синусового", MUTED, None)],
         frames=[8, 20, 18, 14, 8]),
    dict(title="3 · Идиовентрикулярный ритм", end=1.00,
         summary=("Идиовентрикулярный ритм", "QRS широкий, < 40 в мин, P сами по себе"),
         phases=[(0.00, 0.05, "Синусовый узел", "импульс рождается как обычно", MUTED, None),
                 (0.05, 0.15, "Предсердия", "→ зубец P", GREEN, "P"),
                 (0.15, 0.28, "АВ-узел: блок", "к желудочкам импульс не проходит", RED, None),
                 (0.28, 0.48, "Очаг в желудочке", "по миокарду, медленно → широкий QRS", RED, "QRS"),
                 (0.48, 0.80, "Восстановление", "T направлен против QRS", VIOLET, "T"),
                 (0.80, 1.00, "Предсердия снова", "новый P без QRS: ритмы независимы", GREEN, "P")],
         frames=[5, 12, 10, 24, 14, 14]),
]

PX0, PX1, PY0, PY1 = 14, 526, 772, 936
EBASE = 880
PXS = (PX1 - PX0 - 24) / 1.0
PXMV = 82
EX = lambda t: (PX0 + 12 + t * PXS) * K
EY = lambda mv: (EBASE - mv * PXMV) * K


def panel(d):
    d.rounded_rectangle([PX0 * K, PY0 * K, PX1 * K, PY1 * K], radius=12 * K, fill=(253, 232, 234), outline=(232, 170, 176), width=K)
    step = 9.8; x = PX0 + 4; i = 0
    while x < PX1 - 2:
        d.line([(x * K, (PY0 + 3) * K), (x * K, (PY1 - 3) * K)], fill=(236, 160, 168) if i % 5 == 0 else (246, 204, 208), width=K); x += step; i += 1
    for sgn in (-1, 1):
        y = EBASE + (step if sgn > 0 else 0); j = 1 if sgn > 0 else 0
        while PY0 + 2 < y < PY1 - 2:
            d.line([((PX0 + 3) * K, y * K), ((PX1 - 3) * K, y * K)], fill=(236, 160, 168) if j % 5 == 0 else (246, 204, 208), width=K)
            y += sgn * step; j += 1


def tag(d, xy, s, anchor, bold=True, size=11, fill=INK):
    x, y = xy[0] * K, xy[1] * K
    bb = d.textbbox((x, y), s, font=F(size, bold), anchor=anchor)
    d.rounded_rectangle([bb[0] - 5 * K, bb[1] - 3 * K, bb[2] + 5 * K, bb[3] + 3 * K], radius=6 * K, fill=(255, 255, 255))
    d.text((x, y), s, font=F(size, bold), fill=fill, anchor=anchor)


def frame(si, t, pi, final=False):
    sc = SCN[si]
    al = alpha(si, t)[..., None]
    img = Image.fromarray((BASE_ARR * (1 - al) + TINT * al).clip(0, 255).astype(np.uint8))
    ov = Image.new("RGBA", (WW, WH), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    if si == 0:
        lit = [sub(INTERNODAL, ramp(t, 0.05, 0.14)), sub(INTER2, ramp(t, 0.05, 0.14)), sub(INTER3, ramp(t, 0.05, 0.14)),
               sub(BACHMANN, ramp(t, 0.05, 0.11)), sub(HIS, ramp(t, 0.195, 0.205)),
               sub(RBB, ramp(t, 0.205, 0.222)), sub(LBB, ramp(t, 0.205, 0.222)),
               sub(PURK_R, ramp(t, 0.222, 0.235)), sub(PURK_L, ramp(t, 0.222, 0.235))]
        fade = 1 - ramp(t, 0.30, 0.37)
    elif si == 1:
        lit = [sub(HIS, ramp(t, 0.045, 0.055)), sub(RBB, ramp(t, 0.055, 0.072)), sub(LBB, ramp(t, 0.055, 0.072)),
               sub(PURK_R, ramp(t, 0.072, 0.085)), sub(PURK_L, ramp(t, 0.072, 0.085)),
               sub(rev(INTERNODAL), ramp(t, 0.10, 0.17)), sub(rev(INTER2), ramp(t, 0.10, 0.17)), sub(rev(INTER3), ramp(t, 0.10, 0.17)),
               sub(BACHMANN, ramp(t, 0.17, 0.20))]
        fade = 1 - ramp(t, 0.27, 0.34)
    else:
        f2 = ramp(t, 0.85, 0.94)
        lit = [sub(INTERNODAL, max(ramp(t, 0.05, 0.14), f2) if t < 0.30 or t >= 0.85 else ramp(t, 0.05, 0.14)),
               sub(BACHMANN, ramp(t, 0.05, 0.11) if t < 0.30 else ramp(t, 0.85, 0.91))]
        fade = (1 - ramp(t, 0.30, 0.37)) if t < 0.80 else 1.0
        if 0.37 <= t < 0.85: lit = []
    if fade > 0:
        for seg in lit:
            if len(seg) >= 2:
                pts = [O(*p) for p in seg]
                od.line(pts, fill=GOLD + (int(70 * fade),), width=26, joint="curve")
                od.line(pts, fill=GOLD + (int(255 * fade),), width=9, joint="curve")
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)

    def dot(p, r=13, col=GOLD):
        x, y = O(*p)
        d.ellipse([x - r - 8, y - r - 8, x + r + 8, y + r + 8], fill=(255, 225, 120) if col == GOLD else (255, 170, 160))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=INK, width=3)

    def block_mark():
        x, y = O(*AV); r = 26
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255), outline=(220, 40, 30), width=6)
        d.line([x - 13, y - 13, x + 13, y + 13], fill=(220, 40, 30), width=7)
        d.line([x - 13, y + 13, x + 13, y - 13], fill=(220, 40, 30), width=7)

    puls = lambda a_, b_, n=2: abs(math.sin((t - a_) / (b_ - a_) * math.pi * n))
    if si == 0:
        if t < 0.05: dot(SA, 12 + 8 * puls(0, 0.05))
        elif t < 0.15: dot(ppos(INTERNODAL, ramp(t, 0.05, 0.14))); dot(ppos(BACHMANN, ramp(t, 0.05, 0.11)), 9)
        elif t < 0.20: dot(AV, 13 + 7 * puls(0.15, 0.20, 3))
        elif t < 0.205: dot(ppos(HIS, ramp(t, 0.195, 0.205)))
        elif t < 0.222: dot(ppos(RBB, ramp(t, 0.205, 0.222)), 11); dot(ppos(LBB, ramp(t, 0.205, 0.222)), 11)
        elif t < 0.235: dot(ppos(PURK_R, ramp(t, 0.222, 0.235)), 9); dot(ppos(PURK_L, ramp(t, 0.222, 0.235)), 9)
    elif si == 1:
        if t < 0.045: dot(AV, 13 + 8 * puls(0, 0.045))
        elif t < 0.055: dot(ppos(HIS, ramp(t, 0.045, 0.055)))
        elif t < 0.072: dot(ppos(RBB, ramp(t, 0.055, 0.072)), 11); dot(ppos(LBB, ramp(t, 0.055, 0.072)), 11)
        elif t < 0.085: dot(ppos(PURK_R, ramp(t, 0.072, 0.085)), 9); dot(ppos(PURK_L, ramp(t, 0.072, 0.085)), 9)
        if 0.10 <= t < 0.17: dot(ppos(rev(INTERNODAL), ramp(t, 0.10, 0.17)), 11)
        x, y = O(*SA); d.ellipse([x - 12, y - 12, x + 12, y + 12], outline=(120, 126, 138), width=4)
    else:
        if t < 0.05 or 0.80 <= t < 0.85: dot(SA, 12 + 8 * puls(0 if t < 0.5 else 0.80, 0.05 if t < 0.5 else 0.85))
        elif t < 0.15: dot(ppos(INTERNODAL, ramp(t, 0.05, 0.14))); dot(ppos(BACHMANN, ramp(t, 0.05, 0.11)), 9)
        elif 0.85 <= t < 0.95: dot(ppos(INTERNODAL, ramp(t, 0.85, 0.94))); dot(ppos(BACHMANN, ramp(t, 0.85, 0.91)), 9)
        if 0.15 <= t < 0.30 or t >= 0.95: block_mark()
        if 0.26 <= t < 0.33: dot(FOCUS, 12 + 9 * puls(0.26, 0.33, 2), (255, 120, 90))

    tag(d, (SA[0] / 4 - 14, SA[1] / 4 - 4), "СА-узел", "rm")
    tag(d, (AV[0] / 4 - 16, AV[1] / 4 + 18), "АВ-узел", "rm")
    if si == 2:
        tag(d, (FOCUS[0] / 4 + 4, FOCUS[1] / 4 + 30), "очаг в желудочке", "mm", True, 10.5)
    # заголовок
    title = "Источник ритма · " + sc["title"]
    tb = d.textbbox((WW // 2, 22 * K), title, font=F(15.5, True), anchor="mm")
    d.rounded_rectangle([tb[0] - 12 * K, tb[1] - 7 * K, tb[2] + 12 * K, tb[3] + 7 * K], radius=10 * K, fill=(7, 12, 26))
    d.text((WW // 2, 22 * K), title, font=F(15.5, True), fill=WHITE, anchor="mm")
    # подпись фазы
    ph = sc["phases"][pi]
    name, desc, col = (sc["summary"][0], sc["summary"][1], WHITE) if final else (ph[2], ph[3], ph[4])
    d.text((18 * K, 738 * K), name, font=F(17, True), fill=col, anchor="lm")
    d.text((18 * K, 760 * K), desc, font=F(12.5), fill=(225, 230, 238), anchor="lm")
    # ЭКГ
    panel(d)
    if ph[5] and not final:
        ov = Image.new("RGBA", (WW, WH), (0, 0, 0, 0))
        ImageDraw.Draw(ov).rectangle([EX(ph[0]), (PY0 + 4) * K, EX(ph[1]), (PY1 - 4) * K], fill=ph[4] + (70,))
        img.paste(ov, (0, 0), ov); d = ImageDraw.Draw(img)
        d.text(((EX(ph[0]) + EX(ph[1])) / 2, (PY0 + 14) * K), ph[5], font=F(13, True), fill=tuple(int(c * 0.75) for c in ph[4]), anchor="mm")
    pts = []; tt = 0.0
    while tt <= t + 1e-9:
        pts.append((EX(tt), EY(ecg(si, tt)))); tt += 0.002
    if len(pts) > 1:
        d.line(pts, fill=(60, 64, 76), width=int(2.4 * K), joint="curve")
    if not final:
        x, y = pts[-1]; d.ellipse([x - 6 * K, y - 6 * K, x + 6 * K, y + 6 * K], fill=(220, 50, 40))
    d.text(((PX1 - 8) * K, (PY0 + 12) * K), "II отведение", font=F(10.5, True), fill=(150, 90, 96), anchor="rm")
    d.text((WW // 2, 953 * K), "анимация замедлена, быстрые фазы растянуты · схема учебная", font=F(9), fill=MUTED, anchor="mb")
    return img.resize((FW, FH), Image.LANCZOS)


if os.environ.get("TEST"):
    for si, t, pi in ((1, 0.07, 1), (1, 0.15, 2), (2, 0.20, 2), (2, 0.40, 3), (2, 0.90, 5)):
        frame(si, t, pi).save(f"/home/claude/png/rg_{si}_{int(t*100)}.png")
    frame(2, 0.999, 5, True).save("/home/claude/png/rg_2_final.png")
    sys.exit()

frames, durs = [], []
for si, sc in enumerate(SCN):
    for pi, ((a_, b_, *_), n) in enumerate(zip(sc["phases"], sc["frames"])):
        for k in range(n):
            frames.append(frame(si, a_ + (b_ - a_) * k / n, pi)); durs.append(70)
    frames.append(frame(si, sc["end"] - 0.001, len(sc["phases"]) - 1, True)); durs.append(2200)
picks = [frames[i] for i in range(0, len(frames), max(1, len(frames) // 14))]
sw = Image.new("RGB", (FW, FH))
swd = ImageDraw.Draw(sw)
for k, c in enumerate([GREEN, BLUE, RED, ORANGE, VIOLET, GOLD, MUTED, WHITE, (225, 230, 238)]):
    for j in range(6):                                   # оттенки на тёмном и светлом фоне
        mix = tuple(int(c[i] * (1 - j / 8) + (BG[i] if j % 2 else 253) * (j / 8)) for i in range(3))
        swd.rectangle([k * 60, j * 160, k * 60 + 59, j * 160 + 159], fill=mix)
picks = picks + [sw, sw]
mont = Image.new("RGB", (FW, FH * len(picks)))
for k, f in enumerate(picks): mont.paste(f, (0, k * FH))
pal = mont.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
q[0].save(OUT, save_all=True, append_images=q[1:], duration=durs, loop=0, optimize=True, disposal=1)
print(OUT, len(frames), "frames", sum(durs) / 1000, "s", os.path.getsize(OUT) // 1024, "KB")
