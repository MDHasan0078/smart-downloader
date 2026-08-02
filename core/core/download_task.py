"""Wraps a single yt-dlp download as a controllable background task.

Ported from the GTK app's simple_yt_downloader/download_task.py (no GTK
deps there, so this is near-verbatim).

Design notes:
- Every network/subprocess call happens on a background thread started by the
  caller; this module has no thread-safety concerns of its own.
- Pause/resume signals the whole process GROUP (not just yt-dlp itself),
  since yt-dlp commonly spawns ffmpeg as a real child process (merging
  streams, or as an external downloader for HLS/m3u8). See _signal_group().

Windows note: POSIX signal groups (SIGSTOP/SIGCONT) don't exist on Windows.
_on_win32 is True there and _signal_group degrades to a no-op guard so
pause()/resume() report False gracefully; real Windows pause/resume (e.g.
NtSuspendThread or kill-and-continue with a download range) is a Phase 1 item.
"""

import json
import os
import re
import signal
import subprocess
import threading

_ON_WIN32 = os.name == "nt"

PROGRESS_RE = re.compile(
    r"\[download\]\s+(?P<percent>[\d.]+)%"
    r"(?:\s+of\s+~?(?P<size>[\d.]+\w+))?"
    r"(?:\s+at\s+(?P<speed>[\d.]+\w+/s|Unknown speed))?"
    r"(?:\s+ETA\s+(?P<eta>[\d:]+|Unknown))?"
)

DESTINATION_RE = re.compile(r"\[download\] Destination:\s*(.+)")
ALREADY_DOWNLOADED_RE = re.compile(r"has already been downloaded")

POSTPROCESS_START_RE = re.compile(r"^\[(\w+)\]")

_MERGE_LOCK = threading.Lock()

VIDEO_QUALITY_TIERS = ["144", "240", "360", "480", "720", "1080", "1440", "2160"]


def _fmt_size(num_bytes):
    if not num_bytes:
        return None
    return f"{num_bytes / 1024 / 1024:.1f} MB"


def fetch_video_info(url, cookie_args, timeout=30):
    """Fetch the full format list AND duration for a single video (not
    flat-playlist -- that skips format resolution). Returns
    {"formats": [...], "duration": seconds_or_None}."""
    cmd = ["yt-dlp", *cookie_args, "-j", "--no-playlist", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return {"formats": [], "duration": None}
        data = json.loads(result.stdout.splitlines()[0])
        return {"formats": data.get("formats", []), "duration": data.get("duration")}
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, IndexError):
        return {"formats": [], "duration": None}


def fetch_formats(url, cookie_args, timeout=30):
    return fetch_video_info(url, cookie_args, timeout)["formats"]


def estimate_quality_sizes(formats, tiers=VIDEO_QUALITY_TIERS):
    """Returns {tier: bytes_or_None} approximating what
    'bestvideo[height<=tier]+bestaudio' would actually download."""
    video_formats = [
        f for f in formats
        if f.get("height") and f.get("vcodec") not in (None, "none")
    ]
    audio_formats = [
        f for f in formats
        if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")
    ]
    best_audio_size = max(
        (f.get("filesize") or f.get("filesize_approx") or 0 for f in audio_formats),
        default=0,
    )

    sizes = {}
    for tier in tiers:
        height_limit = int(tier)
        candidates = [f for f in video_formats if f["height"] <= height_limit]
        if not candidates:
            sizes[tier] = None
            continue
        best = max(candidates, key=lambda f: f["height"])
        vsize = best.get("filesize") or best.get("filesize_approx") or 0
        total = vsize + best_audio_size
        sizes[tier] = total or None
    return sizes


AUDIO_QUALITY_TIERS = ("128", "192", "256", "best")


