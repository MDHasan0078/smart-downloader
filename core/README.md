# Smart Downloader — engine core

Cross-platform download engine shared by the desktop clients (GTK Linux app,
future Flutter Windows/macOS apps).

The engine is a JSONL bridge: read one JSON command per line on stdin, emit
one JSON event per line on stdout. It wraps `yt-dlp` (+ `ffmpeg` for merges)
and contains no UI code, so it can be driven by any client (Dart via
`Process.start` included).

## Layout

    core/
      core-go/         the Go engine (main, engine, task, config, deps)
      core/            the Python engine package (used in-process by the GTK app)
      build/           dist output (engine binaries, ffmpeg)

## Build

    cd core-go && go build -o ../core/build/dist/engine/engine .

The engine prepends its own directory to PATH at startup, so the bundled
`yt-dlp`/`ffmpeg`/`ffprobe` resolve without installer PATH changes.

## Protocol

Commands: `ping`, `check_deps`, `settings_get`, `settings_set`,
`get_info`, `start`, `pause`, `resume`, `cancel`, `restart`.

Events: `reply`, `progress`, `finished`, `error`.

See `core-go/engine.go` for the command/event reference.
