---
title: Gadget rank stars + control revamp
aliases: [mini player stars, gadget skins]
tags: [design/blueprint, pyqt, audio-player, gadget, ui]
created: 2026-11-08
revised: 2026-11-08 — rev 4: dial dock hit-box fix + dock revamp
status: shipped
default_skin: nightshift
file: updated/audio_player_pro_v2.py
---

# Gadget rank stars + control revamp

> [!summary] What changed
> The mini-player gadget paints **the playing track's star rating plus its rank
> among rated tracks** — readable and editable on the surface itself. The stars are
> **docked to the controls they belong with** (just above the seek bar on the card,
> just above the keys on the dial), both **time readouts are gone**, and the whole
> control set was redrawn as **one rounded icon family**. Eight complete skins ship
> as data and are pickable in Settings.
>
> Everything is still QPainter on a single widget — no child controls, one cheap
> 30 FPS surface.

> [!bug] Rev 4 — why the bottom icons were dead
> The dial's utility cluster was **painted from its own private copy of the geometry**
> (`_paint_circle`: `uy = cy + R * 0.30`) while the click targets came from
> `_compute_circle_layout` (`cy + R * 0.205`). The rev-3 spacing pass moved one copy
> and not the other, so the glyphs sat **17 px below their own hit boxes** and every
> click on a bottom icon landed in empty space. Nothing was wired wrong — the clicks
> simply never reached a target.
>
> Fixed by giving the layout **sole ownership** of the geometry (`self._util_slots`),
> tiling the targets edge to edge (22 × 31 px each, zero dead gaps, glyph smaller than
> its target), and making the dial's `SIZE` key cycle the dial diameter instead of the
> card's S/M/L box, which had made it a genuine no-op.

![[preview_gadget_stars_before_after.png]]

Left column is the pre-change code, right column is the current build. Real `grab()`
captures of the actual widget, not mockups.

---

## 1. What the stars do

| Behaviour | Implementation |
|---|---|
| Reads the playing track's rating | `_refresh_rating()` mirrors `main._get_song_rating(path)`; the gadget never owns the value |
| Ranks it | `#n/total` — *total* counts every track with rating > 0, *n* is `1 + count(rating > mine)` |
| Click to set | `mousePressEvent` → `_star_index_at()` → `_set_rating(i+1)` |
| Click again to clear | `_set_rating()` treats "same value" as 0 |
| Persists | writes `song_profiles[path]['rating']`, then `_save_song_profiles_to_disk()` + `_schedule_save_settings()` |
| Syncs with the playlist column | twice-a-second re-read in `_tick()`; no signal wiring |
| Hover preview | `_hover_hit == 'starN'` fills to that value without touching the profile |
| Live sheen | a specular band travels across filled stars **while playing**, frozen when paused |
| 5/5 state | the rank chip switches to a lit accent fill |

---

## 2. Placement, measured

| Surface | Star row | Sits above | Verified clear of |
|---|---|---|---|
| Card S 268×132 | y 59→71, 12 px stars | seek at y 76 | transport at y 98 |
| Card M 348×168 | y 86→101, 15 px stars | seek at y 106 | transport at y 128 |
| Card L 452×216 | y 131→149, 18 px stars | seek at y 154 | transport at y 176 |
| Card min 244×120 | y 47→59, 12 px stars | seek at y 64 | transport at y 96 |
| Dial 372×372 | centre cy − 0.215R, 104.8 px wide | key tops at cy − 0.124R (4.2 px of air) | utility dock at cy + 0.205R, 22×31 px per slot, tiled |

This revision: stars moved **from under the artist line down to the control cluster**;
dial utility icons lifted **from +0.30R to +0.205R** so the centre reads as one group;
the dial's elapsed-time readout was deleted (the progress arc and its dot carry the
position), and the card's `1:36 / 4:04` labels were removed — the seek bar now owns
the full row and draws a subtle **minute tick** every 60 s instead.

---

## 3. The eight treatments

All eight are data (`GADGET_SKINS`), selectable in **Settings → Skin**.

![[skins_sheet.png]]

