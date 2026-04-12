from typing import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from crucible.ui.theme_system import get_selection_colors, get_status_colors, get_surface_colors
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QPushButton, QWidget

from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen

from crucible.ui.styles import get_text_colors, line_accent
from crucible.ui.tokens import FONT_BASE, FONT_MONO, TITLEBAR_HEIGHT


class _DraggableSearch(QLineEdit):
    """QLineEdit that forwards mouse drags to the compositor when unfocused."""

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton and not self.hasFocus():
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton and not self.hasFocus():
            win = self.window()
            if win.isMaximized():
                win.showNormal()
            else:
                win.showMaximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class TitleBar(QFrame):
    search_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.main_window = parent
        self._right_gap = 0
        self.setObjectName("TitleBarFrame")
        self.setFixedHeight(TITLEBAR_HEIGHT)
        self._apply_style()

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(14, 0, 12, 0)
        self._layout.setSpacing(0)

        self.search_input = _DraggableSearch()
        self.search_input.setPlaceholderText("> filter game")
        self.search_input.setMaximumWidth(240)
        self._apply_search_style()
        self.search_input.textChanged.connect(self.search_changed)
        self._layout.addWidget(self.search_input)
        self._layout.addStretch(1)

        self._min_btn   = self._make_btn("−", self._minimize_window)
        self._min_btn.setAccessibleName("Minimize")
        self._max_btn   = self._make_btn("□", self._maximize_window)
        self._max_btn.setAccessibleName("Maximize")
        self._close_btn = self._make_btn("×", self._close_window, kind="danger")
        self._close_btn.setAccessibleName("Close")

        for b in [self._min_btn, self._max_btn, self._close_btn]:
            self._layout.addWidget(b)

    def _make_btn(self, text: str, callback: Callable[..., None], kind: str = "dim") -> QPushButton:
        b = QPushButton(text)
        b.setFixedSize(24, 20)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFlat(True)
        b.clicked.connect(callback)
        self._style_btn(b, kind)
        return b

    def _style_btn(self, b: QPushButton, kind: str) -> None:
        colors = get_text_colors()
        dim = colors.text_dim
        hover_bg = get_selection_colors().hover_bg
        hc = get_status_colors().danger_hover if kind == "danger" else get_selection_colors().nav_accent
        b.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {dim}; border: none; border-radius: 0px;"
            f" font-family: {FONT_MONO}; font-size: {FONT_BASE}pt; }}"
            f"QPushButton:hover {{ color: {hc}; background: {hover_bg}; }}"
        )

    def _apply_style(self) -> None:
        surfaces = get_surface_colors()
        edge = line_accent()
        self.setStyleSheet(
            f"QFrame#TitleBarFrame {{"
            f" background-color: {surfaces.titlebar_bg};"
            f" border-top: 1px solid {edge};"
            f" border-left: 1px solid {edge};"
            f" border-right: 1px solid {edge};"
            f" border-top-left-radius: 0px; border-top-right-radius: 0px;"
            f"}}"
        )

    def paintEvent(self, event: QPaintEvent | None) -> None:
        """Draw the bottom separator line across the full width."""
        super().paintEvent(event)
        edge = line_accent()
        painter = QPainter(self)
        try:
            painter.setPen(QPen(QColor(edge), 1))
            painter.drawLine(1, self.height() - 1, self.width() - 2, self.height() - 1)
        finally:
            painter.end()

    def set_right_gap(self, gap: int) -> None:
        """Set the right-edge gap in pixels used when painting the bottom separator line."""
        gap = max(0, gap)
        if self._right_gap == gap:
            return
        self._right_gap = gap
        self.update()

    def _apply_search_style(self) -> None:
        sel = get_selection_colors()
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {get_text_colors().text};
                border: none;
                font-family: {FONT_MONO};
                font-size: {FONT_BASE}pt;
                padding: 2px 0px;
                selection-background-color: {sel.text_selection_bg};
                selection-color: {sel.selection_text};
            }}
            QLineEdit:focus {{
                border: none;
            }}
        """)

    def refresh_colors(self) -> None:
        """Reapply theme styles to the titlebar background, search input, and window buttons."""
        self._apply_style()
        self._apply_search_style()
        for b, kind in [(self._min_btn, "dim"), (self._max_btn, "dim"), (self._close_btn, "danger")]:
            self._style_btn(b, kind)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Initiate a compositor-driven window drag on left-click."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        """Toggle maximized state on double-click."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            if self.main_window.isMaximized():
                self.main_window.showNormal()
            else:
                self.main_window.showMaximized()
            event.accept()

    def _minimize_window(self) -> None:
        self.main_window.showMinimized()

    def _maximize_window(self) -> None:
        if self.main_window.isMaximized():
            self.main_window.showNormal()
        else:
            self.main_window.showMaximized()

    def _close_window(self) -> None:
        self.main_window.close()
