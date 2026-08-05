"""Dependency detection for the downloader engine (cross-platform).

yt-dlp and ffmpeg/ffprobe are the external binaries the engine shells out to at
runtime. On desktop installs all three ship bundled next to the app; this module
reports presence/version so the UI can guide the user if they're missing.
"""

import shutil
import subprocess

CHECKED_BINARIES = ["yt-dlp", "ffmpeg", "ffprobe"]


def check_binary(name):
    """Return the resolved path if found on PATH, else None."""
    return shutil.which(name)


def check_all():
    """Return {binary_name: path_or_None} for every externally-shelled-out binary."""
    return {name: check_binary(name) for name in CHECKED_BINARIES}


def missing_binaries():
    return [name for name, path in check_all().items() if path is None]


def get_yt_dlp_version():
    path = check_binary("yt-dlp")
    if not path:
        return None
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"], capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None
