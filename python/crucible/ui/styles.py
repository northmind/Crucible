from PyQt6.QtGui import QColor

from crucible.ui.theme_system import (
    BackgroundColors,
    get_accent,
    get_bg,
    get_selection_colors,
    get_surface_colors,
    get_text,
    get_text_colors,
)
from crucible.ui.tokens import FONT_BASE, FONT_MONO, PROGRESS_HEIGHT, SCROLLBAR_WIDTH


def _colors() -> tuple[str, BackgroundColors]:
    a = get_accent()
    bg = get_bg()
    return a, bg


# ---------------------------------------------------------------------------
# Low-level color helpers
# ---------------------------------------------------------------------------


def shell_fill() -> str:
    """Return the current theme's window background color string."""
    return get_surface_colors().window_bg


def panel_fill() -> str:
    """Return the current theme's panel background color string."""
    return get_surface_colors().panel_bg


def line_accent() -> str:
    """Return the current theme's border color string."""
    return get_bg().border


def line_accent_rgba(alpha: int) -> str:
    """Return the theme border color as an rgba() string with the given alpha."""
    c = QColor(line_accent())
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


# ---------------------------------------------------------------------------
# Parametric QSS helpers
# ---------------------------------------------------------------------------


def mono_label(
    *,
    dim: bool = True,
    size: str = f"{FONT_BASE}pt",
    bold: bool = False,
    padding: str | None = None,
    extra: str = "",
) -> str:
    """Return QSS for a monospace label using theme text colors.

    *dim=True* uses ``text_dim``; *dim=False* uses ``text``.
    """
    tc = get_text_colors()
    color = tc.text_dim if dim else tc.text
    parts = [
        f"color: {color};",
        "background: transparent;",
        f"font-family: {FONT_MONO};",
        f"font-size: {size};",
    ]
    if bold:
        parts.append("font-weight: bold;")
    if padding:
        parts.append(f"padding: {padding};")
    if extra:
        parts.append(extra)
    return " ".join(parts)


def flat_button(
    *,
    size: str = f"{FONT_BASE}pt",
    color: str | None = None,
    hover_color: str | None = None,
    hover_bg: str | None = None,
    disabled_color: str | None = None,
    padding: str = "0 6px",
    extra: str = "",
) -> str:
    """Return QSS for a flat monospace QPushButton with hover state.

    Defaults to dim text that highlights to accent on hover.
    """
    tc = get_text_colors()
    sel = get_selection_colors()
    c = color or tc.text_dim
    hc = hover_color or line_accent()
    parts = [
        f"QPushButton {{ color: {c}; background: transparent; border: none;",
        f" font-family: {FONT_MONO}; font-size: {size}; padding: {padding};",
    ]
    if extra:
        parts.append(f" {extra}")
    parts.append(" }")
    hover_parts = [f"QPushButton:hover {{ color: {hc};"]
    if hover_bg:
        hover_parts.append(f" background: {hover_bg};")
    hover_parts.append(" }")
    if disabled_color:
        parts.append(f"QPushButton:disabled {{ color: {disabled_color}; }}")
    return "".join(parts) + "".join(hover_parts)


def text_input(*, size: str = f"{FONT_BASE}pt") -> str:
    """Return QSS for a themed QLineEdit with selection colors."""
    tc = get_text_colors()
    sel = get_selection_colors()
    return (
        f"QLineEdit {{ background: transparent; color: {tc.text}; border: none;"
        f" font-family: {FONT_MONO}; font-size: {size};"
        f" padding: 2px 0px;"
        f" selection-background-color: {sel.text_selection_bg};"
        f" selection-color: {sel.selection_text}; }}"
        f"QLineEdit::placeholder {{ color: {tc.text_dim}; }}"
    )


def _scrollbar_qss(accent: str) -> str:
    """Return QSS rules for thin accent-colored scrollbars (vertical + horizontal)."""
    return (
        f"QScrollBar:vertical {{ background: transparent; width: {SCROLLBAR_WIDTH}px; margin: 0; }}"
        f"QScrollBar::handle:vertical {{ background: {accent}; min-height: 20px; border: none; }}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
        f"QScrollBar:horizontal {{ background: transparent; height: {SCROLLBAR_WIDTH}px; margin: 0; }}"
        f"QScrollBar::handle:horizontal {{ background: {accent}; min-width: 20px; border: none; }}"
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
        "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
    )


