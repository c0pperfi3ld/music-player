<div align="center">
  <img src="assets/banner.png" alt="Audio Player Pro — cyberpunk dial HUD banner" width="100%"/>

  <a href="https://github.com/c0pperfi3ld/music-player">
    <img src="https://readme-typing-svg.demolab.com?font=Segoe+UI&weight=700&size=21&pause=1400&color=22D3EE&center=true&vCenter=true&width=780&lines=Real-time+DSP+spectrum+visualizers;Floating+Card+%26+Dial+HUD+in+one+click;A-B+looping+and+granular+pitch+%2F+tempo;Pure+PyQt6+%2B+NumPy%2C+zero+telemetry" alt="Audio Player Pro"/>
  </a>

  <br/>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![NumPy FFT](https://img.shields.io/badge/DSP-NumPy%20FFT-013243?style=flat-square&logo=numpy&logoColor=white)](https://numpy.org)
[![Mutagen](https://img.shields.io/badge/tags-Mutagen-ff7a18?style=flat-square)](https://mutagen.readthedocs.io/)
[![License](https://img.shields.io/badge/license-MIT-8b5cf6?style=flat-square)](LICENSE)
[![Telemetry](https://img.shields.io/badge/telemetry-none-10b981?style=flat-square)](#-privacy--local-first)

<br/>

  <b>A studio-grade desktop music player with a real-time vector visualizer engine and a floating HUD that reshapes itself into a card or a dial.</b>

  <br/><br/>

  [Appearance modes](#modes) · [HUD](#hud) · [Visualizers](#visualizers) · [Skins](#skins) · [Quickstart](#quickstart) · [Keys](#keys)

  <br/>
</div>

---

<a id="modes"></a>

## 🎛️ Three Appearance Modes

One segmented switch in the header (**or `Ctrl+1` / `Ctrl+2` / `Ctrl+3`**) moves the app between its three surfaces. The main window hands the desk over to the HUD and takes it back — no minimise-to-tray dance, no lost playlist state.

<table>
<tr>
<th align="center" width="50%">▬ Card HUD</th>
<th align="center" width="50%">◉ Dial HUD</th>
</tr>
<tr>
<td align="center"><img src="design/mode_card.png" alt="Card HUD" width="400"/></td>
<td align="center"><img src="design/mode_dial.png" alt="Dial HUD" width="400"/></td>
</tr>
<tr>
<td align="center" valign="top">A 348×168 desk companion: title, artist, waveform scrubber, star rating with live rank, transport keys and a volume rail.</td>
<td align="center" valign="top">A 372×372 dial: 360° FFT spokes around a glowing seek ring, a volume ring, the rating row and a glass utility capsule.</td>
</tr>
</table>

**▣ Full window** — the workstation surface the HUD is summoned from, and where it hands control back. One split layout holds the playlist table (rating, title, artist, duration, format, quality, size, folder origin, saved settings), the spectrum pane, the waveform overview with A/B loop markers, the transport deck, the remix rack and the YouTube downloader.

> Screenshots above are the app's own widgets rendered offscreen by [`design/mode_probe.py`](design/mode_probe.py) in an empty state — no personal library is ever captured into this repository.

<div align="center">
  <img src="design/switch_dial.png" alt="Appearance mode switch with Dial active" width="204"/>
  <br/>
  <sub>The switch itself — a custom-painted segmented pill, accent-tinted per theme (shown with <b>Dial</b> active).</sub>
</div>

Every route into and out of the HUD funnels through the same state, so the switch can never disagree with reality:

| You do this | The switch follows |
| :--- | :--- |
| Click a segment in the header | → full / card / dial |
| <kbd>Ctrl</kbd>+<kbd>1</kbd> · <kbd>2</kbd> · <kbd>3</kbd> — in the window *and* inside the HUD | → full / card / dial |
| Double-click the dial | → card (flips card ↔ dial) |
| Right-click the HUD → **Appearance mode** | → full / card / dial |
| Minimise the window | → card HUD |
| HUD ✕ or <kbd>Esc</kbd> | → full window |

---

<a id="hud"></a>

## 🔮 The Floating HUD

The same widget, two layouts. The dial stacks three balanced rows inside one circle; the card lays the same controls out in a strip.

```
        ◉ DIAL HUD (372 × 372)                 ▬ CARD HUD (348 × 168)
 ┌───────────────────────────────┐      ┌───────────────────────────────┐
 │  〰 360° FFT spokes + ring     │      │  ┌───┐  Title                 │
 │                               │      │  │art│  Artist                │
 │      ✦ ✦ ✦ ✦ ✧   rating       │      │  └───┘  ▁▂▃▅▇▅▃▂▁  scrubber  │
 │      ⏮  ▶̸  ⏭     transport     │      │   ★ ★ ★ ★ ☆  #3/9             │
 │   [ ⚲ ▭ ⚙ ⤢ ✕ ]  dock         │      │  ⏮ ▶̸ ⏭  ▬▬▬▬▬  vol  ⚲▭⚙⤢✕   │
 └───────────────────────────────┘      └───────────────────────────────┘
```

* **Centered symmetry** — the dial's rating row, transport and utility dock share one vertical axis, and the dock's hit targets tile edge to edge, so a near-miss still lands on the icon you aimed at.
* **Revamped vector glyphs** — hand-built `QPainterPath` icons: a 6-tooth mechanical cog, a tapered pushpin, a split-pane frame, corner expand brackets and a rounded dismiss cross. Each gets a contact shadow so it stays legible over any wallpaper.
* **Always-on-top & edge snapping** — optional pin, optional snap, adjustable opacity, plus a hover-only resize grip.
* **Three capture modes** — opaque card, real glass, or fully transparent over the desktop.

---

<a id="visualizers"></a>

## 🌌 Visualizer Suite

**20 render modes**, driven by vectorized NumPy FFT analysis (log-spaced band edges, per-band attack/decay, peak hold) and painted as a single vector pass per frame.

| | | |
| :--- | :--- | :--- |
| 📊 Spectrum Bars | 🌊 Liquid Wave | 🌀 Radial Halo |
| ✨ Audio Nebula | 🪞 Dual Mirror Wave | 💫 Circular Spectrum |
| 🧬 Dual DNA Helix | 🌌 Neon Plasma Grid | ⚡ Neon Oscilloscope |
| 🚀 Cyber Vortex Tunnel | 🪐 Holographic Rings | ⚡ Concert Laser Show |
| 🔷 Quantum Matrix | ⬡ Cybernetic Hex Hive | 🌊 Spectral Waterfall |
| 🎯 Lissajous Phase Vector | 🌌 Borealis Sound Aurora | 🌆 80s Synth Horizon |
| 🌠 Audio Starburst Galaxy | 💠 Fractal Kaleidoscope | |

The HUD hosts a six-mode subset (`bars`, `wave`, `radial`, `mirror_wave`, `circular_bars`, `sound_aurora`) because it renders at only 348–372 px.

---

<a id="skins"></a>

## 🎨 Gadget Skins

**8 skins**, each owning its own star geometry, plate style, key shape and glow — switched live from the HUD's right-click menu or the settings window.

<div align="center">
  <img src="skins_sheet.png" alt="Gadget skin sheet" width="900"/>
  <br/>
  <sub><b>Nightshift</b> · <b>Vitals</b> · <b>Vinyl</b> · <b>Arcade</b> · <b>Prism</b> · <b>Aurora</b> · <b>Ember</b> · <b>Mono</b></sub>
</div>

The main window ships **11 themes**: Midnight Cyber, Synthwave 80s, Emerald Matrix, Crimson Nebula, Tokyo Violet, Solar Flare, Frost Aurora, Dark Pro, Ocean Deep, Cyber Amber and Minimal Studio.

---

## ⚡ Feature Grid

<table>
<tr>
<td width="50%" valign="top">

#### 🎧 Playback
* Lossless **FLAC · WAV · ALAC · AIFF** plus MP3 · M4A · OGG · OPUS · AAC
* Shuffle, repeat off/all/one, instant track switching
* Speed **0.25× – 2.50×** in 0.01 steps
* Full metadata via Mutagen, cached to disk

</td>
<td width="50%" valign="top">

#### 🎚️ Remix Rack (DSP / FX)
* **Pitch** ±12 semitones, independent of tempo
* **Tempo**, **Reverb**, **Echo / Delay**, **Stereo Width**
* **Bass** and **Treble** shelves, 7-band EQ
* Reset · bypass · render the chain

</td>
</tr>
<tr>
<td width="50%" valign="top">

#### 🔁 A-B Looping
* Punch in an **A** and a **B** point anywhere in a track
* The loop re-asserts itself across track loads (guarded seek)
* The loop zone is drawn straight onto the waveform

</td>
<td width="50%" valign="top">

#### ⭐ Library & Ratings
* Per-song profiles: rating, volume, speed, loop, EQ
* 5-star rating with a live `#rank/total` chip
* Sort, filter, drag-reorder, move to top / bottom
* Multi-folder scanning + YouTube downloader (`yt-dlp`)

</td>
</tr>
</table>

---

<a id="quickstart"></a>

## 🚀 Quickstart

```bash
# 1 — clone
git clone https://github.com/c0pperfi3ld/music-player.git
cd music-player

# 2 — dependencies (PyQt6, numpy, mutagen, yt-dlp)
pip install -r requirements.txt

# 3 — run
python audio_player_pro_v2.py
```

Requires **Python 3.10+**. The first launch scans `~/Music` and `~/Music/AudioPlayerDownloads`.

---

<a id="keys"></a>

## ⌨️ Keys & Mouse

Honest list — these are the shortcuts the code actually wires up.

| Input | Action |
| :--- | :--- |
| <kbd>Ctrl</kbd>+<kbd>1</kbd> / <kbd>2</kbd> / <kbd>3</kbd> | Appearance mode: Full window / Card HUD / Dial HUD |
| <kbd>Space</kbd> | Play / pause *(HUD focused)* |
| <kbd>←</kbd> / <kbd>→</kbd> | Seek ±5 s *(HUD focused)* |
| <kbd>Esc</kbd> | Leave the HUD, back to the full window |
| <kbd>Alt</kbd>/<kbd>Ctrl</kbd> + <kbd>↑</kbd> / <kbd>↓</kbd> | Move the selected track in the playlist *(table focused)* |
| Double-click the dial | Flip dial ↔ card |
| Right-click the HUD | Appearance mode, skin, size, background, visualizer, border |

---

## 🏗️ Architecture

```
music-player/
├── audio_player_pro_v2.py   # the whole app: window, DSP engine, visualizers, HUD
├── design/                  # headless render harness + mode screenshots
│   ├── gadget_study.py      # renders the real HUD offscreen into PNGs
│   └── circle_design.py     # polar/arc geometry for the dial
├── assets/banner.png        # README hero banner
├── requirements.txt
└── .gitignore               # excludes audio, credentials and user data
```

| Layer | What it uses |
| :--- | :--- |
| UI & painting | PyQt6, custom `QPainter` / `QPainterPath` vector passes, spring-animated widgets |
| Audio | `QMediaPlayer` + `QAudioOutput`, frame-accurate position sync |
| DSP | NumPy `rfft` with log-spaced band aggregation and per-band envelope followers |
| Metadata | Mutagen (ID3 / Vorbis / FLAC / MP4) with a JSON cache |
| Downloads | `yt-dlp` with duplicate detection and format conversion |

---

## 🛡️ Privacy & Local-First

* **No telemetry** — no analytics, no phone-home, no accounts.
* **Local data** — library, ratings, per-song profiles, waveform cache and settings stay in your own files.
* **Clean repo** — `.gitignore` blocks every audio extension, `cookies.txt`, credentials, caches and backups, so nothing personal can be committed by accident.

---

<div align="center">

**MIT licensed.** Built with PyQt6 + NumPy — enjoy the music.

<sub>If this was useful, a ⭐ helps.</sub>

</div>
