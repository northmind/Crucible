from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSettings

from crucible.ui.theme_importer import (
    import_vscode_theme_snapshot,
    normalize_vscode_theme_slug,
    _mix_hex,
)

if TYPE_CHECKING:
    from crucible.ui.theme_system import SavedImportedTheme, Theme


_APP_NAME = "Crucible"
_ORG_NAME = "Crucible Launcher"
_THEME_KEY = "theme"
_THEME_SAVED_SLUG_KEY = "theme_saved_slug"
_LEGACY_REMOTE_KEY = "theme_remote_slug"
_SAVED_IMPORTED_THEMES_KEY = "saved_imported_themes"


def get_settings() -> QSettings:
    """Return a QSettings instance for the Crucible application."""
    return QSettings(_ORG_NAME, _APP_NAME)


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
    return {
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


def _saved_theme_needs_refresh(theme: Theme) -> bool:
    return not all([
        theme.accent,
        theme.accent_soft,
        theme.bg,
        theme.border,
        theme.text,
        theme.text_dim,
        theme.chrome_bg,
    ])


def _saved_theme_from_dict(item: dict) -> SavedImportedTheme:
    from crucible.ui.theme_system import SavedImportedTheme, _build_theme

    slug = normalize_vscode_theme_slug(item["slug"])
    theme = _build_theme(
        name=item["name"],
        key=f"saved:{slug}",
        accent=item["accent"],
        accent_soft=item.get("accent_soft") or _mix_hex(item["bg"], item["accent"], 0.18),
        bg=item["bg"],
        border=item["border"],
        text=item["text"],
        text_dim=item["text_dim"],
        chrome_bg=item.get("chrome_bg"),
    )
    return SavedImportedTheme(slug=slug, author=item.get("author") or "Unknown Author", theme=theme)


def list_saved_imported_themes() -> list[SavedImportedTheme]:
    """Return all saved imported themes from QSettings.

    Corrupt entries are logged and silently skipped.
    """
    from crucible.ui.theme_system import SavedImportedTheme

    saved: list[SavedImportedTheme] = []
    for item in _load_saved_theme_items():
        try:
            saved.append(_saved_theme_from_dict(item))
        except (KeyError, TypeError, ValueError):
            logging.getLogger(__name__).warning(
                "Skipping corrupt saved theme entry: %s", item, exc_info=True,
            )
            continue
    return saved


def get_saved_imported_theme(slug: str) -> SavedImportedTheme | None:
    """Find and return a saved imported theme by its slug, or ``None`` if not found."""
    slug = normalize_vscode_theme_slug(slug)
    for saved in list_saved_imported_themes():
        if saved.slug == slug:
            return saved
    return None


def save_imported_theme(theme: Theme, slug: str, author: str = "") -> SavedImportedTheme:
    """Persist or update a saved imported theme in QSettings.

    Args:
        theme: The Theme to save.
        slug: The vscodethemes.com slug identifying the theme.
        author: Optional author name stored alongside the theme.

    Returns:
        The resulting SavedImportedTheme as re-read from storage.
    """
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
    """Activate a saved imported theme and invalidate the theme cache.

    Args:
        slug: The vscodethemes.com slug of the theme to activate.

    Returns:
        The activated Theme instance.

    Raises:
        ValueError: If no saved theme matches the given slug.
    """
    from crucible.ui.theme_system import invalidate_theme_cache

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
    """Activate a builtin theme, clearing any saved-theme selection and cache."""
    from crucible.ui.theme_system import invalidate_theme_cache

    settings = get_settings()
    settings.setValue(_THEME_KEY, theme.key)
    settings.remove(_THEME_SAVED_SLUG_KEY)
    settings.remove(_LEGACY_REMOTE_KEY)
    invalidate_theme_cache()


def remove_saved_imported_theme(slug: str) -> bool:
    """Delete a saved imported theme by slug.

    If the removed theme was the active selection, falls back to the Crucible
    builtin theme.

    Args:
        slug: The vscodethemes.com slug of the theme to remove.

    Returns:
        ``True`` if a theme was removed, ``False`` if the slug was not found.
    """
    from crucible.ui.theme_system import get_builtin_theme, invalidate_theme_cache

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
    """Convert a legacy ``theme_remote_slug`` setting into a full saved imported theme.

    If the legacy key is absent or the remote fetch fails, this is a no-op.
    """
    from crucible.ui.theme_system import theme_from_import_palette, invalidate_theme_cache

    settings = get_settings()
    legacy_slug = settings.value(_LEGACY_REMOTE_KEY, "", type=str) or ""
    if not legacy_slug:
        return
    try:
        imported = import_vscode_theme_snapshot(legacy_slug)
    except (OSError, ValueError, KeyError):
        return
    save_imported_theme(theme_from_import_palette(imported.palette, imported.slug), imported.slug, imported.author)
    settings.setValue(_THEME_KEY, "crucible")
    settings.setValue(_THEME_SAVED_SLUG_KEY, imported.slug)
    settings.remove(_LEGACY_REMOTE_KEY)
    invalidate_theme_cache()
