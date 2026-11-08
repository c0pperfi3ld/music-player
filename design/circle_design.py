"""Circular gadget design study — renders mockups only, touches no app config.

Three ring layouts are drawn with the same QPainter primitives the real widget
will use, so what you approve here is what gets implemented:

  A  dotted radial spokes, app theme colours
  B  solid tapered bars, app theme colours
  C  dotted spokes, reference palette (violet -> magenta -> red on midnight blue)
"""
import math
import os
import sys

from PyQt6.QtGui import (QGuiApplication, QImage, QPainter, QColor, QPen, QBrush, QPolygonF,
                         QRadialGradient, QLinearGradient, QConicalGradient,
                         QPainterPath, QFont, QFontMetrics)
from PyQt6.QtCore import QRectF, QPointF, Qt

OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)
import audio_player_pro_v2 as m          # read-only: theme table only

THEME = m.THEMES['arctic']

REF_BG = QColor('#120a20')
REF_STOPS = [QColor('#7b2ff7'), QColor('#c026d3'), QColor('#f43f5e'), QColor('#ff7a18')]


def lerp(c1, c2, f):
    f = max(0.0, min(1.0, f))
    return QColor(int(c1.red() + (c2.red() - c1.red()) * f),
                  int(c1.green() + (c2.green() - c1.green()) * f),
                  int(c1.blue() + (c2.blue() - c1.blue()) * f))


def with_alpha(c, a):
    c = QColor(c)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


def palette_colour(f, ref=False):
    if ref:
        stops = REF_STOPS
        x = f * (len(stops) - 1)
        i = min(len(stops) - 2, int(x))
        return lerp(stops[i], stops[i + 1], x - i)
    a = QColor(THEME['accent'])
    b = QColor(THEME['accent2'])
    c = QColor(THEME['accent3'])
    if f < 0.5:
        return lerp(a, b, f * 2.0)
    return lerp(b, c, (f - 0.5) * 2.0)


def level(i, n, t):
    """Pseudo spectrum: bass forward, musical motion, deterministic."""
    base = 0.5 + 0.5 * math.sin(i * 0.31 + t * 2.1)
    ripple = 0.5 + 0.5 * math.sin(i * 0.093 - t * 1.27)
    env = 0.45 + 0.55 * math.cos(min(math.pi, abs(i - n * 0.18) / (n * 0.55)))
    v = (0.35 * base + 0.65 * ripple) * env
    return max(0.04, min(1.0, v ** 0.85))


def peak(i, n, t):
    return min(1.0, level(i, n, t) * 1.22 + 0.08 * math.sin(i * 0.7 + t))


