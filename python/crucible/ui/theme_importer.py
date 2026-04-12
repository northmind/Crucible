from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
import urllib.parse
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from crucible.ui.color_utils import (
    color_distance,
    contrast_text,
    mix_hex,
    shift_lightness,
)

_log = logging.getLogger(__name__)
_USER_AGENT = "Mozilla/5.0"
_BASE_URL = "https://vscodethemes.com"
_THEME_RE = re.compile(r'"theme":(?P<theme>\{.*?\})\}\]\},"searchQuery":', re.S)


@dataclass(frozen=True)
class ImportedThemeSnapshot:
    slug: str
    name: str
    author: str
    palette: dict[str, str]


def normalize_vscode_theme_slug(value: str) -> str:
    """Validate and normalize a vscodethemes.com URL or path to a slug.

    Args:
        value: A full ``https://vscodethemes.com/e/...`` URL or a bare
               ``/e/...`` path.

    Returns:
        The normalized slug path (e.g. ``/e/publisher.theme``).

    Raises:
        ValueError: If *value* is empty, not from vscodethemes.com, or does
                    not point to a theme page.
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty theme url")
    if raw.startswith("/e/"):
        return raw.split("?", 1)[0]
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raise ValueError("paste a full vscodethemes url")
    parsed = urllib.parse.urlparse(raw)
    if parsed.netloc not in {"vscodethemes.com", "www.vscodethemes.com"}:
        raise ValueError("url must be from vscodethemes.com")
    if not parsed.path.startswith("/e/"):
        raise ValueError("url must point to a theme page")
    return parsed.path


def import_vscode_theme_snapshot(value: str) -> ImportedThemeSnapshot:
    """Fetch a VS Code theme page and parse it into an ImportedThemeSnapshot.

    Args:
        value: A vscodethemes.com URL or ``/e/...`` slug path.

    Returns:
        An ImportedThemeSnapshot containing the slug, name, author, and
        extracted color palette.

    Raises:
        ValueError: If the URL is invalid or the theme data cannot be
                    extracted from the page HTML.
        urllib.error.URLError: If the HTTP request fails.
    """
    slug = normalize_vscode_theme_slug(value)
    html = _fetch_html(f"{_BASE_URL}{slug}")
    match = _THEME_RE.search(html)
    if not match:
        raise ValueError("could not extract theme data from page")
    data = json.loads(match.group("theme"))
    colors = _extract_color_map(data)

    bg = _pick_color(
        colors,
        "editor.background",
        "panel.background",
        "editorBackground",
        "panelBackground",
        fallback="#15171b",
    )
    chrome_bg = _pick_color(
        colors,
        "activityBar.background",
        "titleBar.activeBackground",
        "sideBar.background",
        "activityBarBackground",
        "titleBarActiveBackground",
        "sideBarBackground",
        fallback=bg,
    )
    text = _pick_color(
        colors,
        "editor.foreground",
        "editorForeground",
        "foreground",
        "tab.activeForeground",
        "titleBar.activeForeground",
        "tabActiveForeground",
        "titleBarActiveForeground",
        fallback=contrast_text(bg),
    )
    text_dim = _pick_color(
        colors,
        "descriptionForeground",
        "sideBar.foreground",
        "sideBarForeground",
        "tab.inactiveForeground",
        "titleBar.inactiveForeground",
        "tabInactiveForeground",
        "titleBarInactiveForeground",
        fallback=mix_hex(text, bg, 0.28),
    )
    accent = _pick_accent_color(
        colors,
        "activityBarBadge.background",
        "badge.background",
        "button.background",
        "focusBorder",
        "progressBar.background",
        "textLink.foreground",
        "list.highlightForeground",
        "activityBar.activeBorder",
        "activityBar.foreground",
        "tab.activeForeground",
        "activityBarBadgeBackground",
        "buttonBackground",
        "activityBarForeground",
        "tabActiveForeground",
        fallback=text,
        bg=bg,
    )
    accent_soft_raw = _pick_color(
        colors,
        "activityBar.activeBackground",
        "tab.activeBackground",
        "list.activeSelectionBackground",
        "activityBarActiveBackground",
        "tabActiveBackground",
        "listActiveSelectionBackground",
        fallback=mix_hex(bg, accent, 0.18),
    )
    accent_soft = _derive_soft_fill(accent_soft_raw, accent, bg)
    border = _pick_border_color(colors, bg, text, text_dim)

    return ImportedThemeSnapshot(
        slug=slug,
        name=data.get("displayName") or data.get("name") or "Imported Theme",
        author=_first_non_empty(
            data.get("publisherDisplayName"),
            data.get("publisherName"),
            data.get("publisher"),
            data.get("publisherId"),
            _infer_author_from_slug(slug),
        ),
        palette={
            "name": data.get("displayName") or data.get("name") or "Imported Theme",
            "accent": accent,
            "accent_soft": accent_soft,
            "bg": bg,
            "chrome_bg": chrome_bg,
            "border": border,
            "text": text,
            "text_dim": text_dim,
        },
    )


def _extract_color_map(data: dict) -> dict[str, str]:
    colors: dict[str, str] = {}
    nested = data.get("colors")
    if isinstance(nested, dict):
        for key, value in nested.items():
            if isinstance(value, str):
                colors[key] = value
    for key, value in data.items():
        if isinstance(value, str):
            colors[key] = value
    return colors


def _pick_border_color(colors: dict[str, str], bg: str, text: str, text_dim: str) -> str:
    quiet_keys = (
        "panel.border",
        "sideBar.border",
        "statusBar.border",
        "tab.border",
        "activityBar.border",
        "titleBar.border",
        "editorGroup.border",
        "contrastBorder",
        "panelBorder",
        "statusBarBorder",
        "tabBorder",
        "tabsContainerBorder",
        "activityBarBorder",
        "titleBarBorder",
        "editorGroupBorder",
        "sideBarSectionHeader.border",
    )
    for key in quiet_keys:
        value = colors.get(key)
        if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            if color_distance(value, bg) >= 20 and color_distance(value, text) >= 28:
                return value
    return _derive_neutral_border(bg, text_dim)


def _pick_color(colors: dict[str, str], *keys: str, fallback: str) -> str:
    for key in keys:
        value = colors.get(key)
        if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            return value
    return fallback


def _is_viable_accent(color: str, bg: str) -> bool:
    """Return True if *color* is chromatic enough and distinct enough from *bg* to serve as accent."""
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    # Channel spread: grays/whites/blacks have near-zero spread
    spread = max(r, g, b) - min(r, g, b)
    if spread < 25:
        return False
    if color_distance(color, bg) < 40:
        return False
    return True


def _pick_accent_color(colors: dict[str, str], *keys: str, fallback: str, bg: str) -> str:
    """Pick the first viable accent color — must be chromatic and distinct from bg."""
    for key in keys:
        value = colors.get(key)
        if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            if _is_viable_accent(value, bg):
                return value
    return fallback


def _derive_soft_fill(raw: str, accent: str, bg: str) -> str:
    fill = raw if raw.lower() != bg.lower() else mix_hex(bg, accent, 0.18)
    if color_distance(fill, bg) < 18:
        fill = mix_hex(bg, accent, 0.18)
    return fill


def _derive_neutral_border(bg: str, text_dim: str) -> str:
    border = mix_hex(bg, text_dim, 0.18)
    if color_distance(border, bg) < 20:
        border = shift_lightness(bg, 22)
    return border


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.read().decode("utf-8", "replace")


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Unknown Author"


def _infer_author_from_slug(slug: str) -> str:
    parts = slug.strip("/").split("/")
    if len(parts) >= 2 and "." in parts[1]:
        publisher = parts[1].split(".", 1)[0]
        return publisher.replace("-", " ").replace("_", " ").title()
    return "Unknown Author"


# ---------------------------------------------------------------------------
# Async import worker (Phase 2f)
# ---------------------------------------------------------------------------


class ThemeImportWorker(QThread):
    """Background thread that fetches and parses a VS Code theme.

    Signals:
        succeeded(ImportedThemeSnapshot): emitted on successful import.
        failed(str): emitted with an error message on failure.
    """

    succeeded = pyqtSignal(object)  # ImportedThemeSnapshot
    failed = pyqtSignal(str)

    def __init__(self, raw_url: str, parent: object | None = None) -> None:
        super().__init__(parent)
        self._raw_url = raw_url

    def run(self) -> None:
        try:
            snapshot = import_vscode_theme_snapshot(self._raw_url)
            self.succeeded.emit(snapshot)
        except (OSError, ValueError, KeyError) as exc:
            _log.debug("Theme import failed for %r: %s", self._raw_url, exc)
            self.failed.emit(str(exc))
