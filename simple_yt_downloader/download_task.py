"""Wraps a single yt-dlp download as a controllable background task.

Design notes:
- Every network/subprocess call happens on a background thread (started by
  the caller); this module never touches GTK, so it has no thread-safety
  concerns of its own. The GTK layer is responsible for marshaling callbacks
  back to the main loop via GLib.idle_add.
- Pause/resume signals the whole process GROUP (not just the yt-dlp
  process itself), since yt-dlp commonly spawns ffmpeg as a real child
  process (merging streams, or as an external downloader for some
  protocols like HLS/m3u8) -- signaling only the parent process left those
  children running untouched. See _signal_group().
"""

import json
import os
import re
import signal
import subprocess
import threading

PROGRESS_RE = re.compile(
    r"\[download\]\s+(?P<percent>[\d.]+)%"
    r"(?:\s+of\s+~?(?P<size>[\d.]+\w+))?"
    r"(?:\s+at\s+(?P<speed>[\d.]+\w+/s|Unknown speed))?"
    r"(?:\s+ETA\s+(?P<eta>[\d:]+|Unknown))?"
)

DESTINATION_RE = re.compile(r"\[download\] Destination:\s*(.+)")
ALREADY_DOWNLOADED_RE = re.compile(r"has already been downloaded")

# Matches the start of any yt-dlp postprocessor step -- "[Merger]",
# "[ExtractAudio]", "[Metadata]", "[VideoConvertor]", etc. -- basically any
# bracketed tag that isn't "[download]" itself. This is yt-dlp's own signal
# that it's about to hand off to ffmpeg.
POSTPROCESS_START_RE = re.compile(r"^\[(\w+)\]")

# Running two ffmpeg-touching steps (merging separate video+audio streams,
# or re-encoding audio) at the exact same time can make one of them fail
# outright under CPU/memory contention (seen in practice: "ERROR:
# Postprocessing: Conversion failed!" when two downloads finished at
# nearly the same moment). The actual downloading (network I/O) stays
# fully parallel -- only this specific step is serialized, by literally
# freezing a process the instant it starts postprocessing until it's its
# turn, then letting it continue. See DownloadTask._maybe_gate_postprocessing().
_MERGE_LOCK = threading.Lock()

VIDEO_QUALITY_TIERS = ["144", "240", "360", "480", "720", "1080", "1440", "2160"]


def _fmt_size(num_bytes):
    if not num_bytes:
        return None
    return f"{num_bytes / 1024 / 1024:.1f} MB"


def fetch_video_info(url, cookie_args, timeout=30):
    """Fetch the full format list AND duration for a single video (not
    flat-playlist -- that skips format resolution, which is exactly what we
    need here). Returns {"formats": [...], "duration": seconds_or_None}.
    """
    cmd = ["yt-dlp", *cookie_args, "-j", "--no-playlist", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return {"formats": [], "duration": None}
        data = json.loads(result.stdout.splitlines()[0])
        return {"formats": data.get("formats", []), "duration": data.get("duration")}
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, IndexError):
        return {"formats": [], "duration": None}


# Kept for any external callers expecting the old name/shape.
def fetch_formats(url, cookie_args, timeout=30):
    return fetch_video_info(url, cookie_args, timeout)["formats"]


