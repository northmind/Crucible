from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from crucible.ui.extraction_bar import _ExtractionBar
from crucible.ui.styles import get_accent, get_bg, get_text_colors
from crucible.ui.theme_system import get_selection_colors

# Re-export so existing imports from detail_bars continue to work
__all__ = ["_ConfirmBar", "_ZipImportBar", "_ExtractionBar"]


class _ConfirmBar(QWidget):
    _H = 38

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("ConfirmBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(self._H)
        self._action: Callable[[], None] | None = None
        self._message = ""
        self._anim    = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        hl = QHBoxLayout(self)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.setSpacing(6)

        self._label = QLabel()
        hl.addWidget(self._label, 1)

        self._yes_btn = QPushButton("yes")
        self._yes_btn.setFlat(True)
        self._yes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._yes_btn.clicked.connect(self._on_yes)
        hl.addWidget(self._yes_btn)

        self._sep = QLabel("\u2502")
        self._sep.setFixedWidth(10)
        self._sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self._sep)

        self._no_btn = QPushButton("no")
        self._no_btn.setFlat(True)
        self._no_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._no_btn.clicked.connect(self._dismiss)
        hl.addWidget(self._no_btn)

        self.refresh_colors()

    def refresh_colors(self) -> None:
        dim = get_text_colors()['text_dim']
        sel = get_selection_colors()
        self.setStyleSheet(
            f"#ConfirmBar {{ background-color: {sel['selection_bg']};"
            f" border-top: 1px solid {sel['nav_accent']}; }}"
        )
        self._label.setStyleSheet(
            f"color: {sel['selection_text']}; font-family: 'Courier New', monospace;"
            f" font-size: 9pt; background: transparent;"
        )
        self._yes_btn.setStyleSheet(
            f"QPushButton {{ color: {sel['selection_text']}; background: transparent; border: none;"
            f" font-family: 'Courier New', monospace; font-size: 9pt; padding: 0 6px; }}"
            f"QPushButton:hover {{ color: {sel['nav_accent']}; }}"
        )
        self._sep.setStyleSheet(
            f"color: {dim}; font-family: 'Courier New', monospace;"
            f" font-size: 9pt; background: transparent;"
        )
        self._no_btn.setStyleSheet(
            f"QPushButton {{ color: {dim}; background: transparent; border: none;"
            f" font-family: 'Courier New', monospace; font-size: 9pt; padding: 0 6px; }}"
            f"QPushButton:hover {{ color: {sel['nav_accent']}; }}"
        )

    def prompt(self, message: str, action: Callable[[], None]) -> None:
        self._message = message
        self._action  = action
        self._label.setText(f"{message}?")
        p_w, p_h = self.parent().width(), self.parent().height()
        self.setFixedWidth(p_w - 1)
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        if not self.isVisible():
            self.move(1, p_h)
            self.show()
            self.raise_()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(1, p_h - self._H))
        self._anim.start()

    def _dismiss(self) -> None:
        p_h = self.parent().height()
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(1, p_h))
        self._anim.finished.connect(self.hide)
        self._anim.start()
        self._action = None

    def _on_yes(self) -> None:
        action, self._action = self._action, None
        self._dismiss()
        if action:
            action()

    def reposition(self, parent_w: int, parent_h: int) -> None:
        self.setFixedWidth(parent_w - 1)
        if self.isVisible():
            self.move(1, parent_h - self._H)


class _ZipImportBar(QWidget):
    _H = 34
    _SLIDE_MS = 160

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("ZipImportBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(self._H)
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(self._SLIDE_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        hl = QHBoxLayout(self)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(8)

        self._label = QLabel("import archive")
        hl.addWidget(self._label)

        self._file = QLabel()
        self._file.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hl.addWidget(self._file, 1)

        self._apply_styles()

    def _apply_styles(self) -> None:
        accent = get_accent()
        bg = get_bg()
        text = get_text_colors()['text']
        dim = get_text_colors()['text_dim']
        self.setStyleSheet(
            f"#ZipImportBar {{ background-color: {bg['bg']}; border-top: 1px solid {accent}; }}"
        )
        self._label.setStyleSheet(
            f"color: {text}; font-family: 'Courier New', monospace; font-size: 9pt; background: transparent;"
        )
        self._file.setStyleSheet(
            f"color: {dim}; font-family: 'Courier New', monospace; font-size: 8pt; background: transparent;"
        )

    def show_file(self, zip_path: str) -> None:
        file_name = zip_path.rsplit('/', 1)[-1] if zip_path else ''
        self._file.setText(file_name.lower())
        p_w, p_h = self.parent().width(), self.parent().height()
        self.setFixedWidth(p_w - 1)
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        if not self.isVisible():
            self.move(1, p_h)
            self.show()
            self.raise_()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(1, p_h - self._H))
        self._anim.start()

    def dismiss(self) -> None:
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        p_h = self.parent().height()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(1, p_h))
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def reposition(self, parent_w: int, parent_h: int) -> None:
        self.setFixedWidth(parent_w - 1)
        if self.isVisible():
            self.move(1, parent_h - self._H)
