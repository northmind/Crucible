"""Unified theme system — data model, persistence, cache, and color getters."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from PyQt6.QtCore import QObject, QSettings, pyqtSignal

from crucible.ui.color_utils import (
    color_distance,
    contrast_text,
    mix_hex,
    validate_hex,
)
from crucible.ui.theme_importer import (
    import_vscode_theme_snapshot,
    normalize_vscode_theme_slug,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Theme-change signal (Phase 2e)
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
# Typed color structures (Phase 2c)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TextColors:
    text: str
    text_dim: str


@dataclass(frozen=True)
class BackgroundColors:
    bg: str
    border: str


@dataclass(frozen=True)
class SurfaceColors:
    window_bg: str
    titlebar_bg: str
    nav_bg: str
    panel_bg: str
    content_bg: str
    status_bg: str
    status_text: str


@dataclass(frozen=True)
class SelectionColors:
    nav_accent: str
    selection_bg: str
    selection_text: str
    text_selection_bg: str
    hover_bg: str


@dataclass(frozen=True)
class StatusColors:
    warning: str
    error: str
    success: str
    info: str
    danger_hover: str
    text_disabled: str


# ---------------------------------------------------------------------------
# Core theme dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Theme:
    name: str
    key: str
    accent: str
    accent_soft: str
    bg: str
    border: str
    text: str
    text_dim: str
    chrome_bg: str = ""
    status_warning: str = ""
    status_error: str = ""
    status_success: str = ""
    status_info: str = ""
    danger_hover: str = ""
    text_disabled: str = ""


@dataclass(frozen=True)
class SavedImportedTheme:
    slug: str
    author: str
    theme: Theme


# ---------------------------------------------------------------------------
# Theme construction and validation (Phase 2g)
# ---------------------------------------------------------------------------

_REQUIRED_COLOR_FIELDS = ("accent", "accent_soft", "bg", "border", "text", "text_dim")


def _build_theme(
    name: str,
    key: str,
    accent: str,
    accent_soft: str,
    bg: str,
    border: str,
    text: str,
    text_dim: str,
    chrome_bg: str | None = None,
    status_warning: str = "",
    status_error: str = "",
    status_success: str = "",
    status_info: str = "",
    danger_hover: str = "",
    text_disabled: str = "",
) -> Theme:
    for field_name, value in [
        ("accent", accent), ("accent_soft", accent_soft), ("bg", bg),
        ("border", border), ("text", text), ("text_dim", text_dim),
    ]:
        try:
            validate_hex(value)
        except ValueError:
            raise ValueError(f"Theme '{name}': invalid hex for {field_name}: {value!r}")
    if chrome_bg:
        try:
            validate_hex(chrome_bg)
        except ValueError:
            chrome_bg = None
    return Theme(
        name=name,
        key=key,
        accent=accent,
        accent_soft=accent_soft,
        bg=bg,
        border=border,
        text=text,
        text_dim=text_dim,
        chrome_bg=chrome_bg or mix_hex(bg, border, 0.08),
        status_warning=status_warning,
        status_error=status_error,
        status_success=status_success,
        status_info=status_info,
        danger_hover=danger_hover,
        text_disabled=text_disabled,
    )


# ---------------------------------------------------------------------------
# Builtin themes
# ---------------------------------------------------------------------------

BUILTIN_THEMES: list[Theme] = [
    _build_theme(
        name="Crucible",
        key="crucible",
        accent="#C06C84",
        accent_soft="#2a2228",
        bg="#15171b",
        border="#3e434d",
        text="#f3f1eb",
        text_dim="#afb5c0",
        chrome_bg="#1c1f24",
        status_warning="#e5c07b",
        status_error="#e06c75",
        status_success="#98c379",
        status_info="#61afef",
        danger_hover="#d27186",
    ),
    _build_theme(
        name="High Contrast",
        key="high-contrast",
        accent="#FFD700",
        accent_soft="#2a2400",
        bg="#000000",
        border="#444444",
        text="#FFFFFF",
        text_dim="#B0B0B0",
        chrome_bg="#0a0a0a",
        status_warning="#FFD700",
        status_error="#FF6B6B",
        status_success="#00E676",
        status_info="#40C4FF",
        danger_hover="#FF8A80",
        text_disabled="#666666",
    ),
]
_THEME_BY_KEY = {theme.key: theme for theme in BUILTIN_THEMES}


def builtin_themes() -> list[Theme]:
    """Return the list of all built-in Theme objects."""
    return BUILTIN_THEMES


def get_builtin_theme(key: str) -> Theme:
    """Return the built-in Theme matching *key*, defaulting to Crucible."""
    return _THEME_BY_KEY.get(key, BUILTIN_THEMES[0])


def theme_from_import_palette(data: dict, slug: str = "") -> Theme:
    """Build a Theme from an imported palette dict."""
    name = data["name"]
    key = data.get("key") or (f"saved:{slug}" if slug else name.lower())
    return _build_theme(
        name=name,
        key=key,
        accent=data["accent"],
        accent_soft=data["accent_soft"],
        bg=data["bg"],
        border=data["border"],
        text=data["text"],
        text_dim=data["text_dim"],
        chrome_bg=data.get("chrome_bg"),
        status_warning=data.get("status_warning", ""),
        status_error=data.get("status_error", ""),
        status_success=data.get("status_success", ""),
        status_info=data.get("status_info", ""),
        danger_hover=data.get("danger_hover", ""),
        text_disabled=data.get("text_disabled", ""),
    )


# ---------------------------------------------------------------------------
# Derived colors
# ---------------------------------------------------------------------------


def _derive_text_selection_bg(theme: Theme) -> str:
    candidate = mix_hex(theme.accent, theme.bg, 0.22)
    if color_distance(candidate, mix_hex(theme.accent_soft, theme.bg, 0.45)) < 36:
        candidate = mix_hex(theme.accent, theme.bg, 0.12)
    if color_distance(candidate, theme.bg) < 48:
        candidate = mix_hex(theme.accent, theme.text, 0.18)
    return candidate


def _derive_selection_text(theme: Theme) -> str:
    if theme.key == "crucible":
        return theme.text if color_distance(theme.text, theme.accent_soft) > 72 else contrast_text(theme.accent_soft)
    candidate = mix_hex(theme.text_dim, theme.text, 0.35)
    if color_distance(candidate, theme.accent_soft) < 60:
        c = contrast_text(theme.accent_soft)
        candidate = mix_hex(theme.text_dim, c, 0.45)
    return candidate


# ---------------------------------------------------------------------------
# QSettings persistence (merged from theme_storage.py)
# ---------------------------------------------------------------------------

_APP_NAME = "Crucible"
_ORG_NAME = "Crucible Launcher"
_THEME_KEY = "theme"
_THEME_SAVED_SLUG_KEY = "theme_saved_slug"
_LEGACY_REMOTE_KEY = "theme_remote_slug"
_SAVED_IMPORTED_THEMES_KEY = "saved_imported_themes"


def get_settings() -> QSettings:
    """Return a QSettings instance for the Crucible application."""
    return QSettings(_ORG_NAME, _APP_NAME)


def get_active_builtin_key() -> str:
    """Return the key of the currently active builtin theme (default ``'crucible'``)."""
    return str(get_settings().value(_THEME_KEY, "crucible", type=str) or "crucible")


def get_active_saved_theme_slug() -> str:
    """Return the slug of the currently active saved theme, or ``''`` if none."""
    return get_settings().value(_THEME_SAVED_SLUG_KEY, "", type=str) or ""


def _load_saved_theme_items() -> list[dict]:
    raw = get_settings().value(_SAVED_IMPORTED_THEMES_KEY, "", type=str) or ""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _write_saved_theme_items(items: list[dict]) -> None:
    get_settings().setValue(_SAVED_IMPORTED_THEMES_KEY, json.dumps(items))


def _saved_theme_to_dict(slug: str, theme: Theme, author: str = "") -> dict:
    d = {
        "slug": slug,
        "author": author,
        "name": theme.name,
        "accent": theme.accent,
        "accent_soft": theme.accent_soft,
        "bg": theme.bg,
        "chrome_bg": theme.chrome_bg,
        "border": theme.border,
        "text": theme.text,
        "text_dim": theme.text_dim,
    }
    for field in ("status_warning", "status_error", "status_success",
                  "status_info", "danger_hover", "text_disabled"):
        val = getattr(theme, field, "")
        if val:
            d[field] = val
    return d


def _saved_theme_needs_refresh(theme: Theme) -> bool:
    return not all([
        theme.accent, theme.accent_soft, theme.bg,
        theme.border, theme.text, theme.text_dim, theme.chrome_bg,
    ])


def _saved_theme_from_dict(item: dict) -> SavedImportedTheme:
    slug = normalize_vscode_theme_slug(item["slug"])
    theme = _build_theme(
        name=item["name"],
        key=f"saved:{slug}",
        accent=item["accent"],
        accent_soft=item.get("accent_soft") or mix_hex(item["bg"], item["accent"], 0.18),
        bg=item["bg"],
        border=item["border"],
        text=item["text"],
        text_dim=item["text_dim"],
        chrome_bg=item.get("chrome_bg"),
        status_warning=item.get("status_warning", ""),
        status_error=item.get("status_error", ""),
        status_success=item.get("status_success", ""),
        status_info=item.get("status_info", ""),
        danger_hover=item.get("danger_hover", ""),
        text_disabled=item.get("text_disabled", ""),
    )
    return SavedImportedTheme(slug=slug, author=item.get("author") or "Unknown Author", theme=theme)


def list_saved_imported_themes() -> list[SavedImportedTheme]:
    """Return all saved imported themes from QSettings."""
    saved: list[SavedImportedTheme] = []
    for item in _load_saved_theme_items():
        try:
            saved.append(_saved_theme_from_dict(item))
        except (KeyError, TypeError, ValueError):
            _log.warning("Skipping corrupt saved theme entry: %s", item, exc_info=True)
    return saved


def get_saved_imported_theme(slug: str) -> SavedImportedTheme | None:
    """Find and return a saved imported theme by its slug, or ``None``."""
    slug = normalize_vscode_theme_slug(slug)
    for saved in list_saved_imported_themes():
        if saved.slug == slug:
            return saved
    return None


def save_imported_theme(theme: Theme, slug: str, author: str = "") -> SavedImportedTheme:
    """Persist or update a saved imported theme in QSettings."""
    slug = normalize_vscode_theme_slug(slug)
    items = _load_saved_theme_items()
    payload = _saved_theme_to_dict(slug, theme, author)
    updated = False
    for index, item in enumerate(items):
        if item.get("slug") == slug:
            items[index] = payload
            updated = True
            break
    if not updated:
        items.append(payload)
    _write_saved_theme_items(items)
    get_settings().remove(_LEGACY_REMOTE_KEY)
    return _saved_theme_from_dict(payload)


def apply_saved_imported_theme(slug: str) -> Theme:
    """Activate a saved imported theme and invalidate the theme cache."""
    slug = normalize_vscode_theme_slug(slug)
    saved = get_saved_imported_theme(slug)
    if saved is None:
        raise ValueError("saved theme not found")
    settings = get_settings()
    settings.setValue(_THEME_KEY, "crucible")
    settings.setValue(_THEME_SAVED_SLUG_KEY, slug)
    settings.remove(_LEGACY_REMOTE_KEY)
    invalidate_theme_cache()
    return saved.theme


def apply_builtin_theme(theme: Theme) -> None:
    """Activate a builtin theme, clearing any saved-theme selection."""
    settings = get_settings()
    settings.setValue(_THEME_KEY, theme.key)
    settings.remove(_THEME_SAVED_SLUG_KEY)
    settings.remove(_LEGACY_REMOTE_KEY)
    invalidate_theme_cache()


def remove_saved_imported_theme(slug: str) -> bool:
    """Delete a saved imported theme by slug."""
    slug = normalize_vscode_theme_slug(slug)
    items = _load_saved_theme_items()
    filtered = [item for item in items if item.get("slug") != slug]
    if len(filtered) == len(items):
        return False
    _write_saved_theme_items(filtered)
    settings = get_settings()
    active_slug = settings.value(_THEME_SAVED_SLUG_KEY, "", type=str) or ""
    if active_slug == slug:
        apply_builtin_theme(get_builtin_theme("crucible"))
    invalidate_theme_cache()
    return True


def migrate_legacy_remote_theme() -> None:
    """Convert a legacy ``theme_remote_slug`` into a full saved imported theme."""
    settings = get_settings()
    legacy_slug = settings.value(_LEGACY_REMOTE_KEY, "", type=str) or ""
    if not legacy_slug:
        return
    try:
        imported = import_vscode_theme_snapshot(legacy_slug)
    except (OSError, ValueError, KeyError):
        return
    save_imported_theme(
        theme_from_import_palette(imported.palette, imported.slug),
        imported.slug,
        imported.author,
    )
    settings.setValue(_THEME_KEY, "crucible")
    settings.setValue(_THEME_SAVED_SLUG_KEY, imported.slug)
    settings.remove(_LEGACY_REMOTE_KEY)
    invalidate_theme_cache()


# ---------------------------------------------------------------------------
# Theme cache and resolution
# ---------------------------------------------------------------------------

_cached_theme: Theme | None = None


def invalidate_theme_cache() -> None:
    """Clear the cached theme so the next ``get_theme()`` re-reads settings.

    Also emits the global ``theme_changed`` signal so connected widgets can
    refresh without being part of a manual cascade.
    """
    global _cached_theme
    _cached_theme = None
    _get_signals().theme_changed.emit()


def get_theme() -> Theme:
    """Return the active theme, resolving from cache, saved themes, or builtin."""
    global _cached_theme
    if _cached_theme is not None:
        return _cached_theme

    settings = get_settings()

    # Check for active saved theme
    saved_slug = settings.value(_THEME_SAVED_SLUG_KEY, "", type=str) or ""
    if saved_slug:
        saved = get_saved_imported_theme(saved_slug)
        if saved is not None:
            if _saved_theme_needs_refresh(saved.theme):
                try:
                    imported = import_vscode_theme_snapshot(saved_slug)
                    saved = save_imported_theme(
                        theme_from_import_palette(imported.palette, imported.slug),
                        imported.slug, imported.author,
                    )
                except (OSError, ValueError, KeyError):
                    _log.warning("Failed to refresh saved theme '%s'", saved_slug, exc_info=True)
            _cached_theme = saved.theme
            return _cached_theme

    # Check for legacy remote slug that needs migration
    legacy_slug = settings.value(_LEGACY_REMOTE_KEY, "", type=str) or ""
    if legacy_slug:
        migrate_legacy_remote_theme()
        saved = get_saved_imported_theme(
            settings.value(_THEME_SAVED_SLUG_KEY, "", type=str) or "",
        )
        if saved is not None:
            _cached_theme = saved.theme
            return _cached_theme

    # Fall back to builtin
    key = settings.value(_THEME_KEY, "crucible")
    _cached_theme = get_builtin_theme(str(key))
    return _cached_theme


# ---------------------------------------------------------------------------
# Public color getters — return typed dataclasses
# ---------------------------------------------------------------------------


def get_accent() -> str:
    """Return the active theme's accent hex color."""
    return get_theme().accent


