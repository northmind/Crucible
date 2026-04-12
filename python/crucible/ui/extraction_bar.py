from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from crucible.ui.styles import get_accent, get_bg
from crucible.ui import styles
from crucible.ui.tokens import ICON_BTN_SIZE, SPACE_XS, SPACE_MD, SPACE_LG
from crucible.ui.widgets import SlidingOverlay, init_styled, make_flat_button


class _ExtractionBar(SlidingOverlay):
    _LINGER_MS = 4000

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        init_styled(self, "ExtractionBar")
        self._init_slide(200)
        self._linger = QTimer(self)
        self._linger.setSingleShot(True)
        self._linger.setInterval(self._LINGER_MS)
        self._linger.timeout.connect(self._dismiss)
        self._build_ui()

    def _build_ui(self) -> None:
        vl = QVBoxLayout(self)
        vl.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_MD, SPACE_MD)
        vl.setSpacing(SPACE_XS)

        top = QHBoxLayout()
        top.setSpacing(SPACE_MD)
        top.setContentsMargins(0, 0, 0, 0)

        self._check = QLabel("\u2713")
        top.addWidget(self._check)

        self._msg = QLabel()
        top.addWidget(self._msg, 1)

        self._close = make_flat_button("\u00d7", size=(ICON_BTN_SIZE, ICON_BTN_SIZE))
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
        self.setStyleSheet(
            f"#ExtractionBar {{ background-color: {bg.bg}; border-top: 2px solid {a}; }}"
        )
        self._check.setStyleSheet(
            styles.mono_label(dim=False, size="11pt", bold=True, extra=f"color: {a};")
        )
        self._msg.setStyleSheet(styles.mono_label(dim=False))
        self._close.setStyleSheet(styles.flat_button(size="11pt", padding="0"))
        sub = styles.mono_label(size="8pt")
        self._dll_lbl.setStyleSheet(sub)
        self._exe_lbl.setStyleSheet(sub)

    def show_result(self, detected_dlls: list[str] | None = None, detected_exe: str | None = None) -> None:
        self._linger.stop()
        self._prep_anim()

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

        self.adjustSize()
        self._slide_up()
        self._linger.start()

    def _dismiss(self) -> None:
        self._linger.stop()
        self._slide_down()
