from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, QEvent
from PyQt6.QtGui import QColor, QEnterEvent, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import QAbstractButton, QWidget

from crucible.ui.styles import get_text_colors
from crucible.ui.theme_system import get_selection_colors


class _StateRow(QAbstractButton):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self.setText(label)
        self.setCheckable(True)
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(lambda _: self.update())

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        p = QPainter(self)
        checked = self.isChecked()
        sel = get_selection_colors()
        accent = QColor(sel['nav_accent'])
        selection_bg = QColor(sel['selection_bg'])
        hover_bg = QColor(sel['hover_bg'])

        if checked:
            p.fillRect(self.rect(), selection_bg)
            p.fillRect(0, 0, 2, self.height(), accent)
        elif self.underMouse():
            p.fillRect(self.rect(), hover_bg)

        font = QFont("Courier New", 8)
        p.setFont(font)
        fm = p.fontMetrics()
        baseline = (self.height() + fm.ascent() - fm.descent()) // 2

        tc = get_text_colors()
        main_color = QColor(sel['selection_text']) if checked else QColor(tc['text_dim'])
        meta_color = accent if checked else QColor(tc['text_dim'])
        left = 18 if checked else 16
        p.setPen(main_color)
        p.drawText(left, baseline, self._label)

        dot = "\u25cf" if checked else "\u00b7"
        dot_w = fm.horizontalAdvance(dot)
        dot_x = self.width() - dot_w - 10

        p.setPen(meta_color)
        p.drawText(dot_x, baseline, dot)
        p.end()

    def sizeHint(self) -> QSize:
        return QSize(200, 28)


class _ProtonRow(_StateRow):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(name, parent=parent)


class _ToolRow(_StateRow):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent=parent)


class _ActionRow(QAbstractButton):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._hovered = False
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        p = QPainter(self)
        sel = get_selection_colors()
        tc = get_text_colors()
        accent = QColor(sel['nav_accent'])
        dim = QColor(tc['text_dim'])
        if self._hovered:
            p.fillRect(self.rect(), QColor(sel['hover_bg']))
        font = QFont("Courier New", 8)
        p.setFont(font)
        fm = p.fontMetrics()
        baseline = (self.height() + fm.ascent() - fm.descent()) // 2
        p.setPen(QColor(sel['selection_text']) if self._hovered else dim)
        p.drawText(16, baseline, self._label)
        p.setPen(accent if self._hovered else dim)
        p.drawText(self.width() - fm.horizontalAdvance("\u203a") - 10, baseline, "\u203a")
        p.end()

    def enterEvent(self, e: QEnterEvent | None) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e: QEvent | None) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def sizeHint(self) -> QSize:
        return QSize(200, 28)


class _DangerRow(QAbstractButton):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name    = name
        self._hovered = False
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _: QPaintEvent | None) -> None:
        p = QPainter(self)
        sel = get_selection_colors()
        dim = QColor(get_text_colors()['text_dim'])
        if self._hovered:
            p.fillRect(self.rect(), QColor(sel['hover_bg']))
        font = QFont("Courier New", 8)
        p.setFont(font)
        fm = p.fontMetrics()
        baseline = (self.height() + fm.ascent() - fm.descent()) // 2
        p.setPen(QColor(sel['selection_text']) if self._hovered else dim)
        p.drawText(10, baseline, self._name)
        if self._hovered:
            p.drawText(self.width() - 76, baseline, 'destructive')
        p.end()

    def enterEvent(self, e: QEnterEvent | None) -> None:
        self._hovered = True;  self.update(); super().enterEvent(e)

    def leaveEvent(self, e: QEvent | None) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)

    def sizeHint(self) -> QSize:
        return QSize(200, 28)


class _AdvRow(_StateRow):
    """Semantic alias for _StateRow used in the advanced-settings section."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent=parent)


# Re-export overlay bars from their new home for backward compatibility.
from crucible.ui.detail_bars import _ConfirmBar, _ExtractionBar, _ZipImportBar

__all__ = [
    '_StateRow', '_ProtonRow', '_ToolRow', '_ActionRow', '_DangerRow', '_AdvRow',
    '_ConfirmBar', '_ExtractionBar', '_ZipImportBar',
]
