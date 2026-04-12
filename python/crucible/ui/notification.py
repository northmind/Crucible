from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from crucible.ui import styles
from crucible.ui.styles import get_text_colors
from crucible.ui.theme_system import get_selection_colors, get_status_colors
from crucible.ui.tokens import FONT_MD, FONT_MONO, ICON_BTN_SIZE, SPACE_MD, SPACE_LG, SPACE_XL
from crucible.ui.widgets import init_styled, make_flat_button

_NOTICE_SYMBOLS = {
    "warning": "\u26a0",
    "error": "\u2715",
    "info": "\u2022",
}


class SlidingNotification(QWidget):
    _WIDTH = 400
    _MARGIN = SPACE_XL
    _SLIDE_MS = 180
    _LINGER_MS = 5000

    def __init__(self, parent: QWidget | None = None, *, show_close: bool = True) -> None:
        super().__init__(parent)
        init_styled(self, "SlidingNotification")
        self._show_close = show_close
        self._anchor_y = self._MARGIN
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(self._SLIDE_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._linger = QTimer(self)
        self._linger.setSingleShot(True)
        self._linger.setInterval(self._LINGER_MS)
        self._linger.timeout.connect(self.dismiss)
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, SPACE_LG, 14, SPACE_LG)
        root.setSpacing(SPACE_MD)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(SPACE_MD)

        self._symbol = QLabel()
        header.addWidget(self._symbol)

        self._title = QLabel()
        header.addWidget(self._title, 1)

        self._close = make_flat_button("\u00d7", size=(ICON_BTN_SIZE, ICON_BTN_SIZE))
        self._close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._close.clicked.connect(self.dismiss)
        self._close.setVisible(self._show_close)
        header.addWidget(self._close)

        root.addLayout(header)

        self._message = QLabel()
        self._message.setWordWrap(True)
        root.addWidget(self._message)

        self.refresh_colors()

    def refresh_colors(self) -> None:
        """Reapply current theme colors to the notification widget."""
        self._apply_kind("info")

    def show_message(self, title: str, message: str, kind: str = "warning", *, anchor_y: int | None = None, linger_ms: int | None = None) -> None:
        """Slide in a notification with the given title, message, and kind ('warning', 'error', or 'info')."""
        if anchor_y is not None:
            self._anchor_y = anchor_y
        self._linger.stop()
        try:
            self._anim.finished.disconnect(self.hide)
        except (RuntimeError, TypeError):
            pass

        self._apply_kind(kind)
        self._title.setText(title.lower())
        self._message.setText(message)

        parent = self.parentWidget()
        if parent is None:
            return

        available_width = max(240, min(self._WIDTH, parent.width() - self._MARGIN * 2))
        self.setFixedWidth(available_width)
        self.adjustSize()

        end = self._visible_pos()
        start = QPoint(parent.width() + self.width(), end.y())

        self._anim.stop()
        if not self.isVisible():
            self.move(start)
            self.show()
            self.raise_()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(end)
        self._anim.start()

        linger = self._LINGER_MS if linger_ms is None else linger_ms
        if linger > 0:
            self._linger.start(linger)

    def dismiss(self) -> None:
        """Animate the notification off-screen to the right and hide it."""
        self._linger.stop()
        if not self.isVisible():
            return
        try:
            self._anim.finished.disconnect(self.hide)
        except (RuntimeError, TypeError):
            pass
        parent = self.parentWidget()
        if parent is None:
            self.hide()
            return
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(parent.width() + self.width(), self.y()))
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def _visible_pos(self) -> QPoint:
        """Return the on-screen anchor point for the notification."""
        parent = self.parentWidget()
        if parent is None:
            return QPoint(0, self._anchor_y)
        x = parent.width() - self.width() - self._MARGIN
        return QPoint(x, self._anchor_y)

    def reposition(self, *, anchor_y: int | None = None) -> None:
        """Reposition the notification to its anchored location if currently visible."""
        if anchor_y is not None:
            self._anchor_y = anchor_y
        if not self.isVisible():
            return
        self.move(self._visible_pos())

    def _apply_kind(self, kind: str) -> None:
        symbol = _NOTICE_SYMBOLS.get(kind, _NOTICE_SYMBOLS["warning"])
        status = get_status_colors()
        bg = styles.get_bg()
        text = get_text_colors()
        selection = get_selection_colors()
        if kind == "warning":
            accent = status.warning
        elif kind == "error":
            accent = status.error
        else:
            accent = selection.nav_accent
        accent_color = QColor(accent)
        tint = f"rgba({accent_color.red()},{accent_color.green()},{accent_color.blue()},0.12)"

        self.setStyleSheet(
            f"#SlidingNotification {{"
            f" background-color: {bg.bg};"
            f" border: 1px solid {bg.border};"
            f" border-left: 3px solid {accent};"
            f" }}"
        )
        self._symbol.setText(symbol)
        self._symbol.setStyleSheet(
            styles.mono_label(dim=False, size="12pt", extra=f"color: {accent};")
        )
        self._title.setStyleSheet(styles.mono_label(dim=False, bold=True))
        self._message.setStyleSheet(styles.mono_label())
        self._close.setVisible(self._show_close)
        self._close.setStyleSheet(
            f"QPushButton {{ color: {text.text_dim}; background: {tint}; border: none; font-family: {FONT_MONO}; font-size: {FONT_MD}pt; }}"
            f"QPushButton:hover {{ color: {accent}; }}"
        )
