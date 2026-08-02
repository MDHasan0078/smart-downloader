# V2 Plan: `smart-downloader` Flutter rewrite (Windows + macOS)

Status: **locked** — decision record, not a living spec.
Android is **dropped** (Chaquopy + ffmpeg-on-Android + scoped storage ruled out).

## Targets

| Platform | UI | Engine | Package | Build machine |
|---|---|---|---|---|
| Windows | Flutter (Dart) | PyInstaller `engine.exe` + bundled yt-dlp/ffmpeg | Inno Setup `.exe` | local (Linux) |
| macOS | same code | same as Windows | `.dmg` (ad-hoc signed) | GitHub Actions macOS runner (education plan) |

One UI codebase, one engine protocol, two near-identical desktop hosts.

## Monorepo layout (this repo, renamed `smart-downloader`)

```
├── simple_yt_downloader/      # existing GTK/Linux app (frozen at 1.0.0)
├── core/                      # Phase 1 — shared Python engine (pip pkg)
│   ├── pyproject.toml
│   ├── core/engine.py         #   JSONL stdin/stdout loop
│   ├── core/download_task.py  #   ported from simple_yt_downloader/
│   ├── core/config.py
│   ├── core/dependencies.py
│   └── build/{windows,macos}/engine.spec   # PyInstaller
├── app/                       # Phase 2 — Flutter project
│   ├── lib/src/
│   │   ├── engine/            #   Dart EngineClient
│   │   ├── models/
│   │   ├── screens/           #   home · queue · settings
│   │   ├── widgets/           #   download_row …
│   │   ├── theme/             #   light/dark/system
│   │   └── assets/icons/      #   ported 17 approved SVGs
│   ├── windows/  macos/  pubspec.yaml
├── .github/workflows/build-macos.yml   # Phase 4 — macOS .dmg CI
├── docs/  scripts/  icon-preview/
```

## Engine protocol (JSONL over stdin/stdout)

Commands in, events out. Same interface on both platforms — Android's
MethodChannel is gone; the two hosts differ only in *how* the process is
spawned (and even that is identical: `Process.start(engine, ...)`).

- `get_info {"url": ...}` → video/playlist metadata JSON
- `start {"url", "format", "quality", "dir", ...}` → streams progress events
  (`state`, `percent`, `speed`, `eta`, `filename`, `merge` phases)
- `pause` / `resume` / `cancel` / `restart` (SIGSTOP model from GTK app)
- `settings {get,set}` → load/save (Windows `%APPDATA%`, macOS
  `~/Library/Application Support`)
- `check_deps` → yt-dlp/ffmpeg presence + versions

## Phases

### Phase 0 — Spike (1–2 days) — Go/No-Go gate
- Flutter scaffold; PyInstaller `engine.exe` ↔ Dart `Process.start` JSONL
  round-trip returning real yt-dlp metadata for a known URL.
- Gate: metadata round-trips → proceed.

### Phase 1 — Engine package (`core/`, Python)
- Extract `download_task.py` / `config.py` / `dependencies.py` into the `core`
  pip package behind `engine.py`.
- Storage adapters per platform; drop `pkexec apt` (no-op on desktop installs).

### Phase 2 — Flutter UI (written once)
- Home (URL + options), Queue (progress/speed/ETA, pause/resume/cancel/
  restart, expandable logs), Settings (dir, quality defaults, theme, cookies).
- Port the 17 approved SVGs as tintable assets; native light/dark/system.

### Phase 3 — Queue state machine
- pending → downloading → paused → done/error; playlists; ffmpeg-merge
  progress; cookies.

### Phase 4 — Packaging ×2
- Windows: Inno Setup bundling engine + yt-dlp + ffmpeg.
- macOS: `.dmg` via GitHub Actions macOS runner (ad-hoc sign; notarization
  deferred until distribution decided).

### Phase 5 — QA + ship
- Real-download tests on both platforms.

## Risks (remaining)
- Dart learning curve.
- Unsigned Windows `.exe` → SmartScreen warning (deferred signing).
- macOS `.dmg` notarization deferred (fine for sideload).

## Decisions log
- 2026-08-03 — Android dropped (engine/storage/store-policy cost).
- 2026-08-03 — Flutter over Kivy/Qt/webview; single codebase.
- 2026-08-03 — Monorepo (no separate repo); GitHub repo renamed
  `MDHasan0078/simple-yt-downloader` → `MDHasan0078/smart-downloader`.
- 2026-08-03 — macOS built via GitHub Actions (no local Mac; education plan
  covers runner minutes).
