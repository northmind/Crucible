from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from crucible.ui.extraction_bar import _ExtractionBar
from crucible.ui.styles import get_accent, get_bg, get_text_colors
from crucible.ui import styles
from crucible.ui.theme_system import get_selection_colors
from crucible.ui.tokens import ROW_HEIGHT, SPACE_SM, SPACE_MD, SPACE_LG
from crucible.ui.widgets import SlidingOverlay, init_styled, make_flat_button

# Re-export so existing imports from detail_bars continue to work
__all__ = ["_ConfirmBar", "_ZipImportBar", "_ExtractionBar"]


class _ConfirmBar(SlidingOverlay):
    _H = ROW_HEIGHT

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        init_styled(self, "ConfirmBar")
        self.setFixedHeight(self._H)
        self._action: Callable[[], None] | None = None
        self._message = ""
        self._init_slide(160)
        self._build_ui()

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
        self._no_btn.clicked.connect(self._dismiss)
        hl.addWidget(self._no_btn)

        self.refresh_colors()

    def refresh_colors(self) -> None:
        dim = get_text_colors().text_dim
        sel = get_selection_colors()
        self.setStyleSheet(
            f"#ConfirmBar {{ background-color: {sel.selection_bg};"
            f" border-top: 1px solid {sel.nav_accent}; }}"
        )
        self._label.setStyleSheet(styles.mono_label(
            dim=False, extra=f"color: {sel.selection_text};",
        ))
        self._yes_btn.setStyleSheet(styles.flat_button(
            color=sel.selection_text, hover_color=sel.nav_accent,
        ))
        self._sep.setStyleSheet(styles.mono_label())
        self._no_btn.setStyleSheet(styles.flat_button(
            color=dim, hover_color=sel.nav_accent,
        ))

    def _bar_height(self) -> int:
        return self._H

    def prompt(self, message: str, action: Callable[[], None]) -> None:
        self._message = message
        self._action  = action
        self._label.setText(f"{message}?")
        self._slide_up()

    def _dismiss(self) -> None:
        self._action = None
        self._slide_down()

    def _on_yes(self) -> None:
        action, self._action = self._action, None
        self._dismiss()
        if action:
            action()


class _ZipImportBar(SlidingOverlay):
    _H = 34

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        init_styled(self, "ZipImportBar")
        self.setFixedHeight(self._H)
        self._init_slide(160)
        self._build_ui()

    def _build_ui(self) -> None:
        hl = QHBoxLayout(self)
        hl.setContentsMargins(SPACE_LG, 0, SPACE_LG, 0)
        hl.setSpacing(SPACE_MD)

        self._label = QLabel("import archive")
        hl.addWidget(self._label)

        self._file = QLabel()
        self._file.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hl.addWidget(self._file, 1)

        self._apply_styles()

    def _apply_styles(self) -> None:
        accent = get_accent()
        bg = get_bg()
        self.setStyleSheet(
            f"#ZipImportBar {{ background-color: {bg.bg}; border-top: 1px solid {accent}; }}"
        )
        self._label.setStyleSheet(styles.mono_label(dim=False))
        self._file.setStyleSheet(styles.mono_label(size="8pt"))

    def _bar_height(self) -> int:
        return self._H

    def show_file(self, zip_path: str) -> None:
        file_name = zip_path.rsplit('/', 1)[-1] if zip_path else ''
        self._file.setText(file_name.lower())
        self._slide_up()

    def dismiss(self) -> None:
        self._slide_down()
