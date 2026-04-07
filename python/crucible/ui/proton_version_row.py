from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import QAbstractButton, QWidget

from crucible.ui.styles import get_text_colors, line_accent


class VersionRow(QAbstractButton):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self.setCheckable(True)
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(lambda _: self.update())

    def paintEvent(self, _: QPaintEvent) -> None:
        """Draw the version name with a check indicator and hover highlight."""
        checked = self.isChecked()
        p = QPainter(self)
        a = QColor(line_accent())
        if checked:
            p.fillRect(self.rect(), QColor(a.red(), a.green(), a.blue(), 18))
        elif self.underMouse():
            p.fillRect(self.rect(), QColor(a.red(), a.green(), a.blue(), 8))
        font = QFont("Courier New", 8)
        p.setFont(font)
        fm = p.fontMetrics()
        baseline = (self.height() + fm.ascent() - fm.descent()) // 2
        dim = QColor(get_text_colors()['text_dim'])
        p.setPen(a if checked else dim)
        p.drawText(10, baseline, self._name)
        dot = "\u25cf" if checked else "\u00b7"
        dot_w = fm.horizontalAdvance(dot)
        p.setPen(a if checked else dim)
        p.drawText(self.width() - dot_w - 10, baseline, dot)
        p.end()

    def sizeHint(self) -> QSize:
        """Return the preferred size for this version row."""
        return QSize(200, 28)
