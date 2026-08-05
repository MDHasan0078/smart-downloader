"""The Settings screen: cookies/folder/defaults/theme + dependency checker.

This is a plain Gtk.Box (not a dialog) because the main window swaps it in
via a Gtk.Stack -- matching the "back arrow" full-window settings pattern
rather than a popup dialog.
"""

import platform
import threading
import webbrowser

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from . import config as config_module
from . import dependencies
from . import updater
from . import __author__, __homepage__, __license__, __version__
from .row_widgets import (
    AUDIO_FORMATS,
    AUDIO_QUALITIES,
    VIDEO_FORMATS,
    VIDEO_QUALITIES,
    _icon_theme_has,
)

STATIC_DEPS = ["python3", "python3-gi", "gir1.2-gtk-3.0"]


def _format_bytes(num):
    """Human-friendly size for the download progress label."""
    if not num:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024
    return f"{num:.1f} GB"


class SettingsView(Gtk.Box):
    def __init__(self, settings, on_back, on_settings_changed, on_theme_changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(14)
        self.set_margin_bottom(14)
        self.set_margin_start(16)
        self.set_margin_end(16)

        self.settings = dict(settings)
        self.on_back = on_back
        self.on_settings_changed = on_settings_changed
        self.on_theme_changed = on_theme_changed

        self._dl_dialog = None
        self._dl_bar = None
        self._dl_label = None
        self._install_dialog = None
        self._install_bar = None

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        back_btn = Gtk.Button()
        back_btn.set_relief(Gtk.ReliefStyle.NONE)
        back_btn.add(Gtk.Image.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON))
        back_btn.connect("clicked", lambda _b: self.on_back())
        header.pack_start(back_btn, False, False, 0)
        title = Gtk.Label(label="Settings")
        title.get_style_context().add_class("title-4")
        header.pack_start(title, False, False, 0)
        self.pack_start(header, False, False, 0)

        self.pack_start(self._section("Cookies file"), False, False, 0)
        cookies_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.cookies_entry = Gtk.Entry()
        self.cookies_entry.set_text(self.settings.get("cookies_file", ""))
        self.cookies_entry.set_editable(False)
        cookies_row.pack_start(self.cookies_entry, True, True, 0)
        browse_btn = Gtk.Button()
        browse_btn.add(Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.BUTTON))
        browse_btn.connect("clicked", self._on_browse_cookies)
        cookies_row.pack_start(browse_btn, False, False, 0)
        self.pack_start(cookies_row, False, False, 0)

        self.use_cookies_check = Gtk.CheckButton(label="Use cookies file")
        self.use_cookies_check.set_active(self.settings.get("use_cookies", False))
        self.pack_start(self.use_cookies_check, False, False, 0)

        self.pack_start(self._section("Download folder"), False, False, 0)
        folder_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.folder_entry = Gtk.Entry()
        self.folder_entry.set_text(self.settings.get("download_dir", ""))
        self.folder_entry.set_editable(False)
        folder_row.pack_start(self.folder_entry, True, True, 0)
        folder_btn = Gtk.Button()
        folder_btn.add(Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.BUTTON))
        folder_btn.connect("clicked", self._on_browse_folder)
        folder_row.pack_start(folder_btn, False, False, 0)
        self.pack_start(folder_row, False, False, 0)

        self.pack_start(self._section("Default video format & quality"), False, False, 0)
        vrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.vfmt_combo = Gtk.ComboBoxText()
        for f in VIDEO_FORMATS:
            self.vfmt_combo.append_text(f.upper())
        vf = self.settings.get("default_video_format", "mp4")
        self.vfmt_combo.set_active(VIDEO_FORMATS.index(vf) if vf in VIDEO_FORMATS else 0)
        self.vqual_combo = Gtk.ComboBoxText()
        for value, display in VIDEO_QUALITIES:
            self.vqual_combo.append(value, display)
        self.vqual_combo.set_active_id(self.settings.get("default_video_quality", "720"))
        vrow.pack_start(self.vfmt_combo, True, True, 0)
        vrow.pack_start(self.vqual_combo, True, True, 0)
        self.pack_start(vrow, False, False, 0)

        self.pack_start(self._section("Default audio format & quality"), False, False, 0)
        arow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.afmt_combo = Gtk.ComboBoxText()
        for f in AUDIO_FORMATS:
            self.afmt_combo.append_text(f.upper())
        af = self.settings.get("default_audio_format", "mp3")
        self.afmt_combo.set_active(AUDIO_FORMATS.index(af) if af in AUDIO_FORMATS else 0)
        self.aqual_combo = Gtk.ComboBoxText()
        for value, display in AUDIO_QUALITIES:
            self.aqual_combo.append(value, display)
        self.aqual_combo.set_active_id(self.settings.get("default_audio_quality", "192"))
        arow.pack_start(self.afmt_combo, True, True, 0)
        arow.pack_start(self.aqual_combo, True, True, 0)
        self.pack_start(arow, False, False, 0)

        self.pack_start(self._section("Appearance"), False, False, 0)
        theme_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        theme_row.get_style_context().add_class("linked")
        self.theme_buttons = {}
        for key, label in [("light", "Light"), ("dark", "Dark")]:
            btn = Gtk.ToggleButton(label=label)
            btn.connect("toggled", self._on_theme_toggled, key)
            theme_row.pack_start(btn, False, False, 0)
            self.theme_buttons[key] = btn
        self.theme_buttons[self.settings.get("theme", "dark")].set_active(True)
        self.pack_start(theme_row, False, False, 0)

        self.pack_start(self._section("Dependencies"), False, False, 0)
        self.deps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.deps_box.get_style_context().add_class("deps-frame")
        self.deps_box.get_style_context().add_class("download-row")
        self.pack_start(self.deps_box, False, False, 0)
        self.fix_deps_btn = Gtk.Button(label="Fix Dependencies")
        self.fix_deps_btn.connect("clicked", self._on_fix_dependencies)
        self.pack_start(self.fix_deps_btn, False, False, 0)
        self._refresh_dependency_status()

        save_btn = Gtk.Button(label="Save changes")
        save_btn.get_style_context().add_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        self.pack_start(save_btn, False, False, 8)

        self.pack_start(self._section("About"), False, False, 0)
        self.pack_start(self._build_about_card(), False, False, 0)

    def _build_about_card(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.get_style_context().add_class("settings-card")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon_name = "folder-download-symbolic"
        if not _icon_theme_has(icon_name):
            icon_name = "image-missing"
        header.pack_start(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG), False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="Simple YT Downloader")
        title.set_xalign(0)
        title.get_style_context().add_class("about-title")
        title_box.pack_start(title, False, False, 0)
        version = Gtk.Label(label=f"v{__version__}")
        version.set_xalign(0)
        version.get_style_context().add_class("caption")
        title_box.pack_start(version, False, False, 0)
        header.pack_start(title_box, True, True, 0)
        card.pack_start(header, False, False, 0)

        desc = Gtk.Label(label="Smart Downloader — a fast, lightweight, open-source "
                               "YouTube downloader. Every quality from 144p to 10K, "
                               "custom resolution support, selectable 30/60/90 fps, "
                               "playlist support and pause/resume.")
        desc.set_xalign(0)
        desc.set_line_wrap(True)
        desc.get_style_context().add_class("about-desc")
        card.pack_start(desc, False, False, 0)

        card.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        card.pack_start(self._about_row("Author", __author__), False, False, 0)
        card.pack_start(self._about_row("License", __license__), False, False, 0)
        card.pack_start(self._about_row("Engine", "yt-dlp · ffmpeg"), False, False, 0)
        card.pack_start(self._about_row(
            "Runtime",
            f"Python {platform.python_version()} · "
            f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}",
        ), False, False, 0)
        github_link = Gtk.LinkButton.new_with_label(__homepage__, __homepage__)
        github_link.set_halign(Gtk.Align.END)
        card.pack_start(self._about_row("GitHub", github_link), False, False, 0)

        card.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        self.update_btn = Gtk.Button(label="Check for Updates")
        self.update_btn.connect("clicked", self._on_check_updates)
        card.pack_start(self.update_btn, False, False, 0)
        return card

    def _about_row(self, key, value):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        key_label = Gtk.Label(label=key)
        key_label.set_xalign(0)
        key_label.get_style_context().add_class("about-key")
        row.pack_start(key_label, False, False, 0)
        if isinstance(value, str):
            value_label = Gtk.Label(label=value)
            value_label.set_xalign(1)
            value_label.get_style_context().add_class("about-value")
            row.pack_start(value_label, True, True, 0)
        else:
            row.pack_start(value, True, True, 0)
        return row

    # ---- Update check (async, like the dependency check) ----------------

    def _on_check_updates(self, _btn):
        self.update_btn.set_sensitive(False)
        self.update_btn.set_label("Checking...")

        def worker():
            info = updater.fetch_latest_release()
            GLib.idle_add(self._on_update_check_done, info)

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_check_done(self, info):
        self.update_btn.set_sensitive(True)
        self.update_btn.set_label("Check for Updates")

        if info is None:
            self._show_info_dialog(
                "Check Failed",
                "Could not reach the update server. Please check your connection.",
                message_type=Gtk.MessageType.ERROR,
            )
            return False

        if updater.version_tuple(info["version"]) > updater.version_tuple(__version__):
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(), flags=0,
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

    # ---- Self-update download & install -------------------------------

    def _start_update_download(self, info):
        """Begin streaming the .deb in the background; show a progress dialog."""
        self._pending_update_info = info
        version = info["version"]
        deb_path = updater.deb_path(version)
        dialog = Gtk.Dialog(
            title=f"Downloading v{version}...",
            transient_for=self.get_toplevel(),
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
            transient_for=self.get_toplevel(),
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

    def _section(self, text):
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.get_style_context().add_class("dim-label")
        return label

    # ---- Actions ---------------------------------------------------------

    def _on_browse_cookies(self, _btn):
        dialog = Gtk.FileChooserDialog(
            title="Select cookies.txt file", parent=self.get_toplevel(),
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            self.cookies_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def _on_browse_folder(self, _btn):
        dialog = Gtk.FileChooserDialog(
            title="Choose download folder", parent=self.get_toplevel(),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            self.folder_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def _on_theme_toggled(self, btn, key):
        if btn.get_active():
            for other_key, other_btn in self.theme_buttons.items():
                if other_key != key:
                    other_btn.set_active(False)
            self.on_theme_changed(key)
        elif not any(b.get_active() for b in self.theme_buttons.values()):
            btn.set_active(True)

    def _on_save(self, _btn):
        self.settings["cookies_file"] = self.cookies_entry.get_text()
        self.settings["use_cookies"] = self.use_cookies_check.get_active()
        self.settings["download_dir"] = self.folder_entry.get_text()
        self.settings["default_video_format"] = (self.vfmt_combo.get_active_text() or "mp4").lower()
        self.settings["default_video_quality"] = self.vqual_combo.get_active_id() or "720"
        self.settings["default_audio_format"] = (self.afmt_combo.get_active_text() or "mp3").lower()
        self.settings["default_audio_quality"] = self.aqual_combo.get_active_id() or "192"
        for key, btn in self.theme_buttons.items():
            if btn.get_active():
                self.settings["theme"] = key
        self.settings["first_run_done"] = True

        config_module.save(self.settings)
        self.on_settings_changed(self.settings)
        self.on_back()

    # ---- Dependency status (async so opening Settings is instant) --------

    def _refresh_dependency_status(self):
        """Shows static deps + a 'Checking...' placeholder immediately, then
        fills in real yt-dlp/ffmpeg status once the background check
        returns. The old synchronous version blocked the whole Settings
        screen from opening for a couple seconds, since checking yt-dlp's
        version means spawning a full Python interpreter as a subprocess
        (`yt-dlp --version`) -- that should never run on the GTK main
        thread."""
        for child in list(self.deps_box.get_children()):
            self.deps_box.remove(child)

        for name in STATIC_DEPS:
            self.deps_box.pack_start(self._dep_row(name, True, "installed"), False, False, 0)

        # shutil.which is instant (no subprocess spawn) so this part doesn't
        # need to be backgrounded -- only the yt-dlp --version call does.
        for name in dependencies.CHECKED_BINARIES:
            row = self._dep_row(name, None, "Checking...")
            row._dep_name = name
            self.deps_box.pack_start(row, False, False, 0)

        self.deps_box.show_all()
        threading.Thread(target=self._check_dependencies_async, daemon=True).start()

    def _check_dependencies_async(self):
        status = dependencies.check_all()
        yt_dlp_version = dependencies.get_yt_dlp_version() if status.get("yt-dlp") else None
        GLib.idle_add(self._on_dependency_check_done, status, yt_dlp_version)

    def _on_dependency_check_done(self, status, yt_dlp_version):
        for child in list(self.deps_box.get_children()):
            if hasattr(child, "_dep_name"):
                self.deps_box.remove(child)

        for name, path in status.items():
            detail = yt_dlp_version if (name == "yt-dlp" and yt_dlp_version) else ("installed" if path else "Not found")
            new_row = self._dep_row(name, bool(path), detail)
            new_row._dep_name = name
            self.deps_box.pack_start(new_row, False, False, 0)

        self.deps_box.show_all()
        return False

    def _dep_row(self, name, ok, detail):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if ok is None:
            icon_name = "view-refresh-symbolic"  # "checking..." state
        else:
            icon_name = "emblem-ok-symbolic" if ok else "dialog-error-symbolic"
        row.pack_start(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU), False, False, 0)
        label = Gtk.Label(label=name)
        label.set_xalign(0)
        row.pack_start(label, True, True, 0)
        detail_label = Gtk.Label(label=detail)
        row.pack_start(detail_label, False, False, 0)
        return row

    def _on_fix_dependencies(self, _btn):
        missing = dependencies.missing_binaries()
        if not missing:
            self._show_info_dialog("All good", "Every dependency is already installed.")
            return

        confirm = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), flags=0, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Install missing dependencies?\n\n{', '.join(missing)}\n\nThis requires your admin password.",
        )
        response = confirm.run()
        confirm.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self.fix_deps_btn.set_sensitive(False)
        self.fix_deps_btn.set_label("Installing...")

        def on_done(success, message):
            GLib.idle_add(self._on_fix_done, success, message)

        threading.Thread(target=dependencies.install_missing, args=(missing, on_done), daemon=True).start()

    def _on_fix_done(self, success, message):
        self.fix_deps_btn.set_sensitive(True)
        self.fix_deps_btn.set_label("Fix Dependencies")
        self._refresh_dependency_status()
        self._show_info_dialog("Success" if success else "Installation failed", message)
        return False

    def _show_info_dialog(self, title, message, message_type=Gtk.MessageType.INFO):
        if message_type is None:
            message_type = (
                Gtk.MessageType.ERROR if title == "Installation failed" else Gtk.MessageType.INFO
            )
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), flags=0,
            message_type=message_type,
            buttons=Gtk.ButtonsType.OK, text=title,
        )
        dialog.format_secondary_text(message[:500])
        dialog.run()
        dialog.destroy()
