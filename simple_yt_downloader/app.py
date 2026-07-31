import re
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from . import config as config_module
from . import dependencies
from . import icons
from . import style
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


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_TITLE)
        icons.register_bundled_icons()
        self._original_theme_name = Gtk.Settings.get_default().get_property("gtk-theme-name")
        self._set_safe_default_size()

        self.settings = config_module.load()
        self._apply_theme(self.settings.get("theme", "system"))
        style.apply()

        self._build_headerbar()

        self.root_stack = Gtk.Stack()
        self.root_stack.set_hhomogeneous(False)
        self.root_stack.set_vhomogeneous(False)
        self.add(self.root_stack)

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

    # ---- Window chrome ----------------------------------------------------

    def _build_headerbar(self):
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title(APP_TITLE)
        self.set_titlebar(header)

        self.theme_btn = Gtk.Button()
        self.theme_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.theme_btn.get_style_context().add_class("headerbar-btn")
        self._update_theme_icon()
        self.theme_btn.connect("clicked", self._on_theme_button_clicked)
        header.pack_end(self.theme_btn)

        settings_btn = Gtk.Button()
        settings_btn.set_relief(Gtk.ReliefStyle.NONE)
        settings_btn.get_style_context().add_class("headerbar-btn")
        settings_btn.add(Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON))
        settings_btn.connect("clicked", lambda _b: self._open_settings())
        header.pack_end(settings_btn)

    def _update_theme_icon(self):
        theme = self.settings.get("theme", "system")
        icon = "weather-clear-symbolic" if theme == "light" else "weather-clear-night-symbolic"
        child = self.theme_btn.get_child()
        if child:
            self.theme_btn.remove(child)
        self.theme_btn.add(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
        self.theme_btn.show_all()

    def _on_theme_button_clicked(self, _btn):
        current = self.settings.get("theme", "system")
        new_theme = "dark" if current in ("light", "system") else "light"
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
        "System" mode restores whatever theme was active before the app
        touched anything, captured once at startup.
        """
        gtk_settings = Gtk.Settings.get_default()
        if theme == "dark":
            gtk_settings.set_property("gtk-theme-name", "Adwaita")
            gtk_settings.set_property("gtk-application-prefer-dark-theme", True)
        elif theme == "light":
            gtk_settings.set_property("gtk-theme-name", "Adwaita")
            gtk_settings.set_property("gtk-application-prefer-dark-theme", False)
        else:  # system
            gtk_settings.set_property("gtk-theme-name", self._original_theme_name)
            gtk_settings.set_property("gtk-application-prefer-dark-theme", False)
        style.reload()

    # ---- Main view (tabs + add bar + row lists) ---------------------------

    def _build_main_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self.tab_stack = Gtk.Stack()
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.tab_stack)
        switcher.set_halign(Gtk.Align.START)
        box.pack_start(switcher, False, False, 0)

        add_label = Gtk.Label(label="Paste one or more links (one per line, or space/comma separated)")
        add_label.set_xalign(0)
        add_label.get_style_context().add_class("caption")
        box.pack_start(add_label, False, False, 0)

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
        box.pack_start(add_row, False, False, 0)

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
            "Nothing completed yet",
            "Finished downloads will appear here.",
        )
        self._completed_stack = completed_stack

        completed_scroller = Gtk.ScrolledWindow()
        completed_scroller.add(completed_stack)
        completed_page.pack_start(completed_scroller, True, True, 0)

        self.tab_stack.add_titled(ongoing_scroller, "ongoing", "Ongoing")
        self.tab_stack.add_titled(completed_page, "completed", "Completed")
        box.pack_start(self.tab_stack, True, True, 0)

        box.pack_start(self._build_download_path_bar(), False, False, 0)

        self.clear_all_btn = clear_all_btn
        self._update_ongoing_empty()
        self._update_completed_empty()

        return box

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
        parent = row.get_parent()
        if new_state == "removed":
            if parent is not None:
                parent.remove(row)
            self._update_ongoing_empty()
        elif new_state == "completed":
            if parent is not None:
                parent.remove(row)
            self.completed_box.pack_start(row, False, False, 0)
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

    def _close_settings(self):
        self.root_stack.set_visible_child_name("main")

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
                "and you can set your cookies file and download folder in Settings."
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
