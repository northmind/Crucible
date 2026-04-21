"""Unified theme system — persistence, cache, derived colors, and public getters."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QSettings, pyqtSignal

from crucible.ui.color_utils import mix_hex
from crucible.ui.theme_types import (
    SelectionColors,
    StatusColors,
    SurfaceColors,
    Theme,
)

# ---------------------------------------------------------------------------
# Theme-change signal
# ---------------------------------------------------------------------------


class _ThemeSignals(QObject):
    """Singleton QObject carrying the global ``theme_changed`` signal."""

    theme_changed = pyqtSignal()


_signals: _ThemeSignals | None = None


def _get_signals() -> _ThemeSignals:
    global _signals
    if _signals is None:
        _signals = _ThemeSignals()
    return _signals


def theme_changed_signal() -> pyqtSignal:
    """Return the global ``theme_changed`` signal (connect to it, don't emit)."""
    return _get_signals().theme_changed


# ---------------------------------------------------------------------------
# Builtin themes (defined in theme_builtins to keep this file under 300 lines)
# ---------------------------------------------------------------------------

from crucible.ui.theme_builtins import (  # noqa: E402
    builtin_themes,
    get_builtin_theme,
)


# ---------------------------------------------------------------------------
# QSettings persistence
# ---------------------------------------------------------------------------

_APP_NAME = "Crucible"
_ORG_NAME = "Crucible Launcher"
_THEME_KEY = "theme"


def get_settings() -> QSettings:
    """Return a QSettings instance for the Crucible application."""
    return QSettings(_ORG_NAME, _APP_NAME)


def apply_builtin_theme(theme: Theme) -> None:
    """Activate a builtin theme and invalidate the theme cache."""
    settings = get_settings()
    settings.setValue(_THEME_KEY, theme.key)
    invalidate_theme_cache()


# ---------------------------------------------------------------------------
# Theme cache and resolution
# ---------------------------------------------------------------------------

_cached_theme: Theme | None = None


def invalidate_theme_cache() -> None:
    """Clear the cached theme so the next ``get_theme()`` re-reads settings."""
    global _cached_theme
    _cached_theme = None
    _get_signals().theme_changed.emit()


def get_theme() -> Theme:
    """Return the active theme, resolving from cache or builtin."""
    global _cached_theme
    if _cached_theme is not None:
        return _cached_theme

    key = get_settings().value(_THEME_KEY, "crucible")
    _cached_theme = get_builtin_theme(str(key))
    return _cached_theme


# ---------------------------------------------------------------------------
# Public color getters — return typed dataclasses
# ---------------------------------------------------------------------------


def get_surface_colors() -> SurfaceColors:
    """Return surface-level colors for the active theme.

    Derives a 3-tone visual hierarchy from the theme's existing colors:
    chrome (titlebar/nav) -> panel (mid-tone) -> content (editor bg).
    """
    theme = get_theme()
    chrome_bg = theme.chrome_bg or mix_hex(theme.bg, theme.border, 0.08)
    return SurfaceColors(
        window_bg=theme.bg,
        nav_bg=chrome_bg,
        panel_bg=mix_hex(chrome_bg, theme.bg, 0.5),
        content_bg=theme.bg,
    )


def get_selection_colors() -> SelectionColors:
    """Return selection and hover colors for the active theme."""
    theme = get_theme()
    return SelectionColors(
        nav_accent=theme.accent,
        selection_bg=theme.accent_soft,
        hover_bg=mix_hex(theme.accent_soft, theme.bg, 0.45),
    )


# Default status palette (One Dark inspired, readable on dark backgrounds)
_DEFAULT_STATUS_WARNING = "#e5c07b"
_DEFAULT_STATUS_ERROR = "#e06c75"
_DEFAULT_STATUS_SUCCESS = "#98c379"
_DEFAULT_STATUS_INFO = "#61afef"


def get_status_colors() -> StatusColors:
    """Return semantic status colors for the active theme."""
    theme = get_theme()
    return StatusColors(
        warning=theme.status_warning or _DEFAULT_STATUS_WARNING,
        error=theme.status_error or _DEFAULT_STATUS_ERROR,
        success=theme.status_success or _DEFAULT_STATUS_SUCCESS,
        info=theme.status_info or _DEFAULT_STATUS_INFO,
        danger_hover=theme.danger_hover or mix_hex(
            theme.accent, _DEFAULT_STATUS_ERROR, 0.5,
        ),
        text_disabled=theme.text_disabled or mix_hex(
            theme.text_dim, theme.bg, 0.5,
        ),
    )
