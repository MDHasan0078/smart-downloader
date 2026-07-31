"""Persistent settings for Simple YT Downloader (GTK3).

Settings live at ~/.config/simple-yt-downloader/config.json.
This is intentionally a flat dict + two functions (load/save) rather than a
class, since the whole app just needs simple get/set access to a handful of
values.
"""

import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/simple-yt-downloader")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "cookies_file": "",
    "use_cookies": False,
    "download_dir": os.path.expanduser("~/Downloads"),
    "default_video_format": "mp4",
    "default_video_quality": "720",
    "default_audio_format": "mp3",
    "default_audio_quality": "192",
    "theme": "system",  # "light" | "dark" | "system"
    "first_run_done": False,
}


def load():
    """Return the saved settings merged over defaults (missing keys filled in)."""
    settings = dict(DEFAULTS)
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            # Guard against a config that's valid JSON but not an object
            # (e.g. a hand-edited file containing a bare list or string).
            if isinstance(saved, dict):
                settings.update(saved)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            # Corrupt config file -- fall back to defaults rather than crashing.
            pass
    _sanitize(settings)
    return settings


def _sanitize(settings):
    """Coerce persisted values back onto their valid domains.

    The config file is user-editable, so a hand-typed value must not crash
    the UI later -- e.g. "theme": "blue" previously made Settings raise a
    KeyError, and an empty download_dir made DownloadTask call
    os.makedirs("") when starting a download.
    """
    if settings.get("theme") not in ("light", "dark", "system"):
        settings["theme"] = DEFAULTS["theme"]
    if not isinstance(settings.get("download_dir"), str) or not settings["download_dir"].strip():
        settings["download_dir"] = DEFAULTS["download_dir"]
    for key in ("use_cookies", "first_run_done"):
        if not isinstance(settings.get(key), bool):
            settings[key] = DEFAULTS[key]
    for key in (
        "cookies_file", "default_video_format", "default_video_quality",
        "default_audio_format", "default_audio_quality",
    ):
        if not isinstance(settings.get(key), str):
            settings[key] = DEFAULTS[key]


def save(settings):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=2)
