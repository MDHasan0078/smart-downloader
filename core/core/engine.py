"""Engine entry point: JSONL bridge between the desktop UI and the downloader.

Reads one JSON command per line on stdin, writes one JSON event per line on
stdout (reply / progress / finished). Line-buffered with flush, so a Dart or
Python client can attach a subprocess and stream in both directions with no
socket setup.

Commands (each with an "id" echoed back in the reply):
    ping                    -> {"pong": true}
    check_deps              -> {"binaries": {...}, "missing": [...],
                                "yt_dlp_version": str|None}
    settings_get            -> {"settings": {...}}
    settings_set            -> merge {"settings": {...}} into config.json
    get_info                -> {"url": ...}
                              single video : {"type":"video", "title",
                                  "duration", "formats": [...]}
                              playlist     : {"type":"playlist", "title",
                                  "entries": [{"url","title","index"}]}
    start                   -> {"url", "mode": video|audio, "video_format",
                                "video_quality", "audio_format",
                                "audio_quality", "task_id"?}
                              replies {"ok":true,"task_id":...} immediately,
                              then streams "progress" and "finished" events.
    pause / resume / cancel -> {"task_id": ...}   -> {"ok": bool, "paused": bool}
    restart                 -> {"task_id": ...}   -> new task, cancels old one

Events (no "id", always include "event"):
    reply      -> {id, ok, ...result}
    progress   -> {task_id, percent, size, speed, eta}
    finished   -> {task_id, success, message}
    error      -> {message}
"""

import json
import sys
import threading
from itertools import count

from . import config, dependencies, download_task

_task_counter = count(1)


class Engine:
    def __init__(self):
        self.settings = config.load()
        self.tasks = {}       # task_id -> {"task": DownloadTask, "config": dict}
        self.completed = {}   # task_id -> {"config": dict, "finished": {success, message}}
        self._write_lock = threading.Lock()

    # ---- protocol helpers ---------------------------------------------

    def _emit(self, event_type, **payload):
        line = json.dumps({"event": event_type, **payload})
        with self._write_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def _reply(self, msg, **payload):
        self._emit("reply", id=msg.get("id"), **payload)

    def handle(self, msg):
        cmd = msg.get("cmd")
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            self._reply(msg, ok=False, error=f"unknown command: {cmd}")
            return
        try:
            result = handler(msg)
            self._reply(msg, ok=True, **result)
        except Exception as exc:
            self._reply(msg, ok=False, error=str(exc))

    # ---- task plumbing -------------------------------------------------

    def _cookie_file(self):
        if self.settings.get("use_cookies") and self.settings.get("cookies_file"):
            return self.settings["cookies_file"]
        return None

    def _build_task(self, cfg):
        task = download_task.DownloadTask(
            cfg["url"],
            cfg.get("download_dir") or self.settings["download_dir"],
            cookies_file=cfg.get("cookies_file") or self._cookie_file(),
        )
        task.mode = cfg.get("mode", "video")
        task.video_format = cfg.get("video_format") or self.settings["default_video_format"]
        task.video_quality = cfg.get("video_quality") or self.settings["default_video_quality"]
        task.audio_format = cfg.get("audio_format") or self.settings["default_audio_format"]
        task.audio_quality = cfg.get("audio_quality") or self.settings["default_audio_quality"]
        return task

    def _spawn_task(self, task_id, task, cfg):
        self.tasks[task_id] = {"task": task, "config": cfg}
        thread = threading.Thread(target=self._run_task, args=(task_id,), daemon=True)
        thread.start()

    def _run_task(self, task_id):
        entry = self.tasks.get(task_id)
        if entry is None:
            return
        task = entry["task"]
        outcome = {}

        def on_progress(progress):
            self._emit("progress", task_id=task_id, **progress)

        def on_finished(ok, message):
            outcome["success"] = ok
            outcome["message"] = message
            self._emit("finished", task_id=task_id, success=ok, message=message)

        task.start(on_progress=on_progress, on_finished=on_finished)
        self.tasks.pop(task_id, None)
        self.completed[task_id] = {"config": entry["config"], "finished": outcome}

    # ---- commands ------------------------------------------------------

    def cmd_ping(self, msg):
        return {"pong": True}

    def cmd_check_deps(self, msg):
        binaries = dependencies.check_all()
        return {
            "binaries": binaries,
            "missing": dependencies.missing_binaries(),
            "yt_dlp_version": dependencies.get_yt_dlp_version(),
        }

    def cmd_settings_get(self, msg):
        return {"settings": self.settings}

    def cmd_settings_set(self, msg):
        patch = msg.get("settings")
        if not isinstance(patch, dict):
            raise ValueError("'settings' must be a dict")
        self.settings.update(patch)
        config._sanitize(self.settings)
        config.save(self.settings)
        return {"settings": self.settings}

    def cmd_get_info(self, msg):
        url = msg.get("url")
        if not url:
            raise ValueError("'url' is required")
        task = self._build_task({"url": url, "mode": "video"})
        task.probe()
        if task.is_playlist:
            return {
                "type": "playlist",
                "title": task.title,
                "entries": [
                    {"index": i, "url": e["url"], "title": e["title"]}
                    for i, e in enumerate(task.playlist_entries)
                ],
            }
        info = download_task.fetch_video_info(url, task._cookie_args())
        return {
            "type": "video",
            "title": task.title,
            "size_str": task.size_str,
            "duration": info["duration"],
            "formats": info["formats"],
        }

    def cmd_start(self, msg):
        url = msg.get("url")
        if not url:
            raise ValueError("'url' is required")
        cfg = {k: msg.get(k) for k in (
            "url", "mode", "video_format", "video_quality",
            "audio_format", "audio_quality", "download_dir", "cookies_file",
        )}
        task = self._build_task(cfg)
        task_id = msg.get("task_id") or f"t{next(_task_counter)}"
        self._spawn_task(task_id, task, cfg)
        return {"task_id": task_id}

    def cmd_restart(self, msg):
        task_id = msg.get("task_id")
        entry = self.tasks.get(task_id) or self.completed.get(task_id)
        if entry is None:
            raise ValueError(f"unknown task: {task_id}")
        running = self.tasks.get(task_id)
        if running:
            running["task"].cancel()
        task = self._build_task(entry["config"])
        self._spawn_task(task_id, task, entry["config"])
        return {"task_id": task_id, "restarted": True}

    def _ctrl(self, msg, action):
        task_id = msg.get("task_id")
        entry = self.tasks.get(task_id)
        if entry is None:
            raise ValueError(f"unknown task: {task_id}")
        task = entry["task"]
        if action == "pause":
            return {"task_id": task_id, "paused": task.pause()}
        if action == "resume":
            resumed = task.resume()
            return {"task_id": task_id, "paused": task.paused, "resumed": resumed}
        task.cancel()
        return {"task_id": task_id, "cancelled": True}

    def cmd_pause(self, msg):
        return self._ctrl(msg, "pause")

    def cmd_resume(self, msg):
        return self._ctrl(msg, "resume")

    def cmd_cancel(self, msg):
        return self._ctrl(msg, "cancel")


def main():
    engine = Engine()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            engine._emit("error", message="invalid JSON on stdin")
            continue
        if not isinstance(msg, dict):
            engine._emit("error", message="expected a JSON object per line")
            continue
        engine.handle(msg)


if __name__ == "__main__":
    main()
