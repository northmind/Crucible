from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QEvent, QSize
from PyQt6.QtGui import QColor, QEnterEvent, QFont, QPainter, QPaintEvent, QResizeEvent
from PyQt6.QtWidgets import QAbstractButton, QPushButton, QWidget

from crucible.ui.theme_system import Theme


class _ThemeBtn(QAbstractButton):
    def __init__(
        self,
        theme: Theme,
        subtitle: str,
        selected: bool,
        removable: bool = False,
        remove_callback: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._subtitle = subtitle
        self._remove_callback = remove_callback
        self.setCheckable(True)
        self.setChecked(selected)
        self.setFixedHeight(112)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False
        self.toggled.connect(lambda _: self.update())
        self._remove_btn: QPushButton | None = None
        if removable:
            self._remove_btn = QPushButton("\u00d7", self)
            self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._remove_btn.setFixedSize(18, 18)
            self._remove_btn.clicked.connect(self._on_remove_clicked)
            self._apply_remove_style()

    def _on_remove_clicked(self) -> None:
        if self._remove_callback is not None:
            self._remove_callback()

    def _apply_remove_style(self) -> None:
        if self._remove_btn is None:
            return
        dim = self._theme.text_dim
        accent = self._theme.accent
        self._remove_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {dim}; border: none; font-family: 'Courier New', monospace; font-size: 9pt; }}"
            f"QPushButton:hover {{ color: {accent}; }}"
        )

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        if self._remove_btn is not None:
            self._remove_btn.move(self.width() - 24, 8)
            self._remove_btn.raise_()

    def set_selected(self, value: bool) -> None:
        self.setChecked(value)
        self.update()

    def set_theme(self, theme: Theme, subtitle: str | None = None) -> None:
        self._theme = theme
        if subtitle is not None:
            self._subtitle = subtitle
        self._apply_remove_style()
        self.update()

    def enterEvent(self, event: QEnterEvent | None) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent | None) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _: QPaintEvent | None) -> None:
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(0, 0, -1, -1)
        border = QColor(theme.border)
        bg_fill = QColor(theme.bg)
        text_color = QColor(theme.text)
        dim_color = QColor(theme.text_dim)
        accent = QColor(theme.accent)

        painter.setPen(accent if self.isChecked() else (QColor(border).lighter(118) if self._hovered else border))
        painter.setBrush(bg_fill)
        painter.drawRoundedRect(rect, 6, 6)

        preview = rect.adjusted(10, 10, -10, -40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.bg))
        painter.drawRoundedRect(preview, 5, 5)

        shell = preview.adjusted(8, 8, -8, -8)
        painter.setBrush(QColor(theme.chrome_bg or theme.bg))
        painter.drawRoundedRect(shell, 4, 4)

        row_left = shell.left() + 8
        row_top = shell.center().y() - 6
        row_w = shell.width() - 16
        row_h = 12
        painter.setBrush(QColor(theme.accent_soft))
        painter.drawRoundedRect(row_left, row_top, row_w, row_h, 3, 3)

        painter.setBrush(QColor(theme.accent))
        painter.drawRoundedRect(row_left, row_top + 2, 2, row_h - 4, 1, 1)
        painter.drawRoundedRect(row_left + 8, row_top + 4, 42, 3, 1, 1)
        painter.setBrush(QColor(theme.text_dim))
        painter.drawRoundedRect(row_left + row_w - 18, row_top + 4, 12, 3, 1, 1)

        meta_left = rect.left() + 12
        meta_width = rect.width() - 24
        title_top = preview.bottom() + 8
        subtitle_top = title_top + 15

        painter.setPen(text_color)
        painter.setFont(QFont("Courier New", 8))
        painter.drawText(meta_left, title_top, meta_width, 12, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, theme.name)

        painter.setPen(dim_color)
        painter.setFont(QFont("Courier New", 7))
        painter.drawText(meta_left, subtitle_top, meta_width, 10, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._subtitle)
        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(100, 112)
