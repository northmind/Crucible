from __future__ import annotations

import logging
from dataclasses import dataclass

from crucible.ui.theme_importer import (
    _hex_to_rgb,
    _mix_hex,
    _color_distance,
    _contrast_text,
)


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


@dataclass(frozen=True)
class SavedImportedTheme:
    slug: str
    author: str
    theme: Theme


def _derive_text_selection_bg(theme: Theme) -> str:
    candidate = _mix_hex(theme.accent, theme.bg, 0.22)
    if _color_distance(candidate, _mix_hex(theme.accent_soft, theme.bg, 0.45)) < 36:
        candidate = _mix_hex(theme.accent, theme.bg, 0.12)
    if _color_distance(candidate, theme.bg) < 48:
        candidate = _mix_hex(theme.accent, theme.text, 0.18)
    return candidate


def _derive_selection_text(theme: Theme) -> str:
    if theme.key == "crucible":
        return theme.text if _color_distance(theme.text, theme.accent_soft) > 72 else _contrast_text(theme.accent_soft)
    candidate = _mix_hex(theme.text_dim, theme.text, 0.35)
    if _color_distance(candidate, theme.accent_soft) < 60:
        contrast = _contrast_text(theme.accent_soft)
        candidate = _mix_hex(theme.text_dim, contrast, 0.45)
    return candidate


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
) -> Theme:
    return Theme(
        name=name,
        key=key,
        accent=accent,
        accent_soft=accent_soft,
        bg=bg,
        border=border,
        text=text,
        text_dim=text_dim,
        chrome_bg=chrome_bg or _mix_hex(bg, border, 0.08),
    )


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
    """Build a Theme from an imported palette dict.

    Args:
        data: Dict with keys 'name', 'accent', 'accent_soft', 'bg', 'border',
              'text', 'text_dim', and optionally 'key' and 'chrome_bg'.
        slug: Optional VS Code theme slug used to derive the theme key.

    Returns:
        A fully constructed Theme instance.

    Raises:
        KeyError: If required palette keys are missing from *data*.
    """
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
    )


# ---------------------------------------------------------------------------
# Persistence delegates — canonical implementations live in theme_storage.py.
# Re-exported here so existing consumers keep working.
# ---------------------------------------------------------------------------
from crucible.ui.theme_storage import (  # noqa: E402
    get_settings,
    get_active_saved_theme_slug,
    list_saved_imported_themes,
    get_saved_imported_theme,
    save_imported_theme,
    apply_saved_imported_theme,
    apply_builtin_theme,
    remove_saved_imported_theme,
    migrate_legacy_remote_theme,
)


_cached_theme: Theme | None = None


def invalidate_theme_cache() -> None:
    """Clear the cached theme so the next ``get_theme()`` call re-reads settings."""
    global _cached_theme
    _cached_theme = None


def get_theme() -> Theme:
    """Return the active theme, resolving from cache, saved themes, or builtin fallback.

    On first call (or after ``invalidate_theme_cache()``), the active theme is
    resolved by checking saved-theme settings, legacy remote slugs, and finally
    the builtin theme key stored in QSettings.  The result is cached for
    subsequent calls.

    Returns:
        The currently active Theme instance.
    """
    global _cached_theme
    if _cached_theme is not None:
        return _cached_theme
    settings = get_settings()
    from crucible.ui.theme_storage import _THEME_SAVED_SLUG_KEY, _LEGACY_REMOTE_KEY, _THEME_KEY, _saved_theme_needs_refresh
    saved_slug = settings.value(_THEME_SAVED_SLUG_KEY, "", type=str) or ""
    if saved_slug:
        saved = get_saved_imported_theme(saved_slug)
        if saved is not None:
            if _saved_theme_needs_refresh(saved.theme):
                try:
                    from crucible.ui.theme_importer import import_vscode_theme_snapshot
                    imported = import_vscode_theme_snapshot(saved_slug)
                    saved = save_imported_theme(theme_from_import_palette(imported.palette, imported.slug), imported.slug, imported.author)
                except (OSError, ValueError, KeyError):
                    logging.getLogger(__name__).warning(
                        "Failed to refresh saved theme '%s'", saved_slug, exc_info=True,
                    )
            _cached_theme = saved.theme
            return _cached_theme
    legacy_slug = settings.value(_LEGACY_REMOTE_KEY, "", type=str) or ""
    if legacy_slug:
        migrate_legacy_remote_theme()
        saved = get_saved_imported_theme(settings.value(_THEME_SAVED_SLUG_KEY, "", type=str) or "")
        if saved is not None:
            _cached_theme = saved.theme
            return _cached_theme
    key = settings.value(_THEME_KEY, "crucible")
    _cached_theme = get_builtin_theme(str(key))
    return _cached_theme


def get_accent() -> str:
    """Return the active theme's accent hex color."""
    return get_theme().accent


def get_text() -> str:
    """Return the active theme's primary text hex color."""
    return get_theme().text


def get_text_colors() -> dict[str, str]:
    """Return ``{'text': ..., 'text_dim': ...}`` from the active theme."""
    theme = get_theme()
    return {"text": theme.text, "text_dim": theme.text_dim}


def get_bg() -> dict[str, str]:
    """Return ``{'bg': ..., 'border': ...}`` from the active theme."""
    theme = get_theme()
    return {"bg": theme.bg, "border": theme.border}


def get_surface_colors() -> dict[str, str]:
    """Return a dict of surface-level color values for the active theme.

    Keys: ``window_bg``, ``titlebar_bg``, ``nav_bg``, ``panel_bg``,
    ``content_bg``, ``status_bg``, ``status_text``.
    """
    theme = get_theme()
    chrome_bg = theme.chrome_bg or _mix_hex(theme.bg, theme.border, 0.08)
    return {
        "window_bg": theme.bg,
        "titlebar_bg": chrome_bg,
        "nav_bg": chrome_bg,
        "panel_bg": chrome_bg,
        "content_bg": theme.bg,
        "status_bg": theme.bg,
        "status_text": theme.text,
    }


def get_selection_colors() -> dict[str, str]:
    """Return a dict of selection and hover color values for the active theme.

    Keys: ``nav_accent``, ``selection_bg``, ``selection_text``,
    ``text_selection_bg``, ``hover_bg``.
    """
    theme = get_theme()
    return {
        "nav_accent": theme.accent,
        "selection_bg": theme.accent_soft,
        "selection_text": _derive_selection_text(theme),
        "text_selection_bg": _derive_text_selection_bg(theme),
        "hover_bg": _mix_hex(theme.accent_soft, theme.bg, 0.45),
    }
