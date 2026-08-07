import re
import threading
import webbrowser

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from . import __version__
from . import config as config_module
from . import dependencies
from . import icons
from . import style
from . import updater
from .download_task import DownloadTask
from .row_widgets import LoadingRow, PlaylistRow, VideoRow, _icon_theme_has
from .settings_view import SettingsView

APP_TITLE = "Simple YT Downloader"

# Splits pasted text on any run of whitespace (including newlines) or
# commas, so it doesn't matter whether the user pastes multiple links each
# on their own line, comma-separated, or space-separated -- all of those
# come through a single-line Gtk.Entry in slightly different mangled forms
# depending on the clipboard source, so we're deliberately permissive here.
_URL_SPLIT_RE = re.compile(r"[\s,]+")


def _format_bytes(num):
    """Human-friendly size for the download progress label."""
    if not num:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024
    return f"{num:.1f} GB"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_TITLE)
        icons.register_bundled_icons()
        self._set_safe_default_size()

        self.settings = config_module.load()
        self._apply_theme(self.settings.get("theme", "dark"))
        style.apply()

        self._pending_update_info = None
        self._dl_dialog = None
        self._dl_bar = None
        self._dl_label = None
        self._install_dialog = None

        self.tab_stack = Gtk.Stack()
        self._build_headerbar()

        self.root_stack = Gtk.Stack()
        self.root_stack.set_hhomogeneous(False)
        self.root_stack.set_vhomogeneous(False)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.pack_start(self.headerbar, False, False, 0)
        outer.pack_start(self.root_stack, True, True, 0)
        self.add(outer)

        self.main_view = self._build_main_view()
        self.root_stack.add_named(self.main_view, "main")

        self.settings_view = None  # built lazily each time it's opened

        self.show_all()

        GLib.idle_add(self._maybe_run_first_time_setup)

    # ---- Window sizing ------------------------------------------------

    def _set_safe_default_size(self):
        """Picks a default window size that's comfortable but never taller
        than the actual screen -- a fixed default previously caused the
        window (and anything pinned to its bottom, like the download path
        bar) to render partly off-screen on smaller displays."""
        self.set_size_request(560, 460)
        try:
            from gi.repository import Gdk
            screen = Gdk.Screen.get_default()
            monitor = screen.get_display().get_monitor(0) if screen else None
            if monitor:
                geometry = monitor.get_workarea()
                screen_w, screen_h = geometry.width, geometry.height
            else:
                screen_w, screen_h = 1280, 800
        except Exception:
            screen_w, screen_h = 1280, 800

        width = min(700, int(screen_w * 0.75))
        height = min(640, int(screen_h * 0.80))
        self.set_default_size(width, height)

    # ---- Window top bar --------------------------------------------------

    def _build_headerbar(self):
        # A slim in-window bar holding the tab switcher plus the update
        # check, theme and settings buttons. The window manager draws the
        # close/minimize/maximize buttons in the user's system theme (no
        # set_titlebar() / CSD), so there's only ONE title bar -- not a
        # Gtk.HeaderBar, which would render a second bar.
        self.headerbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.headerbar.set_margin_top(6)
        self.headerbar.set_margin_start(12)
        self.headerbar.set_margin_end(10)

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.tab_stack)
        switcher.set_valign(Gtk.Align.CENTER)
        self.headerbar.pack_start(switcher, False, False, 0)

        self.theme_btn = Gtk.Button()
        self.theme_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.theme_btn.get_style_context().add_class("headerbar-btn")
        self._update_theme_icon()
        self.theme_btn.connect("clicked", self._on_theme_button_clicked)
        self.headerbar.pack_end(self.theme_btn, False, False, 0)

        settings_btn = Gtk.Button()
        settings_btn.set_relief(Gtk.ReliefStyle.NONE)
        settings_btn.get_style_context().add_class("headerbar-btn")
        settings_btn.add(Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON))
        settings_btn.connect("clicked", lambda _b: self._open_settings())
        self.headerbar.pack_end(settings_btn, False, False, 0)

        self.update_btn = Gtk.Button()
        self.update_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.update_btn.get_style_context().add_class("headerbar-btn")
        self.update_btn.set_valign(Gtk.Align.CENTER)
        self.update_btn.add(Gtk.Image.new_from_icon_name(
            "software-update-available-symbolic", Gtk.IconSize.BUTTON))
        self.update_btn.set_tooltip_text("Check for Updates")
        self.update_btn.connect("clicked", self._on_check_updates)
        self.headerbar.pack_end(self.update_btn, False, False, 0)

    def _update_theme_icon(self):
        theme = self.settings.get("theme", "dark")
        icon = "weather-clear-symbolic" if theme == "light" else "weather-clear-night-symbolic"
        child = self.theme_btn.get_child()
        if child:
            self.theme_btn.remove(child)
        self.theme_btn.add(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
        self.theme_btn.show_all()

    # ---- Update check (async) ------------------------------------------

    def _on_check_updates(self, _btn):
        self.update_btn.set_sensitive(False)

        def worker():
            info = updater.fetch_latest_release()
            GLib.idle_add(self._on_update_check_done, info)

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_check_done(self, info):
        self.update_btn.set_sensitive(True)

        if info is None:
            self._show_info_dialog(
                "Check Failed",
                "Could not reach the update server. Please check your connection.",
                message_type=Gtk.MessageType.ERROR,
            )
            return False

        if updater.version_tuple(info["version"]) > updater.version_tuple(__version__):
            dialog = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,
                text=f"Update available: v{info['version']}",
            )
            dialog.format_secondary_text(
                f"You are running v{__version__}.\n\n"
                "Download the latest release now, or open the release page instead."
            )
            dialog.add_button("Later", Gtk.ResponseType.CLOSE)
            open_btn = dialog.add_button("Open Release Page", Gtk.ResponseType.NO)
            dl_btn = dialog.add_button("Download & Install", Gtk.ResponseType.YES)
            dl_btn.get_style_context().add_class("suggested-action")
            response = dialog.run()
            dialog.destroy()
            if response == Gtk.ResponseType.YES:
                self._start_update_download(info)
            elif response == Gtk.ResponseType.NO:
                webbrowser.open(info["release_url"])
        else:
            self._show_info_dialog(
                "Up to date",
                f"You are running the latest version (v{__version__}).",
            )
        return False

    def _start_update_download(self, info):
        """Begin streaming the .deb in the background; show a progress dialog."""
        self._pending_update_info = info
        version = info["version"]
        deb_path = updater.deb_path(version)
        dialog = Gtk.Dialog(
            title=f"Downloading v{version}...",
            transient_for=self,
            modal=True,
        )
        dialog.get_content_area().set_spacing(10)
        bar = Gtk.ProgressBar()
        bar.set_show_text(True)
        bar.set_text("Starting download...")
        dialog.get_content_area().pack_start(bar, False, False, 0)
        label = Gtk.Label(label="")
        label.set_justify(Gtk.Justification.CENTER)
        label.set_line_wrap(True)
        dialog.get_content_area().pack_start(label, False, False, 0)
        dialog.show_all()
        self._dl_dialog = dialog
        self._dl_bar = bar
        self._dl_label = label

        def worker():
            def on_progress(downloaded, total):
                def update_ui():
                    if self._dl_bar is None:
                        return False
                    if total:
                        self._dl_bar.set_fraction(downloaded / total if total else 0)
                        self._dl_bar.set_text(
                            f"{_format_bytes(downloaded)} / {_format_bytes(total)}"
                        )
                    else:
                        self._dl_bar.pulse()
                        self._dl_bar.set_text(_format_bytes(downloaded))
                    return False

                GLib.idle_add(update_ui)

            try:
                updater.download(info["deb_url"], deb_path, on_progress)
            except updater.DownloadAborted:
                GLib.idle_add(self._on_update_download_done, False, "Download cancelled.")
                return
            except updater.DownloadError as e:
                GLib.idle_add(self._on_update_download_done, False, str(e))
                return
            except OSError as e:
                GLib.idle_add(self._on_update_download_done, False, str(e))
                return
            GLib.idle_add(self._on_update_download_done, True, "")

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_download_done(self, success, message):
        dialog, self._dl_dialog = self._dl_dialog, None
        self._dl_bar = None
        self._dl_label = None
        if dialog is not None:
            dialog.destroy()

        if not success:
            self._show_info_dialog(
                "Download failed",
                message or "Could not download the update.",
                message_type=Gtk.MessageType.ERROR,
            )
            return False

        self._start_install()

    def _start_install(self):
        """Run apt-get via pkexec; the native polkit prompt is shown by pkexec."""
        info = self._pending_update_info
        if info is None:
            self._show_info_dialog(
                "Download failed",
                "The update file could not be located after download.",
                message_type=Gtk.MessageType.ERROR,
            )
            return

        dialog = Gtk.Dialog(
            title="Installing update...",
            transient_for=self,
            modal=True,
        )
        dialog.get_content_area().set_spacing(10)
        bar = Gtk.Spinner()
        bar.start()
        dialog.get_content_area().pack_start(bar, False, False, 0)
        label = Gtk.Label(
            label="Installing via your system password prompt.\n"
            "The app will close when the update is complete."
        )
        label.set_justify(Gtk.Justification.CENTER)
        label.set_line_wrap(True)
        dialog.get_content_area().pack_start(label, False, False, 0)
        dialog.show_all()
        self._install_dialog = dialog

        deb_path = updater.deb_path(info["version"])

        def worker():
            def on_done(success, message):
                GLib.idle_add(self._on_install_done, success, message, deb_path)

            updater.install(deb_path, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_install_done(self, success, message, deb_path):
        updater.cleanup(deb_path)
        dialog, self._install_dialog = self._install_dialog, None
        if dialog is not None:
            dialog.destroy()

        if success:
            self._show_info_dialog(
                "Update complete",
                message + "\nPlease restart the app to use the new version.",
            )
        else:
            self._show_info_dialog(
                "Install failed",
                message,
                message_type=Gtk.MessageType.ERROR,
            )
        return False

    def _show_info_dialog(self, title, message, message_type=Gtk.MessageType.INFO):
        if message_type is None:
            message_type = (
                Gtk.MessageType.ERROR if title == "Installation failed" else Gtk.MessageType.INFO
            )
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=message_type,
            buttons=Gtk.ButtonsType.OK, text=title,
        )
        dialog.format_secondary_text(message[:500])
        dialog.run()
        dialog.destroy()

    def _on_theme_button_clicked(self, _btn):
        current = self.settings.get("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        self.settings["theme"] = new_theme
        config_module.save(self.settings)
        self._apply_theme(new_theme)
        self._update_theme_icon()

    def _apply_theme(self, theme):
        """Forces the actual GTK widget theme to Adwaita for Light/Dark, since
        Linux Mint's default Mint-Y theme family doesn't respond to the
        'prefer dark theme' flag the way Adwaita does -- Mint-Y and
        Mint-Y-Dark are two separate named themes, not one theme with a
        toggle. Setting gtk-application-prefer-dark-theme alone silently did
        nothing on Mint, which is why the toggle previously looked broken.

        Adwaita ships as part of GTK3 itself (a dependency of libgtk-3-0),
        so it's guaranteed present regardless of the user's desktop theme.
        """
        gtk_settings = Gtk.Settings.get_default()
        if theme == "dark":
            gtk_settings.set_property("gtk-theme-name", "Adwaita")
            gtk_settings.set_property("gtk-application-prefer-dark-theme", True)
        else:  # light
            gtk_settings.set_property("gtk-theme-name", "Adwaita")
            gtk_settings.set_property("gtk-application-prefer-dark-theme", False)
        style.reload()

    # ---- Main view (tabs + add bar + row lists) ---------------------------

    def _build_main_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)

        add_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        add_label = Gtk.Label(label="Paste one or more links (one per line, or space/comma separated)")
        add_label.set_xalign(0)
        add_label.get_style_context().add_class("caption")
        add_section.pack_start(add_label, False, False, 0)

        add_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        url_scroller = Gtk.ScrolledWindow()
        url_scroller.set_shadow_type(Gtk.ShadowType.NONE)
        url_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # Tall enough to show 2-3 lines at once, so pasting several URLs is
        # visibly obvious rather than looking like a single-line entry that
        # silently accepted multiple links.
        url_scroller.set_min_content_height(64)
        url_scroller.set_max_content_height(120)

        self.url_view = Gtk.TextView()
        self.url_view.set_wrap_mode(Gtk.WrapMode.CHAR)
        self.url_view.get_style_context().add_class("url-input")
        self.url_buffer = self.url_view.get_buffer()
        url_scroller.add(self.url_view)
        add_row.pack_start(url_scroller, True, True, 0)

        add_btn = Gtk.Button(label="Add")
        add_btn.get_style_context().add_class("suggested-action")
        add_btn.connect("clicked", self._on_add_clicked)
        add_btn.set_valign(Gtk.Align.CENTER)
        add_row.pack_start(add_btn, False, False, 0)
        add_section.pack_start(add_row, False, False, 0)

        self.add_section = add_section
        box.pack_start(add_section, False, False, 0)

        self.ongoing_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.completed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        ongoing_stack = self._rows_stack(
            self.ongoing_box,
            "folder-download-symbolic",
            "No downloads yet",
            "Paste one or more YouTube links above to get started.",
        )
        self._ongoing_stack = ongoing_stack

        ongoing_scroller = Gtk.ScrolledWindow()
        ongoing_scroller.add(ongoing_stack)

        completed_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        clear_all_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        clear_all_btn = Gtk.Button(label="Clear All")
        clear_all_btn.set_no_show_all(True)
        clear_all_btn.set_visible(False)
        clear_all_btn.connect("clicked", self._on_clear_completed)
        clear_all_row.pack_end(clear_all_btn, False, False, 0)
        completed_page.pack_start(clear_all_row, False, False, 0)

        completed_stack = self._rows_stack(
            self.completed_box,
            "emblem-ok-symbolic",
            "Nothing here yet",
            "Finished and cancelled downloads will appear here.",
        )
        self._completed_stack = completed_stack

        completed_scroller = Gtk.ScrolledWindow()
        completed_scroller.add(completed_stack)
        completed_page.pack_start(completed_scroller, True, True, 0)

        self.tab_stack.add_titled(ongoing_scroller, "ongoing", "Ongoing")
        self.tab_stack.add_titled(completed_page, "completed", "Completed")
        box.pack_start(self.tab_stack, True, True, 0)

        self.tab_stack.connect("notify::visible-child-name", self._on_tab_switched)

        box.pack_start(self._build_download_path_bar(), False, False, 0)

        self.clear_all_btn = clear_all_btn
        self._update_ongoing_empty()
        self._update_completed_empty()

        return box

    def _on_tab_switched(self, stack, _pspec=None):
        """Paste-input section is Ongoing-only; hide it on Completed."""
        self.add_section.set_visible(stack.get_visible_child_name() == "ongoing")

    def _rows_stack(self, rows_box, icon_name, title, hint):
        """Swaps an empty-state placeholder in and out based on whether the
        given list has rows. Keeping the stack non-homogeneous means the
        list page keeps its natural height instead of being forced to match
        the empty placeholder (and vice versa)."""
        stack = Gtk.Stack()
        stack.set_hhomogeneous(False)
        stack.set_vhomogeneous(False)
        stack.add_named(self._empty_state(icon_name, title, hint), "empty")
        stack.add_named(rows_box, "list")
        return stack

    def _empty_state(self, icon_name, title, hint):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("empty-state")
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name(
            icon_name if _icon_theme_has(icon_name) else "image-missing",
            Gtk.IconSize.DIALOG,
        )
        box.pack_start(icon, False, False, 0)

        title_label = Gtk.Label(label=title)
        title_label.get_style_context().add_class("empty-title")
        box.pack_start(title_label, False, False, 0)

        hint_label = Gtk.Label(label=hint)
        hint_label.get_style_context().add_class("empty-hint")
        box.pack_start(hint_label, False, False, 0)
        return box

    def _update_ongoing_empty(self):
        has_rows = len(self.ongoing_box.get_children()) > 0
        self._ongoing_stack.set_visible_child_name("list" if has_rows else "empty")
        return False

    def _update_completed_empty(self):
        has_rows = len(self.completed_box.get_children()) > 0
        self._completed_stack.set_visible_child_name("list" if has_rows else "empty")
        self.clear_all_btn.set_visible(has_rows)
        return False

    def _on_clear_completed(self, _btn):
        for child in list(self.completed_box.get_children()):
            self.completed_box.remove(child)
        self._update_completed_empty()

    def _build_download_path_bar(self):
        """Download folder picker pinned to the bottom of the main window,
        so it's changeable in one click without going into Settings."""
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.get_style_context().add_class("download-row")
        bar.get_style_context().add_class("path-bar")

        icon = Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.BUTTON)
        bar.pack_start(icon, False, False, 0)

        self.path_label = Gtk.Label(label=self.settings.get("download_dir", ""))
        self.path_label.set_xalign(0)
        self.path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        bar.pack_start(self.path_label, True, True, 0)

        change_btn = Gtk.Button(label="Change")
        change_btn.connect("clicked", self._on_change_download_path)
        bar.pack_start(change_btn, False, False, 0)

        return bar

    def _on_change_download_path(self, _btn):
        dialog = Gtk.FileChooserDialog(
            title="Choose download folder", parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        dialog.set_filename(self.settings.get("download_dir", ""))
        if dialog.run() == Gtk.ResponseType.OK:
            new_path = dialog.get_filename()
            self.settings["download_dir"] = new_path
            config_module.save(self.settings)
            self.path_label.set_text(new_path)
        dialog.destroy()

    # ---- Add flow (supports pasting multiple URLs at once) ---------------

    def _on_add_clicked(self, _btn):
        start, end = self.url_buffer.get_start_iter(), self.url_buffer.get_end_iter()
        raw_text = self.url_buffer.get_text(start, end, False).strip()
        if not raw_text:
            return
        self.url_buffer.set_text("")

        urls = [u for u in _URL_SPLIT_RE.split(raw_text) if u]
        if not urls:
            return

        # When multiple links are pasted at once, skip the extra per-quality
        # size-fetch call for each one -- firing several of those
        # concurrently adds needless network/CPU load right when the intent
        # is clearly "queue these quickly", and the size hint matters less
        # when you're batch-adding than when carefully picking one video's
        # quality. Single adds and playlists still get it.
        is_batch = len(urls) > 1

        for url in urls:
            loading_row = LoadingRow(url)
            self.ongoing_box.pack_start(loading_row, False, False, 0)
            threading.Thread(
                target=self._probe_and_replace, args=(url, loading_row, is_batch), daemon=True
            ).start()

        self._update_ongoing_empty()

    def _probe_and_replace(self, url, loading_row, is_batch=False):
        probe_task = DownloadTask(
            url, self.settings["download_dir"],
            self.settings["cookies_file"] if self.settings.get("use_cookies") else None,
        )
        try:
            probe_task.probe()
        except RuntimeError as e:
            GLib.idle_add(self._on_probe_failed, loading_row, str(e))
            return
        GLib.idle_add(self._on_probe_succeeded, loading_row, probe_task, url, is_batch)

    def _on_probe_failed(self, loading_row, message):
        # Drop the stuck spinner row so a dead/offline link doesn't linger
        # in the Ongoing list forever, then surface the error to the user.
        parent = loading_row.get_parent()
        if parent is not None:
            parent.remove(loading_row)
        self._update_ongoing_empty()
        dialog = Gtk.MessageDialog(
            parent=self, type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK,
            message_format="Couldn't process this link",
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
        return False

    def _on_probe_succeeded(self, loading_row, probe_task, url, is_batch=False):
        self.ongoing_box.remove(loading_row)

        if probe_task.is_playlist:
            row = PlaylistRow(url, self.settings, self._on_row_state_change,
                               probe_task.playlist_entries, probe_task.title)
        else:
            row = VideoRow(url, self.settings, self._on_row_state_change,
                            preprobed_task=probe_task, skip_quality_sizes=is_batch)

        self.ongoing_box.pack_start(row, False, False, 0)
        self._update_ongoing_empty()
        return False

    def _on_row_state_change(self, row, new_state):
        if new_state == "removed":
            # Covers Clear All, the per-row clear button, and cancelling a
            # playlist before it ever started (wrong URL dismissal).
            parent = row.get_parent()
            if parent is not None:
                parent.remove(row)
            self._update_ongoing_empty()
            self._update_completed_empty()
        elif new_state == "completed":
            # Cancelled downloads and fully-finished ones both land here.
            # Guard against a duplicate transition (a Retry that raced a
            # late completion callback): don't re-pack a row already here.
            if row.get_parent() is self.completed_box:
                self._update_completed_empty()
                return
            parent = row.get_parent()
            if parent is not None:
                parent.remove(row)
            self.completed_box.pack_start(row, False, False, 0)
            self._update_ongoing_empty()
            self._update_completed_empty()
        elif new_state == "active":
            # A Retry just moved this row back to Ongoing to resume.
            if row.get_parent() is self.ongoing_box:
                self._update_ongoing_empty()
                return
            parent = row.get_parent()
            if parent is not None:
                parent.remove(row)
            self.ongoing_box.pack_start(row, False, False, 0)
            self._update_ongoing_empty()
            self._update_completed_empty()

    # ---- Settings navigation -----------------------------------------

    def _open_settings(self):
        self.settings_view = SettingsView(
            self.settings, self._close_settings, self._on_settings_saved, self._apply_theme,
        )
        if self.root_stack.get_child_by_name("settings"):
            self.root_stack.remove(self.root_stack.get_child_by_name("settings"))
        settings_scroller = Gtk.ScrolledWindow()
        settings_scroller.add(self.settings_view)
        self.root_stack.add_named(settings_scroller, "settings")
        self.settings_view.show_all()
        settings_scroller.show_all()
        self.root_stack.set_visible_child_name("settings")
        self.headerbar.hide()  # settings view has its own back button; drop the top bar

    def _close_settings(self):
        self.root_stack.set_visible_child_name("main")
        self.headerbar.show()

    def _on_settings_saved(self, new_settings):
        self.settings = new_settings
        self._update_theme_icon()

    # ---- First run ---------------------------------------------------

    def _maybe_run_first_time_setup(self):
        if not self.settings.get("first_run_done"):
            dialog = Gtk.MessageDialog(
                transient_for=self, flags=0, message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Welcome to Simple YT Downloader",
            )
            dialog.format_secondary_text(
                "Let's quickly check that everything needed is installed, "
                "and you can set your cookies file in Settings and your "
                "download folder from the bar at the bottom of the window."
            )
            dialog.run()
            dialog.destroy()
            self._open_settings()

        missing = dependencies.missing_binaries()
        if missing:
            self._prompt_install_missing(missing)
        return False

    def _prompt_install_missing(self, missing):
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0, message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Missing dependencies",
        )
        dialog.format_secondary_text(
            f"This app needs: {', '.join(missing)}\n\n"
            "Install them now? This requires your admin password."
        )
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            def on_done(success, message):
                GLib.idle_add(self._on_first_install_done, success, message)
            threading.Thread(
                target=dependencies.install_missing, args=(missing, on_done), daemon=True
            ).start()

    def _on_first_install_done(self, success, message):
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.INFO if success else Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Dependencies installed" if success else "Installation failed",
        )
        dialog.format_secondary_text(message[:500])
        dialog.run()
        dialog.destroy()
        return False


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.mahmudul.simpleytdownloader")
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = MainWindow(self)
        self.window.present()


def main():
    app = Application()
    return app.run()
