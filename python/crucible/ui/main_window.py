from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QVariantAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QApplication, QSizePolicy,
)
from PyQt6.QtGui import QFont, QFontDatabase, QColor, QPalette, QResizeEvent

from crucible.ui import styles
from crucible.ui.titlebar import TitleBar
from crucible.ui.nav_sidebar import NavSidebar
from crucible.ui.side_panel_host import SidePanelHost, PANEL_DETAIL, PANEL_SETTINGS, PANEL_PROTON
from crucible.ui.resize_handles import setup_resize_handles, update_resize_handles
from crucible.ui.panel_animation import PanelAnimationMixin
from crucible.ui.drag_drop import DragDropMixin
from crucible.ui.game_events import GameEventsMixin
from crucible.ui.game_library_list import GameLibraryListWidget
from crucible.ui.detail_panel import GameDetailPanel, PANEL_W as DETAIL_PANEL_W
from crucible.ui.settings_panel import SettingsPanel, PANEL_W as SETTINGS_PANEL_W
from crucible.ui.proton_panel import ProtonPanel, PANEL_W as PROTON_PANEL_W
from crucible.core.managers import GameManager
from crucible.core.proton_manager import ProtonManager
from crucible.core.workers import UmuUpdateWorker, register_worker
from crucible.ui.widgets import SlidingNotification