| Skin | Stars | Key | Plate | Motion |
|---|---|---|---|---|
| **Nightshift** *(default)* | amber `#ffce6a`, rounded, bloom 0.55 | filled circle, gradient | glass | quiet breathe, 1.22 pop |
| **Vitals** | accent, thin sparkle, bloom 0.32 | outlined ring, 2 px accent border | hairline only | telemetrical, 1.16 pop |
| **Vinyl** | gold foil, rounded, bloom 0.22 | soft square, embossed | none | barely-there, 1.12 pop |
| **Arcade** | candy pink→violet, fat, bloom 0.78 | filled circle, big bloom | glass | springy 1.42 overshoot |
| **Prism** | conical violet→cyan→pink, facet, bloom 0.92 | filled circle + **orbit arc** | glass | aurora bloom, 1.26 pop |
| **Aurora** | green→cyan→violet, thin sparkle, bloom 0.72 | filled circle + **orbit arc** | glass | drifting, 1.30 pop |
| **Ember** | gold→orange→red, sharp, bloom 0.62 | soft square | hairline | warm, 1.24 pop |
| **Mono** | white→steel, facet, bloom 0.14 | outlined ring | glass | flat, 1.10 pop |

### Image prompts

> [!example] Nightshift
> `dark mini music player widget, deep navy #0d1117 card, soft glass rounded plates with hairline borders, filled cyan gradient circular play key with soft bloom, five amber #ffce6a stars with faint warm halo, pill badge "#3/9", monospaced details, product still, 3/4 lighting, 4k`

> [!example] Vitals
> `HUD audio widget, dark slate #0e1116, accent-green #00e676 outlined circular key with 2px ring, hairline bordered side plates, five needle-thin green stars, clinical instrument panel, flat lighting, 4k`

> [!example] Vinyl
> `editorial album player, charcoal #14120f, gold foil stars #e8c37a→#b3894a with engraved edges, embossed soft-square key, no button plates, restrained luxury print feel, 4k`

> [!example] Arcade
> `playful toy audio player, near-black #0b0a10, chunky candy-pink stars #ff5d8f→#a855f7, fat glossy key, thick glass plates, high bloom, sticker-like, 4k`

> [!example] Prism
> `aurora glass audio widget, midnight #0b1020, five stars filled with a violet-cyan-pink conical sweep #b388ff #22d3ee #f472b6, refractive glass plates, thin orbiting accent arc around the key, heavy bloom, 4k`

> [!example] Aurora
> `minimal audio widget, deep teal-black, five thin four-point sparkle stars filled green→cyan→violet #7df9d0 #38bdf8 #a78bfa, glass plates, orbiting accent arc around a filled key, soft northern-lights bloom, 4k`

> [!example] Ember
> `warm audio widget, near-black #100d0b, five sharp stars gold→orange→red #ffd08a #ff9147 #d92d20, hairline bordered side plates, soft-square key glowing ember-orange, subtle heat haze, 4k`

> [!example] Mono
> `monochrome audio widget, near-black, five faceted stars white→steel #ffffff→#8b95a5, glass plates, thin outlined ring key, no bloom, swiss instrumentation feel, 4k`

---

## 4. Control revamp

| Control | Now |
|---|---|
| Play / pause | **soft triangle / pill-pair** glyph: filled gradient key, inner top highlight, radial bloom (+45% on hover), 6% press squash, near-black glyph, optional orbiting arc for Prism/Aurora |
| Prev / next | **rounded chevron + pill bar** inside a glass plate with hover lift and accent wash |
| Rail (close, pin, pane, size, gear) | **new glyph family**: rounded X, pushpin with head/stem/baseline, split-pane frame with a lit panel, four-corner expand brackets, 8-tooth cog with a thinner ring |
| Dial utility dock | the five dial keys now sit in a **floating glass capsule** with a hairline border and top highlight; hover adds an accent plate, a radial glow and a 0.9 px lift; `pin` and `pane` show a **lit plate plus an accent dot** while active; hovering names the key in a small pill (`PIN` / `PANE` / `SETTINGS` / `SIZE` / `CLOSE`). Skins with `plate = none` (vinyl, ember) get a hairline rule instead of the capsule |
| Volume | spring-thickened rail, always-visible knob, accent halo when hot; a `volume` speaker+wave glyph ships for pairing |
| Seek | no numerals — full-width bar, buffered band, inch-proof knob, minute ticks |

