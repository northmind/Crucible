from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from crucible.ui.styles import get_accent, get_bg, get_text_colors


class _ExtractionBar(QWidget):
    _SLIDE_MS = 200
    _LINGER_MS = 4000

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("ExtractionBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(self._SLIDE_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._linger = QTimer(self)
        self._linger.setSingleShot(True)
        self._linger.setInterval(self._LINGER_MS)
        self._linger.timeout.connect(self._dismiss)
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        vl = QVBoxLayout(self)
        vl.setContentsMargins(12, 10, 10, 10)
        vl.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.setContentsMargins(0, 0, 0, 0)

        self._check = QLabel("\u2713")
        top.addWidget(self._check)

        self._msg = QLabel()
        top.addWidget(self._msg, 1)

        self._close = QPushButton("\u00d7")
        self._close.setFlat(True)
        self._close.setFixedSize(18, 18)
        self._close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._close.clicked.connect(self._dismiss)
        top.addWidget(self._close)

        vl.addLayout(top)

        self._dll_lbl = QLabel()
        self._dll_lbl.hide()
        vl.addWidget(self._dll_lbl)

        self._exe_lbl = QLabel()
        self._exe_lbl.setWordWrap(True)
        self._exe_lbl.hide()
        vl.addWidget(self._exe_lbl)

        self._apply_styles()

    def _apply_styles(self) -> None:
        a = get_accent()
        bg = get_bg()
        dim = get_text_colors()['text_dim']
        text_color = get_text_colors()['text']
        self.setStyleSheet(
            f"#ExtractionBar {{ background-color: {bg['bg']}; border-top: 2px solid {a}; }}"
        )
        self._check.setStyleSheet(
            f"color: {a}; font-family: 'Courier New', monospace; font-size: 11pt; font-weight: bold; background: transparent;"
        )
        self._msg.setStyleSheet(
            f"color: {text_color}; font-family: 'Courier New', monospace; font-size: 9pt; background: transparent;"
        )
        self._close.setStyleSheet(
            f"QPushButton {{ color: {dim}; background: transparent; border: none; font-family: 'Courier New', monospace; font-size: 11pt; padding: 0; }}"
            f"QPushButton:hover {{ color: {a}; }}"
        )
        sub = (
            f"color: {dim}; font-family: 'Courier New', monospace;"
            f" font-size: 8pt; background: transparent;"
        )
        self._dll_lbl.setStyleSheet(sub)
        self._exe_lbl.setStyleSheet(sub)

    def show_result(self, detected_dlls: list[str] | None = None, detected_exe: str | None = None) -> None:
        self._linger.stop()
        try:
            self._anim.finished.disconnect()
        except (RuntimeError, TypeError):
            pass

        if detected_dlls and detected_exe:
            msg = "extracted \u2014 overrides set, exe found"
        elif detected_dlls:
            msg = "extracted \u2014 overrides set"
        elif detected_exe:
            msg = "extracted \u2014 exe found"
        else:
            msg = "archive extracted"
        self._msg.setText(msg)

        if detected_dlls:
            shown = detected_dlls[:5]
            rest = len(detected_dlls) - len(shown)
            lines = [f"  \u00b7 {d}" for d in shown]
            if rest:
                lines.append(f"  +{rest} more")
            self._dll_lbl.setText("\n".join(lines))
            self._dll_lbl.show()
        else:
            self._dll_lbl.hide()

        if detected_exe:
            self._exe_lbl.setText(f"  exe  \u00b7  {detected_exe}")
            self._exe_lbl.show()
        else:
            self._exe_lbl.hide()

        p_w, p_h = self.parent().width(), self.parent().height()
        self.setFixedWidth(p_w - 1)
        self.adjustSize()
        h = self.height()
        end_y = p_h - h
        start_y = p_h

        if not self.isVisible():
            self.move(1, start_y)
            self.show()
            self.raise_()

        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(1, end_y))
        self._anim.start()
        self._linger.start()

    def _dismiss(self) -> None:
        self._linger.stop()
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
            self.move(1, parent_h - self.height())
