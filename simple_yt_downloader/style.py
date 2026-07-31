"""Custom GTK CSS so the app matches the "Indigo Tonal" design (Material-lite
for GTK3): layered @theme_base_color surfaces with hairline borders instead
of shadows, one shared control-height band, semantic status hues that color
icons/dots only, and a single indigo accent applied even to native widgets
(checkboxes, selection).

Colors are hardcoded to a specific indigo palette rather than derived from
the active GTK theme, since Linux Mint's Mint-Y theme family doesn't
implement @theme_selected_bg_color the way Adwaita does -- deriving from it
produced inconsistent/wrong-looking accents. Card backgrounds use
@theme_base_color so they stay correct in both Light and Dark (white in
Adwaita-light, near-black in Adwaita-dark); borders and muted text derive
from @theme_fg_color.

GTK3 constraints honored:
- No "togglebutton" CSS node -- GtkToggleButton renders as "button" with
  :checked, so one rule covers both segmented controls.
- No box-shadow (GTK3 blur is unreliable on Mint) -- elevation is faked
  with surfaces + 1px hairlines.
- Valid GTK3 selectors only (button, box, label, textview, progressbar,
  scrollbar, selection, etc.), working in Light + Dark + System.
"""

CSS = """
/* ---- Tokens ---------------------------------------------------- */
@define-color accent #4f46e5;
@define-color accent_hover shade(@accent, 1.08);
@define-color accent_active shade(@accent, 0.92);
@define-color accent_fg #ffffff;

@define-color surface @theme_base_color;
@define-color surface_alt alpha(@theme_fg_color, 0.06);
@define-color border_color alpha(@theme_fg_color, 0.14);
@define-color border_strong alpha(@theme_fg_color, 0.26);

@define-color text_muted alpha(@theme_text_color, 0.62);
@define-color text_faint alpha(@theme_text_color, 0.42);

/* Status hues: chosen for >=3:1 contrast on both Adwaita light & dark.
   They color icons/dots only; body status text stays theme-adaptive. */
@define-color success #2da44e;
@define-color error #e5484d;
@define-color warning #b45309;

/* ---- Window & scrollbars --------------------------------------- */
window { background-color: @theme_bg_color; }

scrollbar { background: none; }
scrollbar trough {
    background: alpha(@theme_fg_color, 0.08);
    border-radius: 4px;
}
scrollbar slider {
    background: alpha(@theme_fg_color, 0.28);
    border-radius: 4px;
    min-width: 8px;
    min-height: 8px;
}
scrollbar slider:hover { background: alpha(@theme_fg_color, 0.45); }

/* ---- HeaderBar ------------------------------------------------- */
headerbar label.title { font-weight: 700; }

.headerbar-btn {
    min-height: 28px;
    min-width: 28px;
    padding: 4px;
    border-radius: 6px;
}

/* ---- Cards ------------------------------------------------------
   One card language for video rows, playlist rows, loading rows, and
   the download-path bar. Vertical rhythm comes from CSS margin (rows no
   longer set Python margins), so every card aligns to the 12px window
   gutter. */
.download-row {
    background-color: @surface;
    border: 1px solid @border_color;
    border-radius: 12px;
    padding: 12px;
    margin: 2px 0;
}
.download-row:hover { border-color: @border_strong; }

.download-row label.title {
    font-size: 13px;
    font-weight: 600;
}

/* Slim pinned path bar variant */
.download-row.path-bar { padding: 8px 10px; }
.download-row.path-bar image { color: @text_muted; }
.download-row.path-bar label { color: @text_muted; }
.download-row.path-bar button { min-height: 26px; }

/* ---- Caption & status text ------------------------------------- */
label.caption {
    font-size: 11px;
    color: @text_faint;
}
label.status-text { color: @text_muted; }

label.count-badge {
    font-size: 11px;
    font-weight: 600;
    color: @text_muted;
    background: alpha(@theme_fg_color, 0.09);
    border-radius: 8px;
    padding: 1px 7px;
}

/* ---- URL composer (the TextView IS the card) -------------------- */
textview.url-input {
    background-color: @surface;
    border: 1px solid @border_color;
    border-radius: 12px;
    padding: 8px;
    color: @theme_text_color;
}
textview.url-input:focus {
    border-color: @accent;
    background-color: alpha(@accent, 0.03);
}

/* ---- Buttons ---------------------------------------------------- */
button.suggested-action {
    min-height: 30px;
    padding: 6px 18px;
    border-radius: 8px;
    background-color: @accent;
    background-image: none;
    color: @accent_fg;
}
button.suggested-action:hover {
    background-color: @accent_hover;
    background-image: none;
}
button.suggested-action:active { background-color: @accent_active; }
button.suggested-action:disabled {
    background-color: @accent;
    opacity: 0.55;
}

/* Flat icon buttons (pause/cancel/retry/logs/settings/browse).
   GTK3 auto-adds .image-button to buttons whose only child is an image;
   the fallback-glyph buttons keep the same shape via the same class
   (added in row_widgets._icon_button). */
button.image-button {
    min-height: 28px;
    min-width: 28px;
    padding: 4px;
    border-radius: 7px;
    background: none;
    background-image: none;
    border: none;
    box-shadow: none;
    color: @text_muted;
}
button.image-button:hover {
    background: alpha(@theme_fg_color, 0.08);
    color: @theme_text_color;
}
button.image-button:active { background: alpha(@theme_fg_color, 0.14); }
button.image-button:disabled { opacity: 0.4; }

/* ---- Segmented pills (Video/Audio + Settings theme control) -----
   GtkToggleButton renders as node "button" with :checked -- there is no
   "togglebutton" node. One rule covers both controls.
   NOTE: do NOT set border-radius here -- the theme owns the joined
   corner rounding of .linked buttons. */
box.linked > button {
    min-height: 28px;
    padding: 0 14px;
}
box.linked > button:checked {
    background-color: @accent;
    background-image: none;
    color: @accent_fg;
}
box.linked > button:checked:hover { background-color: @accent_hover; }
box.linked > button:not(:checked):hover {
    background-color: alpha(@theme_fg_color, 0.07);
}
box.linked > button:disabled { opacity: 0.55; }

/* ---- Combos ----------------------------------------------------- */
combobox > button {
    min-height: 28px;
    border-radius: 6px;
}
combobox:disabled { opacity: 0.55; }

/* ---- Progress bars (text lives in the status line now) ---------- */
progressbar { min-height: 6px; }
progressbar > trough {
    min-height: 6px;
    border-radius: 3px;
    border: none;
    background-color: alpha(@theme_fg_color, 0.12);
}
progressbar > trough > progress {
    min-height: 6px;
    border-radius: 3px;
    background-color: @accent;
    background-image: none;
}
progressbar.error > trough > progress { background-color: @error; }

/* ---- Tabs (stock Gtk.StackSwitcher) ------------------------------ */
stackswitcher > button {
    background: none;
    border: none;
    box-shadow: none;
    border-radius: 0;
    border-bottom: 3px solid transparent;
    padding: 8px 10px;
    margin-right: 12px;
    min-height: 32px;
}
stackswitcher > button:checked {
    border-bottom: 3px solid @accent;
    color: @accent;
    font-weight: 600;
}
stackswitcher > button:hover {
    background: alpha(@theme_fg_color, 0.05);
    border-radius: 6px;
}

/* ---- Empty states ------------------------------------------------ */
box.empty-state { padding: 48px 24px; }
box.empty-state image { opacity: 0.4; }
box.empty-state label.empty-title { font-size: 15px; font-weight: 600; }
box.empty-state label.empty-hint { color: @text_muted; }

/* ---- Settings About card ----------------------------------------- */
box.settings-card {
    background-color: @surface;
    border: 1px solid @border_color;
    border-radius: 12px;
    padding: 14px;
}
box.settings-card label.about-title { font-size: 16px; font-weight: 700; }
box.settings-card label.about-desc { color: @text_muted; }
box.settings-card label.about-key { color: @text_muted; }
box.settings-card label.about-value { color: @theme_text_color; }
box.settings-card separator { margin-top: 4px; margin-bottom: 4px; }

/* ---- Native-widget accent (kills Adwaita's blue bleed) ----------- */
checkbutton check, checkbutton radio { border-radius: 4px; }
checkbutton check:checked, checkbutton radio:checked {
    background-color: @accent;
    border-color: @accent;
}
selection {
    background-color: alpha(@accent, 0.9);
    color: @accent_fg;
}
entry { border-radius: 6px; }
entry:focus { border-color: @accent; }
"""