def estimate_audio_quality_sizes(duration_seconds, formats=None, tiers=AUDIO_QUALITY_TIERS):
    """Audio sizes estimated from bitrate * duration (yt-dlp re-encodes to
    whatever --audio-quality is requested). 'best' is None unless the source
    audio bitrate can be found in `formats`."""
    if not duration_seconds:
        return {t: None for t in tiers}

    sizes = {}
    for tier in tiers:
        if tier == "best":
            abr = None
            if formats:
                audio_only = [
                    f for f in formats
                    if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")
                ]
                abrs = [f.get("abr") for f in audio_only if f.get("abr")]
                abr = max(abrs) if abrs else None
            if not abr:
                sizes[tier] = None
                continue
            bitrate_kbps = abr
        else:
            bitrate_kbps = int(tier)
        sizes[tier] = (bitrate_kbps * 1000 / 8) * duration_seconds
    return sizes


def sum_quality_sizes(size_dicts, tiers=None):
    """Sums a list of {tier: bytes_or_None} dicts. A tier is None only if
    every video in the list is missing that tier."""
    if tiers is None:
        tiers = VIDEO_QUALITY_TIERS
    totals = {tier: 0 for tier in tiers}
    known = {tier: False for tier in tiers}
    for sizes in size_dicts:
        for tier in tiers:
            value = sizes.get(tier)
            if value:
                totals[tier] += value
                known[tier] = True
    return {tier: (totals[tier] if known[tier] else None) for tier in tiers}


