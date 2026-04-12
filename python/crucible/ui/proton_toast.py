from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from crucible.ui import styles
from crucible.ui.styles import get_text_colors
from crucible.ui.theme_system import get_selection_colors
from crucible.ui.tokens import ROW_HEIGHT, PROGRESS_HEIGHT, SPACE_SM, SPACE_MD, SPACE_LG
from crucible.ui.widgets import SlidingOverlay, init_styled, make_flat_button

_H = ROW_HEIGHT
_PROGRESS_H = PROGRESS_HEIGHT


class _ProtonToast(SlidingOverlay):
    """Sliding overlay for confirms, status messages, and download progress."""

    def __init__(
        self,
        parent: QWidget,
        on_dismiss: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        init_styled(self, "ProtonToast")
        self.setFixedHeight(_H)
        self._action: Callable[[], None] | None = None
        self._on_dismiss_cb = on_dismiss
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self.dismiss)
        self._init_slide(160)
        self._build_ui()

    # ---- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        hl = QHBoxLayout(self)
        hl.setContentsMargins(SPACE_LG, 0, SPACE_MD, 0)
        hl.setSpacing(SPACE_SM)

        self._label = QLabel()
        hl.addWidget(self._label, 1)

        self._yes_btn = make_flat_button("yes")
        self._yes_btn.clicked.connect(self._on_yes)
        hl.addWidget(self._yes_btn)

        self._sep = QLabel("\u2502")
        self._sep.setFixedWidth(10)
        self._sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self._sep)

        self._no_btn = make_flat_button("no")
        self._no_btn.clicked.connect(self.dismiss)
        hl.addWidget(self._no_btn)

        self._cancel_btn = make_flat_button("cancel")
        self._cancel_btn.hide()
        hl.addWidget(self._cancel_btn)

        # Thin progress bar — absolute overlay at top of toast
        self._progress = QProgressBar(self)
        self._progress.setFixedHeight(_PROGRESS_H)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.move(0, 0)
        self._progress.hide()

        self.refresh_colors()

    def refresh_colors(self) -> None:
        sel = get_selection_colors()
        dim = get_text_colors().text_dim
        self.setStyleSheet(
            f"#ProtonToast {{ background-color: {sel.selection_bg};"
            f" border-top: 1px solid {sel.nav_accent}; }}"
        )
        self._label.setStyleSheet(styles.mono_label(
            dim=False, extra=f"color: {sel.selection_text};",
        ))
        btn_s = styles.flat_button(
            color=sel.selection_text, hover_color=sel.nav_accent,
        )
        self._yes_btn.setStyleSheet(btn_s)
        self._cancel_btn.setStyleSheet(btn_s)
        self._no_btn.setStyleSheet(styles.flat_button(
            color=dim, hover_color=sel.nav_accent,
        ))
        self._sep.setStyleSheet(styles.mono_label())
        self._progress.setStyleSheet(
            f"QProgressBar {{ background: transparent; border: none; }}"
            f" QProgressBar::chunk {{ background: {sel.nav_accent}; }}"
        )

    # ---- SlidingOverlay hooks -------------------------------------------

    def _bar_height(self) -> int:
        return _H

    def _on_slide_width(self, width: int) -> None:
        self._progress.setFixedWidth(width)

    def _on_hidden(self) -> None:
        self.hide()
        self._progress.hide()
        self._progress.setValue(0)

    # ---- Slide mechanics ------------------------------------------------

    def dismiss(self) -> None:
        self._auto_timer.stop()
        self._action = None
        if self._on_dismiss_cb:
            self._on_dismiss_cb()
        self._slide_down()

    # ---- Public API -----------------------------------------------------

    def prompt(self, message: str, action: Callable[[], None]) -> None:
        """Show confirm toast: message? + yes / no."""
        self._auto_timer.stop()
        self._action = action
        self._label.setText(f"{message}?")
        self._yes_btn.setEnabled(True)
        self._no_btn.setEnabled(True)
        self._yes_btn.show()
        self._sep.show()
        self._no_btn.show()
        self._cancel_btn.hide()
        self._progress.hide()
        self._slide_up()

    def show_status(self, message: str, duration_ms: int = 1500) -> None:
        """Show a status message that auto-dismisses."""
        self._auto_timer.stop()
        self._action = None
        self._label.setText(message)
        self._yes_btn.hide()
        self._sep.hide()
        self._no_btn.hide()
        self._cancel_btn.hide()
        self._progress.hide()
        self._slide_up()
        self._auto_timer.start(duration_ms)

    def show_progress(self, message: str, on_cancel: Callable[[], None]) -> None:
        """Show download progress with thin accent bar and cancel button."""
        self._auto_timer.stop()
        self._action = None
        self._label.setText(message)
        self._yes_btn.hide()
        self._sep.hide()
        self._no_btn.hide()
        try:
            self._cancel_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._cancel_btn.clicked.connect(on_cancel)
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.show()
        self._progress.setValue(0)
        self._progress.show()
        self._slide_up()

    def set_progress(self, percent: int) -> None:
        self._progress.setValue(percent)

    def set_message(self, message: str) -> None:
        self._label.setText(message)

    def disable_cancel(self) -> None:
        self._cancel_btn.setEnabled(False)

    def _on_yes(self) -> None:
        self._yes_btn.setEnabled(False)
        self._no_btn.setEnabled(False)
        action, self._action = self._action, None
        if action:
            action()
