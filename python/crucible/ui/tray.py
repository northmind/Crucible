"""System tray icon with context menu for Crucible."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from crucible.core.events import event_bus

if TYPE_CHECKING:
    from crucible.ui.main_window import MainWindow

logger = logging.getLogger(__name__)

_ICON_PATH = Path(__file__).parent.parent / "assets" / "images" / "icon.jpg"


class SystemTrayIcon(QSystemTrayIcon):
    """Crucible system tray icon with show/hide and running-game list."""

    def __init__(self, main_window: MainWindow) -> None:
        icon = QIcon(str(_ICON_PATH)) if _ICON_PATH.is_file() else QIcon()
        super().__init__(icon, main_window)
        self._window = main_window
        self._running_names: list[str] = []

        self._menu = QMenu()
        self._toggle_action = QAction("Hide", self._menu)
        self._toggle_action.triggered.connect(self._toggle_window)
        self._menu.addAction(self._toggle_action)

        self._running_menu = self._menu.addMenu("Running Games")
        self._running_menu.setEnabled(False)

        self._menu.addSeparator()
        quit_action = QAction("Quit", self._menu)
        quit_action.triggered.connect(self._quit)
        self._menu.addAction(quit_action)

        self.setContextMenu(self._menu)
        self.setToolTip("Crucible Game Launcher")
        self.activated.connect(self._on_activated)

        # Connect to event bus for live running-game updates
        event_bus.game_launched.connect(self._on_game_launched)
        event_bus.game_exited.connect(self._on_game_exited)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self._window.isVisible():
            self._window.hide()
            self._toggle_action.setText("Show")
        else:
            self._window.showNormal()
            self._window.activateWindow()
            self._toggle_action.setText("Hide")

    def _quit(self) -> None:
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def _on_game_launched(self, name: str) -> None:
        if name not in self._running_names:
            self._running_names.append(name)
        self._refresh_running_menu()

    def _on_game_exited(self, name: str) -> None:
        if name in self._running_names:
            self._running_names.remove(name)
        self._refresh_running_menu()

    def _refresh_running_menu(self) -> None:
        self._running_menu.clear()
        if not self._running_names:
            self._running_menu.setEnabled(False)
            return
        self._running_menu.setEnabled(True)
        for name in sorted(self._running_names):
            self._running_menu.addAction(name)