class DownloadTask:
    """One video's worth of download state and control."""

    def __init__(self, url, download_dir, cookies_file=None):
        self.url = url
        self.download_dir = download_dir
        self.cookies_file = cookies_file

        self.title = None
        self.size_str = None
        self.is_playlist = False
        self.playlist_entries = []  # list of {"url", "title"} when is_playlist

        self.mode = "video"  # "video" | "audio"
        self.video_format = "mp4"
        self.video_quality = "720"
        self.audio_format = "mp3"
        self.audio_quality = "192"

        self.process = None
        self.paused = False
        self.cancelled = False
        self.log_lines = []

        self._lock = threading.Lock()

    # ---- Metadata / playlist detection ----------------------------------

    def _cookie_args(self):
        if self.cookies_file and os.path.isfile(self.cookies_file):
            return ["--cookies", self.cookies_file]
        return []

    @staticmethod
    def _normalize_entry_url(entry):
        url = entry.get("url") or entry.get("webpage_url")
        if url and url.startswith("http"):
            return url
        video_id = entry.get("id") or url
        return f"https://www.youtube.com/watch?v={video_id}"

    def probe(self):
        """Detect playlist vs single video; populate title/entries.
        Raises RuntimeError on failure."""
        cmd = ["yt-dlp", *self._cookie_args(), "--flat-playlist", "--dump-single-json", self.url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timed out fetching video info.")
        except FileNotFoundError:
            raise RuntimeError("yt-dlp is not installed.")

        if result.returncode != 0:
            raise RuntimeError((result.stderr or "Could not fetch video info.").strip()[-400:])

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise RuntimeError("Unexpected response from yt-dlp.")

        entries = data.get("entries")
        if entries and len(entries) > 1:
            self.is_playlist = True
            self.title = data.get("title") or "Playlist"
            self.playlist_entries = [
                {
                    "url": self._normalize_entry_url(e),
                    "title": e.get("title") or e.get("id") or "Untitled",
                }
                for e in entries
            ]
        else:
            self.is_playlist = False
            single = entries[0] if entries else data
            self.title = single.get("title") or "Untitled"
            self._fetch_size_estimate()

    def _fetch_size_estimate(self):
        fmt = self.build_format_string()
        cmd = [
            "yt-dlp", *self._cookie_args(),
            "-f", fmt,
            "--print", "%(filesize,filesize_approx)r",
            self.url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            total = sum(
                float(tok)
                for line in result.stdout.splitlines()
                for tok in line.strip().split()
                if tok.replace(".", "", 1).isdigit()
            )
            self.size_str = f"{total / 1024 / 1024:.1f} MB" if total else "Unknown size"
        except (subprocess.SubprocessError, OSError, ValueError):
            self.size_str = "Unknown size"

    # ---- Format string building ------------------------------------------

    def build_format_string(self):
        if self.mode == "audio":
            return "bestaudio"
        res = self.video_quality
        ext = self.video_format
        return (
            f"bestvideo[height<={res}][ext={ext}]+bestaudio/"
            f"bestvideo[height<={res}]+bestaudio/best[height<={res}]"
        )

    def build_postprocess_args(self):
        if self.mode == "audio":
            quality = "0" if self.audio_quality == "best" else f"{self.audio_quality}K"
            return ["-x", "--audio-format", self.audio_format, "--audio-quality", quality]
        return ["--merge-output-format", self.video_format]

    # ---- Download control --------------------------------------------

    def start(self, on_progress, on_finished, on_log=None):
        """Spawn the yt-dlp subprocess and stream progress to callbacks.

        on_progress(dict): {"percent", "size", "speed", "eta"}
        on_finished(success: bool, message: str) -- called once on exit.
        on_log(line: str) -- optional, each raw yt-dlp output line.

        All callbacks run on a background thread.
        """
        self.paused = False
        self.cancelled = False
        self.log_lines = []
        self._acquired_merge_lock = False
        self._merge_lock_held = False

        os.makedirs(self.download_dir, exist_ok=True)
        cmd = [
            "yt-dlp", *self._cookie_args(),
            "-f", self.build_format_string(),
            *self.build_postprocess_args(),
            "--newline",
            "-o", os.path.join(self.download_dir, "%(title)s.%(ext)s"),
            self.url,
        ]

        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                start_new_session=True,  # own process group -- see _signal_group()
            )
        except FileNotFoundError:
            on_finished(False, "yt-dlp is not installed.")
            return

        for line in self.process.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            self.log_lines.append(line)
            if on_log:
                on_log(line)

            match = PROGRESS_RE.search(line)
            if match:
                on_progress({
                    "percent": float(match.group("percent")),
                    "size": match.group("size") or self.size_str,
                    "speed": match.group("speed") or "",
                    "eta": match.group("eta") or "",
                })
                continue

            self._maybe_gate_postprocessing(line)

        self.process.wait()
        self._release_merge_lock_if_held()

        if self.cancelled:
            on_finished(False, "Cancelled")
        elif self.process.returncode == 0:
            on_finished(True, "Done")
        else:
            tail = "\n".join(self.log_lines[-5:])
            on_finished(False, tail or "Download failed.")

    def _maybe_gate_postprocessing(self, line):
        """First non-'[download]' bracketed tag means yt-dlp is handing off
        to ffmpeg: SIGSTOP the group until the global merge lock frees up,
        serializing only the CPU-bound ffmpeg phase."""
        if self._acquired_merge_lock:
            return
        m = POSTPROCESS_START_RE.match(line)
        if not m or m.group(1).lower() == "download":
            return

        self._acquired_merge_lock = True
        still_running = self._signal_group(signal.SIGSTOP)
        if still_running:
            _MERGE_LOCK.acquire()
            self._merge_lock_held = True
            if not self.paused:
                self._signal_group(signal.SIGCONT)

    def _release_merge_lock_if_held(self):
        if self._merge_lock_held:
            self._merge_lock_held = False
            try:
                _MERGE_LOCK.release()
            except RuntimeError:
                pass

    def _signal_group(self, sig):
        if _ON_WIN32:
            return False
        try:
            os.killpg(os.getpgid(self.process.pid), sig)
            return True
        except (OSError, ProcessLookupError):
            try:
                self.process.send_signal(sig)
                return True
            except OSError:
                return False

    def pause(self):
        with self._lock:
            if self.process and self.process.poll() is None and not self.paused:
                if self._signal_group(signal.SIGSTOP):
                    self.paused = True
                    return True
                return False
        return False

    def resume(self):
        """Try SIGCONT first; caller should re-call start() if this reports
        failure (safety net for a long-paused/expired URL)."""
        with self._lock:
            if self.process and self.paused:
                if self._signal_group(signal.SIGCONT):
                    self.paused = False
                    return True
                return False
        return False

    def cancel(self):
        with self._lock:
            self.cancelled = True
            if self.process and self.process.poll() is None:
                if _ON_WIN32:
                    self.process.terminate()
                    return
                # SIGCONT first, unconditionally: a download waiting on the
                # merge gate is SIGSTOPped with paused == False, so SIGTERM
                # would otherwise stay pending until a later SIGCONT.
                self._signal_group(signal.SIGCONT)
                self._signal_group(signal.SIGTERM)
