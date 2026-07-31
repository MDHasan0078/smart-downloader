"""Bundled icon theme registration.

The app registers its own tiny icon theme ("simple-yt-downloader") as the
active icon theme for the whole application. That theme contains only the
icons the app uses directly; every other icon name inherits from whatever
theme the user has selected on the desktop. This makes the interface
independent of third-party icon themes (the original reason a Resume/Pause
control could render blank) while still following the user's icon styling
for everything else.

On a normal (deb) install the module lives under /usr/lib and is
read-only, and the active desktop theme is only known at runtime, so the
theme is materialised into the user cache directory with an index.theme
whose Inherits line points at the user's real icon theme.
"""

import os
import shutil
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

THEME_NAME = "simple-yt-downloader"

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SOURCE_THEME_DIR = os.path.join(_BASE_DIR, "icons", THEME_NAME)
_SOURCE_ACTIONS_DIR = os.path.join(_SOURCE_THEME_DIR, "scalable", "actions")


def _cache_themes_root():
    try:
        from gi.repository import GLib

        root = GLib.get_user_cache_dir()
    except Exception:
        root = os.path.expanduser("~/.cache")
    return os.path.join(root, "simple-yt-downloader", "icons")


def _sync_icon_files():
    actions_dir = os.path.join(_cache_themes_root(), THEME_NAME, "scalable", "actions")
    os.makedirs(actions_dir, exist_ok=True)
    for name in os.listdir(_SOURCE_ACTIONS_DIR):
        src = os.path.join(_SOURCE_ACTIONS_DIR, name)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(actions_dir, name)
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
            shutil.copy2(src, dst)


def _write_index_theme(inherits):
    theme_dir = os.path.join(_cache_themes_root(), THEME_NAME)
    os.makedirs(theme_dir, exist_ok=True)
    contents = (
        "[Icon Theme]\n"
        "Name=Simple YT Downloader\n"
        "Comment=Icons bundled with Simple YT Downloader\n"
        "Directories=scalable/actions\n"
        "Inherits={0}\n"
        "\n"
        "[scalable/actions]\n"
        "Size=16\n"
        "MinSize=8\n"
        "MaxSize=512\n"
        "Type=Scalable\n"
        "Context=Actions\n"
    ).format(inherits)
    with open(os.path.join(theme_dir, "index.theme"), "w") as fh:
        fh.write(contents)


_registered = False


def register_bundled_icons():
    """Makes the bundled icon theme the application's active icon theme.

    Safe to call more than once; never raises. On any failure the app
    simply falls back to whatever the desktop provides, so icon
    registration can never take the application down.
    """
    global _registered
    if _registered:
        return
    _registered = True

    try:
        settings = Gtk.Settings.get_default()
        if settings is None:
            return
        current_theme = settings.get_property("gtk-icon-theme-name") or "hicolor"

        _sync_icon_files()
        _write_index_theme(current_theme)

        theme = Gtk.IconTheme.get_default()
        paths = list(theme.get_search_path())
        themes_root = _cache_themes_root()
        if themes_root not in paths:
            theme.set_search_path([themes_root] + paths)

        settings.set_property("gtk-icon-theme-name", THEME_NAME)
    except Exception:
        sys.stderr.write(
            "simple-yt-downloader: warning: failed to register bundled icons\n"
        )
