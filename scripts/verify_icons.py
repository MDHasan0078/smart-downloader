#!/usr/bin/env python3
import os
import sys

from gi.repository import GdkPixbuf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE_DIR = os.path.join(ROOT, "simple_yt_downloader", "icons",
                          "simple-yt-downloader", "scalable", "actions")

NAMES = [
    "media-playback-start", "media-playback-pause", "media-record", "process-stop",
    "view-refresh", "pan-up", "pan-down", "window-close", "emblem-ok",
    "dialog-error", "folder", "folder-download", "emblem-system",
    "weather-clear", "weather-clear-night", "go-previous", "image-missing",
    "software-update-available",
]
THEMES = {"light": "#2e3436", "dark": "#fdfdfd", "accent": "#3584e4"}
SIZES = (16, 32)
# Icons with a hardcoded fill (no currentColor): expected fg color regardless
# of theme. image-missing deliberately uses a fixed gray so it stays visible
# on both light and dark backgrounds.
FIXED_COLORS = {"image-missing": "#8f8f8f"}


def icon_filename(name):
    if name == "image-missing":
        return name + ".svg"
    return name + "-symbolic.svg"


def load_pixbuf(path, size, color):
    with open(path, "r", encoding="utf-8") as fh:
        data = fh.read()
    if "currentColor" in data:
        data = data.replace("currentColor", color)
    loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
    loader.set_size(size, size)
    loader.write(data.encode("utf-8"))
    loader.close()
    return loader.get_pixbuf()


def fg_pixels(pixbuf, color):
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    px = pixbuf.get_pixels()
    row = pixbuf.get_rowstride()
    n = 0
    for y in range(pixbuf.get_height()):
        for x in range(pixbuf.get_width()):
            i = y * row + x * 3
            if (abs(px[i] - r) < 12 and abs(px[i + 1] - g) < 12
                    and abs(px[i + 2] - b) < 12):
                n += 1
    return n


def main():
    failures = 0
    for name in NAMES:
        path = os.path.join(BUNDLE_DIR, icon_filename(name))
        expected = FIXED_COLORS.get(name, None)
        for theme, color in THEMES.items():
            for size in SIZES:
                pb = load_pixbuf(path, size, color)
                n = fg_pixels(pb, expected or color)
                status = "ok" if n > 0 else "BLANK"
                if status == "BLANK":
                    failures += 1
                print("%-26s %-6s %2dpx  %5d fgpx  %s" %
                      (name, theme, size, n, status))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
