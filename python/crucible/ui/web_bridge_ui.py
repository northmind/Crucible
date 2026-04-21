"""Web bridge UI mixin — themes, window controls, env options, winetricks.

Mixed into WebBridge by web_bridge.py.  All signals referenced
(toastRequested, themeColorsChanged) are defined on WebBridge.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QApplication, QMainWindow

from crucible.ui.theme_system import (
    builtin_themes,
    get_theme,
    get_builtin_theme,
    apply_builtin_theme,
    get_surface_colors,
    get_selection_colors,
    get_status_colors,
    theme_changed_signal,
)

if TYPE_CHECKING:
    from crucible.ui.artwork_manager import ArtworkManager
    from crucible.core.managers import GameManager

class WebBridgeUIMixin:
    """Mixin providing theme, window, env-option, and winetricks slots."""

    _gm: GameManager
    _artwork: ArtworkManager

    def _connect_theme_signal(self) -> None:
        theme_changed_signal().connect(self._emit_theme_colors)

    # --- Themes ---

    @pyqtSlot(result=str)
    def getActiveThemeKey(self) -> str:
        return get_theme().key

    @pyqtSlot(result="QVariant")
    def getThemes(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name, "key": t.key, "accent": t.accent,
                "bg": t.bg, "text": t.text, "text_dim": t.text_dim,
                "border": t.border, "accent_soft": t.accent_soft,
                "chrome_bg": t.chrome_bg,
            }
            for t in builtin_themes()
        ]

    @pyqtSlot(result="QVariant")
    def getThemeColors(self) -> dict[str, str]:
        theme = get_theme()
        surface = get_surface_colors()
        selection = get_selection_colors()
        status = get_status_colors()
        return {
            "accent": theme.accent, "accent_soft": theme.accent_soft,
            "bg": theme.bg, "border": theme.border,
            "text": theme.text, "text_dim": theme.text_dim,
            "chrome_bg": theme.chrome_bg,
            "window_bg": surface.window_bg, "nav_bg": surface.nav_bg,
            "panel_bg": surface.panel_bg, "content_bg": surface.content_bg,
            "nav_accent": selection.nav_accent,
            "selection_bg": selection.selection_bg,
            "hover_bg": selection.hover_bg,
            "warning": status.warning, "error": status.error,
            "success": status.success, "info": status.info,
            "danger_hover": status.danger_hover,
            "text_disabled": status.text_disabled,
        }

    @pyqtSlot(str)
    def setTheme(self, key: str) -> None:
        theme = get_builtin_theme(key)
        apply_builtin_theme(theme)

    def _emit_theme_colors(self) -> None:
        self.themeColorsChanged.emit()  # type: ignore[attr-defined]

    # --- Window controls ---

    @pyqtSlot()
    def minimizeWindow(self) -> None:
        win = self._find_window()
        if win:
            win.showMinimized()

    @pyqtSlot()
    def maximizeWindow(self) -> None:
        win = self._find_window()
        if win:
            if win.isMaximized():
                win.showNormal()
            else:
                win.showMaximized()

    @pyqtSlot()
    def closeWindow(self) -> None:
        win = self._find_window()
        if win:
            win.close()

    @pyqtSlot()
    def startDrag(self) -> None:
        """Initiate system window move (for frameless drag region)."""
        win = self._find_window()
        if win and win.windowHandle():
            win.windowHandle().startSystemMove()

    @pyqtSlot(result=str)
    def openFileDialog(self) -> str:
        from crucible.ui.widgets import get_executable_path
        return get_executable_path(self._find_window()) or ""

    @pyqtSlot(str, result=str)
    def openDirDialog(self, title: str) -> str:
        from crucible.ui.widgets import get_directory_path
        return get_directory_path(self._find_window(), title) or ""

    # --- Winetricks ---

    @pyqtSlot(str)
    def launchWinetricks(self, game_name: str) -> None:
        game = self._gm.get_game(game_name)
        if not game:
            self.toastRequested.emit("Game not found", "error")
            return
        resolved = self._gm.global_config.resolve(game)
        from crucible.core.paths import safe_name
        from crucible.core.launch_env import resolve_prefix
        sname = safe_name(game_name)
        prefix_path = str(resolve_prefix(resolved, sname, self._gm.prefixes_dir))
        proton_name = resolved.get('proton_version', '') or None
        result = self._gm.launch_winetricks(prefix_path, proton_name)
        if result is None:
            self.toastRequested.emit("Failed to launch Winetricks — check Proton and umu-run", "error")

    @pyqtSlot(str)
    def setActiveView(self, view_id: str) -> None:
        """Track the active navigation tab for drag-drop gating."""
        self._active_view = view_id

    @pyqtSlot(str)
    def setModalGameName(self, name: str) -> None:
        """Track which game is open in the modal for zip drop targeting."""
        self._modal_game_name = name

    # --- Internal ---

    def _find_window(self):
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                if isinstance(w, QMainWindow):
                    return w
        return None
