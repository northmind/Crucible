from __future__ import annotations

import subprocess
from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from crucible.ui.styles import get_text_colors, line_accent
from crucible.ui.theme_system import get_selection_colors, get_surface_colors


class NavSidebar(QWidget):
    """Vertical icon sidebar for primary navigation actions."""

    def __init__(self, main_window: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._active_key = None
        self.setFixedWidth(44)
        self.setObjectName("NavSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_style()

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 6, 0, 8)
        vl.setSpacing(4)
        vl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self._add_btn = self._make_btn("add", "+", self._open_add_game)
        self._proton_btn = self._make_btn("proton", "⬡", self._open_proton)
        self._kofi_btn = self._make_btn("kofi", "♥", self._open_kofi, size=11)
        self._settings_btn = self._make_btn("settings", "≡", self._open_settings)
        for button in (self._add_btn, self._proton_btn):
            vl.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        vl.addStretch()
        vl.addWidget(self._kofi_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        vl.addWidget(self._settings_btn, 0, Qt.AlignmentFlag.AlignHCenter)

    def _make_btn(self, key: str, text: str, callback: Callable[[], None], size: int = 13) -> QPushButton:
        """Create a sidebar navigation button with active-state styling."""
        a = get_selection_colors()['nav_accent']
        dim = get_text_colors()['text_dim']
        hover_bg = get_selection_colors()['hover_bg']
        b = QPushButton(text)
        b.setProperty('nav_key', key)
        b.setFixedSize(32, 32)
        b.setFlat(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setProperty("font_size", size)
        active = key == self._active_key
        b.setStyleSheet(
            f"QPushButton {{ background: {hover_bg if active else 'transparent'}; color: {a if active else dim}; border: none; border-radius: 0px;"
            f" border-left: 2px solid {a if active else 'transparent'}; padding-left: 2px;"
            f" font-family: 'Courier New', monospace; font-size: {size}pt; }}"
            f"QPushButton:hover {{ color: {a}; background: transparent; border-left: 2px solid {a if active else 'transparent'}; }}"
        )
        b.clicked.connect(callback)
        return b

    def _apply_style(self) -> None:
        """Apply background and border styling from the current theme."""
        surfaces = get_surface_colors()
        edge = line_accent()
        self.setStyleSheet(
            f"background-color: {surfaces['nav_bg']};"
            f"border-left: 1px solid {edge};"
            f"border-right: 1px solid {edge};"
            f"border-bottom: 1px solid {edge};"
        )

    def refresh_colors(self) -> None:
        """Re-apply all button and background colors after a theme change."""
        self._apply_style()
        a = get_selection_colors()['nav_accent']
        dim = get_text_colors()['text_dim']
        hover_bg = get_selection_colors()['hover_bg']
        for b in (self._add_btn, self._proton_btn, self._kofi_btn, self._settings_btn):
            sz = b.property("font_size") or 13
            key = b.property('nav_key')
            active = key == self._active_key
            b.setStyleSheet(
                f"QPushButton {{ background: {hover_bg if active else 'transparent'}; color: {a if active else dim}; border: none;"
                f" border-left: 2px solid {a if active else 'transparent'}; padding-left: 2px; border-radius: 0px;"
                f" font-family: 'Courier New', monospace; font-size: {sz}pt; }}"
                f"QPushButton:hover {{ color: {a}; background: transparent; border-left: 2px solid {a if active else 'transparent'}; }}"
            )

    def set_active(self, key: str | None) -> None:
        """Highlight the given nav key (or clear if None)."""
        self._active_key = key
        self.refresh_colors()

    def _open_add_game(self) -> None:
        if hasattr(self._main_window, 'open_add_game'):
            self._main_window.open_add_game()

    def _open_proton(self) -> None:
        if hasattr(self._main_window, 'toggle_proton'):
            self._main_window.toggle_proton()

    def _open_kofi(self) -> None:
        from crucible.core.paths import clean_env
        from crucible.ui.settings_panel import KOFI_URL
        subprocess.Popen(['xdg-open', KOFI_URL], env=clean_env(), start_new_session=True)

    def _open_settings(self) -> None:
        if hasattr(self._main_window, 'toggle_settings'):
            self._main_window.toggle_settings()
