# Smart Downloader — engine core

Cross-platform download engine shared by the desktop clients (GTK Linux app,
future Flutter Windows/macOS apps).

The engine is a JSONL bridge: read one JSON command per line on stdin, emit
one JSON event per line on stdout. It wraps `yt-dlp` (+ `ffmpeg` for merges)
and contains no UI code, so it can be:

- driven by `python -m core.engine` during development, or
- frozen with PyInstaller into a single `engine` binary and driven by any
  client (Dart via `Process.start` included).

## Layout

    core/
      core/            the engine package (config, dependencies, download_task, engine)
      build/           PyInstaller specs per platform (linux/, windows/, macos/)
      pyproject.toml

## Protocol

Commands: `ping`, `check_deps`, `settings_get`, `settings_set`,
`get_info`, `start`, `pause`, `resume`, `cancel`, `restart`.

Events: `reply`, `progress`, `finished`, `error`.

See `core/engine.py` docstring for the full command/event reference.