def get_text() -> str:
    """Return the active theme's primary text hex color."""
    return get_theme().text


def get_text_colors() -> TextColors:
    """Return text colors from the active theme."""
    theme = get_theme()
    return TextColors(text=theme.text, text_dim=theme.text_dim)


def get_bg() -> BackgroundColors:
    """Return background colors from the active theme."""
    theme = get_theme()
    return BackgroundColors(bg=theme.bg, border=theme.border)


def get_surface_colors() -> SurfaceColors:
    """Return surface-level colors for the active theme.

    Derives a 3-tone visual hierarchy from the theme's existing colors:
    chrome (titlebar/nav) → panel (mid-tone) → content (editor bg).
    """
    theme = get_theme()
    chrome_bg = theme.chrome_bg or mix_hex(theme.bg, theme.border, 0.08)
    return SurfaceColors(
        window_bg=theme.bg,
        titlebar_bg=chrome_bg,
        nav_bg=chrome_bg,
        panel_bg=mix_hex(chrome_bg, theme.bg, 0.5),
        content_bg=theme.bg,
        status_bg=mix_hex(theme.bg, theme.accent, 0.06),
        status_text=theme.text,
    )


def get_selection_colors() -> SelectionColors:
    """Return selection and hover colors for the active theme."""
    theme = get_theme()
    return SelectionColors(
        nav_accent=theme.accent,
        selection_bg=theme.accent_soft,
        selection_text=_derive_selection_text(theme),
        text_selection_bg=_derive_text_selection_bg(theme),
        hover_bg=mix_hex(theme.accent_soft, theme.bg, 0.45),
    )


# Default status palette (One Dark inspired, readable on dark backgrounds)
_DEFAULT_STATUS_WARNING = "#e5c07b"
_DEFAULT_STATUS_ERROR = "#e06c75"
_DEFAULT_STATUS_SUCCESS = "#98c379"
_DEFAULT_STATUS_INFO = "#61afef"


def get_status_colors() -> StatusColors:
    """Return semantic status colors for the active theme.

    Uses explicit theme values when set, otherwise falls back to sensible
    defaults derived from the theme's palette.
    """
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


# ---------------------------------------------------------------------------
# Animation toggle
# ---------------------------------------------------------------------------

_ANIMATIONS_KEY = "animations_enabled"


def animations_enabled() -> bool:
    """Return whether UI animations are enabled (default: True)."""
    return get_settings().value(_ANIMATIONS_KEY, True, type=bool)


def set_animations_enabled(enabled: bool) -> None:
    """Persist the animation-enabled preference."""
    get_settings().setValue(_ANIMATIONS_KEY, enabled)
