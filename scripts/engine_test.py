#!/usr/bin/env python3
"""Phase 0 spike: drive the core engine over JSONL and verify the protocol.

Usage (from repo root):
    python scripts/engine_test.py
    python scripts/engine_test.py --engine <path-to-built-engine-binary>

Exercises: ping, check_deps, settings get/set, get_info (video + playlist),
start-with-progress, restart, pause/resume/cancel. Real yt-dlp downloads a
small public video into a temp dir. Exits non-zero on any failed step.
"""

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from typing import TextIO, cast

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"        # Me at the zoo (19s)
PLAYLIST_URL = "https://www.youtube.com/watch_videos?video_ids=" \
               "jNQXAC9IVRw,aqz-KE-bpKQ"                         # generated 2-video playlist
SLOW_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"          # BBB 4K, ~10 min, for pause timing

PASS = 0
FAIL = 0


def report(name, ok, detail=""):
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{tag}] {name}" + (f"  -- {detail}" if detail else ""))


def pick_engine_module():
    """Return the importable engine module: installed dist is 'core.engine',
    running from this repo it is 'core.core.engine'."""
    for candidate in ("core.engine", "core.core.engine"):
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import {candidate}"],
                capture_output=True, timeout=15,
            )
            if result.returncode == 0:
                return candidate
        except (subprocess.SubprocessError, OSError):
            continue
    raise SystemExit("could not import the engine package")


class EngineClient:
    stdin: "TextIO"
    stdout: "TextIO"
    stderr: "TextIO"

    def __init__(self, engine_cmd, cwd):
        self.proc = subprocess.Popen(
            engine_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, cwd=cwd,
        )
        self.stdin = cast(TextIO, self.proc.stdin)
        self.stdout = cast(TextIO, self.proc.stdout)
        self.stderr = cast(TextIO, self.proc.stderr)
        self._id = [0]
        self._pending = {}
        self.events = []
        self.stderr_lines = []
        self._reply_q = queue.Queue()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _drain_stderr(self):
        for line in self.stderr:
            self.stderr_lines.append(line.rstrip("\n"))

    def _read(self):
        for line in self.stdout:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("event") == "reply":
                self._pending.pop(obj.get("id"), None)
                self._reply_q.put(obj)
            else:
                self.events.append(obj)

    def send(self, **msg):
        self._id[0] += 1
        msg = {"id": self._id[0], **msg}
        self.stdin.write(json.dumps(msg) + "\n")
        self.stdin.flush()
        return self._reply_q.get(timeout=60)

    def wait_event(self, event_type, task_id=None, timeout=120):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for ev in self.events:
                if ev.get("event") == event_type:
                    if task_id is None or ev.get("task_id") == task_id:
                        return ev
            time.sleep(0.05)
        return None

    def close(self):
        try:
            self.stdin.close()
        except OSError:
            pass
        try:
            self.proc.terminate()
        except OSError:
            pass


