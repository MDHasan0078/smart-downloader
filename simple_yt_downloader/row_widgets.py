"""Row widgets shown in the Ongoing / Completed lists.

LoadingRow  -- shown briefly while a pasted link is being probed.
VideoRow    -- a single video/audio download with format+quality controls.
PlaylistRow -- a playlist: shared controls + an expandable, scrollable list
               of child videos, downloaded sequentially by reusing
               DownloadTask.
"""

import os
import time
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from .download_task import (
    DownloadTask, fetch_video_info, estimate_quality_sizes,
    estimate_audio_quality_sizes, sum_quality_sizes, _fmt_size,
    AUDIO_QUALITY_TIERS,
)

VIDEO_FORMATS = ["mp4", "mkv", "webm"]
VIDEO_QUALITIES = [
    ("144", "144p"), ("240", "240p"), ("360", "360p"),
    ("480", "480p"), ("720", "720p (HD)"), ("1080", "1080p (Full HD)"),
    ("1440", "1440p (2K)"), ("2160", "2160p (4K)"),
]
AUDIO_FORMATS = ["mp3", "m4a", "opus", "wav", "flac"]
AUDIO_QUALITIES = [
    ("128", "128 kbps"), ("192", "192 kbps"),
    ("256", "256 kbps"), ("best", "Best available"),
]

_ICON_FALLBACK_GLYPHS = {
    "media-playback-pause-symbolic": "⏸",
    "media-playback-start-symbolic": "▶",
    "pan-down-symbolic": "▾",
    "pan-up-symbolic": "▴",
    "window-close-symbolic": "✕",
    "folder-symbolic": "📁",
    "folder-download-symbolic": "⬇",
    "emblem-ok-symbolic": "✓",
}


def _icon_theme_has(icon_name):
    try:
        theme = Gtk.IconTheme.get_default()
        return theme.has_icon(icon_name)
    except Exception:
        return False


def _icon_button(icon_name, tooltip=""):
    btn = Gtk.Button()
    btn.set_relief(Gtk.ReliefStyle.NONE)
    btn.get_style_context().add_class("image-button")
    _set_button_icon(btn, icon_name)
    if tooltip:
        btn.set_tooltip_text(tooltip)
    return btn


def _set_button_icon(btn, icon_name):
    child = btn.get_child()
    if child:
        btn.remove(child)
    if _icon_theme_has(icon_name):
        btn.add(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.SMALL_TOOLBAR))
    else:
        glyph = _ICON_FALLBACK_GLYPHS.get(icon_name, "•")
        btn.add(Gtk.Label(label=glyph))
    btn.show_all()


def _set_image_icon(image, icon_name, size=Gtk.IconSize.MENU):
    name = icon_name if _icon_theme_has(icon_name) else "image-missing"
    image.set_from_icon_name(name, size)


class LoadingRow(Gtk.Box):
    """Placeholder shown while a pasted link is being probed."""

    def __init__(self, url):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.get_style_context().add_class("download-row")
        spinner = Gtk.Spinner()
        spinner.start()
        self.pack_start(spinner, False, False, 0)
        label = Gtk.Label(label=f"Checking link: {url}")
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        self.pack_start(label, True, True, 0)
        self.show_all()


