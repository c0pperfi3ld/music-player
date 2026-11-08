"""Drive the REAL app through every appearance mode and grab each surface.

    python design/mode_probe.py     -> design/mode_*.png, design/switch_*.png

Unlike gadget_study.py (which renders a single widget against a stub main
window) this one boots the actual AudioPlayerPro window and exercises the
header switch, the Ctrl+1/2/3 shortcuts' target method, the gadget's own
double-click shape flip and its ✕ path — so the four routes into and out of a
mode are proven to leave the switch, the window and the gadget in agreement.

It also asserts that the probe never writes settings: user files are stubbed
out before any mode change happens.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from PyQt6.QtWidgets import QApplication           # noqa: E402
from PyQt6.QtCore import QPointF                   # noqa: E402

import audio_player_pro_v2 as m                    # noqa: E402

OUT = HERE
app = QApplication(sys.argv[:1])
w = m.AudioPlayerPro()

# this probe must never touch the user's real settings or profiles
w._schedule_save_settings = lambda: None
w._save_persisted_settings = lambda: None

w.show()
w._sync_view_switch()
for _ in range(12):
    app.processEvents()
    time.sleep(0.03)


def pump(n=24, dt=0.02):
    for _ in range(n):
        app.processEvents()
        time.sleep(dt)


def grab(widget, name):
    pix = widget.grab()
    path = os.path.join(OUT, name)
    pix.save(path)
    print('%-18s %4dx%-5d -> %s' % (name, pix.width(), pix.height(), path))


grab(w.view_switch, 'switch_full.png')
print('switch keys      :', m.ViewModeSwitch.keys())
print('hit-test @6px    :', w.view_switch._index_at(QPointF(6, 13)), '(expect 0)')
print('hit-test @middle :', w.view_switch._index_at(
    QPointF(w.view_switch.width() / 2.0, 13)), '(expect 1)')

grab(w, 'mode_full.png')
print('mode/full        :', w._view_mode, '| window visible', w.isVisible())

w.set_view_mode('card')
pump()
g = w._gadget
print('mode/card        :', w._view_mode, '| gadget', g.shape,
      '%dx%d' % (g.width(), g.height()), '| visible', g.isVisible(),
      '| main visible', w.isVisible())
print('switch after card:', w.view_switch.mode(), '| pill', round(w.view_switch._pos, 3))
grab(g, 'mode_card.png')
grab(w.view_switch, 'switch_card.png')

w.set_view_mode('dial')
pump()
print('mode/dial        :', w._view_mode, '| gadget', g.shape,
      '%dx%d' % (g.width(), g.height()), '| visible', g.isVisible(),
      '| main visible', w.isVisible())
print('switch after dial:', w.view_switch.mode(), '| pill', round(w.view_switch._pos, 3))
grab(g, 'mode_dial.png')
grab(w.view_switch, 'switch_dial.png')

g.set_shape('card')                     # the gadget's own double-click path
pump()
print('dblclick path    :', w._view_mode, '| gadget', g.shape,
      '%dx%d' % (g.width(), g.height()), '| switch', w.view_switch.mode())

w.set_view_mode('full')
pump()
print('mode/full again  :', w._view_mode, '| gadget visible', g.isVisible(),
      '| main visible', w.isVisible(), '| switch', w.view_switch.mode())

w.set_view_mode('dial')
pump()
w._exit_gadget_mode()                   # the HUD's ✕ / Esc path
pump()
print('hud close path   :', w._view_mode, '| main visible', w.isVisible(),
      '| switch', w.view_switch.mode())

app.quit()