def scroll_area(*, accent: str | None = None) -> str:
    """Return QSS for a QScrollArea with thin accent-colored scrollbars."""
    a = accent or line_accent()
    return "QScrollArea { background: transparent; border: none; }" + _scrollbar_qss(a)


def list_scroll_area(*, accent: str | None = None) -> str:
    """Return QSS for a QListWidget with transparent items and thin scrollbars."""
    a = accent or line_accent()
    return (
        "QListWidget { background-color: transparent; border: none; outline: none; }"
        " QListWidget::item { background-color: transparent; border: none; padding: 0; }"
        " QListWidget::item:selected, QListWidget::item:hover { background-color: transparent; }"
    ) + " " + _scrollbar_qss(a)


def divider() -> str:
    """Return QSS for a 1px horizontal separator line."""
    return f"background: {line_accent()};"


def section_header() -> str:
    """Return QSS for an accent-colored section header label."""
    return mono_label(dim=False, extra=f"color: {get_accent()};")


def focus_outline() -> str:
    """Return a QSS ``outline`` rule for keyboard-focus indicators.

    Apply this inside a ``:focus`` pseudo-state to give a 1px dashed
    accent-colored outline around interactive widgets.
    """
    return f"outline: 1px dashed {get_accent()}; outline-offset: 2px;"

# ---------------------------------------------------------------------------
# Composite QSS helpers
# ---------------------------------------------------------------------------


def progress_bar() -> str:
    """Return QSS for a 4px-tall accent-colored progress bar."""
    a, bg = _colors()
    return f"""
        QProgressBar {{
            border: none;
            border-bottom: 1px solid {a};
            text-align: center;
            color: transparent;
            background-color: {bg.bg};
            max-height: {PROGRESS_HEIGHT}px;
            min-height: {PROGRESS_HEIGHT}px;
        }}
        QProgressBar::chunk {{ background-color: {a}; }}
    """


def tooltip() -> str:
    """Return QSS for themed QToolTip widgets."""
    a, bg = _colors()
    return f"""
        QToolTip {{
            color: {get_text()};
            background-color: {bg.bg};
            border: 1px solid {bg.border};
            padding: 3px 6px;
            font-family: {FONT_MONO};
            font-size: {FONT_BASE}pt;
        }}
    """


def window_bg() -> str:
    """Return QSS for a transparent, borderless background."""
    return "background: transparent; border: none;"


def central_widget() -> str:
    """Return QSS for the main central widget and its child containers."""
    edge = line_accent()
    return (
        f"#CentralWidget {{"
        f" background: {shell_fill()};"
        f" border: 1px solid {edge};"
        f" border-radius: 0px;"
        f" }}"
        f"#CentralWidget > QWidget {{ background: transparent; }}"
        f"#CentralWidget #MainContainer {{"
        f" background: transparent;"
        f" border: none;"
        f" }}"
    )


def file_dialog() -> str:
    """Return QSS for fully themed QFileDialog widgets."""
    a, bg = _colors()
    light = QColor(a).lighter(130).name()
    return f"""
        QFileDialog {{
            background-color: {bg.bg};
            color: {a};
        }}
        QWidget {{
            background-color: {bg.bg};
            color: {a};
            font-family: {FONT_MONO};
        }}
        QTreeView, QListView {{
            background-color: {bg.bg};
            color: {a};
            border: none;
            selection-background-color: {a};
            selection-color: {bg.bg};
        }}
        QTreeView::item:hover, QListView::item:hover {{
            color: {light};
        }}
        QHeaderView::section {{
            background-color: {bg.bg};
            color: {a};
            border: none;
            padding: 4px;
        }}
        QLineEdit {{
            background-color: {bg.bg};
            color: {a};
            border: none;
            border-bottom: 1px solid {bg.border};
            padding: 4px;
        }}
        QPushButton {{
            background-color: transparent;
            color: {a};
            border: none;
            padding: 4px 10px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {a};
            color: {bg.bg};
        }}
        QComboBox {{
            background-color: {bg.bg};
            color: {a};
            border: none;
            padding: 4px;
        }}
        QScrollBar:vertical {{ background: {bg.bg}; width: 4px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {a}; min-height: 20px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QSplitter::handle {{ background: {bg.border}; }}
        QLabel {{ color: {a}; background-color: transparent; }}
        QToolButton {{
            background-color: transparent;
            color: {a};
            border: none;
            padding: 4px;
        }}
        QToolButton:hover {{
            background-color: {a};
            color: {bg.bg};
        }}
    """