class ModeQualityBar(Gtk.Box):
    """The Video/Audio toggle + Format/Quality dropdowns row."""

    def __init__(self, defaults):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.mode = "video"
        self._video_quality_sizes = {}
        self._audio_quality_sizes = {}

        self.video_btn = Gtk.ToggleButton(label="Video")
        self.audio_btn = Gtk.ToggleButton(label="Audio")
        self.video_btn.set_active(True)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.get_style_context().add_class("linked")
        box.pack_start(self.video_btn, False, False, 0)
        box.pack_start(self.audio_btn, False, False, 0)
        self.pack_start(box, False, False, 0)

        self.format_combo = Gtk.ComboBoxText()
        self.quality_combo = Gtk.ComboBoxText()
        self.pack_end(self.quality_combo, False, False, 0)
        self.pack_end(self.format_combo, False, False, 0)

        self._defaults = defaults
        self._populate_for_mode("video")

        self.video_btn.connect("toggled", self._on_video_toggled)
        self.audio_btn.connect("toggled", self._on_audio_toggled)

    def _on_video_toggled(self, btn):
        if btn.get_active():
            self.audio_btn.set_active(False)
            self.mode = "video"
            self._populate_for_mode("video")
        elif not self.audio_btn.get_active():
            btn.set_active(True)

    def _on_audio_toggled(self, btn):
        if btn.get_active():
            self.video_btn.set_active(False)
            self.mode = "audio"
            self._populate_for_mode("audio")
        elif not self.video_btn.get_active():
            btn.set_active(True)

    def _populate_for_mode(self, mode):
        self.format_combo.remove_all()
        self.quality_combo.remove_all()
        if mode == "video":
            for fmt in VIDEO_FORMATS:
                self.format_combo.append_text(fmt.upper())
            default_fmt = self._defaults.get("default_video_format", "mp4")
            idx = VIDEO_FORMATS.index(default_fmt) if default_fmt in VIDEO_FORMATS else 0
            self.format_combo.set_active(idx)

            for value, display in VIDEO_QUALITIES:
                size_text = self._video_quality_sizes.get(value)
                label = f"{display} ({size_text})" if size_text else display
                self.quality_combo.append(value, label)
            default_q = self._defaults.get("default_video_quality", "720")
            self.quality_combo.set_active_id(default_q)
            if self.quality_combo.get_active() == -1:
                self.quality_combo.set_active(4)
        else:
            for fmt in AUDIO_FORMATS:
                self.format_combo.append_text(fmt.upper())
            default_fmt = self._defaults.get("default_audio_format", "mp3")
            idx = AUDIO_FORMATS.index(default_fmt) if default_fmt in AUDIO_FORMATS else 0
            self.format_combo.set_active(idx)

            for value, display in AUDIO_QUALITIES:
                size_text = self._audio_quality_sizes.get(value)
                label = f"{display} ({size_text})" if size_text else display
                self.quality_combo.append(value, label)
            default_q = self._defaults.get("default_audio_quality", "192")
            self.quality_combo.set_active_id(default_q)
            if self.quality_combo.get_active() == -1:
                self.quality_combo.set_active(1)

    def get_selection(self):
        fmt = (self.format_combo.get_active_text() or "").lower()
        quality_id = self.quality_combo.get_active_id()
        return self.mode, fmt, quality_id

    def set_video_quality_sizes(self, size_map):
        self._video_quality_sizes = {k: v for k, v in size_map.items() if v}
        if self.mode == "video":
            current = self.quality_combo.get_active_id()
            self._populate_for_mode("video")
            if current:
                self.quality_combo.set_active_id(current)

    def set_audio_quality_sizes(self, size_map):
        self._audio_quality_sizes = {k: v for k, v in size_map.items() if v}
        if self.mode == "audio":
            current = self.quality_combo.get_active_id()
            self._populate_for_mode("audio")
            if current:
                self.quality_combo.set_active_id(current)

    def set_sensitive_all(self, sensitive):
        self.video_btn.set_sensitive(sensitive)
        self.audio_btn.set_sensitive(sensitive)
        self.format_combo.set_sensitive(sensitive)
        self.quality_combo.set_sensitive(sensitive)