def estimate_quality_sizes(formats, tiers=VIDEO_QUALITY_TIERS):
    """Returns {tier: bytes_or_None} approximating what
    'bestvideo[height<=tier]+bestaudio' would actually download -- mirrors
    the format-selection logic used in build_format_string().
    """
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
    """Audio files don't pre-exist at arbitrary target bitrates (yt-dlp
    re-encodes to whatever --audio-quality is requested), so unlike video
    there's no lookup -- size is estimated from bitrate * duration.

    'best' is left without a size (None) unless we can find the source's
    actual best-available audio bitrate in `formats`, since guessing a
    number here would be fabricating a figure we don't actually know.
    """
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
    """Sums a list of {tier: bytes_or_None} dicts -- used to total a
    playlist's per-quality size across its videos. A tier is left as None
    (unknown) only if every video in the list is missing that tier."""
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
        """Detect whether the URL is a playlist and fetch basic metadata.

        Uses --flat-playlist so this stays fast even for large playlists
        (it doesn't resolve each video's formats, just lists them).
        Populates self.is_playlist / self.playlist_entries / self.title.
        Raises RuntimeError on failure (bad link, no connection, etc).
        """
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
            # entries with exactly one item still comes from a playlist-style
            # URL (e.g. watch?v=X&list=Y) -- flatten to the single video.
            single = entries[0] if entries else data
            self.title = single.get("title") or "Untitled"
            self._fetch_size_estimate()

    def _fetch_size_estimate(self):
        """Best-effort file size estimate for the currently selected format."""
        fmt = self.build_format_string()
        cmd = [
            "yt-dlp", *self._cookie_args(),
            "-f", fmt,
            "--print", "%(filesize,filesize_approx)r",
            self.url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            # --print "%(filesize,filesize_approx)r" can emit one or two
            # space-separated values on a single line (filesize then
            # filesize_approx); sum every numeric token rather than assuming
            # the whole line is one float.
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

    def start(self, on_progress, on_finished):
        """Spawn the yt-dlp subprocess and stream progress to callbacks.

        on_progress(dict) is called for each parsed progress update:
            {"percent": float, "size": str, "speed": str, "eta": str}
        on_finished(success: bool, message: str) is called once when the
        process exits (or is cancelled).

        Both callbacks are invoked from this background thread -- the caller
        must marshal them to the GTK main loop if touching widgets.
        """
        # A DownloadTask can be restarted after a failure (retry, or the
        # resume() safety-net restart), so reset lifecycle state here -- a
        # stale run bleeding into the new one previously left a fresh
        # download SIGSTOPped at the merge gate forever (paused=True
        # survived the restart) or marked it cancelled prematurely.
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
        """The first time we see a non-'[download]' bracketed tag (e.g.
        "[Merger]", "[ExtractAudio]"), yt-dlp is about to hand off to
        ffmpeg. Freeze the process right there (SIGSTOP, via the same
        process-group signaling pause/resume uses) and only let it
        continue once the global merge lock is free -- this way the
        network-bound download phase stays fully parallel across
        different videos, and only the CPU-bound ffmpeg phase is
        serialized, one at a time.
        """
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
            # If the user manually paused it while it was waiting for the
            # merge lock, respect that instead of silently overriding
            # their click -- leave it stopped; their own resume() call
            # will SIGCONT it later.
            if not self.paused:
                self._signal_group(signal.SIGCONT)
        # If the process already exited by the time we tried to stop it
        # (very small/instant conversions), there's nothing to gate --
        # just proceed without ever having held the lock.

    def _release_merge_lock_if_held(self):
        if self._merge_lock_held:
            self._merge_lock_held = False
            try:
                _MERGE_LOCK.release()
            except RuntimeError:
                pass

    def _signal_group(self, sig):
        """Sends a signal to the whole process group (yt-dlp + any children
        it spawned, like ffmpeg), not just the yt-dlp process itself.

        This matters: yt-dlp commonly hands work off to ffmpeg as a real
        subprocess -- for merging separate video/audio streams, and as an
        external downloader for some protocols (e.g. HLS/m3u8 streams).
        Signaling only the yt-dlp process left those children running
        untouched, which is why pause previously failed to actually stop
        the download in some cases. Falls back to signaling just the
        process directly if the group signal isn't available for some
        reason (e.g. already reaped).
        """
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
        failure, since that's the safety net for a long-paused/expired URL."""
        with self._lock:
            if self.process and self.paused:
                if self._signal_group(signal.SIGCONT):
                    self.paused = False
                    # SIGCONT succeeding doesn't guarantee the download is
                    # still healthy (a stale connection can still fail on the
                    # next read) -- the stdout loop in start() will surface
                    # that naturally via on_finished(False, ...).
                    return True
                return False
        return False

    def cancel(self):
        with self._lock:
            self.cancelled = True
            if self.process and self.process.poll() is None:
                # SIGCONT first, unconditionally: a download waiting on the
                # merge gate is SIGSTOPped with paused == False, so the
                # SIGTERM below would otherwise stay *pending* until some
                # later SIGCONT delivered it -- and an app exit in that
                # window left an orphaned stopped yt-dlp/ffmpeg behind.
                # SIGCONT on a running process is a harmless no-op.
                self._signal_group(signal.SIGCONT)
                self._signal_group(signal.SIGTERM)
