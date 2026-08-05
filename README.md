# Simple YT Downloader (GTK edition)

[![Latest release](https://img.shields.io/github/v/release/MDHasan0078/smart-downloader?label=latest)](https://github.com/MDHasan0078/smart-downloader/releases)

Smart Downloader — a fast, lightweight, open-source YouTube downloader.
Every quality from 144p to 10K, custom resolution support, selectable
30/60/90 fps, playlist support and pause/resume.

Single persistent window, no popup-dialog chains. Runs on Debian/Ubuntu-based
Linux distros (tested on Linux Mint).

## Features

- **Video or audio** downloads, per-download format and quality selection
- **Per-quality file size estimates** shown right in the dropdown
  (e.g. `720p (410.9 MB)`), for both video and audio
- **Paste multiple links at once** (space/comma/newline separated) —
  each downloads independently
- **Playlist support** — detects playlists automatically, shows every
  video in a scrollable list (not just the first few), with per-video
  progress
- **Pause / resume** any download mid-transfer, including videos still
  queued in a playlist (mark them "Held" before their turn even comes up)
- **Retry** a failed download without re-adding the link
- Downloads run in parallel; only the CPU-heavy merge/convert step is
  serialized to avoid ffmpeg conflicts when two videos finish at once
- **Ongoing / Completed** tabs (session-only) with a one-click "Clear All"
- Inline collapsible, auto-scrolling logs per download
- Settings: cookies file, default video/audio format & quality, Light/Dark
  theme, and a built-in dependency checker with a one-click "Fix
  Dependencies" button
- Download-folder picker pinned to the main window (defaults to
  `~/Downloads`)
- **Check for Updates** (Settings → About) — queries the GitHub releases API
  in the background and offers to **Download & Install** the latest version
  for your platform: `.deb` via `pkexec` on Linux, silent installer on
  Windows, `.dmg` → Applications (admin prompt) on macOS — the downloaded
  file is cleaned up afterwards — or open the release page instead

## Install

Download the latest `.deb` from
[Releases](https://github.com/MDHasan0078/smart-downloader/releases) and install it:

```bash
sudo dpkg -i simple-yt-downloader_*.deb
sudo apt install -f -y   # pulls in any missing dependencies
```

The latest release also ships **macOS** and **Windows** builds of the app
(see the release assets for the platform you're on).

### Dependencies

- `python3`, `python3-gi`, `gir1.2-gtk-3.0` (GTK3 + Python bindings)
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) — the actual download engine
- `ffmpeg` — required for merging video+audio streams and audio extraction
- `policykit-1` — used for the in-app "Fix Dependencies" installer prompt

These are declared in `packaging/control`'s `Depends:` line, so a normal
`dpkg -i` + `apt install -f` pulls in anything missing automatically.

## Running from source

```bash
git clone https://github.com/MDHasan0078/smart-downloader.git
cd smart-downloader
python3 run.py
```

Requires `python3-gi` and `gir1.2-gtk-3.0` installed on your system (there's
no pip package for GTK3 bindings — install via your distro's package
manager).

## Building the .deb yourself

```bash
./scripts/build_deb.sh
```

Produces `simple-yt-downloader_<version>_all.deb` in the repo root.

## Project structure

```
simple_yt_downloader/     the actual application (Python + GTK3)
  app.py                main window, headerbar, tabs, multi-URL add flow,
                         first-run flow, Light/Dark theme forcing
  row_widgets.py         VideoRow / PlaylistRow / the quality dropdown bar,
                         icon-fallback helpers, retry/hold/pause logic
  download_task.py       wraps a single yt-dlp subprocess: probing,
                          format-size estimation, download, pause/resume
                          (process-group signaling), merge serialization
  settings_view.py       the Settings screen (async dependency checking +
                         in-app "Check for Updates" against the GitHub API)
  dependencies.py        checks/installs yt-dlp + ffmpeg via pkexec
  config.py              settings persistence (~/.config/simple-yt-downloader)
  style.py                the app's CSS (rounded cards, accent color, etc.)
packaging/               .deb control file, postinst/postrm, desktop entry, icons
scripts/build_deb.sh     rebuilds the .deb from source
run.py                   dev entry point (no install needed)
```

## Notable implementation details

A few things that took real debugging to get right, worth knowing if you're
reading the source:

- **Pause/resume signals the whole process group**, not just the yt-dlp
  process. yt-dlp commonly hands work off to `ffmpeg` as a real child
  process (merging streams, or as an external downloader for some
  protocols) — signaling only the parent left that child running
  untouched. See `_signal_group()` in `download_task.py`.
- **Concurrent merge conflicts are prevented via a detect-and-gate
  approach**: the moment yt-dlp's output shows any postprocessor step
  starting (`[Merger]`, `[ExtractAudio]`, etc.), that process is frozen
  (same process-group SIGSTOP) until a global lock is free, then resumed.
  Actual downloading stays fully parallel; only the CPU-bound ffmpeg phase
  serializes.
- **Dark/Light theme forces `gtk-theme-name` to `"Adwaita"`** rather than
  just setting the "prefer dark" property. Linux Mint's default theme
  (Mint-Y) doesn't implement that property the way Adwaita does — Mint-Y
  and Mint-Y-Dark are two separate named themes, not one theme with a
  toggle.
- **The root `Gtk.Stack` has `hhomogeneous`/`vhomogeneous` set to `False`**,
  and Settings is wrapped in its own `Gtk.ScrolledWindow`. Without both of
  these, opening Settings (a tall screen) permanently inflates the whole
  window's size even after navigating back to the main view.
- **Dependency checks run on a background thread.** Checking yt-dlp's
  version means spawning a full Python interpreter as a subprocess — doing
  that synchronously during Settings' `__init__` blocked the screen from
  opening for a couple of seconds.

## Known limitations

- Playlists over 8 videos estimate total size from a sample of the first 8
  (scaled up), rather than querying every single video — shown with a `~`
  prefix.
- Audio quality sizes are estimated (`bitrate × duration`), since a file at
  an arbitrary target bitrate doesn't exist until it's actually encoded.
- Downloads within one playlist run sequentially, not concurrently — an
  intentional choice to avoid rate-limit risk.
- Tested primarily on Linux Mint (Cinnamon); should work on other
  GTK3-based Debian/Ubuntu desktops but unverified there.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) and
[ffmpeg](https://ffmpeg.org/). Not affiliated with YouTube.
