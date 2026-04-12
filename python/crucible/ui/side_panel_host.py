from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QResizeEvent
from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from crucible.ui import styles

# Panel key constants used across main_window, panel_animation, game_events,
# nav_sidebar, and detail_panel to avoid stringly-typed dispatch.
PANEL_DETAIL = 'detail'
PANEL_SETTINGS = 'settings'
PANEL_PROTON = 'proton'

# Width constraints for panel resizing
MIN_PANEL_W = 240
MAX_PANEL_W = 500
HANDLE_W = 5


class _PanelResizeHandle(QWidget):
    """Thin drag handle on the left edge of the panel host."""

    drag_delta = pyqtSignal(int)  # horizontal pixel delta (negative = wider)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedWidth(HANDLE_W)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setStyleSheet("background: transparent;")
        self._drag_start_x: int | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_x = event.globalPosition().toPoint().x()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start_x is not None:
            current_x = event.globalPosition().toPoint().x()
            delta = current_x - self._drag_start_x
            self._drag_start_x = current_x
            self.drag_delta.emit(delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_x = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class SidePanelHost(QWidget):
    """Stacked container that hosts side panels (detail, settings, proton)."""

    width_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidePanelHost")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._stack = QStackedWidget()
        self._stack.setObjectName("SidePanelStack")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 0, 1, 0)
        layout.setSpacing(0)
        layout.addWidget(self._stack)
        self._panels: dict[str, QWidget] = {}
        self._active_key: str | None = None
        self._custom_width: int | None = None

        self._handle = _PanelResizeHandle(self)
        self._handle.drag_delta.connect(self._on_drag_delta)

        self._apply_style()
        self.hide()

    def _apply_style(self) -> None:
        """Apply border and background styling from the current theme."""
        edge = styles.line_accent()
        fill = styles.panel_fill()
        self.setStyleSheet(
            f"#SidePanelHost {{ background: {fill}; border-left: 1px solid {edge};"
            f" border-right: 1px solid {edge}; }}"
            "#SidePanelStack { background: transparent; border: none; }"
        )

    def add_panel(self, key: str, widget: QWidget) -> None:
        """Register a panel widget under the given key."""
        self._panels[key] = widget
        self._stack.addWidget(widget)

    def set_active_panel(self, key: str) -> None:
        """Switch to the panel registered under *key* and show the host."""
        widget = self._panels[key]
        self._active_key = key
        self._stack.setCurrentWidget(widget)
        self.show()
        self.raise_()

    def current_key(self) -> str | None:
        """Return the key of the currently active panel, or None."""
        return self._active_key

    def get_custom_width(self, key: str | None = None) -> int | None:
        """Return the shared user-set width, or None if not resized."""
        return self._custom_width

    def refresh_colors(self) -> None:
        """Re-apply styling after a theme change."""
        self._apply_style()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the drag handle positioned along the left edge."""
        super().resizeEvent(event)
        self._handle.setGeometry(0, 0, HANDLE_W, self.height())
        self._handle.raise_()

    def _on_drag_delta(self, delta: int) -> None:
        """Adjust the panel width by *delta* pixels (negative = wider)."""
        if self._active_key is None:
            return
        current_w = self.width()
        new_w = max(MIN_PANEL_W, min(MAX_PANEL_W, current_w - delta))
        if new_w == current_w:
            return
        self._custom_width = new_w
        self.width_changed.emit(new_w)
