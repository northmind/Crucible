from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import QAbstractButton, QWidget

from crucible.ui.styles import get_text_colors
from crucible.ui.theme_system import get_selection_colors


class VersionRow(QAbstractButton):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._highlighted = False
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def highlighted(self) -> bool:
        return self._highlighted

    @highlighted.setter
    def highlighted(self, value: bool) -> None:
        if self._highlighted != value:
            self._highlighted = value
            self.update()

    def paintEvent(self, _: QPaintEvent) -> None:
        """Draw the version name with hover/highlight state."""
        p = QPainter(self)
        sel = get_selection_colors()
        accent = QColor(sel.nav_accent)
        hover_bg = QColor(sel.hover_bg)
        selection_bg = QColor(sel.selection_bg)

        if self._highlighted:
            p.fillRect(self.rect(), selection_bg)
            p.fillRect(0, 0, 2, self.height(), accent)
        elif self.underMouse():
            p.fillRect(self.rect(), hover_bg)

        font = QFont("Courier New", 8)
        p.setFont(font)
        fm = p.fontMetrics()
        baseline = (self.height() + fm.ascent() - fm.descent()) // 2

        tc = get_text_colors()
        main_color = QColor(sel.selection_text) if self._highlighted else QColor(tc.text_dim)
        meta_color = accent if self._highlighted else QColor(tc.text_dim)
        left = 18 if self._highlighted else 16
        p.setPen(main_color)
        p.drawText(left, baseline, self._name)

        dot = "\u25cf" if self._highlighted else "\u00b7"
        dot_w = fm.horizontalAdvance(dot)
        p.setPen(meta_color)
        p.drawText(self.width() - dot_w - 10, baseline, dot)
        p.end()

    def sizeHint(self) -> QSize:
        """Return the preferred size for this version row."""
        return QSize(200, 28)
