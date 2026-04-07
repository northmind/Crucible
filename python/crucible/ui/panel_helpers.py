from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import QAbstractButton, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from crucible.ui.styles import get_text_colors, line_accent_rgba
from crucible.ui.theme_system import get_selection_colors


class TabBar(QWidget):
    switched = pyqtSignal(int)

    def __init__(self, labels: list[str], parent: QWidget | None = None, variant: str = "panel") -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self._variant = variant
        self._active = 0
        self._btns: list[QPushButton] = []

        hl = QHBoxLayout(self)
        hl.setContentsMargins(14, 0, 14, 0)
        hl.setSpacing(0)

        for i, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setFlat(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self.set_current_index(idx))
            self._btns.append(btn)
            hl.addWidget(btn, 0)

        hl.addStretch(1)
        self._refresh_styles()

    @property
    def active_index(self) -> int:
        """Return the zero-based index of the currently active tab."""
        return self._active

    def set_current_index(self, idx: int) -> None:
        """Switch to the tab at *idx*, emitting ``switched``; out-of-range values are ignored."""
        if idx < 0 or idx >= len(self._btns):
            return
        self._active = idx
        self._refresh_styles()
        self.switched.emit(idx)

    def reset(self) -> None:
        """Reset the tab bar to the first tab."""
        self.set_current_index(0)

    def refresh_colors(self) -> None:
        """Reapply theme-derived colors to all tab buttons."""
        self._refresh_styles()

    def _refresh_styles(self) -> None:
        selection = get_selection_colors()
        accent = selection['nav_accent']
        active_text = selection['selection_text']
        colors = get_text_colors()
        dim = colors['text_dim']
        active_bg = selection['selection_bg']
        hover_bg = selection['hover_bg']

        for i, btn in enumerate(self._btns):
            is_active = i == self._active
            if self._variant == "detail":
                btn.setStyleSheet(
                    f"QPushButton {{ background: {active_bg if is_active else 'transparent'}; color: {active_text if is_active else dim};"
                    f" border: none; border-bottom: 1px solid {accent if is_active else 'transparent'};"
                    f" border-radius: 0px; padding: 0 12px; min-width: 0;"
                    f" font-family: 'Courier New', monospace; font-size: 9pt; }}"
                    f"QPushButton:hover {{ color: {accent}; background: {active_bg if is_active else hover_bg}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {active_bg if is_active else 'transparent'}; color: {active_text if is_active else dim}; border: none;"
                    f" border-radius: 0px; padding: 0 11px; min-width: 0;"
                    f" font-family: 'Courier New', monospace; font-size: 8.5pt; text-align: left; }}"
                    f"QPushButton:hover {{ color: {accent}; background: {active_bg if is_active else hover_bg}; }}"
                )


class _SectionHeaderButton(QAbstractButton):
    def __init__(self, title: str, *, expanded: bool = False, color: str | None = None, hover_color: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._expanded = expanded
        self._color = color
        self._hover_color = hover_color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(28)

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self.update()

    def is_expanded(self) -> bool:
        return self._expanded

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        try:
            selection = get_selection_colors()
            colors = get_text_colors()
            accent = QColor(selection['nav_accent'])
            default_color = QColor(self._color or colors['text_dim'])
            title_color = QColor(selection['selection_text']) if self._expanded else default_color
            if self.underMouse():
                title_color = QColor(self._hover_color or selection['nav_accent'])
            font = QFont('Courier New', 8)
            font.setStyleHint(QFont.StyleHint.TypeWriter)
            painter.setFont(font)
            fm = painter.fontMetrics()
            baseline = (self.height() + fm.ascent() - fm.descent()) // 2

            left = 14
            arrow = '▾' if self._expanded else '▸'
            title_x = left + 12

            painter.setPen(accent)
            painter.drawText(left, baseline, arrow)
            painter.setPen(title_color)
            painter.drawText(title_x, baseline, self._title)
        finally:
            painter.end()


def build_collapsible_section(
    title: str,
    content: QWidget,
    *,
    expanded: bool = False,
    color: str | None = None,
    hover_color: str | None = None,
) -> tuple[QWidget, _SectionHeaderButton]:
    """Build a collapsible section with a clickable header that toggles *content* visibility."""
    content.setStyleSheet('background: transparent; border: none;')

    outer = QWidget()
    outer.setStyleSheet('background: transparent;')
    layout = QVBoxLayout(outer)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    header = _SectionHeaderButton(
        title,
        expanded=expanded,
        color=color,
        hover_color=hover_color,
    )
    content.setVisible(expanded)

    def toggle() -> None:
        is_expanded = not header.is_expanded()
        header.set_expanded(is_expanded)
        content.setVisible(is_expanded)

    separator = QWidget()
    separator.setFixedHeight(1)
    separator.setStyleSheet(f'background: {line_accent_rgba(72)}; border: none;')

    header.clicked.connect(toggle)
    layout.addWidget(header)
    layout.addWidget(content)
    layout.addWidget(separator)
    return outer, header
