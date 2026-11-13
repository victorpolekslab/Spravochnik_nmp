"""Общие функции для SVG-схем цикла «ЭКГ»."""
import math, random, os, sys


W, H = 960, 540
INK = "#1f2430"; MUTED = "#6b7280"; RED = "#d0342c"; BLUE = "#2f6fb5"
GREEN = "#2e8b57"; ORANGE = "#e08a00"; VIOLET = "#7b4bb7"; BROWN = "#8b5a2b"
GRID_S = "#f7d4d4"; GRID_B = "#eaa3a3"
FONT = "DejaVu Sans, Arial, sans-serif"


def svg(body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}" font-family="{FONT}">\n'
            f'<title>{title}</title>\n'
            f'<rect width="{W}" height="{H}" rx="18" fill="#ffffff"/>\n{body}\n</svg>\n')


def text(x, y, s, size=18, fill=INK, anchor="start", weight="normal"):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{s}</text>')


def gauss(t, a, mu, sd):
    return a * math.exp(-((t - mu) ** 2) / (2 * sd * sd))


def beat(t, scale=1.0):
    """Один кардиоцикл, t в секундах от начала цикла; результат в мВ."""
    v = (gauss(t, 0.15, 0.10, 0.022) + gauss(t, -0.10, 0.205, 0.007)
         + gauss(t, 1.05, 0.225, 0.009) + gauss(t, -0.28, 0.245, 0.009)
         + gauss(t, 0.32, 0.43, 0.04))
    return v * scale


def ecg(t, rr=0.8, scale=1.0):
    return beat(t % rr, scale)


def grid(x0, y0, w, h, px_mm):
    out = []
    n = int(w / px_mm)
    for i in range(n + 1):
        x = x0 + i * px_mm
        big = i % 5 == 0
        out.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0+h}" '
                   f'stroke="{GRID_B if big else GRID_S}" stroke-width="{1.2 if big else 0.6}"/>')
    m = int(h / px_mm)
    for j in range(m + 1):
        y = y0 + j * px_mm
        big = j % 5 == 0
        out.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+w}" y2="{y:.1f}" '
                   f'stroke="{GRID_B if big else GRID_S}" stroke-width="{1.2 if big else 0.6}"/>')
    return "\n".join(out)


def trace(fn, x0, y_base, w, px_per_s, px_per_mv, color=INK, width=2.2, step=0.5):
    pts = []
    x = 0.0
    while x <= w:
        t = x / px_per_s
        pts.append(f"{x0 + x:.1f},{y_base - fn(t) * px_per_mv:.1f}")
        x += step
    return (f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')


def calib(x, y_base, px_mm, color=INK):
    h = 10 * px_mm
    return (f'<polyline points="{x},{y_base} {x+px_mm},{y_base} {x+px_mm},{y_base-h} '
            f'{x+6*px_mm},{y_base-h} {x+6*px_mm},{y_base} {x+7*px_mm},{y_base}" '
            f'fill="none" stroke="{color}" stroke-width="2"/>')




def smooth(e0, e1, x):
    if x <= e0: return 0.0
    if x >= e1: return 1.0
    u = (x - e0) / (e1 - e0)
    return u * u * (3 - 2 * u)


def beat_p(t, P=0.15, Q=-0.08, R=1.0, S=-0.25, T=0.3, st=0.0, qrs=1.0, pr=0.0, qt=1.0, U=0.0):
    """Настраиваемый кардиоцикл (мВ). qrs — множитель ширины QRS, pr — сдвиг QRS (с), qt — растяжение ST–T."""
    c = 0.225 + pr
    v = gauss(t, P, 0.10, 0.022)
    v += gauss(t, Q, c - 0.02 * qrs, 0.007 * qrs) + gauss(t, R, c, 0.009 * qrs) + gauss(t, S, c + 0.02 * qrs, 0.009 * qrs)
    tc = c + 0.205 * qt
    v += gauss(t, T, tc, 0.04 * (0.6 + 0.4 * qt))
    if U:
        v += gauss(t, U, tc + 0.16, 0.03)
    if st:
        v += st * smooth(c + 0.013 * qrs, c + 0.037 * qrs, t) * (1 - smooth(tc - 0.03, tc + 0.07, t))
    return v
