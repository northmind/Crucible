from PyQt6.QtGui import QColor

from crucible.ui.theme_system import (
    get_accent,
    get_bg,
    get_surface_colors,
    get_text,
    get_text_colors,
)


def _colors() -> tuple[str, dict[str, str]]:
    a = get_accent()
    bg = get_bg()
    return a, bg


def shell_fill() -> str:
    """Return the current theme's window background color string."""
    return get_surface_colors()['window_bg']


def panel_fill() -> str:
    """Return the current theme's panel background color string."""
    return get_surface_colors()['panel_bg']


def progress_bar() -> str:
    """Return QSS for a 4px-tall accent-colored progress bar."""
    a, bg = _colors()
    return f"""
        QProgressBar {{
            border: none;
            border-bottom: 1px solid {a};
            text-align: center;
            color: transparent;
            background-color: {bg['bg']};
            max-height: 4px;
            min-height: 4px;
        }}
        QProgressBar::chunk {{ background-color: {a}; }}
    """


def dim_label() -> str:
    """Return inline QSS for dim-colored monospace labels."""
    tc = get_text_colors()
    return f"color: {tc['text_dim']}; background: transparent; font-family: 'Courier New', monospace; font-size: 9pt;"


def tooltip() -> str:
    """Return QSS for themed QToolTip widgets."""
    a, bg = _colors()
    return f"""
        QToolTip {{
            color: {get_text()};
            background-color: {bg['bg']};
            border: 1px solid {bg['border']};
            padding: 3px 6px;
            font-family: "Courier New", monospace;
            font-size: 9pt;
        }}
    """


def window_bg() -> str:
    """Return QSS for a transparent, borderless background."""
    return "background: transparent; border: none;"


def line_accent() -> str:
    """Return the current theme's border color string."""
    return get_bg()['border']


def line_accent_rgba(alpha: int) -> str:
    """Return the theme border color as an rgba() string with the given alpha."""
    c = QColor(line_accent())
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


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
            background-color: {bg['bg']};
            color: {a};
        }}
        QWidget {{
            background-color: {bg['bg']};
            color: {a};
            font-family: "Courier New", monospace;
        }}
        QTreeView, QListView {{
            background-color: {bg['bg']};
            color: {a};
            border: none;
            selection-background-color: {a};
            selection-color: {bg['bg']};
        }}
        QTreeView::item:hover, QListView::item:hover {{
            color: {light};
        }}
        QHeaderView::section {{
            background-color: {bg['bg']};
            color: {a};
            border: none;
            padding: 4px;
        }}
        QLineEdit {{
            background-color: {bg['bg']};
            color: {a};
            border: none;
            border-bottom: 1px solid {bg['border']};
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
            color: {bg['bg']};
        }}
        QComboBox {{
            background-color: {bg['bg']};
            color: {a};
            border: none;
            padding: 4px;
        }}
        QScrollBar:vertical {{ background: {bg['bg']}; width: 4px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {a}; min-height: 20px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QSplitter::handle {{ background: {bg['border']}; }}
        QLabel {{ color: {a}; background-color: transparent; }}
        QToolButton {{
            background-color: transparent;
            color: {a};
            border: none;
            padding: 4px;
        }}
        QToolButton:hover {{
            background-color: {a};
            color: {bg['bg']};
        }}
    """
