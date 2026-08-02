#!/usr/bin/env python3
import cairo
import math
import os
import sys

from gi.repository import Gdk, GdkPixbuf, Pango, PangoCairo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_DIR = os.path.join(ROOT, "icon-preview")
BUNDLE_DIR = os.path.join(ROOT, "simple_yt_downloader", "icons",
                          "simple-yt-downloader", "scalable", "actions")

NAMES = [
    "media-playback-start", "media-playback-pause", "media-record", "process-stop",
    "view-refresh", "pan-up", "pan-down", "window-close", "emblem-ok",
    "dialog-error", "folder", "folder-download", "emblem-system",
    "weather-clear", "weather-clear-night", "go-previous", "image-missing",
]


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


class Panel:
    def __init__(self, width, height, bg):
        self.surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
        self.ctx = cairo.Context(self.surface)
        self.ctx.set_source_rgb(*bg)
        self.ctx.paint()
        self.pc = PangoCairo.create_layout(self.ctx)
        self.layout = self.pc
        self.layout.set_font_description(
            Pango.FontDescription.from_string("sans 13"))

    def icon(self, pixbuf, x, y):
        Gdk.cairo_set_source_pixbuf(self.ctx, pixbuf, x, y)
        self.ctx.paint()

    def text(self, s, x, y, rgb, size=13, bold=False):
        fd = Pango.FontDescription.from_string("sans %d" % size)
        if bold:
            fd.set_weight(Pango.Weight.BOLD)
        self.layout.set_font_description(fd)
        self.layout.set_text(s)
        self.ctx.set_source_rgb(*rgb)
        self.ctx.move_to(x, y)
        PangoCairo.show_layout(self.ctx, self.layout)

    def save(self, path):
        self.surface.write_to_png(path)
        print("wrote %s" % path)


def hex_color(css):
    h = css.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


LIGHT_BG = (0xF6 / 255, 0xF5 / 255, 0xF4 / 255)
DARK_BG = (0x2E / 255, 0x34 / 255, 0x36 / 255)
LIGHT_FG = "#2e3436"
DARK_FG = "#fdfdfd"
LIGHT_TEXT = (0x44 / 255, 0x46 / 255, 0x49 / 255)
DARK_TEXT = (0xCC / 255, 0xCC / 255, 0xCC / 255)


def render_grid(out_path, bg, fg, text_rgb, caption):
    cols = 4
    cell_w, cell_h = 210, 88
    rows = math.ceil(len(NAMES) / cols)
    pad, header = 12, 46
    W = pad * 2 + cols * cell_w
    H = header + rows * cell_h + pad
    p = Panel(W, H, bg)
    p.text(caption, pad, 12, text_rgb, size=15, bold=True)
    p.text("16px", pad + 34, 26, text_rgb, size=11)
    for i, name in enumerate(NAMES):
        r, c = divmod(i, cols)
        cx = pad + c * cell_w + cell_w / 2
        y = header + r * cell_h
        icon = load_pixbuf(os.path.join(NEW_DIR, icon_filename(name)), 32, fg)
        small = load_pixbuf(os.path.join(NEW_DIR, icon_filename(name)), 16, fg)
        p.icon(icon, cx - 16, y + 6)
        p.icon(small, cx - 40, y + 46)
        p.text(name.replace("media-", "").replace("-symbolic", "")
               .replace("-", " "), cx - 40, y + 66, text_rgb, size=12)
    p.save(out_path)


def render_before_after(out_path, bg, fg, text_rgb):
    name_w, cell_w, cell_h = 150, 70, 62
    pad, header = 12, 46
    W = pad * 2 + name_w + cell_w * 2
    H = header + len(NAMES) * cell_h + pad
    p = Panel(W, H, bg)
    p.text("Before  vs  After (32px)", pad, 12, text_rgb, size=15, bold=True)
    old_x = pad + name_w + cell_w / 2
    new_x = old_x + cell_w
    p.text("old", old_x - 14, 30, text_rgb, size=11)
    p.text("new", new_x - 14, 30, text_rgb, size=11)
    for i, name in enumerate(NAMES):
        y = header + i * cell_h
        old_path = os.path.join(BUNDLE_DIR, icon_filename(name))
        new_path = os.path.join(NEW_DIR, icon_filename(name))
        if os.path.exists(old_path):
            old = load_pixbuf(old_path, 32, fg)
        else:
            old = None
        new = load_pixbuf(new_path, 32, fg)
        p.text(name.replace("media-", "").replace("-symbolic", "")
               .replace("-", " "), pad, y + 10, text_rgb, size=12, bold=False)
        if old is not None:
            p.icon(old, old_x - 16, y + 10)
        p.icon(new, new_x - 16, y + 10)
    p.save(out_path)


def main():
    out = os.path.join(NEW_DIR, "rendered")
    os.makedirs(out, exist_ok=True)
    render_grid(os.path.join(out, "preview_light.png"), LIGHT_BG, LIGHT_FG,
                LIGHT_TEXT, "simple-yt-downloader — redesigned (light)")
    render_grid(os.path.join(out, "preview_dark.png"), DARK_BG, DARK_FG,
                DARK_TEXT, "simple-yt-downloader — redesigned (dark)")
    render_before_after(os.path.join(out, "before_after.png"), LIGHT_BG,
                        LIGHT_FG, LIGHT_TEXT)


if __name__ == "__main__":
    main()
