"""Standalone render harness for the mini-player gadget — no app config touched.

Builds the REAL MiniPlayerGadget against a stub main window, then grabs it at the
real shipped sizes so design gates are judged on the shipping surface, not prose.

    python design/gadget_study.py before    -> before_*.png   (pre-change code)
    python design/gadget_study.py after     -> after_*.png    (patched code)
    python design/gadget_study.py skins     -> skins_sheet.png (all five treatments)

Run with the native platform plugin (default on Windows): the offscreen plugin
reports no font families and every label renders as tofu.
"""
import os
import sys
import time

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPainter, QColor, QFont
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtCore import Qt, QRectF

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)
sys.path.insert(0, APP_DIR)
import audio_player_pro_v2 as m  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else 'before'
FAKE_TRACK = os.path.join(APP_DIR, '__no_such_track__.flac')
TRACKS = [dict(title='Neon Rainfall', artist='Aiko Tanaka', rating=4)]
LIBRARY = [5, 5, 4, 4, 3, 3, 2, 1]      # rated library, so the rank chip is real


class FakeVisualizer:
    audio_buffer = None


class FakeMain:
    """Minimal surface of AudioPlayerPro that MiniPlayerGadget actually touches."""

    def __init__(self):
        self.theme_key = 'midnight'
        self.gadget_enabled = True
        self._gadget_active = False
        self.player = QMediaPlayer()
        self.audio_out = None
        self.battery_volume = None
        self.visualizer = FakeVisualizer()
        self.current_playing_track = None
        self.current_index = 0
        self._meta = {}
        self.song_profiles = {}
        self.saved = 0
        for i, v in enumerate(LIBRARY):
            self.song_profiles[os.path.normpath('lib_%02d.flac' % i)] = {'rating': v}

    # ── playlist-facing helpers the gadget calls ──
    def _get_song_title(self, path):
        return self._meta.get(path, {}).get('title', '')

    def _get_song_artist(self, path):
        return self._meta.get(path, {}).get('artist', '')

    def _get_song_rating(self, path):
        p = self.song_profiles.get(os.path.normpath(str(path)))
        return int(p.get('rating', 0)) if p else 0

    def _save_song_profiles_to_disk(self):
        self.saved += 1

    def _schedule_save_settings(self):
        self.saved += 1

    def _toggle_play(self):
        pass

    def _prev_track(self):
        pass

    def _next_track(self):
        pass

    def _open_settings_window(self):
        pass

    def _exit_gadget_mode(self):
        pass


def make_gadget(main, shape='card', size='m', skin=None):
    g = m.MiniPlayerGadget(main)
    g.shape = shape
    g.bg_mode = 'opaque'
    if skin:
        g.skin_key = skin
    if hasattr(g, 'set_size_key'):
        g.set_size_key(size)
    if shape == 'circle':
        g.resize(g.width(), g.width())
    g.refresh_track(force=True)
    g.position_ms = 96_000
    g.duration_ms = 244_000
    g.buffered = 0.42
    g.playing = True
    g._anim_t = 3.0
    for sp in getattr(g, '_btn_scale', {}).values():
        sp.value = 1.0
    for sp in getattr(g, '_star_scale', []):
        sp.value = 1.0              # settled: _tick never runs in this harness
    g.update()
    QApplication.processEvents()
    return g


def settle(g, n=3):
    for _ in range(n):
        QApplication.processEvents()
        time.sleep(0.02)


def render(g):
    settle(g)
    pm = g.grab()
    if pm.isNull() or pm.width() < 10:
        raise SystemExit('grab failed: %sx%s' % (pm.width(), pm.height()))
    w, h = pm.width(), pm.height()
    out = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(QColor('#0b0f14'))
    p = QPainter(out)
    p.drawPixmap(0, 0, pm)
    p.end()
    return out


def shot(g, name, hover=None, star_hover=None):
    if hover is not None:
        g._hover = True
        g._hover_hit = hover
        sp = getattr(g, '_btn_scale', {}).get(hover)
        if sp is not None:
            sp.value = 1.16
        if hasattr(g, '_hover_star'):
            g._hover_star = star_hover
    out = render(g)
    path = os.path.join(APP_DIR, '%s_%s.png' % (TAG, name))
    out.save(path)
    print('%s  %dx%d' % (path, out.width(), out.height()))


def skin_sheet(rows):
    """One PNG: every skin as a real card + circle render, labelled."""
    pad, label_w, gap = 26, 138, 24
    cw = max(c[0].width() for c in rows)
    ch = max(c[0].height() for c in rows)
    dw = max(c[1].width() for c in rows)
    dh = max(c[1].height() for c in rows)
    row_h = max(ch, dh) + gap
    W = pad * 2 + label_w + cw + gap + dw
    H = pad * 2 + row_h * len(rows) - gap
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor('#0b0f14'))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    for i, (card, circ, name, desc) in enumerate(rows):
        top = pad + i * row_h
        p.setPen(QColor('#e5e7eb'))
        f = QFont('Segoe UI', 10)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(pad, top + ch / 2.0 - 14, label_w, 18),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), name)
        p.setPen(QColor('#7d8590'))
        p.setFont(QFont('Consolas', 7))
        p.drawText(QRectF(pad, top + ch / 2.0 + 4, label_w, 14),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), desc)
        p.drawImage(int(pad + label_w), int(top + (ch - card.height()) / 2.0), card)
        p.drawImage(int(pad + label_w + cw + gap), int(top + (ch - dh) / 2.0), circ)
    p.end()
    path = os.path.join(APP_DIR, '%s_sheet.png' % TAG)
    img.save(path)
    print('%s  %dx%d' % (path, W, H))


def main():
    app = QApplication(sys.argv[:1])
    fm = FakeMain()
    fm._meta[FAKE_TRACK] = TRACKS[0]
    fm.current_playing_track = FAKE_TRACK
    fm.song_profiles[os.path.normpath(FAKE_TRACK)] = {'rating': TRACKS[0]['rating']}

    if TAG == 'skins':
        rows = []
        for key in m.GADGET_SKIN_KEYS:
            card = make_gadget(fm, 'card', 'm', key)
            circ = make_gadget(fm, 'circle', 'm', key)
            rows.append((render(card), render(circ), m.GADGET_SKIN_LABELS[key], key))
            card.deleteLater()
            circ.deleteLater()
        skin_sheet(rows)
        return

    card = make_gadget(fm, 'card', 'm')
    print('card size:', card.width(), 'x', card.height())
    shot(card, 'card_idle')
    shot(card, 'card_hover', hover='play')
    shot(card, 'card_star_hover', hover='star2', star_hover=1)

    for key in ('s', 'l'):
        g = make_gadget(fm, 'card', key)
        print('card size', key, ':', g.width(), 'x', g.height())
        shot(g, 'card_%s' % key)
        g.deleteLater()

    circ = make_gadget(fm, 'circle', 'm')
    print('circle size:', circ.width(), 'x', circ.height())
    shot(circ, 'circle_idle')
    shot(circ, 'circle_hover', hover='play')
    print('settings writes:', fm.saved)


if __name__ == '__main__':
    main()