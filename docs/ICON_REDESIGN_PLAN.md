# Implementation Plan: Redesign of the 17 Bundled Symbolic Icons

Status: PLANNING (no code or icon files changed yet)
Scope: `simple_yt_downloader/icons/simple-yt-downloader/scalable/actions/*.svg` only,
       plus one optional 1-line fallback-glyph tweak in `row_widgets.py`.
Out of scope: `icons.py` mechanics, `index.theme`, app behaviour.

---

## 1. Recommended design direction: **A — hand-drawn refinement to match Adwaita/WhiteSur geometry**

**Why A over B (copy files) and C (mixed):**

1. **The app already targets this style.** The app forces the Adwaita *widget* theme
   (`app.py::_apply_theme`) and the bundled theme's rewritten `Inherits` points at the
   user's real icon theme (WhiteSur-dark on this machine). Both Adwaita and WhiteSur-dark
   symbolic icon sets use the same geometric language. Matching that language is what
   "professional and native to the GTK3/Linux desktop" means here.
2. **License.** The project is MIT ("MIT-clean" was a deliberate choice). Adwaita's icon
   theme is LGPL-2.1+ and WhiteSur's is GPL-family (neither ships a COPYING in the
   installed tree, so verify before any copying). Verbatim copying (direction B) would
   contaminate the bundle. Simple geometric shapes (triangles, circles, chevrons,
   X marks) are not copyrightable expression — matching anchor points/sizes while
   authoring our own path data is the standard clean-room practice and keeps MIT-clean.
   Direction A is effectively "clean-room re-derivation of the reference geometry".
3. **Scope control.** A is a pure aesthetic swap of 17 small files; C adds nothing over A.

**Reference geometry source of truth** (read from this machine):
- Adwaita: `/usr/share/icons/Adwaita/symbolic/{actions,ui,status,emblems,places}/*.svg`
- WhiteSur-dark: `~/.local/share/icons/WhiteSur-dark/{actions,status,emblems,places}/symbolic/*.svg`

**Shared conventions for every new file (constraints):**
- `viewBox="0 0 16 16"`, `width="16" height="16"`.
- Fill/stroke only with `fill="currentColor"` and/or `stroke="currentColor"`; the single
  exception is `image-missing.svg` (fixed `#8f8f8f`, see §3).
- No `<style>`, no CSS classes, no gradients, no filters, no `enable-background`,
  no `<defs>`. Inline attributes only (portable across librsvg versions; WhiteSur's
  `.ColorScheme-Text` trick is exactly what we do **not** replicate).
- Coordinates on the 0.5px grid where possible; stroke widths 1.1–2.2; round caps/joins
  on all strokes; no sub-pixel noise at 16px.
- **Biggest single change: adopt the reference *footprint*.** Current icons carry
  1–3px margins and look small/floaty. Adwaita/WhiteSur symbols bleed to ~14–16px of the
  glyph box. Every "fuller" spec below exists to fix the "small, cheap" look.

---

## 2. Per-icon specification (17 files)

Legend: **[FIX]** full replacement · **[POLISH]** minor tweak · **[KEEP]** as-is.
Exact path data is given; run the §4 visual gate before shipping, small ±0.5px nudges
after eyeballing are expected and welcome.