# Appended only when the active theme is dark. GTK3 has no @media support,
# so instead of CSS conditionals the provider reloads with this block
# appended whenever the theme changes (style.reload). @theme_fg_color is
# near-white in dark themes, so a slightly stronger alpha reads as a small
# light hairline against near-black surfaces.
_CSS_DARK_OVERRIDES = """
box.download-row { border-color: alpha(@theme_fg_color, 0.32); }
box.download-row:hover { border-color: alpha(@theme_fg_color, 0.55); }
box.settings-card { border-color: alpha(@theme_fg_color, 0.32); }
textview.url-input { border-color: alpha(@theme_fg_color, 0.32); }
textview.url-input:focus {
    border-color: @accent;
    background-color: alpha(@accent, 0.06);
}
"""

# Appended when the theme is light. Adwaita-light (and Mint-Y-light) set
# BOTH @theme_bg_color and @theme_base_color to pure white, so without a
# forced canvas the window, cards, and path bar collapse into one flat
# white slab. Giving the window a cool indigo-tinted gray canvas makes the
# white surfaces read as layered cards again, and slightly stronger borders
# keep them crisp against it.
_CSS_LIGHT_OVERRIDES = """
window { background-color: #eef0f6; }
box.download-row { border-color: alpha(@theme_fg_color, 0.22); }
box.download-row:hover { border-color: alpha(@theme_fg_color, 0.40); }
box.settings-card { border-color: alpha(@theme_fg_color, 0.22); }
textview.url-input { border-color: alpha(@theme_fg_color, 0.22); }
textview.url-input:focus { background-color: alpha(@accent, 0.05); }
"""

