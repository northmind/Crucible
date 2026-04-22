"""System tray icon with context menu for Crucible."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

if TYPE_CHECKING:
    from crucible.ui.main_window import MainWindow

logger = logging.getLogger(__name__)

_ICON_PATH = Path(__file__).parent.parent / "assets" / "images" / "icon.jpg"


class SystemTrayIcon(QSystemTrayIcon):
    """Crucible system tray icon with show/hide and quit actions."""

    def __init__(self, main_window: MainWindow) -> None:
        icon = QIcon(str(_ICON_PATH)) if _ICON_PATH.is_file() else QIcon()
        super().__init__(icon, main_window)
        self._window = main_window

        self._menu = QMenu()
        self._toggle_action = QAction("Hide", self._menu)
        self._toggle_action.triggered.connect(self._toggle_window)
        self._menu.addAction(self._toggle_action)

        self._menu.addSeparator()
        quit_action = QAction("Quit", self._menu)
        quit_action.triggered.connect(self._quit)
        self._menu.addAction(quit_action)

        self.setContextMenu(self._menu)
        self.setToolTip("Crucible Game Launcher")
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def sync_toggle_action(self) -> None:
        self._toggle_action.setText("Hide" if self._window.isVisible() else "Show")

    def _toggle_window(self) -> None:
        if self._window.isVisible():
            self._window.hide()
        else:
            self._window.restore_and_activate()
        self.sync_toggle_action()

    def _quit(self) -> None:
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