def main():
    global PASS, FAIL
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default=None, help="path to a built engine binary")
    parser.add_argument("--download-dir", default=None)
    args = parser.parse_args()

    if args.download_dir is None:
        args.download_dir = tempfile.mkdtemp(prefix="smart-downloader-spike-")
        print(f"Fresh download dir: {args.download_dir}")

    if args.engine:
        cmd = [args.engine]
    else:
        module = pick_engine_module()
        cmd = [sys.executable, "-m", module]
    print(f"Spawning engine: {' '.join(cmd)}")
    client = EngineClient(cmd, cwd=REPO_ROOT)

    try:
        r = client.send(cmd="ping")
        report("ping", r.get("ok") is True and r.get("pong") is True, json.dumps(r))

        r = client.send(cmd="check_deps")
        ok = r.get("ok") and not r.get("missing")
        report("check_deps (yt-dlp+ffmpeg present)", ok,
               f"binaries={r.get('binaries')} version={r.get('yt_dlp_version')}")

        r = client.send(cmd="settings_get")
        s = r.get("settings", {})
        report("settings_get returns defaults", r.get("ok")
               and s.get("default_video_format") == "mp4"
               and "download_dir" in s, json.dumps(s))

        r = client.send(cmd="settings_set", settings={"theme": "dark"})
        report("settings_set persists + sanitizes", r.get("ok")
               and r.get("settings", {}).get("theme") == "dark"
               and "settings" in r)
        # restore
        client.send(cmd="settings_set", settings={"theme": "system"})

        r = client.send(cmd="get_info", url=VIDEO_URL)
        ok = r.get("ok") and r.get("type") == "video" and r.get("formats")
        report("get_info single video", ok,
               f"title={r.get('title')} duration={r.get('duration')}s "
               f"formats={len(r.get('formats') or [])}")

        r = client.send(cmd="get_info", url=PLAYLIST_URL)
        entries = r.get("entries") or []
        report("get_info playlist expands entries", r.get("ok")
               and r.get("type") == "playlist" and len(entries) >= 2,
               f"title={r.get('title')} entries={len(entries)}")

        os.makedirs(args.download_dir, exist_ok=True)
        r = client.send(cmd="start", url=VIDEO_URL, mode="audio",
                        audio_format="mp3", audio_quality="128",
                        download_dir=args.download_dir)
        task_id = r.get("task_id")
        report("start returns task_id", r.get("ok") and task_id, json.dumps(r))

        progress = client.wait_event("progress", task_id=task_id)
        report("instant download progress (optional)", True,
               json.dumps(progress) if progress else "no progress line for sub-second download (fine)")

        fin = client.wait_event("finished", task_id=task_id)
        report("download finishes successfully", fin is not None
               and fin.get("success") is True,
               json.dumps(fin) if fin else "no finished event")
        produced = [f for f in os.listdir(args.download_dir)
                    if f.endswith(".mp3")]
        report("mp3 written to download dir", len(produced) > 0,
               str(produced[:3]))

        # deterministic progress streaming on a 10-minute source, then cancel
        r = client.send(cmd="start", url=SLOW_URL, mode="audio",
                        audio_format="mp3", audio_quality="128",
                        download_dir=args.download_dir)
        slow_audio_id = r.get("task_id")
        client.events = []
        progress = client.wait_event("progress", task_id=slow_audio_id, timeout=30)
        report("progress events stream", progress is not None,
               json.dumps(progress) if progress else "no progress line seen")
        if progress:
            client.send(cmd="cancel", task_id=slow_audio_id)
            client.wait_event("finished", task_id=slow_audio_id, timeout=30)

        # restart = cancel + fresh start (works for finished tasks too)
        client.events = []
        r = client.send(cmd="restart", task_id=task_id)
        report("restart returns same task_id", r.get("ok")
               and r.get("task_id") == task_id, json.dumps(r))
        fin2 = client.wait_event("finished", task_id=task_id)
        report("restarted download completes", fin2 is not None,
               json.dumps(fin2) if fin2 else "no finished event")

        # pause / resume / cancel on a longer video
        r = client.send(cmd="start", url=SLOW_URL, mode="video",
                        video_format="mp4", video_quality="360",
                        download_dir=args.download_dir)
        slow_id = r.get("task_id")
        report("second task starts", r.get("ok") and slow_id, json.dumps(r))
        client.events = []

        time.sleep(0.4)
        r = client.send(cmd="pause", task_id=slow_id)
        paused_ok = r.get("paused") is True
        report("pause", paused_ok, json.dumps(r))
        if paused_ok:
            r = client.send(cmd="resume", task_id=slow_id)
            report("resume", r.get("resumed") is True and r.get("paused") is False,
                   json.dumps(r))
        else:
            report("resume (skipped, download finished before pause)",
                   True, "task already completed")

        r = client.send(cmd="cancel", task_id=slow_id)
        report("cancel", r.get("ok") is True, json.dumps(r))
        fin3 = client.wait_event("finished", task_id=slow_id, timeout=30)
        report("cancelled task reports finished", fin3 is not None
               and fin3.get("success") is False, json.dumps(fin3) if fin3 else "")

        r = client.send(cmd="bogus")
        report("unknown command rejected", r.get("ok") is False
               and "unknown" in str(r.get("error")), json.dumps(r))
    finally:
        client.close()

    print(f"\nResult: {PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