_provider = None


def _compose_css():
    """Full CSS text for the currently active theme: base rules plus the
    light or dark override block. Kept as a pure function so the smoke test
    can assert which block applies per theme."""
    data = CSS.encode("utf-8")
    if _screen_is_dark():
        data += _CSS_DARK_OVERRIDES.encode("utf-8")
    else:
        data += _CSS_LIGHT_OVERRIDES.encode("utf-8")
    return data


def _screen_is_dark():
    """Reads GTK's theme settings to decide whether the UI is currently
    rendering dark. This mirrors app._apply_theme (Light forces Adwaita +
    prefer-dark off, Dark forces prefer-dark on, System keeps the user's
    own theme) and also catches user-level dark themes such as Mint-Y-Dark.

    A luminance probe window was the first approach, but a realized-but-
    unmapped window is not restyled after a theme switch, so its
    @theme_bg_color read stayed light inside a running app."""
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    settings = Gtk.Settings.get_default()
    if settings is None:
        return False
    if settings.get_property("gtk-application-prefer-dark-theme"):
        return True
    theme = (settings.get_property("gtk-theme-name") or "").lower()
    return theme.endswith("dark")


def apply():
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, Gtk

    global _provider

    data = _compose_css()

    if _provider is None:
        _provider = Gtk.CssProvider()
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(
            screen, _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    _provider.load_from_data(data)


def reload():
    """Re-runs apply() with the currently active theme, so the dark-mode
    border overrides follow Light/Dark/System changes instantly. No-op
    until the provider has been created once."""
    if _provider is not None:
        apply()
