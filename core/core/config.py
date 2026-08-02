"""Persistent settings for the downloader engine (cross-platform).

Same flat-dict + load/save design as the GTK app's config, but the config
directory resolves per-platform:
  Windows: %APPDATA%/simple-yt-downloader
  macOS:   ~/Library/Application Support/simple-yt-downloader
  Linux:   ~/.config/simple-yt-downloader
"""

import json
import os
import sys

if sys.platform == "win32":
    _base = os.environ.get("APPDATA") or os.path.expanduser("~")
    CONFIG_DIR = os.path.join(_base, "simple-yt-downloader")
elif sys.platform == "darwin":
    CONFIG_DIR = os.path.join(
        os.path.expanduser("~"), "Library", "Application Support",
        "simple-yt-downloader",
    )
else:
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config",
                              "simple-yt-downloader")

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
    """Return saved settings merged over defaults (missing keys filled in)."""
    settings = dict(DEFAULTS)
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                settings.update(saved)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    _sanitize(settings)
    return settings


def _sanitize(settings):
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
