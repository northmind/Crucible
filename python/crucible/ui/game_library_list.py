from __future__ import annotations

import atexit

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QFrame, QStackedWidget,
)

from crucible.core.managers import GameManager
from crucible.core.types import GameDict
from crucible.ui.artwork_manager import ArtworkManager
from crucible.ui.game_item import (
    _ROW,
    _SIZE_WORKERS,
    _compute_install_size,
    _EmptyLibrarySurface,
    GameItemWidget,
)
from crucible.ui.styles import get_accent

_POLL_RUNNING_INTERVAL_MS = 2000
_SELECT_DEBOUNCE_MS = 250
_SIZE_DEFER_MS = 3000        # delay before size computation to let install_dir resolve
_REFRESH_DEBOUNCE_MS = 200   # coalesce rapid-fire refresh signals


class GameLibraryListWidget(QWidget):
    game_launch           = pyqtSignal(dict)
    game_stop             = pyqtSignal(dict)
    game_selected         = pyqtSignal(dict)
    game_deselected       = pyqtSignal()
    browse_requested      = pyqtSignal()
    count_changed         = pyqtSignal(int, int)
    running_state_changed = pyqtSignal(str, bool)
    _size_done            = pyqtSignal(str, str)

    def __init__(self, game_manager: GameManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.game_manager  = game_manager
        self.accent_color  = get_accent()
        self.artwork_manager = ArtworkManager()
        self.artwork_manager.name_fetched.connect(self._on_name_fetched)
        self._size_done.connect(self._on_size_ready)
        self._filter       = ""
        self._selected_name: str | None = None
        self._size_cache: dict[str, str] = {}
        self._size_pending: set[str] = set()
        self._size_deferred: dict[str, str] = {}
        self._size_immediate: set[str] = set()
        from concurrent.futures import ThreadPoolExecutor
        self._size_executor = ThreadPoolExecutor(max_workers=_SIZE_WORKERS, thread_name_prefix="game-size")
        # Belt-and-suspenders shutdown: atexit fires if the process exits
        # without a Qt close event (e.g. SIGTERM, sys.exit from a background
        # thread), while closeEvent handles the normal window-close path.
        # Both are idempotent — calling shutdown() on an already-shut-down
        # executor is a harmless no-op.
        atexit.register(self._size_executor.shutdown, wait=False, cancel_futures=True)

        self._size_defer_timer = QTimer(self)
        self._size_defer_timer.setSingleShot(True)
        self._size_defer_timer.setInterval(_SIZE_DEFER_MS)
        self._size_defer_timer.timeout.connect(self._flush_deferred_sizes)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(_REFRESH_DEBOUNCE_MS)
        self._refresh_timer.timeout.connect(self.refresh)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_RUNNING_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_running_games)
        self._poll_timer.start()

        self._select_guard = False
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 1, 0)
        layout.setSpacing(0)

        self._top_gap = QLabel()
        self._top_gap.setFixedHeight(8)
        layout.addWidget(self._top_gap)

        self.list_widget = QListWidget()
        self.list_widget.setSpacing(0)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        scrollbar = self.list_widget.verticalScrollBar()
        if scrollbar:
            scrollbar.setSingleStep(10)
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_widget.setStyleSheet(
            "QListWidget { background-color: transparent; border: none; outline: none; }"
            " QListWidget::item { background-color: transparent; border: none; padding: 0; }"
            " QListWidget::item:selected, QListWidget::item:hover { background-color: transparent; }"
            " QScrollBar:vertical { background: transparent; width: 2px; margin: 0; }"
            " QScrollBar::handle:vertical { background: palette(link); min-height: 20px; border: none; }"
            " QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            " QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
            " QScrollBar:horizontal { background: transparent; height: 2px; margin: 0; }"
            " QScrollBar::handle:horizontal { background: palette(link); min-width: 20px; border: none; }"
            " QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
            " QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
        )

        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(0)

        self._empty_surface = _EmptyLibrarySurface(self.accent_color, self.empty_widget)
        self._empty_surface.browse_requested.connect(self.browse_requested.emit)
        empty_layout.addWidget(self._empty_surface, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.list_widget)
        self.stack.addWidget(self.empty_widget)
        layout.addWidget(self.stack, 1)

    def set_accent(self, color: str) -> None:
        """Update the accent color and refresh the game list."""
        self.accent_color = color
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the game list from the game manager, preserving selection and sizes."""
        accent = self.accent_color
        self._top_gap.setStyleSheet('background: transparent; border: none;')
        self._empty_surface.set_accent(accent)
        games = self.game_manager.get_games()
        self.list_widget.clear()

        seen_names = {game['name'] for game in games}
        self._size_cache = {name: size for name, size in self._size_cache.items() if name in seen_names}
        self._size_pending.intersection_update(seen_names)

        for game in games:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, game)
            item.setSizeHint(QSize(400, _ROW))

            widget = GameItemWidget(game, self.accent_color)
            widget.selected.connect(self._on_item_selected)
            widget.launch_clicked.connect(self.game_launch)
            widget.stop_clicked.connect(self.game_stop)
            widget.set_running(self.game_manager.is_game_running(game['name']))
            if game['name'] == self._selected_name:
                widget.set_selected(True)

            size_str = self._size_cache.get(game['name'])
            if size_str is not None:
                widget.set_size(size_str)

            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

            install_dir = game.get('install_dir', '')
            if install_dir and size_str is None and game['name'] not in self._size_pending:
                name = game['name']
                if name in self._size_immediate:
                    self._size_immediate.discard(name)
                    self._submit_size_computation(name, install_dir)
                else:
                    self._size_deferred[name] = install_dir

        if self._size_deferred:
            self._size_defer_timer.start()

        self.stack.setCurrentIndex(1 if len(games) == 0 else 0)
        self.filter_games(self._filter)

    def _on_item_selected(self, game: GameDict) -> None:
        if self._select_guard:
            return
        self._select_guard = True
        QTimer.singleShot(_SELECT_DEBOUNCE_MS, self._clear_select_guard)
        name = game['name']
        if name == self._selected_name:
            self._set_selected(None)
            self.game_deselected.emit()
        else:
            self._set_selected(name)
            self.game_selected.emit(game)

    def _clear_select_guard(self) -> None:
        self._select_guard = False

    def _set_selected(self, name: str | None) -> None:
        self._selected_name = name
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            w = self.list_widget.itemWidget(item)
            if w:
                w.set_selected(w.game_data['name'] == name)

    def invalidate_size(self, game_name: str) -> None:
        """Clear cached size for *game_name* and mark it for immediate recomputation."""
        self._size_cache.pop(game_name, None)
        self._size_pending.discard(game_name)
        self._size_deferred.pop(game_name, None)
        self._size_immediate.add(game_name)

    def _flush_deferred_sizes(self) -> None:
        """Submit all deferred size computations to the thread pool."""
        batch = dict(self._size_deferred)
        self._size_deferred.clear()
        for game_name, install_dir in batch.items():
            if game_name in self._size_cache or game_name in self._size_pending:
                continue
            self._submit_size_computation(game_name, install_dir)

    def _submit_size_computation(self, game_name: str, install_dir: str) -> None:
        """Submit a single size computation to the background thread pool."""
        self._size_pending.add(game_name)
        future = self._size_executor.submit(_compute_install_size, install_dir)
        future.add_done_callback(
            lambda fut, gn=game_name: self._size_done.emit(
                gn,
                fut.result() if fut.exception() is None else "\u2014",
            )
        )

    def schedule_refresh(self) -> None:
        """Request a debounced refresh so rapid-fire signals coalesce into one rebuild."""
        self._refresh_timer.start()

    def clear_selection(self) -> None:
        """Deselect all games in the list."""
        self._set_selected(None)

    def select_game(self, name: str | None) -> None:
        """Programmatically select a game by name, or deselect if None."""
        self._set_selected(name)

    def filter_games(self, text: str) -> None:
        """Show only games whose names contain the given filter text."""
        self._filter = text.lower().strip()
        total = self.list_widget.count()
        visible = 0
        for i in range(total):
            item = self.list_widget.item(i)
            game = item.data(Qt.ItemDataRole.UserRole)
            match = not self._filter or (game and self._filter in game['name'].lower())
            item.setHidden(not match)
            if match:
                visible += 1
        self.count_changed.emit(total, visible)

    def _poll_running_games(self) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            game = item.data(Qt.ItemDataRole.UserRole)
            if game:
                widget = self.list_widget.itemWidget(item)
                if widget:
                    was_running = widget.is_running
                    is_running  = self.game_manager.is_game_running(game['name'])
                    if was_running != is_running:
                        if was_running and not is_running:
                            self.game_manager.on_game_exited(game['name'])
                        widget.set_running(is_running)
                        self.running_state_changed.emit(game['name'], is_running)

    def _on_size_ready(self, game_name: str, size_str: str) -> None:
        self._size_pending.discard(game_name)
        self._size_cache[game_name] = size_str
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            w = self.list_widget.itemWidget(item)
            if w and w.game_data['name'] == game_name:
                w.set_size(size_str)
                break

    def _on_name_fetched(self, old_name: str, steam_name: str) -> None:
        game = self.game_manager.get_game(old_name)
        if not game:
            return
        exe_path = game.get('exe_path', '')
        if exe_path:
            from crucible.core.paths import display_name_from_exe
            auto_name = display_name_from_exe(exe_path)
            if old_name != auto_name:
                return
        if self.game_manager.rename_game(old_name, steam_name):
            self.schedule_refresh()

    def prefetch_artwork_for_game(self, game_name: str, exe_path: str = '') -> None:
        """Start a background artwork fetch for the given game."""
        self.artwork_manager.fetch_artwork(game_name, exe_path)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Shut down the background size-computation thread pool."""
        self._size_executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)
