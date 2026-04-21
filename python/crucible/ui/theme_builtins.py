"""Builtin theme definitions for Crucible."""

from __future__ import annotations

from crucible.ui.color_utils import mix_hex, validate_hex


# ---------------------------------------------------------------------------
# Core theme dataclass (imported here to avoid circular deps)
# ---------------------------------------------------------------------------

from crucible.ui.theme_types import Theme


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
        name="Catppuccin Mocha",
        key="catppuccin-mocha",
        accent="#cba6f7",
        accent_soft="#2a2440",
        bg="#1e1e2e",
        border="#45475a",
        text="#cdd6f4",
        text_dim="#a6adc8",
        chrome_bg="#181825",
    ),
    _build_theme(
        name="Nord",
        key="nord",
        accent="#88c0d0",
        accent_soft="#2e3440",
        bg="#2e3440",
        border="#4c566a",
        text="#eceff4",
        text_dim="#d8dee9",
        chrome_bg="#272c36",
    ),
    _build_theme(
        name="Dracula",
        key="dracula",
        accent="#bd93f9",
        accent_soft="#312450",
        bg="#282a36",
        border="#44475a",
        text="#f8f8f2",
        text_dim="#bfbfbf",
        chrome_bg="#21222c",
    ),
    _build_theme(
        name="Gruvbox Dark",
        key="gruvbox-dark",
        accent="#fe8019",
        accent_soft="#3c2a14",
        bg="#282828",
        border="#504945",
        text="#ebdbb2",
        text_dim="#a89984",
        chrome_bg="#1d2021",
    ),
    _build_theme(
        name="Tokyo Night",
        key="tokyo-night",
        accent="#7aa2f7",
        accent_soft="#1f2335",
        bg="#1a1b26",
        border="#3b4261",
        text="#c0caf5",
        text_dim="#a9b1d6",
        chrome_bg="#16161e",
    ),
    _build_theme(
        name="Rosé Pine",
        key="rose-pine",
        accent="#c4a7e7",
        accent_soft="#2a2438",
        bg="#191724",
        border="#403d52",
        text="#e0def4",
        text_dim="#908caa",
        chrome_bg="#1f1d2e",
    ),
    _build_theme(
        name="Everforest",
        key="everforest",
        accent="#a7c080",
        accent_soft="#2b3328",
        bg="#2d353b",
        border="#4f585e",
        text="#d3c6aa",
        text_dim="#9da9a0",
        chrome_bg="#272e33",
    ),
    _build_theme(
        name="Solarized Dark",
        key="solarized-dark",
        accent="#268bd2",
        accent_soft="#0a3749",
        bg="#002b36",
        border="#2a4f5a",
        text="#839496",
        text_dim="#657b83",
        chrome_bg="#001e27",
    ),
]

_THEME_BY_KEY = {theme.key: theme for theme in BUILTIN_THEMES}


def builtin_themes() -> list[Theme]:
    """Return the list of all built-in Theme objects."""
    return BUILTIN_THEMES


def get_builtin_theme(key: str) -> Theme:
    """Return the built-in Theme matching *key*, defaulting to Crucible."""
    return _THEME_BY_KEY.get(key, BUILTIN_THEMES[0])
