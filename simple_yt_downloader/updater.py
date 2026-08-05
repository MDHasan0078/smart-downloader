"""Self-update support for the Linux GTK app.

The app never checks for updates on its own -- the whole flow starts from
the user clicking "Check for Updates" in Settings. This module only handles
the mechanics: finding the right .deb asset in a GitHub release, downloading
it to the user cache, installing it via a polkit password prompt, and
cleaning the downloaded file up afterwards.

All network/privileged work runs on a background thread; the caller is
responsible for marshaling callbacks back to the GTK main loop (GLib.idle_add).
"""

import json
import os
import subprocess
import urllib.error
import urllib.request

REPO = "MDHasan0078/smart-downloader"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_DOWNLOAD_BASE = f"https://github.com/{REPO}/releases/download"
USER_AGENT = "simple-yt-downloader"

DEB_PREFIX = "simple-yt-downloader"
DEB_SUFFIX = "_all.deb"


class DownloadError(Exception):
    pass


class DownloadAborted(DownloadError):
    pass


def cache_dir():
    """User-writable cache dir for downloaded .deb files."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    path = os.path.join(base, "simple-yt-downloader")
    os.makedirs(path, exist_ok=True)
    return path


def deb_path(version):
    """Absolute cache path for the given version's .deb."""
    return os.path.join(cache_dir(), f"{DEB_PREFIX}_{version}{DEB_SUFFIX}")


def version_tuple(version):
    """Parse '2.1.0' (or '2.1', '2.1.0-1') into (2, 1, 0) for comparison."""
    parts = []
    for part in str(version).split("."):
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def fetch_latest_release():
    """Query the GitHub API for the latest release.

    Returns {"version", "release_url", "deb_url"} or None on any failure.
    deb_url is always populated: if the API's asset list is missing or the
    API is rate-limited, it falls back to the deterministic
    releases/download URL, which is served from GitHub's CDN and is not
    subject to the API rate limit.
    """
    try:
        request = urllib.request.Request(
            RELEASE_API,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                return None
            data = json.loads(response.read().decode("utf-8"))
        version = str(data.get("tag_name", "")).lstrip("v")
        if not version:
            return None
        return {
            "version": version,
            "release_url": data.get("html_url")
            or f"{RELEASE_DOWNLOAD_BASE}/v{version}",
            "deb_url": find_deb_asset(version, data),
        }
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None


def find_deb_asset(version, release_json):
    """Return the browser_download_url of the .deb asset, or the
    deterministic CDN URL as a fallback if the asset isn't listed."""
    expected = f"{DEB_PREFIX}_{version}{DEB_SUFFIX}"
    for asset in release_json.get("assets") or []:
        if asset.get("name") == expected:
            url = asset.get("browser_download_url")
            if url:
                return url
    return f"{RELEASE_DOWNLOAD_BASE}/v{version}/{expected}"


def download(url, dest, on_progress, abort_event=None):
    """Stream `url` to `dest`, calling on_progress(downloaded, total) as
    data arrives (total may be None if there's no Content-Length).

    Returns dest on success. Raises DownloadAborted if abort_event is set,
    DownloadError for HTTP/network failures. A partial file is written as
    `<dest>.part` and removed on failure, so the caller only ever sees
    either a complete dest or no leftover temp file.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest + ".part"
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw_total = response.headers.get("Content-Length")
            total = int(raw_total) if raw_total and raw_total.isdigit() else None
            downloaded = 0
            with open(tmp, "wb") as f:
                while True:
                    if abort_event is not None and abort_event.is_set():
                        raise DownloadAborted()
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if abort_event is not None and abort_event.is_set():
                        raise DownloadAborted()
                    on_progress(downloaded, total)
        os.replace(tmp, dest)
        return dest
    except DownloadAborted:
        raise
    except (urllib.error.URLError, OSError) as e:
        raise DownloadError(str(e)) from e
    finally:
        if not os.path.exists(dest) and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def install(path, on_done):
    """Install a .deb via pkexec (native polkit password prompt).

    Runs synchronously in whatever thread calls it -- callers should invoke
    this from a background thread and marshal `on_done` back to the GTK
    main loop themselves (e.g. via GLib.idle_add).

    on_done(success: bool, message: str) is invoked exactly once.
    """
    try:
        result = subprocess.run(
            ["pkexec", "apt-get", "install", "-y", os.path.abspath(path)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            on_done(True, "Update installed successfully.")
        else:
            err = (result.stderr or result.stdout or "Unknown error").strip()
            on_done(False, err[-500:])
    except subprocess.TimeoutExpired:
        on_done(False, "Installation timed out.")
    except FileNotFoundError:
        on_done(False, "pkexec is not available on this system.")
    except OSError as e:
        on_done(False, str(e))


def cleanup(path):
    """Best-effort removal of the downloaded .deb (and any partial file)."""
    for candidate in (path, path + ".part"):
        try:
            if candidate and os.path.exists(candidate):
                os.remove(candidate)
        except OSError:
            pass