# ── icon primitives (same geometry as the live gadget) ───────────────────────
def icon(p, kind, c, s, colour):
    p.save()
    p.translate(round(c.x()), round(c.y()))
    pen_w = max(1.3, s * 0.26)
    p.setPen(QPen(colour, pen_w, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == 'play':
        path = QPainterPath()
        path.moveTo(-s * 0.40, -s * 0.62)
        path.lineTo(s * 0.66, 0.0)
        path.lineTo(-s * 0.40, s * 0.62)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawPath(path)
    elif kind == 'pause':
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawRoundedRect(QRectF(-s * 0.56, -s * 0.62, s * 0.36, s * 1.24), 1.4, 1.4)
        p.drawRoundedRect(QRectF(s * 0.20, -s * 0.62, s * 0.36, s * 1.24), 1.4, 1.4)
    elif kind in ('prev', 'next'):
        sign = -1.0 if kind == 'prev' else 1.0
        path = QPainterPath()
        path.moveTo(sign * s * 0.52, -s * 0.62)
        path.lineTo(-sign * s * 0.42, 0.0)
        path.lineTo(sign * s * 0.52, s * 0.62)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawPath(path)
        bar_x = -sign * s * 0.72 - (s * 0.14 if sign > 0 else 0.0)
        p.drawRoundedRect(QRectF(bar_x, -s * 0.62, s * 0.16, s * 1.24), 1.2, 1.2)
    elif kind == 'close':
        p.drawLine(QPointF(-s * 0.5, -s * 0.5), QPointF(s * 0.5, s * 0.5))
        p.drawLine(QPointF(s * 0.5, -s * 0.5), QPointF(-s * 0.5, s * 0.5))
    elif kind == 'pin':
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawEllipse(QPointF(0, -s * 0.30), s * 0.34, s * 0.34)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(0, s * 0.06), QPointF(0, s * 0.62))
        p.drawLine(QPointF(-s * 0.40, s * 0.60), QPointF(s * 0.40, s * 0.60))
    elif kind == 'pane':
        p.drawRoundedRect(QRectF(-s * 0.62, -s * 0.52, s * 1.02, s * 0.86), 2.0, 2.0)
        p.setBrush(colour)
        p.drawRoundedRect(QRectF(-s * 0.10, -s * 0.16, s * 0.74, s * 0.62), 1.6, 1.6)
    elif kind == 'size':
        p.drawLine(QPointF(-s * 0.58, -s * 0.18), QPointF(-s * 0.58, -s * 0.58))
        p.drawLine(QPointF(-s * 0.58, -s * 0.58), QPointF(-s * 0.18, -s * 0.58))
        p.drawLine(QPointF(s * 0.58, s * 0.18), QPointF(s * 0.58, s * 0.58))
        p.drawLine(QPointF(s * 0.58, s * 0.58), QPointF(s * 0.18, s * 0.58))
    p.restore()


def ring_arc(p, cx, cy, r, start_deg, sweep_deg, width, grad_stops, cap=True):
    rect = QRectF(cx - r, cy - r, r * 2, r * 2)
    pen = QPen(QColor(255, 255, 255, 40), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap if cap else Qt.PenCapStyle.FlatCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(rect, int(-start_deg * 16), int(-sweep_deg * 16))
    # coloured progress on top
    cg = QConicalGradient(cx, cy, -start_deg)
    for f, c in grad_stops:
        cg.setColorAt(f, c)
    pen2 = QPen(QBrush(cg), width)
    pen2.setCapStyle(Qt.PenCapStyle.RoundCap if cap else Qt.PenCapStyle.FlatCap)
    p.setPen(pen2)
    frac = min(1.0, sweep_deg / 360.0)
    p.drawArc(rect, int(-start_deg * 16), int(-sweep_deg * 16))


def render(size=360, variant='A', t=0.0, beats=None):
    ref = variant == 'C'
    W = H = size
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    cx, cy = W / 2.0, H / 2.0
    R = W / 2.0 - size * 0.014

    acc = palette_colour(0.0, ref)
    acc2 = palette_colour(0.55, ref)
    acc3 = palette_colour(1.0, ref)

    # ── card ──
    card = QRadialGradient(QPointF(cx, cy - R * 0.2), R * 1.25)
    if ref:
        card.setColorAt(0.0, QColor('#1b1030'))
        card.setColorAt(0.62, REF_BG)
        card.setColorAt(1.0, QColor('#0a0614'))
    else:
        base = QColor(THEME['bg_card'])
        base.setAlphaF(1.0)
        edge = QColor(THEME['bg'])
        card.setColorAt(0.0, base.lighter(118))
        card.setColorAt(0.75, base)
        card.setColorAt(1.0, edge.darker(112))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(card))
    p.drawEllipse(QPointF(cx, cy), R, R)

    # inner seat for the controls
    seat = QRadialGradient(QPointF(cx, cy - R * 0.1), R * 0.52)
    seat.setColorAt(0.0, QColor(255, 255, 255, 22))
    seat.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(QBrush(seat))
    p.drawEllipse(QPointF(cx, cy), R * 0.46, R * 0.46)

    # ── spectrum ring ──
    n = 132 if size >= 480 else 108
    r0 = R * 0.705
    max_len = R * 0.285
    dot_step = max(2.0, size / 210.0)
    base_dot = max(0.7, size / 220.0)

    if variant == 'B':
        buckets = {}
        C_BUCKETS = 14
        for i in range(n):
            f = i / float(n)
            th = math.radians(-90.0 + 360.0 * f)
            lv = level(i, n, t)
            ln = max_len * (0.10 + 0.90 * lv)
            ci = min(C_BUCKETS - 1, int(f * C_BUCKETS))
            buckets.setdefault(ci, []).append(
                (cx + math.cos(th) * r0, cy + math.sin(th) * r0,
                 cx + math.cos(th) * (r0 + ln), cy + math.sin(th) * (r0 + ln)))
        for ci, segs in buckets.items():
            path = QPainterPath()
            for x1, y1, x2, y2 in segs:
                path.moveTo(x1, y1)
                path.lineTo(x2, y2)
            p.setPen(QPen(with_alpha(palette_colour(ci / float(C_BUCKETS - 1), ref), 0.92),
                          max(1.4, size / 210.0), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        peaks = [QPointF(cx + math.cos(math.radians(-90.0 + 360.0 * (i / float(n)))) * (r0 + max_len * (0.10 + 0.90 * peak(i, n, t))),
                         cy + math.sin(math.radians(-90.0 + 360.0 * (i / float(n)))) * (r0 + max_len * (0.10 + 0.90 * peak(i, n, t))))
                 for i in range(n)]
        p.setPen(QPen(QColor(255, 255, 255, 190), max(1.2, size / 260.0),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPoints(QPolygonF(peaks))
    else:
        # dotted spokes, batched: one drawPoints() per (dot size, colour bucket)
        C_BUCKETS = 14
        buckets = {}
        peaks = []
        for i in range(n):
            f = i / float(n)
            th = math.radians(-90.0 + 360.0 * f)
            lv = level(i, n, t)
            ln = max_len * (0.08 + 0.92 * lv)
            dots = max(3, int(ln / dot_step))
            ci = min(C_BUCKETS - 1, int(f * C_BUCKETS))
            cos_t, sin_t = math.cos(th), math.sin(th)
            for k in range(dots):
                fk = k / float(max(1, dots - 1))
                rad = r0 + ln * fk
                si = 0 if fk < 0.34 else (1 if fk < 0.67 else 2)
                buckets.setdefault((si, ci), []).append(QPointF(cx + cos_t * rad, cy + sin_t * rad))
            pr = r0 + max_len * (0.08 + 0.92 * peak(i, n, t))
            peaks.append(QPointF(cx + cos_t * pr, cy + sin_t * pr))

        for (si, ci), pts in buckets.items():
            col = palette_colour(ci / float(C_BUCKETS - 1), ref)
            width = base_dot * (1.62 - 0.32 * si) * 2.0
            alpha = 0.96 - 0.16 * si
            p.setPen(QPen(with_alpha(col, alpha), width, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawPoints(QPolygonF(pts))
        p.setPen(QPen(QColor(255, 255, 255, 200), max(1.0, base_dot * 1.5),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPoints(QPolygonF(peaks))

    # ── faint outer rim ──
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(with_alpha(acc, 0.22), max(1.0, size / 360.0)))
    p.drawEllipse(QPointF(cx, cy), R - 1, R - 1)

    # ── circular seek ring (outer of the two) ──
    r_seek = R * 0.575
    seek_frac = 0.34
    sweep = 300.0
    start = 120.0
    # base
    p.setPen(QPen(QColor(255, 255, 255, 26), max(2.0, size / 150.0),
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(cx - r_seek, cy - r_seek, r_seek * 2, r_seek * 2),
              int(-start * 16), int(-sweep * 16))
    # progress
    cg = QConicalGradient(cx, cy, -start)
    cg.setColorAt(0.0, acc)
    cg.setColorAt(0.75, acc2)
    cg.setColorAt(1.0, acc3)
    pen = QPen(QBrush(cg), max(3.0, size / 100.0), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawArc(QRectF(cx - r_seek, cy - r_seek, r_seek * 2, r_seek * 2),
              int(-start * 16), int(-sweep * seek_frac * 16))
    # knob
    kn_a = math.radians(-(start + sweep * seek_frac))
    kx, ky = cx + math.cos(kn_a) * r_seek, cy + math.sin(kn_a) * r_seek
    halo = QRadialGradient(QPointF(kx, ky), size / 22.0)
    halo.setColorAt(0.0, with_alpha(acc, 0.55))
    halo.setColorAt(1.0, with_alpha(acc, 0.0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(halo))
    p.drawEllipse(QPointF(kx, ky), size / 22.0, size / 22.0)
    p.setBrush(QColor(255, 255, 255, 250))
    p.drawEllipse(QPointF(kx, ky), max(2.4, size / 110.0), max(2.4, size / 110.0))
    p.setBrush(acc)
    p.drawEllipse(QPointF(kx, ky), max(1.2, size / 230.0), max(1.2, size / 230.0))

    # ── circular volume ring (inner) ──
    r_vol = R * 0.455
    vol_frac = 0.62
    v_start = 210.0
    v_sweep = 120.0
    p.setPen(QPen(QColor(255, 255, 255, 22), max(1.6, size / 200.0),
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(QRectF(cx - r_vol, cy - r_vol, r_vol * 2, r_vol * 2),
              int(-v_start * 16), int(-v_sweep * 16))
    p.setPen(QPen(with_alpha(acc2 if not ref else palette_colour(0.72, True), 0.96),
                  max(2.4, size / 145.0),
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(QRectF(cx - r_vol, cy - r_vol, r_vol * 2, r_vol * 2),
              int(-v_start * 16), int(-v_sweep * vol_frac * 16))
    vk_a = math.radians(-(v_start + v_sweep * vol_frac))
    vx, vy = cx + math.cos(vk_a) * r_vol, cy + math.sin(vk_a) * r_vol
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawEllipse(QPointF(vx, vy), max(1.8, size / 150.0), max(1.8, size / 150.0))

    # ── transport inside the circle ──
    icon_col = QColor(255, 255, 255, 232)
    dim = with_alpha(QColor(THEME['text_dim'] if not ref else '#b9a7d8'), 0.85)
    ty = cy - R * 0.02
    gap = R * 0.235
    icon_size = max(9.0, R * 0.088)
    icon(p, 'prev', QPointF(cx - gap, ty), icon_size, dim)
    icon(p, 'pause', QPointF(cx, ty), icon_size * 1.16, acc)
    icon(p, 'next', QPointF(cx + gap, ty), icon_size, dim)

    # ── utility cluster, bottom inside the circle ──
    uy = cy + R * 0.30
    ugap = R * 0.115
    us = max(5.0, R * 0.042)
    for k, kind in enumerate(('pin', 'pane', 'size', 'close')):
        icon(p, kind, QPointF(cx + (k - 1.5) * ugap, uy), us, with_alpha(dim, 0.8))

    # ── time readout (no title, no artist) ──
    if variant in ('A', 'C'):
        f = QFont('Consolas', max(6, int(size / 46)))
        p.setFont(f)
        p.setPen(with_alpha(QColor(255, 255, 255, 150), 0.9))
        fm = QFontMetrics(f)
        txt = "1:32"
        p.drawText(QPointF(cx - fm.horizontalAdvance(txt) / 2.0, cy + R * 0.175), txt)

    # ── orbiting motes: the "super detailed" layer ──
    groups = {0: [], 1: [], 2: []}
    for k in range(46 if size >= 480 else 34):
        th_a = math.radians((k * 137.508 + t * 26.0) % 360.0)
        rr = R * (0.735 + 0.055 * math.sin(k * 1.7 + t * 1.9))
        x, y = cx + math.cos(th_a) * rr, cy + math.sin(th_a) * rr
        a = 0.10 + 0.16 * (0.5 + 0.5 * math.sin(k * 2.3 - t * 2.6))
        groups[min(2, int(a / 0.09))].append(QPointF(x, y))
    for gi, pts in groups.items():
        if not pts:
            continue
        p.setPen(QPen(QColor(255, 255, 255, 40 + gi * 34), max(0.7, size / 460.0),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPoints(QPolygonF(pts))

    p.end()
    return img


def main():
    app = QGuiApplication(sys.argv)

    for variant, label in (('A', 'dots'), ('B', 'bars'), ('C', 'reference')):
        for size in (360, 560):
            img = render(size=size, variant=variant, t=0.8)
            path = os.path.join(OUT, 'circle_%s_%s_%d.png' % (variant, label, size))
            img.save(path)
            print('saved', os.path.basename(path), flush=True)

    # beat sequence, side by side
    frames = []
    for k in range(4):
        frames.append(render(size=300, variant='A', t=0.8 + k * 0.42))
    strip = QImage(300 * 4 + 30, 300, QImage.Format.Format_ARGB32_Premultiplied)
    strip.fill(QColor(0, 0, 0, 0))
    sp = QPainter(strip)
    for k, fr in enumerate(frames):
        sp.drawImage(k * 310, 0, fr)
    sp.end()
    strip.save(os.path.join(OUT, 'circle_A_beats.png'))
    print('saved circle_A_beats.png', flush=True)


if __name__ == '__main__':
    main()