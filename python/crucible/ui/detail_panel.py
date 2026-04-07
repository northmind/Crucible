from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QHideEvent, QResizeEvent
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from crucible.ui.artwork_manager import ArtworkManager
from crucible.ui.detail_panel_artwork import ArtworkMixin
from crucible.ui.detail_panel_config import ConfigMixin
from crucible.ui.detail_panel_dnd import DragDropMixin
from crucible.ui.detail_panel_tools import ToolsMixin
from crucible.ui.detail_widgets import _ConfirmBar, _ExtractionBar, _ZipImportBar
from crucible.ui.panel_helpers import build_collapsible_section
from crucible.ui.styles import get_accent, panel_fill

from crucible.core.managers import GameManager
from crucible.core.proton_manager import ProtonManager
from crucible.core.types import GameDict


PANEL_W = 288


class GameDetailPanel(ConfigMixin, ArtworkMixin, DragDropMixin, ToolsMixin, QWidget):
    launch_requested = pyqtSignal(dict)
    stop_requested = pyqtSignal(dict)
    zip_drop = pyqtSignal(dict, str)
    zip_drag_preview = pyqtSignal(bool, str)
    notification_requested = pyqtSignal(str, str, str)
    closed = pyqtSignal()
    game_updated = pyqtSignal()
    game_deleted = pyqtSignal()
    panel_width_changed = pyqtSignal(int)

    def __init__(self, artwork_manager: ArtworkManager, game_manager: GameManager, proton_manager: ProtonManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('DetailPanel')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._game = None
        self._running = False
        self._loading = False
        self._artwork_manager = artwork_manager
        self._game_manager = game_manager
        self._proton_manager = proton_manager
        self._artwork_pixmap = QPixmap()
        self._art_mode = 'artwork'
        self._art_notice_visible = False
        self._zip_drag_active = False
        self._wt_proc = None
        artwork_manager.artwork_ready.connect(self._on_artwork_ready)
        self.setAcceptDrops(True)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._auto_save)

        self._apply_style()
        self._build_ui()
        self.refresh_colors()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._art = QWidget()
        self._art.setObjectName('DetailArt')
        self._art.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._art.setFixedHeight(156)
        self._art.setStyleSheet(
            'background:'
            ' linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0.0) 34%),'
            ' linear-gradient(180deg, rgba(0,0,0,0.0), rgba(0,0,0,0.16) 100%),'
            ' #1a1d23;'
        )
        art_layout = QVBoxLayout(self._art)
        art_layout.setContentsMargins(0, 0, 0, 0)
        art_layout.setSpacing(0)

        self._art_image = QLabel(self._art)
        self._art_image.setScaledContents(False)
        self._art_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._art_image.lower()
        self._art_image.setStyleSheet('background: transparent; border: none;')

        self._art_notice = QWidget(self._art)
        self._art_notice.setObjectName('DetailArtNotice')
        self._art_notice.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        notice_layout = QVBoxLayout(self._art_notice)
        notice_layout.setContentsMargins(18, 16, 18, 16)
        notice_layout.setSpacing(8)

        self._art_notice_title = QLabel()
        notice_layout.addWidget(self._art_notice_title)

        self._art_notice_message = QLabel()
        self._art_notice_message.setWordWrap(True)
        notice_layout.addWidget(self._art_notice_message, 1)

        self._art_notice_anim = QPropertyAnimation(self._art_notice, b'pos')
        self._art_notice_anim.setDuration(180)
        self._art_notice_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._art_notice.hide()

        root.addWidget(self._art)

        self._scroll = self._make_scroll_page()
        root.addWidget(self._scroll, 1)
        self._content_layout = self._scroll.widget().layout()

        self._confirm_bar = _ConfirmBar(self)
        self._zip_import_bar = _ZipImportBar(self)
        self._extraction_bar = _ExtractionBar(self)

        for drop_target in (
            self._art,
            self._art_image,
            self._art_notice,
            self._scroll.viewport(),
            self._scroll.widget(),
            self._zip_import_bar,
        ):
            drop_target.setAcceptDrops(True)
            drop_target.installEventFilter(self)

    def _make_scroll_page(self) -> QScrollArea:
        accent = get_accent()
        scroll = QScrollArea()
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            'QScrollArea { background: transparent; border: none; }'
            f'QScrollBar:vertical {{ background: transparent; width: 2px; margin: 0; }}'
            f'QScrollBar::handle:vertical {{ background: {accent}; min-height: 20px; border: none; }}'
            'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }'
            'QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }'
            f'QScrollBar:horizontal {{ background: transparent; height: 2px; margin: 0; }}'
            f'QScrollBar::handle:horizontal {{ background: {accent}; min-width: 20px; border: none; }}'
            'QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }'
            'QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }'
        )
        scroll.viewport().setAutoFillBackground(False)
        inner = QWidget()
        inner.setStyleSheet('background: transparent;')
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 10, 0, 16)
        layout.setSpacing(0)
        scroll.setWidget(inner)
        return scroll

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _section_title(self, name: str) -> str:
        titles = {
            'game config': 'Game Config',
            'proton': 'Proton',
            'upscaling': 'Graphics / Upscaling',
            'compatibility': 'Compatibility',
            'debug': 'Debug',
            'tools': 'Tools',
            'desktop shortcut': 'Desktop Shortcut',
            'logs': 'Logs',
            'remove data': 'Remove Data',
        }
        return titles.get(name, name.title())

    def _add_section(self, name: str, widget: QWidget, *, expanded: bool) -> None:
        self._content_layout.addSpacing(6)
        section, header = build_collapsible_section(
            self._section_title(name),
            widget,
            expanded=expanded,
        )
        self._section_headers[name] = header
        self._content_layout.addWidget(section)

    def show_game(self, game: GameDict) -> None:
        """Display the detail panel for the given game, fetching its artwork and rebuilding the view."""
        self._stop_winetricks()
        self._game = game
        self.clear_launch_error()
        self._artwork_pixmap = QPixmap()
        self._art_image.setPixmap(QPixmap())
        artwork_exe_path = '' if game.get('exe_match_mode') == 'custom' else game.get('exe_path', '')
        self._artwork_manager.fetch_artwork(game['name'], artwork_exe_path)
        self._rebuild_view()
        self.panel_width_changed.emit(PANEL_W)

    def set_running(self, running: bool) -> None:
        """Update the running state and rebuild the view if the state changed."""
        was_running = self._running
        self._running = running
        if self._game and was_running != running:
            self._rebuild_view()
            if not running:
                QTimer.singleShot(1500, self._refresh_logs_if_idle)
                QTimer.singleShot(3500, self._refresh_logs_if_idle)

    def _refresh_logs_if_idle(self) -> None:
        if self._game and not self._running:
            self._rebuild_view()

    def show_extraction_result(self, detected_dlls: list[str] | None = None, detected_exe: str | None = None) -> None:
        """Dismiss the import bar and show zip extraction results in the extraction bar."""
        self._zip_drag_active = False
        self._zip_import_bar.dismiss()
        self._extraction_bar.show_result(detected_dlls, detected_exe)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Rescale artwork and reposition overlay bars on panel resize."""
        super().resizeEvent(event)
        self._apply_artwork_scale()
        self._art_notice.setGeometry(0, 0, self._art.width(), self._art.height())
        if self._art_notice_visible:
            self._art_notice.move(0, 0)
        else:
            self._art_notice.move(self._art_notice_hidden_pos())
        self._confirm_bar.reposition(self.width(), self.height())
        self._zip_import_bar.reposition(self.width(), self.height())
        self._extraction_bar.reposition(self.width(), self.height())

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop winetricks and dismiss all overlay bars when the panel is hidden."""
        self._stop_winetricks()
        self._dismiss_confirm_bar()
        self._zip_import_bar.dismiss()
        self._extraction_bar._dismiss()
        super().hideEvent(event)

    def _apply_style(self) -> None:
        self.setStyleSheet(f'background: {panel_fill()}; border: none;')

    def refresh_colors(self) -> None:
        """Reapply theme styles to all panel elements and rebuild the view."""
        self._apply_style()
        self._confirm_bar.refresh_colors()
        self._zip_import_bar._apply_styles()
        self._extraction_bar._apply_styles()
        self._apply_art_notice_style()
        accent = get_accent()
        self._scroll.setStyleSheet(
            'QScrollArea { background: transparent; border: none; }'
            f'QScrollBar:vertical {{ background: transparent; width: 2px; margin: 0; }}'
            f'QScrollBar::handle:vertical {{ background: {accent}; min-height: 20px; border: none; }}'
            'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }'
            'QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }'
            f'QScrollBar:horizontal {{ background: transparent; height: 2px; margin: 0; }}'
            f'QScrollBar::handle:horizontal {{ background: {accent}; min-width: 20px; border: none; }}'
            'QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }'
            'QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }'
        )
        self._rebuild_view()