class MainWindow(PanelAnimationMixin, DragDropMixin, GameEventsMixin, QMainWindow):
    """Top-level frameless window hosting the game library and side panels."""

    def __init__(self) -> None:
        super().__init__()

        self._set_monospace_font()
        self.game_manager = GameManager()
        self.proton_manager = ProtonManager()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(980, 600)
        self.resize(1128, 760)

        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        central.setStyleSheet(styles.central_widget())
        self.setCentralWidget(central)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        central.setLayout(layout)

        self.titlebar = TitleBar(self)
        layout.addWidget(self.titlebar)

        self.main_container = QWidget()
        self.main_container.setObjectName("MainContainer")
        self.main_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.main_container.setStyleSheet(styles.window_bg())
        self.main_layout = QHBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.nav_sidebar = NavSidebar(self)
        self.main_layout.addWidget(self.nav_sidebar)

        self.library_widget = GameLibraryListWidget(self.game_manager)
        self.library_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.main_layout.addWidget(self.library_widget, 1)

        self._panel_host = SidePanelHost(parent=central)

        self.detail_panel = GameDetailPanel(
            self.library_widget.artwork_manager,
            self.game_manager,
            self.proton_manager,
        )
        self.settings_panel = SettingsPanel()
        self.settings_panel.accent_changed.connect(self.on_accent_changed)
        self.proton_panel = ProtonPanel(self.proton_manager)

        self._panel_host.add_panel(PANEL_DETAIL, self.detail_panel)
        self._panel_host.add_panel(PANEL_SETTINGS, self.settings_panel)
        self._panel_host.add_panel(PANEL_PROTON, self.proton_panel)

        self._panel_open = False
        self._active_panel_key = None
        self._return_panel_key = None
        self._edit_panel_w = DETAIL_PANEL_W
        self._panel_anim = QPropertyAnimation(self._panel_host, b"geometry")
        self._panel_anim.setDuration(180)
        self._panel_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._margin_anim = QVariantAnimation(self)
        self._margin_anim.setDuration(180)
        self._margin_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._margin_anim.valueChanged.connect(self._on_panel_margin_changed)

        self._panel_margin_right = 0
        self._zip_drag_preview_active = False

        self.nav_sidebar.set_active(None)
        self._notification = SlidingNotification(central)
        self._drag_preview = SlidingNotification(central, show_close=False)

        layout.addWidget(self.main_container, 1)

        self.resize_handles = setup_resize_handles(self)
        self.setAcceptDrops(True)
        self._connect_signals()
        QTimer.singleShot(100, self._load_initial_data)

    def _connect_signals(self) -> None:
        """Wire up all inter-widget signals."""
        self.titlebar.search_changed.connect(self.library_widget.filter_games)
        self.library_widget.game_launch.connect(self._on_game_launch)
        self.library_widget.game_stop.connect(self._on_game_stop)
        self.library_widget.game_selected.connect(self._on_game_selected)
        self.library_widget.game_deselected.connect(self._close_detail)
        self.library_widget.browse_requested.connect(self.open_add_game)
        self.library_widget.running_state_changed.connect(self._on_running_state_changed)
        self.detail_panel.launch_requested.connect(self._on_game_launch)
        self.detail_panel.stop_requested.connect(self._on_game_stop)
        self.detail_panel.zip_drop.connect(self._on_zip_drop)
        self.detail_panel.zip_drag_preview.connect(self._on_zip_drag_preview)
        self.detail_panel.notification_requested.connect(self._show_notification)
        self.detail_panel.closed.connect(self._close_detail)
        self.detail_panel.game_updated.connect(self._on_game_updated)
        self.detail_panel.game_deleted.connect(self._on_game_deleted)
        self.detail_panel.panel_width_changed.connect(self._on_panel_width_changed)
        self.library_widget.artwork_manager.install_dir_resolved.connect(
            self._on_install_dir_resolved,
        )

    # ------------------------------------------------------------------
    # Panel width helpers
    # ------------------------------------------------------------------

    def _current_panel_width(self) -> int:
        """Return the pixel width of the currently open panel, or 0."""
        if self._active_panel_key is None:
            return 0
        return self._panel_width_for_key(self._active_panel_key)

    def _panel_width_for_key(self, key: str | None) -> int:
        """Return the fixed width associated with a panel key."""
        if key == PANEL_DETAIL:
            return self._edit_panel_w
        if key == PANEL_SETTINGS:
            return SETTINGS_PANEL_W
        if key == PANEL_PROTON:
            return PROTON_PANEL_W
        return self._edit_panel_w

    def _sync_titlebar_seam(self) -> None:
        """Keep the titlebar right gap aligned with the panel width."""
        self.titlebar.set_right_gap(self._current_panel_width())

    def _on_panel_margin_changed(self, value: int) -> None:
        self._panel_margin_right = int(value)
        self._apply_main_layout_margins()
        self.titlebar.set_right_gap(self._panel_margin_right)

    def _apply_main_layout_margins(self) -> None:
        self.main_layout.setContentsMargins(0, 0, self._panel_margin_right, 0)

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _set_monospace_font(self) -> None:
        """Select the best available monospace font for the application."""
        preferred = ["Courier New", "Monospace", "Source Code Pro", "Consolas", "DejaVu Sans Mono"]
        available = QFontDatabase.families()
        selected = None
        for family in preferred:
            if family in available:
                selected = family
                break
        if not selected:
            mono = [f for f in available if 'mono' in f.lower() or 'courier' in f.lower()]
            selected = mono[0] if mono else "Courier New"
        font = QFont(selected, 10)
        app = QApplication.instance()
        if app:
            app.setFont(font)

    def _load_initial_data(self) -> None:
        """Scan games, proton versions, and kick off a UMU update check."""
        self.game_manager.scan_games()
        self.proton_manager.scan_installed()
        self.library_widget.refresh()
        worker = UmuUpdateWorker(parent=self)
        register_worker(worker)
        worker.start()

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Reposition resize handles and panels on window resize."""
        super().resizeEvent(event)
        update_resize_handles(self.resize_handles, self.width(), self.height())
        if self._panel_open and self._panel_anim.state() != self._panel_anim.State.Running:
            self._panel_host.setGeometry(self._panel_geometry(True))
        self._sync_titlebar_seam()
        self._notification.reposition(anchor_y=self._notification_anchor_y())
        self._drag_preview.reposition(anchor_y=self._drag_notice_anchor_y())

    # ------------------------------------------------------------------
    # Game management
    # ------------------------------------------------------------------

    def open_add_game(self) -> None:
        """Open a file dialog to select a game executable."""
        from crucible.ui.widgets import get_executable_path
        exe_path = get_executable_path(self)
        if exe_path:
            self._add_game_from_path(exe_path)

    def _add_game_from_path(self, exe_path: str) -> None:
        """Derive a game name from the exe path and register it."""
        from crucible.core.paths import display_name_from_exe, find_game_root
        name = display_name_from_exe(exe_path)
        install_dir = find_game_root(exe_path) or str(Path(exe_path).parent)
        success = self.game_manager.add_game(
            name=name, exe=exe_path, proton="", args="",
            custom_overrides="", install_dir=install_dir,
        )
        if success:
            self.library_widget.refresh()
            self.library_widget.prefetch_artwork_for_game(name, exe_path)
        else:
            self._show_notification("Error", "Failed to add game. Check logs.", "error")

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _notification_anchor_y(self) -> int:
        return self.titlebar.height() + 16

    def _show_notification(self, title: str, message: str, kind: str = "warning") -> None:
        """Display a sliding notification banner."""
        self._notification.show_message(title, message, kind, anchor_y=self._notification_anchor_y())
        self._notification.raise_()

    # ------------------------------------------------------------------
    # Theme / accent
    # ------------------------------------------------------------------

    def on_accent_changed(self, color: str) -> None:
        """Apply a new accent colour across the entire application palette."""
        app = QApplication.instance()
        if not app:
            return
        palette = app.palette()
        c = QColor(color)
        for role in (
            QPalette.ColorRole.Highlight, QPalette.ColorRole.Link,
            QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
        ):
            palette.setColor(role, c)
        app.setPalette(palette)
        self.refresh_colors()

    def refresh_colors(self) -> None:
        """Repaint all widgets after a theme or accent change."""
        self.centralWidget().setStyleSheet(styles.central_widget())
        self.main_container.setStyleSheet(styles.window_bg())
        self.titlebar.refresh_colors()
        self.nav_sidebar.refresh_colors()
        self._panel_host.refresh_colors()
        self.detail_panel.refresh_colors()
        self.settings_panel.refresh_colors()
        self.proton_panel.refresh_colors()
        self._notification.refresh_colors()
        self._drag_preview.refresh_colors()
        accent = styles.get_accent()
        self.library_widget.set_accent(accent)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(styles.tooltip())