### 1. media-playback-start-symbolic.svg — **[FIX]** ← the icon the user complained about
Current: `M4.5 3.1 L13.5 8 L4.5 12.9 Z` — squat, base too close to centre.
Adwaita footprint: base x=2, y 2.5→13.5, apex (11.8,8). WhiteSur footprint:
base x≈5.17, y 2.66→13.34, apex (13.5,8). Target the WhiteSur footprint (user's desktop):
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="currentColor" d="M5 2.5 L13.5 8 L5 13.5 Z"/></svg>
```
Taller (11px vs 9.8px), apex anchored at the right edge, base pulled to x=5. Sharp
corners, matching both references. This is the single most visible fix.

### 2. media-playback-pause-symbolic.svg — **[FIX]**
Current bars 2.4px wide, y 3.2→12.8 (small). Adwaita: w=3, x 3–6 & 10–13, y≈1–15.
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><rect x="3" y="2" width="3" height="12" rx="1" fill="currentColor"/><rect x="10" y="2" width="3" height="12" rx="1" fill="currentColor"/></svg>
```

### 3. media-record-symbolic.svg — **[KEEP]**
Current `circle r=5` at (8,8) is byte-identical in footprint to WhiteSur's record icon.
No change.

### 4. process-stop-symbolic.svg — **[FIX]** (semantic change: square → X)
Used for `cancel_btn` ("Cancel playlist", row_widgets.py:488) and the `cancelled`
status badge (row_widgets.py:707) — i.e. **cancel**, not media-stop. Adwaita's
process-stop is an X; WhiteSur's is a circle+X. The X reads "cancelled" natively.
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="M4.8 4.8 L11.2 11.2 M11.2 4.8 L4.8 11.2"/></svg>
```
Corollary (in scope): update the fallback glyph in `row_widgets.py:41` from `"■"` to
`"✕"` so the unicode fallback matches the new glyph.
Alternative (flag): if a media-"stop" square is preferred, keep the rounded square but
enlarge to `x=3 y=3 w=10 h=10 rx=2`. The X is recommended on semantics.

### 5. view-refresh-symbolic.svg — **[FIX]** (rev2 — Adwaita port)
Hand-built arc + corner arrow replaced with Adwaita's battle-tested circular refresh
loop (open arc + built-in arrowhead), fill → `currentColor`:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="currentColor" d="m 7.40625 1 c -0.613281 0.007812 -1.234375 0.089844 -1.847656 0.253906 c -3.273438 0.878906 -5.558594 3.855469 -5.558594 7.246094 s 2.285156 6.367188 5.558594 7.242188 c 3.273437 0.878906 6.742187 -0.558594 8.4375 -3.492188 c 0.277344 -0.480469 0.109375 -1.089844 -0.367188 -1.367188 c -0.476562 -0.273437 -1.089844 -0.109374 -1.367187 0.367188 c -1.246094 2.160156 -3.777344 3.207031 -6.1875 2.5625 c -2.40625 -0.644531 -4.074219 -2.820312 -4.074219 -5.3125 c 0 -2.496094 1.667969 -4.667969 4.074219 -5.3125 c 2.410156 -0.644531 4.941406 0.402344 6.1875 2.5625 c 0.058593 0.085938 0.125 0.164062 0.203125 0.226562 l -0.019532 0.015626 l -0.007812 0.007812 h -1.4375 c -0.550781 0 -1 0.449219 -1 1 c 0 0 0 1 1 1 h 5 v -5 s 0.003906 -1 -1 -1 c -0.550781 0 -1 0.449219 -1 1 v 1.6875 l -0.015625 0.011719 l -0.011719 0.011719 c -1.277344 -2.179688 -3.53125 -3.519532 -5.953125 -3.691407 c -0.203125 -0.015625 -0.40625 -0.019531 -0.613281 -0.019531 z m 0 0"/></svg>
```
(Same geometry the system theme already renders for refresh buttons.)

### 6./7. pan-up-symbolic.svg / pan-down-symbolic.svg — **[FIX]** (rev4 — smooth "V"/caret chevron)
Used for expand/collapse (row_widgets.py:436, 621) and "Show logs"
(row_widgets.py:265). Filled triangles (both Adwaita's and WhiteSur's) were
rejected — user wants a **"V"-shaped dropdown caret with smooth edges**: a
stroke chevron with round linecap/linejoin, stroke → `currentColor`:
```xml
<!-- pan-up-symbolic.svg -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="M3.5 10.5 L8 5.5 L12.5 10.5"/></svg>
<!-- pan-down-symbolic.svg -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="M3.5 5.5 L8 10.5 L12.5 5.5"/></svg>
```

### 8. window-close-symbolic.svg — **[KEEP]**
Current two 1.8px strokes `M4 4 L12 12 M12 4 L4 12` already match WhiteSur's
stroke-width ≈1.91 close glyph. Optional zero-risk polish: add `stroke-linejoin="round"`.
No functional change.

### 9. emblem-ok-symbolic.svg — **[POLISH]**
Current stroke check already matches the WhiteSur footprint. Nudge endpoints onto the
WhiteSur anchors and keep round caps/joins:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" d="M3.8 8.2 L6.7 11 L12.2 5.5"/></svg>
```

### 10. dialog-error-symbolic.svg — **[KEEP]**
Circle r=6 + vertical bar + dot = the "!" convention that WhiteSur uses (WhiteSur:
circle ring + bar x 7–9 y 4–9 + dot r=1 at (8,11); Adwaita uses a dash, but WhiteSur is
the user's desktop, and "!" is the clearer error mark). Current geometry is already
faithful. Optional ±0.3px r nudge; otherwise unchanged.

### 11. folder-symbolic.svg — **[FIX]**
Current folder (x 2–14, y 4.5–12, shallow tab) is the main "small/floaty" offender.
Reference folders are full-bleed (WhiteSur: x 0–16, tab peak y=2, body top y=4,
bottom y=15). Fuller, angular folder with the same tab+body construction as today:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="currentColor" d="M1.5 3.5 h4.2 l1.5 1.8 H14.5 V12.8 H1.5 Z"/></svg>
```
(x 1.5–14.5, tab peak y=3.5, body top y=5.3, bottom y=12.8.)

### 12. folder-download-symbolic.svg — **[FIX]** (folder geometry only; arrow kept)
Used for the download-folder picker (settings_view.py:147) and the empty-state
(app.py:191, at DIALOG 48px). **Deliberately diverges from WhiteSur**, whose
folder-download is a circle+down-arrow: the app's context is "the folder downloads go
into", so folder+arrow is the clearer metaphor. Keep the current arrow, sit it in the
new fuller folder:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" fill="currentColor" d="M1.5 3.5 h4.2 l1.5 1.8 H14.5 V12.8 H1.5 Z M7.5 7 h1 v3 h-1 Z M8 11.4 L6.3 9.6 h3.4 Z"/></svg>
```
Note the evenodd is not needed (sub-shapes don't overlap); a plain `fill="currentColor"`
is fine. Alternative flagged: adopt WhiteSur's circle+arrow for pure consistency.

### 13. emblem-system-symbolic.svg — **[FIX]** (rev3 — Adwaita port, differentiated from sun)
Hand-built gears read like the sun at small sizes. Use Adwaita's battle-tested 8-tooth
gear path verbatim (chunky teeth + open center), fill → `currentColor`:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="currentColor" d="m 8 0 c -0.550781 0 -1 0.449219 -1 1 v 0.238281 c 0 0.464844 -0.378906 0.902344 -0.820312 1.046875 c -0.023438 0.007813 -0.042969 0.011719 -0.0625 0.019532 c -0.445313 0.148437 -1.007813 0.015624 -1.28125 -0.359376 l -0.140626 -0.195312 c -0.15625 -0.214844 -0.390624 -0.359375 -0.652343 -0.398438 c -0.261719 -0.042968 -0.53125 0.019532 -0.742188 0.175782 c -0.449219 0.324218 -0.550781 0.949218 -0.222656 1.398437 l 0.140625 0.199219 c 0.277344 0.375 0.226562 0.953125 -0.050781 1.328125 c -0.011719 0.015625 -0.023438 0.035156 -0.035157 0.050781 c -0.273437 0.378906 -0.804687 0.601563 -1.25 0.457032 l -0.230468 -0.074219 c -0.523438 -0.171875 -1.089844 0.117187 -1.257813 0.640625 c -0.171875 0.527344 0.113281 1.089844 0.640625 1.261718 l 0.222656 0.074219 c 0.445313 0.144531 0.738282 0.636719 0.75 1.101563 v 0.070312 c 0.015626 0.464844 -0.304687 0.960938 -0.746093 1.105469 l -0.226563 0.070313 c -0.527344 0.171874 -0.8125 0.738281 -0.640625 1.261718 c 0.167969 0.523438 0.734375 0.8125 1.257813 0.640625 l 0.230468 -0.074219 c 0.445313 -0.144531 0.976563 0.078126 1.25 0.457032 c 0.011719 0.015625 0.027344 0.035156 0.039063 0.050781 c 0.277344 0.375 0.324219 0.953125 0.050781 1.328125 l -0.144531 0.203125 c -0.324219 0.445313 -0.226563 1.070313 0.222656 1.394531 c 0.445313 0.324219 1.070313 0.226563 1.394531 -0.21875 l 0.144532 -0.199218 c 0.273437 -0.378907 0.835937 -0.507813 1.277344 -0.359376 c 0.019531 0.007813 0.042968 0.011719 0.0625 0.019532 c 0.445312 0.140625 0.820312 0.578125 0.820312 1.046875 v 0.238281 c 0 0.550781 0.449219 1 1 1 s 1 -0.449219 1 -1 v -0.238281 c 0 -0.46875 0.378906 -0.90625 0.820312 -1.046875 c 0.023438 -0.007813 0.042969 -0.015625 0.066407 -0.023438 c 0.441406 -0.144531 1.003906 -0.015625 1.277343 0.363282 l 0.144532 0.199218 c 0.324218 0.445313 0.949218 0.542969 1.394531 0.21875 c 0.445313 -0.324218 0.546875 -0.949218 0.222656 -1.394531 l -0.148437 -0.203125 c -0.273438 -0.375 -0.226563 -0.953125 0.050781 -1.328125 c 0.015625 -0.015625 0.027344 -0.035156 0.039063 -0.050781 c 0.273437 -0.378906 0.804687 -0.601563 1.25 -0.457032 l 0.234374 0.078126 c 0.523438 0.167968 1.085938 -0.121094 1.257813 -0.644532 c 0.171875 -0.523437 -0.117187 -1.089844 -0.640625 -1.257812 l -0.230469 -0.074219 c -0.445312 -0.144531 -0.734375 -0.640625 -0.746093 -1.105469 c 0 -0.023437 0 -0.046875 0 -0.070312 c -0.015626 -0.464844 0.300781 -0.957032 0.746093 -1.101563 l 0.230469 -0.074219 c 0.523438 -0.171874 0.8125 -0.734374 0.640625 -1.261718 c -0.171875 -0.523438 -0.734375 -0.8125 -1.257813 -0.640625 l -0.230468 0.074219 c -0.445313 0.144531 -0.980469 -0.078126 -1.253906 -0.457032 c -0.011719 -0.015625 -0.023438 -0.035156 -0.035157 -0.050781 c -0.277343 -0.375 -0.324219 -0.953125 -0.050781 -1.328125 l 0.144531 -0.199219 c 0.324219 -0.445312 0.226563 -1.074219 -0.222656 -1.398437 c -0.214844 -0.15625 -0.480469 -0.21875 -0.742187 -0.179688 c -0.265626 0.042969 -0.5 0.1875 -0.652344 0.402344 l -0.144532 0.195312 c -0.273437 0.378907 -0.835937 0.507813 -1.28125 0.363282 c -0.019531 -0.007813 -0.039062 -0.015625 -0.0625 -0.023438 c -0.441406 -0.140625 -0.820312 -0.578125 -0.820312 -1.046875 v -0.238281 c 0 -0.550781 -0.449219 -1 -1 -1 z m 0 4 c 0.871094 0 1.675781 0.273438 2.332031 0.742188 c 0.003907 0.007812 0.011719 0.015624 0.019531 0.023437 c 0.011719 0.003906 0.019532 0.007813 0.03125 0.015625 c 0.660157 0.484375 1.160157 1.171875 1.421876 1.976562 v 0.007813 s 0.003906 0.003906 0.003906 0.007813 c 0.292968 0.851562 0.15625 1.65625 0 2.457031 c 0 0 -0.003906 0.003906 -0.003906 0.007812 v 0.003907 c -0.261719 0.800781 -0.757813 1.488281 -1.414063 1.976562 c -0.015625 0.003906 -0.027344 0.011719 -0.039063 0.019531 c -0.007812 0.003907 -0.015624 0.011719 -0.019531 0.019531 c -0.65625 0.46875 -1.460937 0.742188 -2.332031 0.742188 c -0.855469 0 -1.644531 -0.265625 -2.289062 -0.714844 c -0.019532 -0.015625 -0.042969 -0.035156 -0.0625 -0.046875 c -0.011719 -0.007812 -0.023438 -0.015625 -0.035157 -0.019531 c -0.652343 -0.484375 -1.148437 -1.160156 -1.40625 -1.945312 c -0.003906 -0.015626 -0.007812 -0.023438 -0.011719 -0.035157 c -0.003906 -0.007812 -0.007812 -0.015625 -0.011718 -0.019531 c -0.285156 -0.847656 -0.148438 -1.644531 0 -2.4375 c 0.003906 -0.007812 0.007812 -0.011719 0.011718 -0.019531 c 0.003907 -0.011719 0.007813 -0.023438 0.011719 -0.039063 c 0.261719 -0.785156 0.757813 -1.460937 1.414063 -1.945312 c 0.007812 -0.003906 0.019531 -0.007813 0.027344 -0.015625 c 0.019531 -0.011719 0.042968 -0.03125 0.058593 -0.046875 c 0.648438 -0.449219 1.4375 -0.714844 2.292969 -0.714844 z m 0 0"/></svg>
```
(Same geometry the system theme already renders for the settings gear; empty center.)

### 14. weather-clear-symbolic.svg — **[POLISH]**
Current (disk r=3 + 8 stroke rays) already matches the WhiteSur construction. Align ray
extents to WhiteSur's (rays from r≈4.4 to r≈6.9, i.e. y 1.1–3.6), stroke 1.5 round caps:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="8" r="3" fill="currentColor"/><g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M8 1.1 v2.5 M8 12.4 v2.5 M1.1 8 h2.5 M12.4 8 h2.5 M3.1 3.1 l1.8 1.8 M12.9 3.1 l-1.8 1.8 M12.9 12.9 l-1.8 -1.8 M3.1 12.9 l1.8 -1.8"/></g></svg>
```

### 15. weather-clear-night-symbolic.svg — **[FIX]** (rev3 — Adwaita port)
Both hand-built crescents (two-arc fill, then evenodd two-circle) read poorly. Use
Adwaita's battle-tested moon path verbatim (two-crescent construction), fill →
`currentColor`:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="currentColor" d="m 0.917969 8.003906 c 0 3.914063 3.164062 7.078125 7.078125 7.078125 c 3.605468 -0.007812 6.617187 -2.703125 7.023437 -6.285156 c 0.042969 -0.378906 -0.136719 -0.75 -0.457031 -0.957031 c -0.324219 -0.203125 -0.738281 -0.207032 -1.0625 -0.003906 c -0.609375 0.375 -1.316406 0.578124 -2.03125 0.578124 c -2.140625 0 -3.882812 -1.742187 -3.882812 -3.882812 c 0 -0.714844 0.203124 -1.421875 0.578124 -2.03125 c 0.203126 -0.324219 0.199219 -0.738281 -0.003906 -1.0625 c -0.207031 -0.320312 -0.578125 -0.5 -0.957031 -0.457031 c -3.582031 0.40625 -6.277344 3.417969 -6.285156 7.023437 z m 4.667969 -3.472656 c 0 3.253906 2.628906 5.882812 5.886718 5.882812 c 1.085938 0 2.152344 -0.304687 3.078125 -0.878906 l -1.519531 -0.960937 c -0.289062 2.554687 -2.464844 4.503906 -5.035156 4.507812 c -2.796875 0 -5.078125 -2.28125 -5.078125 -5.078125 c 0.003906 -2.570312 1.953125 -4.746094 4.507812 -5.035156 l -0.960937 -1.519531 c -0.574219 0.925781 -0.875 1.992187 -0.878906 3.082031 z"/></svg>
```
(Same crescent the system theme already renders everywhere; identical geometry, just
`currentColor` instead of the fixed `#222222`.)

### 16. go-previous-symbolic.svg — **[FIX]** (drop the tail)
Used for the settings back button (settings_view.py:46). Current = chevron **plus a
horizontal tail** (reads as rewind). WhiteSur's go-previous is a pure two-segment
chevron; that is the native back affordance:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" d="M10.2 2.5 L4.6 8 L10.2 13.5"/></svg>
```

### 17. image-missing.svg — **[FIX]** (see §3; name unchanged)
Replace the current frame + mountain + two X marks (the X's read as harsh) with the
Adwaita "broken picture" motif — frame with a notched corner + small sun + mountain —
hand-authored, fixed `#8f8f8f`:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill="none" stroke="#8f8f8f" stroke-width="1.3" stroke-linejoin="round" d="M6.5 3.2 H13 a1 1 0 0 1 1 1 v7.6 a1 1 0 0 1 -1 1 H3 a1 1 0 0 1 -1 -1 v-6.1 a1 1 0 0 1 1 -1 h2.5 Z"/><circle cx="11" cy="5.4" r="1" fill="#8f8f8f"/><path fill="#8f8f8f" d="M3.2 11.8 l2.6 -2.7 l1.7 1.7 l2.2 -2.2 l2.6 3.2 Z"/></svg>
```
Frame has the broken top-left corner (path starts at x=6.5 on the top edge — the notch),
a sun dot top-right, a filled mountain along the bottom. **Keep the fixed mid-gray** —
it is readable on both light and dark thumbnails; Adwaita itself ships
`image-missing-symbolic` with a fixed gray (35% opacity), i.e. even upstream does not
recolor it.

---

## 3. image-missing naming decision: **stay non-symbolic, keep fixed gray — no code edits**

Weighed:
- **Rename to image-missing-symbolic + currentColor** would make GTK3 recolor it with
  the theme fg — but at full opacity a placeholder would shout; Adwaita's intent is a
  *subdued* placeholder, and controlling that via GTK3's recolor is unreliable (opacity
  handling is implementation-detail). It would also force edits at 4 reference sites +
  the fallback-key entry for zero visual gain.
- **Stay as-is (non-symbolic, fixed #8f8f8f)**: matches Adwaita's actual shipped
  behaviour, reads on light and dark, zero code churn. ✅ **Recommended.**

Exact reference sites that would need editing *only if* we renamed (recorded for
completeness, not to be touched):
- `simple_yt_downloader/row_widgets.py:89` (fallback in `_set_image_icon`)
- `simple_yt_downloader/row_widgets.py:54` (fallback glyph map key)
- `simple_yt_downloader/app.py:252` (empty-state fallback)
- `simple_yt_downloader/settings_view.py:149` (about-card fallback)
- bundle file rename `image-missing.svg` → `image-missing-symbolic.svg`

---

## 4. Verification plan

### 4a. Automated pixel-count render test (3 theme states, must still pass)
New script `scripts/verify_icons.py` (PyGObject, headless-safe), run after editing:
1. Register the bundled theme exactly like the app: `_sync_icon_files()` +
   `_write_index_theme(<current theme>)` (import from `simple_yt_downloader.icons`,
   or copy the 15 lines) so icons resolve from the cache.
2. For each of the 17 names, for each state —
   `light`: icon theme `Adwaita`, symbolic fg light;
   `dark`: icon theme `Adwaita-dark`, symbolic fg light;
   `system`: icon theme `WhiteSur-dark` (the rewritten Inherits target) —
   `Gtk.IconTheme.lookup_icon(name, size, 0)` at sizes **16 and 48**, load symbolic,
   render to pixbuf, assert **non-transparent pixel count > 0**.
3. Exit non-zero on any failure. This mirrors the prior manual verification
   ("visible pixel counts > 0 in Adwaita-light/Adwaita-dark/WhiteSur-dark").

### 4b. Human-reviewable screenshot grid (the AI cannot judge aesthetics — a human must)
Same script additionally renders **all 17 icons at 16px and 32px** in a labeled grid on
a neutral background, twice — light panel (`#f6f5f4`) and dark panel (`#2e3436`) — and
writes:
- `/tmp/syt_icon_grid_light.png`
- `/tmp/syt_icon_grid_dark.png`
Use `Gtk.Image` widgets shown in a real `Gtk.Window` + `Gdk.pixbuf_get_from_window` when
a display is available (true-to-app rendering including symbolic recoloring); fall back
to direct pixbuf composition otherwise. The user opens the PNGs and gives the visual
verdict; any icon can then be nudged (expect ±0.5px tweaks) and re-graded.

---

## 5. Build / reinstall / commit strategy

1. `git checkout dev` (last commit `e692dbc` — both branches at the same point; work on
   `dev` per the repo's established workflow).
2. Replace the 17 SVGs with the §2 content. If process-stop becomes the X, also change
   `row_widgets.py:41` fallback glyph `"■"` → `"✕"`. Nothing else.
3. Run §4a; visually grade §4b; iterate on any flagged icon.
4. `scripts/build_deb.sh`, then `pkexec dpkg -i simple-yt-downloader_*.deb` (close the
   running app first). The cache at `~/.cache/simple-yt-downloader/icons/` re-syncs
   automatically on next launch: `_sync_icon_files` copies by **size mismatch**, and the
   new files have different sizes. No manual cache clearing.
5. Commit on `dev` (message style: e.g. `Redesign bundled symbolic icons to match Adwaita/WhiteSur geometry`), **wait for user approval**, then merge `dev` → `main`.

---

## 6. Risks / tradeoffs

- **License (primary).** Recommended plan keeps the bundle MIT-clean (hand-authored
  paths; matching simple geometric shapes is not copyrightable). If anyone later decides
  to verbatim-copy Adwaita (LGPL-2.1+) or WhiteSur (GPL-family) files, that changes the
  bundle's licensing story — do not do it without an explicit decision. (Neither theme
  ships a COPYING in the installed tree; verify upstream before relying on it.)
- **process-stop semantics (square → X).** Deliberate: the app uses this icon for
  *cancel*. If the user prefers a media-stop square, revert to the enlarged rounded
  square and keep the `"■"` fallback glyph.
- **Full-bleed footprints.** Some icons (folder, pause, play) grow noticeably. That is
  the point (matches the desktop), but it is the most likely thing to feel "too big" —
  the §4b grid is the gate; dial margins ±0.5px there.
- **16px crispness.** Hand-authored paths can introduce sub-pixel jaggies; mitigated by
  0.5px-grid coordinates, ≥1.1px strokes, round caps/joins, and the visual gate.
- **folder-download divergence.** Deliberately keeps folder+arrow instead of WhiteSur's
  circle+arrow (semantic clarity); flagged as an alternative.
- **No functional risk.** Icon lookup, theme registration, and rendering paths are
  untouched; the pixel-count test re-verifies all 17 resolve in all 3 theme states.
