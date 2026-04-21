"""Main application window — frameless QWebEngineView shell.

Loads index.html via QWebEngineView, exposes WebBridge over QWebChannel,
manages system tray, geometry save/restore, and edge resize handles.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, QEvent
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel

from crucible.ui.app_settings import (
    auto_update_umu,
    custom_proton_dir,
    minimize_to_tray,
    restore_geometry,
)
from crucible.ui.web_bridge import WebBridge
from crucible.ui.resize_handles import setup_resize_handles, update_resize_handles
from crucible.core.managers import GameManager
from crucible.core.proton_manager import ProtonManager
from crucible.core.workers import UmuUpdateWorker, register_worker
from crucible.ui.tray import SystemTrayIcon

_WEB_DIR = Path(__file__).parent / "web"


class _LocalPage(QWebEnginePage):
    """Block navigation away from the bundled local UI."""

    def __init__(self, web_root: Path, parent=None) -> None:
        super().__init__(parent)
        self._web_root = web_root.resolve()

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):  # noqa: N802
        del nav_type, is_main_frame
        if not url.isLocalFile():
            return False
        try:
            return Path(url.toLocalFile()).resolve().is_relative_to(self._web_root)
        except OSError:
            return False


class MainWindow(QMainWindow):
    """Frameless window hosting QWebEngineView with QWebChannel bridge."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(900, 560)
        self.resize(1050, 660)

        self.game_manager = GameManager()
        self.proton_manager = ProtonManager()
        self._bridge = WebBridge(self.game_manager, self.proton_manager)

        self._view = QWebEngineView(self)
        self._page = _LocalPage(_WEB_DIR, self._view)
        self._view.setPage(self._page)
        self.setCentralWidget(self._view)

        # Dark background before page loads — prevents white flash
        self._view.page().setBackgroundColor(QColor("#09090b"))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("background-color: #09090b;")

        ws = self._view.settings()
        ws.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True,
        )

        channel = QWebChannel(self._view.page())
        channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(channel)

        self._view.setUrl(QUrl.fromLocalFile(str(_WEB_DIR / "index.html")))
        self._view.loadFinished.connect(self._on_load_finished)

        self._handles = setup_resize_handles(self)

        self._tray = SystemTrayIcon(self)
        self._tray.show()

        self._restore_geometry()
        self._page_ready = False
        QTimer.singleShot(500, self._install_drop_filter)

    # -- Page load completion --------------------------------------------------

    def _on_load_finished(self, ok: bool) -> None:
        if ok and not self._page_ready:
            self._page_ready = True
            self.show()
            self._load_initial_data()

    # -- Drag-and-drop (event filter on QWebEngineView) ----------------------

    def _install_drop_filter(self) -> None:
        target = self._view.focusProxy() or self._view
        target.setAcceptDrops(True)
        target.installEventFilter(self)
        self._drop_target = target

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        etype = event.type()
        if obj is not getattr(self, "_drop_target", None):
            return super().eventFilter(obj, event)

        if etype == QEvent.Type.DragEnter:
            accepted, msg = self._check_drag_accept(event.mimeData())
            if accepted:
                event.acceptProposedAction()
                safe = msg.replace("'", "\\'")
                self._run_js(f"window._showDragToast && _showDragToast('{safe}')")
                return True
            event.ignore()
            return True

        elif etype == QEvent.Type.DragMove:
            accepted, _ = self._check_drag_accept(event.mimeData())
            if accepted:
                event.acceptProposedAction()
            else:
                event.ignore()
            return True

        elif etype == QEvent.Type.DragLeave:
            self._run_js("window._hideDragToast && _hideDragToast()")

        elif etype == QEvent.Type.Drop:
            self._run_js("window._hideDragToast && _hideDragToast()")
            self._handle_drop(event.mimeData())
            event.acceptProposedAction()
            return True

        return super().eventFilter(obj, event)

    def _check_drag_accept(self, mime) -> tuple[bool, str]:
        """Return (accepted, toast_message) based on file types and active view."""
        if not mime.hasUrls():
            return False, ""
        view = self._bridge.active_view
        has_exe = any(
            u.isLocalFile() and u.toLocalFile().lower().endswith(".exe")
            for u in mime.urls()
        )
        has_zip = any(
            u.isLocalFile() and u.toLocalFile().lower().endswith(".zip")
            for u in mime.urls()
        )
        if has_exe and view == "library":
            return True, "Drop to add game"
        if has_zip and view == "modal":
            return True, "Drop to apply archive"
        return False, ""

    def _handle_drop(self, mime) -> None:
        if not mime.hasUrls():
            return
        view = self._bridge.active_view
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            lower = path.lower()
            if lower.endswith(".exe") and view == "library":
                self._add_dropped_exe(path)
            elif lower.endswith(".zip") and view == "modal":
                self._apply_dropped_zip(path)

    def _add_dropped_exe(self, exe_path: str) -> None:
        result = self._bridge.addGame(exe_path)
        if result.get("success"):
            game = result.get("game") or {}
            name = game.get("name") or result.get("name") or "game"
            if game:
                game_json = json.dumps(game)
                self._run_js(
                    f"if(window.insertPendingGameCard) insertPendingGameCard({game_json})",
                )
            self._toast(f"Added {name}")
        else:
            self._toast(result.get("error", "Failed to add game"), "error")

    def _apply_dropped_zip(self, zip_path: str) -> None:
        result = self._bridge.applyZipToGame(zip_path)
        if not result.get("success"):
            self._toast(result.get("error", "Extract failed"), "error")
            return
        dlls = result.get("added_dlls", [])
        exe = result.get("exe", "")
        self._show_extraction_toast(dlls, exe)
        # Refresh the modal with updated game data
        name = self._bridge.modal_game_name
        if name:
            safe = name.replace("'", "\\'")
            self._run_js(f"if(window.openGameModal) openGameModal('{safe}')")

    def _show_extraction_toast(self, dlls: list[str], exe: str) -> None:
        if dlls and exe:
            title = "Extracted — overrides set, exe found"
        elif dlls:
            title = "Extracted — overrides set"
        elif exe:
            title = "Extracted — exe found"
        else:
            self._toast("Archive extracted")
            return
        lines = [title]
        for dll in dlls[:5]:
            lines.append(f"· {dll}")
        if len(dlls) > 5:
            lines.append(f"+{len(dlls) - 5} more")
        if exe:
            lines.append(f"exe: {Path(exe).name}")
        safe = "\n".join(lines).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
        self._run_js(f"if(window.showToast) showToast('{safe}', 'success')")

    def _toast(self, msg: str, level: str = "success") -> None:
        safe = msg.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
        self._run_js(f"if(window.showToast) showToast('{safe}', '{level}')")

    def _run_js(self, code: str) -> None:
        self._view.page().runJavaScript(code)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        update_resize_handles(self._handles, self.width(), self.height())

    def _restore_geometry(self) -> None:
        if not restore_geometry():
            return
        from crucible.ui.theme_system import get_settings
        geo = get_settings().value("window_geometry")
        if geo is not None and isinstance(geo, dict):
            self.setGeometry(
                geo.get("x", 100), geo.get("y", 100),
                geo.get("w", 1128), geo.get("h", 760),
            )

    def closeEvent(self, event) -> None:
        if minimize_to_tray() and self._tray.isVisible():
            self.hide()
            event.ignore()
            return
        self._save_geometry()
        super().closeEvent(event)

    def _save_geometry(self) -> None:
        if not restore_geometry():
            return
        from crucible.ui.theme_system import get_settings
        g = self.geometry()
        get_settings().setValue("window_geometry", {
            "x": g.x(), "y": g.y(), "w": g.width(), "h": g.height(),
        })

    def _load_initial_data(self) -> None:
        extra = custom_proton_dir()
        if extra:
            self.proton_manager.add_search_dir(Path(extra))
        self.game_manager.scan_games()
        self.proton_manager.scan_installed()
        self._bridge.ensureDefaultRunner()
        self._bridge.gamesChanged.emit()
        self._bridge.protonChanged.emit()
        if auto_update_umu():
            app = QApplication.instance()
            worker = UmuUpdateWorker(parent=app)
            register_worker(worker)
            worker.start()