class VideoRow(Gtk.Box):
    """A single video or audio download."""

    def __init__(self, url, settings, on_state_change, preprobed_task=None, skip_quality_sizes=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.get_style_context().add_class("download-row")

        self.settings = settings
        self.on_state_change = on_state_change
        self.task = preprobed_task or DownloadTask(
            url,
            settings["download_dir"],
            settings["cookies_file"] if settings.get("use_cookies") else None,
        )
        self._started = False

        self.quality_bar = ModeQualityBar(settings)
        self.pack_start(self.quality_bar, False, False, 0)

        self.title_label = Gtk.Label(label="Fetching title...")
        self.title_label.get_style_context().add_class("title")
        self.title_label.set_xalign(0)
        self.title_label.set_line_wrap(True)
        self.pack_start(self.title_label, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(False)
        self.progress.set_no_show_all(True)
        self.progress.set_visible(False)
        self.pack_start(self.progress, False, False, 0)

        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.status_label = Gtk.Label(label="")
        self.status_label.set_xalign(0)
        self.status_label.get_style_context().add_class("status-text")
        status_row.pack_start(self.status_label, True, True, 0)

        self.start_btn = Gtk.Button(label="Start")
        self.start_btn.get_style_context().add_class("suggested-action")
        self.start_btn.connect("clicked", self._on_start_clicked)
        self.start_btn.set_no_show_all(True)
        status_row.pack_end(self.start_btn, False, False, 0)

        self.pause_btn = _icon_button("media-playback-pause-symbolic", "Pause")
        self.pause_btn.connect("clicked", self._on_pause_clicked)
        self.pause_btn.set_no_show_all(True)
        self.pause_btn.set_visible(False)
        status_row.pack_end(self.pause_btn, False, False, 0)

        self.logs_btn = _icon_button("pan-down-symbolic", "Show logs")
        self.logs_btn.connect("clicked", self._on_logs_toggled)
        status_row.pack_end(self.logs_btn, False, False, 0)

        self.cancel_btn = _icon_button("window-close-symbolic", "Cancel")
        self.cancel_btn.connect("clicked", self._on_cancel_clicked)
        status_row.pack_end(self.cancel_btn, False, False, 0)

        self.retry_btn = _icon_button("view-refresh-symbolic", "Retry")
        self.retry_btn.connect("clicked", self._on_retry_clicked)
        self.retry_btn.set_no_show_all(True)
        self.retry_btn.set_visible(False)
        status_row.pack_end(self.retry_btn, False, False, 0)

        self.pack_start(status_row, False, False, 0)

        self.logs_revealer = Gtk.Revealer()
        scroller = Gtk.ScrolledWindow()
        scroller.set_min_content_height(80)
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.logs_view = Gtk.TextView()
        self.logs_view.set_editable(False)
        self.logs_view.set_monospace(True)
        self.logs_buffer = self.logs_view.get_buffer()
        self._logs_end_mark = self.logs_buffer.create_mark(
            "end", self.logs_buffer.get_end_iter(), False
        )
        scroller.add(self.logs_view)
        self.logs_revealer.add(scroller)
        self.pack_start(self.logs_revealer, False, False, 0)

        self.show_all()
        self.progress.set_visible(False)
        self.pause_btn.set_visible(False)

        if preprobed_task is not None:
            self._on_probe_done()
            if not skip_quality_sizes:
                threading.Thread(target=self._fetch_quality_sizes, daemon=True).start()
        else:
            threading.Thread(target=self._probe, daemon=True).start()

    def _probe(self):
        try:
            self.task.probe()
        except RuntimeError as e:
            GLib.idle_add(self._on_probe_error, str(e))
            return
        GLib.idle_add(self._on_probe_done)
        self._fetch_quality_sizes()

    def _fetch_quality_sizes(self):
        info = fetch_video_info(self.task.url, self.task._cookie_args())
        formats, duration = info["formats"], info["duration"]
        if not formats:
            return
        video_sizes = estimate_quality_sizes(formats)
        video_text = {tier: _fmt_size(b) for tier, b in video_sizes.items()}
        GLib.idle_add(self.quality_bar.set_video_quality_sizes, video_text)
        audio_sizes = estimate_audio_quality_sizes(duration, formats)
        audio_text = {tier: _fmt_size(b) for tier, b in audio_sizes.items()}
        GLib.idle_add(self.quality_bar.set_audio_quality_sizes, audio_text)

    def _on_probe_error(self, message):
        self.title_label.set_text(f"⚠ {message}")
        self.start_btn.set_visible(False)
        return False

    def _on_probe_done(self):
        self.title_label.set_text(self.task.title or "Untitled")
        size = self.task.size_str or ""
        self.status_label.set_text(size)
        self.start_btn.set_visible(True)
        return False

    def _on_start_clicked(self, _btn):
        mode, fmt, quality = self.quality_bar.get_selection()
        self.task.mode = mode
        if mode == "video":
            self.task.video_format = fmt
            self.task.video_quality = quality
        else:
            self.task.audio_format = fmt
            self.task.audio_quality = quality

        self._started = True
        self.quality_bar.set_sensitive_all(False)
        self.start_btn.set_visible(False)
        self.progress.set_visible(True)
        self.pause_btn.set_visible(True)
        self.status_label.set_text("Starting...")

        threading.Thread(target=self._run_download, daemon=True).start()

    def _run_download(self):
        def on_progress(info):
            GLib.idle_add(self._on_progress, info)

        def on_finished(success, message):
            GLib.idle_add(self._on_finished, success, message)

        self.task.start(on_progress, on_finished)

    def _on_progress(self, info):
        self.progress.set_fraction(min(info["percent"] / 100.0, 1.0))
        parts = [f"{info['percent']:.0f}%"] + [
            p for p in (info.get("size"), info.get("speed"), info.get("eta") and f"ETA {info['eta']}") if p
        ]
        self.status_label.set_text("  ·  ".join(parts))
        self._append_log(self.task.log_lines[-1] if self.task.log_lines else "")
        return False

    def _on_finished(self, success, message):
        self.pause_btn.set_visible(False)
        if success:
            self.progress.set_fraction(1.0)
            self.status_label.set_text("Complete")
            self.cancel_btn.set_visible(False)
            self.on_state_change(self, "completed")
        else:
            self.status_label.set_text(f"Failed: {message.splitlines()[-1] if message else 'error'}")
            self.progress.get_style_context().add_class("error")
            if message != "Cancelled":
                self.retry_btn.set_visible(True)
        return False

    def _on_retry_clicked(self, _btn):
        """Re-runs the same download from scratch with the same
        format/quality that was already selected -- resets the task's
        internal state (a DownloadTask isn't designed to reuse a dead
        process handle) rather than creating a new row."""
        self.retry_btn.set_visible(False)
        self.progress.get_style_context().remove_class("error")
        self.progress.set_fraction(0.0)
        self.status_label.set_text("Retrying...")
        self.cancel_btn.set_visible(True)
        self.pause_btn.set_visible(True)

        # DownloadTask.start() resets paused/cancelled/log_lines itself.
        self.task.process = None

        threading.Thread(target=self._run_download, daemon=True).start()

    def _on_pause_clicked(self, _btn):
        if not self.task.paused:
            if self.task.pause():
                self._set_pause_icon("media-playback-start-symbolic", "Resume")
                self.status_label.set_text("Paused")
            else:
                # Previously this failed silently -- the button just
                # wouldn't change, with no indication why. Surface it
                # instead, since a stale process reference or a
                # just-finished download are the likely causes.
                self.status_label.set_text("Couldn't pause (already finished or unavailable)")
        else:
            resumed = self.task.resume()
            if not resumed:
                threading.Thread(target=self._run_download, daemon=True).start()
            self._set_pause_icon("media-playback-pause-symbolic", "Pause")

    def _set_pause_icon(self, icon_name, tooltip):
        _set_button_icon(self.pause_btn, icon_name)
        self.pause_btn.set_tooltip_text(tooltip)

    def _on_cancel_clicked(self, _btn):
        self.task.cancel()
        self.on_state_change(self, "removed")

    def _on_logs_toggled(self, _btn):
        revealed = not self.logs_revealer.get_reveal_child()
        self.logs_revealer.set_reveal_child(revealed)
        icon_name = "pan-up-symbolic" if revealed else "pan-down-symbolic"
        _set_button_icon(self.logs_btn, icon_name)

    def _append_log(self, line):
        if not line:
            return
        end_iter = self.logs_buffer.get_end_iter()
        self.logs_buffer.insert(end_iter, line + "\n")
        self.logs_buffer.move_mark(self._logs_end_mark, self.logs_buffer.get_end_iter())
        self.logs_view.scroll_to_mark(self._logs_end_mark, 0.0, False, 0.0, 0.0)


class PlaylistRow(Gtk.Box):
    """A playlist: shared quality controls + sequential child downloads."""

    def __init__(self, url, settings, on_state_change, entries, playlist_title):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.get_style_context().add_class("download-row")

        self.settings = settings
        self.on_state_change = on_state_change
        self.entries = entries
        self.cancelled = False
        self.current_task = None
        self.current_idx = None
        # Per-entry "hold" flags: a video marked held is skipped by the
        # runner even once its turn comes up, until un-held. This is what
        # lets you pause a video BEFORE it starts downloading, not just the
        # one currently in progress.
        self.held = [False] * len(entries)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.expand_btn = _icon_button("pan-down-symbolic")
        self.expand_btn.connect("clicked", self._on_expand_toggled)
        header.pack_start(self.expand_btn, False, False, 0)

        title_label = Gtk.Label(label=playlist_title)
        title_label.get_style_context().add_class("title")
        title_label.set_xalign(0)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        header.pack_start(title_label, True, True, 0)

        self.count_label = Gtk.Label(label=f"0 / {len(entries)}")
        self.count_label.get_style_context().add_class("count-badge")
        header.pack_start(self.count_label, False, False, 0)

        self.pause_btn = _icon_button("media-playback-pause-symbolic", "Pause current video")
        self.pause_btn.connect("clicked", self._on_pause_clicked)
        self.pause_btn.set_no_show_all(True)
        self.pause_btn.set_visible(False)
        header.pack_start(self.pause_btn, False, False, 0)

        self.cancel_btn = _icon_button("process-stop-symbolic", "Cancel playlist")
        self.cancel_btn.connect("clicked", self._on_cancel_clicked)
        self.cancel_btn.set_no_show_all(True)
        self.cancel_btn.set_visible(False)
        header.pack_start(self.cancel_btn, False, False, 0)

        self.pack_start(header, False, False, 0)

        self.quality_bar = ModeQualityBar(settings)
        self.pack_start(self.quality_bar, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(False)
        self.pack_start(self.progress, False, False, 0)

        self.current_status_label = Gtk.Label(label="")
        self.current_status_label.get_style_context().add_class("status-text")
        self.current_status_label.set_xalign(0)
        self.current_status_label.get_style_context().add_class("dim-label")
        self.pack_start(self.current_status_label, False, False, 0)

        start_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.start_btn = Gtk.Button(label="Start Playlist")
        self.start_btn.get_style_context().add_class("suggested-action")
        self.start_btn.connect("clicked", self._on_start_clicked)
        start_row.pack_end(self.start_btn, False, False, 0)
        self.pack_start(start_row, False, False, 0)

        self.child_revealer = Gtk.Revealer()
        self.child_revealer.set_reveal_child(True)
        child_box_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        child_box_outer.set_margin_top(6)

        child_scroller = Gtk.ScrolledWindow()
        child_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        child_scroller.set_min_content_height(180)
        child_scroller.set_max_content_height(320)
        child_scroller.set_propagate_natural_height(True)

        self.child_list = Gtk.ListBox()
        self.child_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.child_rows = []
        for idx, entry in enumerate(entries):
            self.child_rows.append(self._make_child_row(idx, entry["title"], "Queued"))
        for row in self.child_rows:
            self.child_list.add(row)
        child_scroller.add(self.child_list)
        child_box_outer.pack_start(child_scroller, False, False, 0)

        self.child_revealer.add(child_box_outer)
        self.pack_start(self.child_revealer, False, False, 0)

        self.show_all()
        self.cookies_file = settings["cookies_file"] if settings.get("use_cookies") else None
        threading.Thread(target=self._fetch_quality_sizes, daemon=True).start()

    def _fetch_quality_sizes(self):
        cookie_args = ["--cookies", self.cookies_file] if self.cookies_file and os.path.isfile(self.cookies_file) else []
        SAMPLE_CAP = 8
        sample = self.entries[:SAMPLE_CAP]
        per_video_video_sizes = []
        per_video_audio_sizes = []
        for entry in sample:
            info = fetch_video_info(entry["url"], cookie_args)
            formats, duration = info["formats"], info["duration"]
            if formats:
                per_video_video_sizes.append(estimate_quality_sizes(formats))
                per_video_audio_sizes.append(estimate_audio_quality_sizes(duration, formats))

        if not per_video_video_sizes:
            return

        is_estimate = len(self.entries) > SAMPLE_CAP
        scale = (len(self.entries) / len(sample)) if is_estimate else 1

        video_summed = sum_quality_sizes(per_video_video_sizes)
        video_text = {}
        for tier, v in video_summed.items():
            if not v:
                continue
            scaled = int(v * scale)
            text = _fmt_size(scaled)
            video_text[tier] = f"~{text}" if is_estimate else text
        GLib.idle_add(self.quality_bar.set_video_quality_sizes, video_text)

        audio_summed = sum_quality_sizes(per_video_audio_sizes, tiers=AUDIO_QUALITY_TIERS)
        audio_text = {}
        for tier, v in audio_summed.items():
            if not v:
                continue
            scaled = int(v * scale)
            text = _fmt_size(scaled)
            audio_text[tier] = f"~{text}" if is_estimate else text
        GLib.idle_add(self.quality_bar.set_audio_quality_sizes, audio_text)

    def _make_child_row(self, idx, title, status):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("media-record-symbolic", Gtk.IconSize.MENU)
        box.pack_start(icon, False, False, 0)
        label = Gtk.Label(label=title)
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        box.pack_start(label, True, True, 0)
        status_label = Gtk.Label(label=status)
        box.pack_start(status_label, False, False, 0)

        # Visible from the start, not just once this video is actively
        # downloading -- lets you mark any queued video to hold before its
        # turn even comes up, instead of having to catch it right as it
        # starts.
        pause_btn = _icon_button("media-playback-pause-symbolic", "Pause / hold this video")
        pause_btn.connect("clicked", self._on_child_pause_clicked, idx)
        box.pack_start(pause_btn, False, False, 0)

        retry_btn = _icon_button("view-refresh-symbolic", "Retry this video")
        retry_btn.connect("clicked", self._on_child_retry_clicked, idx)
        retry_btn.set_no_show_all(True)
        retry_btn.set_visible(False)
        box.pack_start(retry_btn, False, False, 0)

        row.add(box)
        row._icon = icon
        row._status_label = status_label
        row._pause_btn = pause_btn
        row._retry_btn = retry_btn
        row._status_state = "queued"
        return row

    def _on_expand_toggled(self, _btn):
        revealed = not self.child_revealer.get_reveal_child()
        self.child_revealer.set_reveal_child(revealed)
        icon_name = "pan-up-symbolic" if revealed else "pan-down-symbolic"
        _set_button_icon(self.expand_btn, icon_name)

    def _on_start_clicked(self, _btn):
        mode, fmt, quality = self.quality_bar.get_selection()
        self._mode, self._fmt, self._quality = mode, fmt, quality
        self.quality_bar.set_sensitive_all(False)
        self.start_btn.set_visible(False)
        self.pause_btn.set_visible(True)
        self.cancel_btn.set_visible(True)
        threading.Thread(target=self._run_playlist, daemon=True).start()

    def _run_playlist(self):
        total = len(self.entries)
        completed = 0
        pending = list(range(total))

        while pending:
            if self.cancelled:
                break

            # Skip over any held videos -- if EVERY remaining video is
            # held, wait and recheck periodically (the user might un-hold
            # one at any time).
            next_i = None
            for i in pending:
                if not self.held[i]:
                    next_i = i
                    break
            if next_i is None:
                time.sleep(0.5)
                continue

            pending.remove(next_i)
            i = next_i
            entry = self.entries[i]

            task = DownloadTask(
                entry["url"],
                self.settings["download_dir"],
                self.settings["cookies_file"] if self.settings.get("use_cookies") else None,
            )
            task.mode = self._mode
            if self._mode == "video":
                task.video_format = self._fmt
                task.video_quality = self._quality
            else:
                task.audio_format = self._fmt
                task.audio_quality = self._quality
            self.current_task = task
            self.current_idx = i

            if i < len(self.child_rows):
                GLib.idle_add(self._set_child_status, i, "downloading", 0)

            def on_progress(info, idx=i):
                GLib.idle_add(self._on_child_progress, idx, info)

            task.start(on_progress, lambda s, m: None)

            # A cancel signal either came in while this child was still
            # queued (loop broke above) or stopped the in-flight task --
            # mark the current child "cancelled" rather than "failed".
            success = (not self.cancelled) and task.process and task.process.returncode == 0
            if i < len(self.child_rows):
                if self.cancelled:
                    GLib.idle_add(self._set_child_status, i, "cancelled", 100)
                else:
                    GLib.idle_add(self._set_child_status, i, "done" if success else "failed", 100)
            if success:
                completed += 1
            self.current_task = None
            self.current_idx = None
            GLib.idle_add(self._on_overall_progress, completed, total)

        GLib.idle_add(self._on_playlist_finished, completed, total, self.cancelled)

    def _set_child_status(self, idx, status, percent):
        row = self.child_rows[idx]
        row._status_state = status
        icon_name = {
            "queued": "media-record-symbolic",
            "held": "media-playback-pause-symbolic",
            "downloading": "media-playback-start-symbolic",
            "done": "emblem-ok-symbolic",
            "failed": "dialog-error-symbolic",
            "cancelled": "process-stop-symbolic",
        }.get(status, "media-record-symbolic")
        _set_image_icon(row._icon, icon_name)
        text = {
            "queued": "Queued", "held": "Held", "downloading": "Downloading...",
            "done": "Done", "failed": "Failed", "cancelled": "Cancelled",
        }.get(status, status)
        row._status_label.set_text(text)
        # A finished row has nothing left to pause -- disable rather than
        # leave a dead button that looks clickable but does nothing.
        row._pause_btn.set_sensitive(status not in ("done", "failed", "cancelled"))
        row._retry_btn.set_visible(status == "failed")
        return False

    def _on_child_retry_clicked(self, _btn, idx):
        """Retries just this one video independently -- the main sequential
        runner has already moved past this index by the time it's failed,
        so this spins up its own one-off DownloadTask rather than trying
        to re-insert it into the already-running queue."""
        if self.cancelled:
            return
        if idx >= len(self.entries):
            return
        entry = self.entries[idx]
        row = self.child_rows[idx]
        row._retry_btn.set_visible(False)

        task = DownloadTask(
            entry["url"],
            self.settings["download_dir"],
            self.settings["cookies_file"] if self.settings.get("use_cookies") else None,
        )
        task.mode = self._mode
        if self._mode == "video":
            task.video_format = self._fmt
            task.video_quality = self._quality
        else:
            task.audio_format = self._fmt
            task.audio_quality = self._quality

        GLib.idle_add(self._set_child_status, idx, "downloading", 0)
        threading.Thread(target=self._run_single_retry, args=(task, idx), daemon=True).start()

    def _run_single_retry(self, task, idx):
        def on_progress(info, i=idx):
            GLib.idle_add(self._on_child_progress, i, info)

        task.start(on_progress, lambda s, m: None)
        success = task.process and task.process.returncode == 0
        GLib.idle_add(self._set_child_status, idx, "done" if success else "failed", 100)
        if success:
            GLib.idle_add(self._on_retry_success_bump)

    def _on_retry_success_bump(self):
        """A retried video succeeding after the playlist already finished
        should still count toward the total shown -- bump the completed
        count so it doesn't look stuck at the old number."""
        current_text = self.count_label.get_text()
        try:
            done, total = current_text.split("/")
            done = int(done.strip()) + 1
            total = int(total.strip())
            self.count_label.set_text(f"{done} / {total}")
            self.progress.set_fraction(done / total if total else 0)
        except (ValueError, ZeroDivisionError):
            pass
        return False

    def _on_child_progress(self, idx, info):
        parts = [f"{info['percent']:.0f}%"]
        if info.get("speed"):
            parts.append(info["speed"])
        if info.get("eta"):
            parts.append(f"ETA {info['eta']}")
        detail = "  ·  ".join(parts)

        if idx < len(self.child_rows):
            self.child_rows[idx]._status_label.set_text(detail)

        if idx < len(self.entries):
            title = self.entries[idx]["title"]
            self.current_status_label.set_text(f"Now downloading: {title}  —  {detail}")
        return False

    def _on_overall_progress(self, completed, total):
        self.count_label.set_text(f"{completed} / {total}")
        self.progress.set_fraction(completed / total if total else 0)
        return False

    def _on_playlist_finished(self, completed, total, cancelled=False):
        self.pause_btn.set_visible(False)
        self.cancel_btn.set_visible(False)
        if cancelled:
            self.current_status_label.set_text(f"Cancelled: {completed}/{total} downloaded")
        else:
            self.current_status_label.set_text(f"Finished: {completed}/{total} downloaded")
        if not cancelled and completed == total:
            self.on_state_change(self, "completed")
        return False

    def _on_cancel_clicked(self, _btn):
        """Stops the whole playlist: halts the runner (it breaks out of the
        queue loop) and cancels whichever child is mid-download so the
        blocking task.start() returns immediately."""
        self.cancelled = True
        if self.current_task is not None:
            self.current_task.cancel()
        self.cancel_btn.set_sensitive(False)

    def _toggle_current_pause(self):
        """Pauses/resumes whichever video is ACTIVELY downloading right
        now -- shared by the header pause button and that video's own row
        button, so both stay in sync no matter which one triggered it."""
        if not self.current_task:
            return
        if not self.current_task.paused:
            if self.current_task.pause():
                self._set_all_pause_icons("media-playback-start-symbolic")
            else:
                self.current_status_label.set_text("Couldn't pause (already finished or unavailable)")
        else:
            resumed = self.current_task.resume()
            if not resumed:
                threading.Thread(target=self._run_download_current, daemon=True).start()
            self._set_all_pause_icons("media-playback-pause-symbolic")

    def _toggle_hold(self, idx):
        """Marks a not-yet-started video to be skipped by the runner when
        its turn comes up, without waiting for it to actually start first.
        This is the difference from _toggle_current_pause: that one signals
        a live process; this one just flags an entry the runner hasn't
        reached yet."""
        if idx >= len(self.entries) or idx >= len(self.child_rows):
            return
        row = self.child_rows[idx]
        if getattr(row, "_status_state", "queued") in ("done", "failed"):
            return  # nothing to hold on a finished row

        self.held[idx] = not self.held[idx]
        if self.held[idx]:
            self._set_child_status(idx, "held", 0)
            _set_button_icon(row._pause_btn, "media-playback-start-symbolic")
        else:
            self._set_child_status(idx, "queued", 0)
            _set_button_icon(row._pause_btn, "media-playback-pause-symbolic")

    def _on_pause_clicked(self, _btn):
        self._toggle_current_pause()

    def _on_child_pause_clicked(self, _btn, idx):
        if idx == self.current_idx and self.current_task is not None:
            # This row is the one actually downloading right now -- pause
            # the real process.
            self._toggle_current_pause()
        else:
            # Not started yet (or already finished, guarded inside) --
            # just flag it to be skipped/held when its turn comes up.
            self._toggle_hold(idx)

    def _run_download_current(self):
        # Safety-net restart if SIGCONT failed (e.g. stale connection).
        if self.current_task:
            self.current_task.start(lambda info: None, lambda s, m: None)

    def _set_all_pause_icons(self, icon_name):
        _set_button_icon(self.pause_btn, icon_name)
        if self.current_idx is not None and self.current_idx < len(self.child_rows):
            _set_button_icon(self.child_rows[self.current_idx]._pause_btn, icon_name)
