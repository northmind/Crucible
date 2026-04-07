from __future__ import annotations

from dataclasses import dataclass
import json
import re
import urllib.parse
import urllib.request

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
        "tab.activeForeground",
        "titleBar.activeForeground",
        "editorForeground",
        "tabActiveForeground",
        "titleBarActiveForeground",
        fallback=_contrast_text(bg),
    )
    text_dim = _pick_color(
        colors,
        "descriptionForeground",
        "activityBar.inactiveForeground",
        "tab.inactiveForeground",
        "titleBar.inactiveForeground",
        "activityBarInactiveForeground",
        "tabInactiveForeground",
        "titleBarInactiveForeground",
        fallback=_mix_hex(text, bg, 0.42),
    )
    accent = _pick_color(
        colors,
        "activityBar.foreground",
        "tab.activeForeground",
        "activityBarForeground",
        "tabActiveForeground",
        "activityBarBadge.background",
        "button.background",
        "activityBarBadgeBackground",
        "buttonBackground",
        fallback=text,
    )
    accent_soft_raw = _pick_color(
        colors,
        "activityBar.activeBackground",
        "tab.activeBackground",
        "list.activeSelectionBackground",
        "activityBarActiveBackground",
        "tabActiveBackground",
        "listActiveSelectionBackground",
        fallback=_mix_hex(bg, accent, 0.18),
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
            if _color_distance(value, bg) >= 20 and _color_distance(value, text) >= 28:
                return value
    return _derive_neutral_border(bg, text_dim)


def _pick_color(colors: dict[str, str], *keys: str, fallback: str) -> str:
    for key in keys:
        value = colors.get(key)
        if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            return value
    return fallback


def _derive_soft_fill(raw: str, accent: str, bg: str) -> str:
    fill = raw if raw.lower() != bg.lower() else _mix_hex(bg, accent, 0.18)
    if _color_distance(fill, bg) < 18:
        fill = _mix_hex(bg, accent, 0.18)
    return fill


def _derive_neutral_border(bg: str, text_dim: str) -> str:
    border = _mix_hex(bg, text_dim, 0.18)
    if _color_distance(border, bg) < 20:
        border = _shift_lightness(bg, 22)
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


def _contrast_text(bg_hex: str) -> str:
    r, g, b = _hex_to_rgb(bg_hex)
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    return "#f3f1eb" if luminance < 0.55 else "#17191e"


def _mix_hex(a_hex: str, b_hex: str, amount: float) -> str:
    amount = max(0.0, min(1.0, amount))
    ar, ag, ab = _hex_to_rgb(a_hex)
    br, bg, bb = _hex_to_rgb(b_hex)
    r = round(ar + (br - ar) * amount)
    g = round(ag + (bg - ag) * amount)
    b = round(ab + (bb - ab) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def _shift_lightness(value: str, amount: int) -> str:
    r, g, b = _hex_to_rgb(value)
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    delta = amount if luminance < 0.5 else -amount
    r = max(0, min(255, r + delta))
    g = max(0, min(255, g + delta))
    b = max(0, min(255, b + delta))
    return f"#{r:02x}{g:02x}{b:02x}"


def _color_distance(a_hex: str, b_hex: str) -> int:
    ar, ag, ab = _hex_to_rgb(a_hex)
    br, bg, bb = _hex_to_rgb(b_hex)
    return abs(ar - br) + abs(ag - bg) + abs(ab - bb)


_HEX_COLOR_RE = re.compile(r'^#?[0-9a-fA-F]{6}$')


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if not _HEX_COLOR_RE.match(value):
        raise ValueError(f"Invalid hex color: #{value}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
