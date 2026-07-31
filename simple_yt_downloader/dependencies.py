"""Dependency detection and repair.

python3 / python3-gi / gir1.2-gtk-3.0 are not checked here: if any of those
were missing the app could not have started in the first place, so they're
reported as always-present static entries by the UI layer, not probed here.

yt-dlp and ffmpeg are the two external binaries the app actually shells out
to at runtime, so those are the ones worth live-checking.
"""

import shutil
import subprocess

CHECKED_BINARIES = ["yt-dlp", "ffmpeg"]


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


def install_missing(missing, on_done):
    """Install missing packages via apt using a GUI polkit prompt (pkexec).

    Runs synchronously in whatever thread calls it -- callers should invoke
    this from a background thread and marshal `on_done` back to the GTK main
    loop themselves (e.g. via GLib.idle_add).

    on_done is called with (success: bool, message: str).
    """
    if not missing:
        on_done(True, "Nothing to install.")
        return

    # Map binary names to the apt package that provides them.
    pkg_map = {"yt-dlp": "yt-dlp", "ffmpeg": "ffmpeg"}
    packages = [pkg_map[name] for name in missing if name in pkg_map]

    try:
        result = subprocess.run(
            ["pkexec", "apt-get", "install", "-y"] + packages,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            on_done(True, "Installed successfully: " + ", ".join(packages))
        else:
            err = (result.stderr or result.stdout or "Unknown error").strip()
            on_done(False, err[-500:])
    except subprocess.TimeoutExpired:
        on_done(False, "Installation timed out.")
    except FileNotFoundError:
        on_done(False, "pkexec is not available on this system.")
    except OSError as e:
        on_done(False, str(e))