Every glyph shares one optical weight — `max(1.1, s * 0.22)` stroke, round caps and
joins — so nothing looks heavier than its neighbours at 12 px.

---

## 5. Where the code lives

| Symbol | Role |
|---|---|
| `GADGET_SKINS` / `GADGET_SKIN_KEYS` | the eight treatments, as data |
| `_star_path()` | 5-point (or sparkle) geometry, inner radius per skin |
| `_star_brush()` | amber / accent / gold / candy / prism / aurora / ember / mono fills |
| `_paint_stars()` | stars, rank chip, hover preview, glow, playing sheen |
| `_refresh_rating()` / `_set_rating()` | mirror from the playlist, write-through on click |
| `_paint_key()` | filled gradient key, ring variant, orbit arc |
| `_paint_icon()` | the whole glyph family, incl. `volume` |
| `_compute_layout()` | card metrics: 30 px transport band, docked star row, per-star hits |
| `_compute_circle_layout()` | dial metrics: star row at −0.215R, dock at +0.205R; **owns** `_util_slots` = `(name, kind, hit_rect, glyph_rect)` |
| `_paint_seek()` | full-width bar + minute ticks, no time text |
| `gadget_skin_combo` | Settings → Skin picker (8 entries) |

---

## 6. Verification

| Check | Result |
|---|---|
| Hit routing resolves 0–4 on card and dial, miss returns `None` | pass |
| Click writes `song_profiles`, fires both save hooks; same-star click clears | pass |
| Rank math (rating 3 of `[5,5,4,4,3,3,2,1]` + own) → `#5/9` | pass |
| External profile change mirrored without a click | pass |
| Star row clear of seek/transport at S, M, L and 244×120 | pass |
| Dial: row inside the ring, clear of keys and the lifted utility cluster | pass |
| All **eight** skins render card + dial | pass |
| `state()` / `apply_state()` round-trip a skin, unknown keys ignored | pass |
| Headless full-app build: main window, SettingsWindow with **8** skin entries, `set_gadget_option('skin','prism')` applied | pass |
| **Every dock glyph is drawn at its own slot centre** (paint instrumented, not assumed) | pass |
| Click on the **painted** glyph fires: pin → `toggle_pin`, pane → `cycle_pane`, gear → settings, size → `cycle_size`, close → exit | pass |
| Near-miss 2 px below the glyph still fires (tiled targets, no dead gaps) | pass |
| `pin` really toggles always-on-top; `size` resizes the dial 372 → 440; `pane` changes the dial centre | pass |
| Star routing still resolves 0–4; star row clears the keys by 4.2 px; dock clears the keys | pass |
| Card rail still fires all five keys; card `cycle_size` still cycles S/M/L | pass |
| All eight skins render both shapes with the dock | pass |

**48/48 checks**, 0 failed, plus a headless end-to-end build of the real
`AudioPlayerPro` inside a sandboxed copy so no library or settings file was touched.

---

## 7. Open ends

- The rank chip needs ~135 px of row width, so the S card shows stars without a
  number. It can move under the artist instead if you want it there.
- `arcade`, `prism` and `aurora` bloom hard; they look best with `bg_mode = glass`
  over a busy wallpaper.
- A ninth skin is a one-line dict entry: `star`, `fill`, `glow`, `plate`, `key`,
  `chip`, `pop`, `orbit`.
- Card and dial time text are both gone by request. If the dial should keep a
  position readout, one `_fmt(self.position_ms)` call restores it.
- On the dial, `PANE` shows the visualizer as a strip inside the ring; `AUTO` and
  `ART` keep it hidden there, so the default dial look is unchanged.
- The dock's hover caption is deliberately small (9–11 px). If it reads as noise,
  delete the `if cap:` block in `_paint_circle` and the geometry is untouched.